"""Dump imports: ask for an upload URL, PUT the file to R2, say it is there.

1. `POST /workspaces/{id}/imports`           creates the job and returns a presigned PUT URL
2. the browser PUTs the file straight to R2
3. `POST /workspaces/{id}/imports/{job}/start` checks the object and queues the job
4. `GET  /workspaces/{id}/imports/{job}`       polls the status
"""

from datetime import timedelta
from typing import cast

from django.conf import settings
from django.db import transaction
from django.db.models import Q, QuerySet
from django.http import HttpRequest
from django.utils import timezone
from ninja import Router
from ninja.security import django_auth

from accounts.models import User
from common.response.domain import SuccessEnvelope, errors, success
from common.throttling.scoped import WorkspaceImportThrottle
from workspaces import importer, quota, storage
from workspaces.access import writable_workspace
from workspaces.errors import (
    DumpTooLarge,
    ImportInProgress,
    ImportNotFound,
    ImportNotReady,
    InvalidName,
)
from workspaces.import_schemas import (
    ImportCreatedOut,
    ImportIn,
    ImportOut,
    import_dict,
)
from workspaces.models import ImportJob
from workspaces.tasks import run_import

router = Router(tags=["workspace imports"])


def _user(request: HttpRequest) -> User:
    return cast(User, request.user)


def _active(user: User) -> QuerySet[ImportJob]:
    """Jobs that still hold the user's one import slot. An upload nobody finished
    (its URL has expired) and a job that stopped reporting do not."""
    now = timezone.now()
    upload_window = now - timedelta(seconds=settings.DUMP_PRESIGN_SECONDS)
    stale = now - timedelta(seconds=importer.STALE_AFTER_SECONDS)
    return ImportJob.objects.filter(owner=user).filter(
        Q(status=ImportJob.AWAITING_UPLOAD, created_at__gte=upload_window)
        | Q(status=ImportJob.QUEUED, updated_at__gte=stale)
        | Q(status=ImportJob.RUNNING, updated_at__gte=stale)
    )


def _job(user: User, workspace_id: int, job_id: int) -> ImportJob:
    workspace = writable_workspace(user, workspace_id)
    job = ImportJob.objects.filter(pk=job_id, workspace=workspace).first()
    if job is None:
        raise ImportNotFound()
    return importer.expire_if_stale(job)


@router.post(
    "/{workspace_id}/imports",
    response={
        200: SuccessEnvelope[ImportCreatedOut],
        **errors(401, 404, 409, 422, 429),
    },
    auth=django_auth,
    throttle=[WorkspaceImportThrottle()],
)
def create_import(request: HttpRequest, workspace_id: int, payload: ImportIn) -> dict:
    """Start a dump import. Send the file's name (`.sql` or `.sql.gz`) and exact
    size in bytes; PUT the file to `upload_url` with that exact length, then call
    `start`. Fails with `workspace_not_empty` at run time unless `replace` is set
    or the workspace has no tables."""
    user = _user(request)
    workspace = writable_workspace(user, workspace_id)
    name = payload.filename.lower()
    if not name.endswith(storage.SUFFIXES):
        raise InvalidName("Upload a .sql or .sql.gz file made with pg_dump.")
    if payload.size < 1:
        raise InvalidName("The file is empty.")
    if payload.size > settings.DUMP_MAX_FILE_BYTES:
        raise DumpTooLarge()
    quota.ensure_room(workspace)
    with transaction.atomic():
        User.objects.select_for_update().get(pk=user.pk)  # one active import per user
        if _active(user).exists():
            raise ImportInProgress()
        key = storage.new_key(user.pk, workspace.pk, gzipped=name.endswith(".gz"))
        job = ImportJob.objects.create(
            workspace=workspace,
            owner=user,
            object_key=key,
            size_bytes=payload.size,
            replace=payload.replace,
        )
    data = import_dict(job)
    data.update(
        upload_url=storage.presign_put(key, payload.size),
        upload_expires_in=settings.DUMP_PRESIGN_SECONDS,
        max_bytes=settings.DUMP_MAX_FILE_BYTES,
    )
    return success(data, message="Upload the file, then start the import.")


@router.post(
    "/{workspace_id}/imports/{job_id}/start",
    response={200: SuccessEnvelope[ImportOut], **errors(401, 404, 409, 422, 429)},
    auth=django_auth,
    throttle=[WorkspaceImportThrottle()],
)
def start_import(request: HttpRequest, workspace_id: int, job_id: int) -> dict:
    """Say the upload is done. Checks the file is in the bucket and within the
    cap, then queues the job; poll `GET` for the result."""
    job = _job(_user(request), workspace_id, job_id)
    if job.status != ImportJob.AWAITING_UPLOAD:
        raise ImportNotReady()
    try:
        storage.stored_size(job.object_key)
    except DumpTooLarge:
        storage.delete(job.object_key)
        job.status = ImportJob.FAILED
        job.error_code = DumpTooLarge.error_code
        job.error_message = DumpTooLarge.message
        job.save()
        raise
    job.status = ImportJob.QUEUED
    job.save(update_fields=["status", "updated_at"])
    run_import(job.pk)
    job.refresh_from_db()
    return success(import_dict(job), message="Import queued.")


@router.get(
    "/{workspace_id}/imports/{job_id}",
    response={200: SuccessEnvelope[ImportOut], **errors(401, 404, 429)},
    auth=django_auth,
)
def get_import(request: HttpRequest, workspace_id: int, job_id: int) -> dict:
    """The status of one import; poll until `succeeded` or `failed`."""
    return success(import_dict(_job(_user(request), workspace_id, job_id)))


@router.get(
    "/{workspace_id}/imports",
    response={200: SuccessEnvelope[list[ImportOut]], **errors(401, 404, 429)},
    auth=django_auth,
)
def list_imports(request: HttpRequest, workspace_id: int) -> dict:
    """The workspace's last ten imports, newest first."""
    workspace = writable_workspace(_user(request), workspace_id)
    jobs = ImportJob.objects.filter(workspace=workspace)[:10]
    return success([import_dict(importer.expire_if_stale(j)) for j in jobs])
