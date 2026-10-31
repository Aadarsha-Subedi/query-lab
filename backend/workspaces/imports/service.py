"""Starting, describing and cancelling imports. The upload is spooled to a file
in UPLOAD_TMP_DIR (the container disk, shared by web and worker) while its size is
counted against IMPORT_MAX_FILE_BYTES, then a Huey job loads it."""

import contextlib
import json
import os
import shutil
import uuid
from pathlib import Path
from typing import Any

from django.conf import settings
from django.core.files.uploadedfile import UploadedFile
from django.utils import timezone

from accounts.models import User
from ask import schema as ask_schema
from workspaces import connections, naming, quota
from workspaces.errors import (
    ImportBusy,
    ImportDiskFull,
    ImportNotCancellable,
    ImportNotFound,
    ImportOptionsInvalid,
    ImportTooLarge,
    TableNameTaken,
)
from workspaces.imports import plan as planning
from workspaces.imports import progress, sniff
from workspaces.models import ImportJob, Workspace


def upload_dir() -> Path:
    path = Path(settings.UPLOAD_TMP_DIR)
    path.mkdir(parents=True, exist_ok=True, mode=0o700)
    return path


def spool(upload: UploadedFile) -> tuple[str, int]:
    """Copy the upload to a private file, refusing as soon as it passes the cap.
    The disk must have room for twice the cap, so a burst cannot fill it."""
    cap = settings.IMPORT_MAX_FILE_BYTES
    if upload.size is not None and upload.size > cap:
        raise ImportTooLarge()
    folder = upload_dir()
    if shutil.disk_usage(folder).free < 2 * cap:
        raise ImportDiskFull()
    path = folder / f"{uuid.uuid4().hex}.csv"
    size = 0
    descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    try:
        with os.fdopen(descriptor, "wb") as out:
            for chunk in upload.chunks():
                size += len(chunk)
                if size > cap:
                    raise ImportTooLarge()
                out.write(chunk)
    except BaseException:
        with contextlib.suppress(OSError):
            path.unlink()
        raise
    return str(path), size


def read_sample(path: str) -> bytes:
    with open(path, "rb") as handle:
        return handle.read(settings.IMPORT_SNIFF_BYTES)


def parse_options(raw: str | None) -> dict[str, Any]:
    if not raw:
        return {}
    try:
        options = json.loads(raw)
    except ValueError:
        raise ImportOptionsInvalid("The options are not valid JSON.") from None
    if not isinstance(options, dict):
        raise ImportOptionsInvalid("The options must be a JSON object.")
    return options


def _existing_tables(workspace: Workspace) -> list[str]:
    with (
        connections.workspace_connection(
            workspace.pk, "rw", workspace.credential_version
        ) as connection,
        connection.cursor() as cursor,
    ):
        known = ask_schema.schema_from_cursor(
            cursor, workspace.schema_name, show_hidden=True
        )
    return [t.name for t in known.tables]


def resolve_table_name(workspace: Workspace, options: dict, filename: str) -> str:
    taken = _existing_tables(workspace)
    wanted = options.get("table_name")
    if wanted:
        name = naming.identifier_slug(str(wanted), kind="table")
        if name in taken:
            raise TableNameTaken()
        return name
    return naming.table_name(Path(filename).stem, taken)


def sniff_file(path: str, options: dict) -> sniff.Sniffed:
    delimiter = options.get("delimiter")
    if delimiter is not None and delimiter not in sniff.DELIMITERS:
        raise ImportOptionsInvalid("The delimiter is a comma, semicolon, tab or pipe.")
    return sniff.sniff(
        read_sample(path), delimiter=delimiter, has_header=options.get("has_header")
    )


def preview(upload: UploadedFile, options: dict) -> dict[str, Any]:
    """What an import would do with this file, without keeping it."""
    path, _ = spool(upload)
    try:
        sniffed = sniff_file(path, options)
    finally:
        with contextlib.suppress(OSError):
            os.unlink(path)
    return {
        "delimiter": sniffed.delimiter,
        "has_header": sniffed.has_header,
        "columns": [
            {
                "index": i,
                "header": sniffed.headers[i],
                "name": sniffed.names[i],
                "type": sniffed.types[i],
            }
            for i in range(sniffed.column_count)
        ],
        "rows": sniffed.sample_rows,
    }


def start(
    workspace: Workspace, actor: User, upload: UploadedFile, options: dict
) -> ImportJob:
    active = ImportJob.objects.filter(
        workspace__owner=actor, status__in=ImportJob.ACTIVE
    ).count()
    if active >= settings.IMPORT_MAX_CONCURRENT:
        raise ImportBusy()
    quota.ensure_room(workspace)
    path, size = spool(upload)
    try:
        sniffed = sniff_file(path, options)
        table = resolve_table_name(workspace, options, upload.name or "import")
        planning.build(
            sniffed, options, table
        )  # refuse bad options now, not in the job
    except BaseException:
        with contextlib.suppress(OSError):
            os.unlink(path)
        raise
    return ImportJob.objects.create(
        workspace=workspace,
        table_name=table,
        original_name=(upload.name or "")[:255],
        bytes_total=size,
        options=options,
        file_path=path,
    )


def get_job(workspace: Workspace, job_id: int) -> ImportJob:
    job = ImportJob.objects.filter(pk=job_id, workspace=workspace).first()
    if job is None:
        raise ImportNotFound()
    return job


def discard_file(job: ImportJob) -> None:
    if job.file_path:
        with contextlib.suppress(OSError):
            os.unlink(job.file_path)


def cancel(job: ImportJob) -> ImportJob:
    if job.is_terminal:
        raise ImportNotCancellable()
    if job.status == ImportJob.STATUS_QUEUED:
        updated = ImportJob.objects.filter(
            pk=job.pk, status=ImportJob.STATUS_QUEUED
        ).update(status=ImportJob.STATUS_CANCELLED, finished_at=timezone.now())
        if updated:
            discard_file(job)
            job.refresh_from_db()
            return job
    progress.request_cancel(job.pk)  # running: the job stops between batches
    job.refresh_from_db()
    return job


def cancel_all(workspace: Workspace) -> None:
    """Before a workspace is dropped: nothing may keep loading into it."""
    for job in ImportJob.objects.filter(
        workspace=workspace, status__in=ImportJob.ACTIVE
    ):
        progress.request_cancel(job.pk)
        ImportJob.objects.filter(pk=job.pk, status=ImportJob.STATUS_QUEUED).update(
            status=ImportJob.STATUS_CANCELLED, finished_at=timezone.now()
        )
        discard_file(job)


def job_dict(job: ImportJob) -> dict[str, Any]:
    live = progress.read(job.pk) if job.status == ImportJob.STATUS_RUNNING else {}
    return {
        "id": job.pk,
        "workspace_id": job.workspace_id,
        "table_name": job.table_name,
        "status": job.status,
        "original_name": job.original_name,
        "bytes_total": job.bytes_total,
        "bytes_read": int(live.get("bytes_read", job.bytes_read)),
        "rows_loaded": int(live.get("rows", job.rows_loaded)),
        "phase": live.get("phase", ""),
        "error_code": job.error_code,
        "error_message": job.error_message,
        "events_url": f"/api/workspaces/{job.workspace_id}/imports/{job.pk}/events",
        "created_at": job.created_at,
        "started_at": job.started_at,
        "finished_at": job.finished_at,
    }
