from datetime import datetime
from typing import cast

from django.http import HttpRequest, StreamingHttpResponse
from ninja import File, Form, Router, Schema, Status, UploadedFile
from ninja.security import django_auth

from accounts.models import User
from common.response.domain import SuccessEnvelope, errors, success
from workspaces.access import writable_workspace
from workspaces.imports import service
from workspaces.imports import tasks as import_tasks
from workspaces.imports.stream import ImportEventStream
from workspaces.models import ImportJob

router = Router(tags=["workspace imports"])

IMPORT_ERRORS = errors(400, 401, 404, 409, 413, 422, 429, 503)


class ImportOut(Schema):
    id: int
    workspace_id: int
    table_name: str
    # queued, running, succeeded, failed or cancelled
    status: str
    original_name: str
    bytes_total: int
    bytes_read: int
    rows_loaded: int
    # starting, scanning, loading or finishing while it runs
    phase: str
    error_code: str
    error_message: str
    events_url: str
    created_at: datetime
    started_at: datetime | None
    finished_at: datetime | None


class PreviewColumn(Schema):
    index: int
    header: str
    # What the column would be called, and the type guessed from the first rows.
    name: str
    type: str


class PreviewOut(Schema):
    delimiter: str
    has_header: bool
    columns: list[PreviewColumn]
    rows: list[list[str]]


def _user(request: HttpRequest) -> User:
    return cast(User, request.user)


OPTIONS_HELP = (
    "`options` is a JSON object: `table_name`, `delimiter`, `has_header`, "
    "`columns` (a list of `{index, name, type, skip, description}`), `description`, "
    "`header_descriptions`, `primary_key` (column names) and `relations` (a list of "
    "`{columns, parent_table, parent_columns, on_delete}`)."
)


@router.post(
    "/{workspace_id}/imports/preview",
    response={200: SuccessEnvelope[PreviewOut], **IMPORT_ERRORS},
    auth=django_auth,
)
def preview_import(
    request: HttpRequest,
    workspace_id: int,
    file: File[UploadedFile],
    options: Form[str | None] = None,
) -> dict:
    (
        """Look at a CSV before importing it: the delimiter, whether the first row is
    a header, the column names and a guessed type for each, and the first rows.
    Nothing is kept. Send the same file to `POST /imports`, with `options` holding
    any changes, to import it. """
        + OPTIONS_HELP
    )
    writable_workspace(_user(request), workspace_id)
    return success(service.preview(file, service.parse_options(options)))


@router.post(
    "/{workspace_id}/imports",
    response={202: SuccessEnvelope[ImportOut], **IMPORT_ERRORS},
    auth=django_auth,
)
def start_import(
    request: HttpRequest,
    workspace_id: int,
    file: File[UploadedFile],
    options: Form[str | None] = None,
) -> Status:
    (
        """Upload a CSV to become a new table. Answers 202 at once with a job; follow
    it on `events_url` (server-sent events) or poll the job. The file is checked
    for size, text encoding and columns before the job is queued; a bad file
    during loading leaves nothing behind. """
        + OPTIONS_HELP
    )
    workspace = writable_workspace(_user(request), workspace_id)
    job = service.start(workspace, _user(request), file, service.parse_options(options))
    import_tasks.run_import(job.pk)
    job.refresh_from_db()
    return Status(
        202, success(service.job_dict(job), message="Import queued.", status_code=202)
    )


@router.get(
    "/{workspace_id}/imports",
    response={200: SuccessEnvelope[list[ImportOut]], **IMPORT_ERRORS},
    auth=django_auth,
)
def list_imports(request: HttpRequest, workspace_id: int) -> dict:
    """The workspace's 20 most recent imports."""
    workspace = writable_workspace(_user(request), workspace_id)
    jobs = ImportJob.objects.filter(workspace=workspace)[:20]
    return success([service.job_dict(job) for job in jobs])


@router.get(
    "/{workspace_id}/imports/{job_id}",
    response={200: SuccessEnvelope[ImportOut], **IMPORT_ERRORS},
    auth=django_auth,
)
def get_import(request: HttpRequest, workspace_id: int, job_id: int) -> dict:
    workspace = writable_workspace(_user(request), workspace_id)
    return success(service.job_dict(service.get_job(workspace, job_id)))


@router.get(
    "/{workspace_id}/imports/{job_id}/events",
    response={200: None, **IMPORT_ERRORS},
    auth=django_auth,
)
def import_events(
    request: HttpRequest, workspace_id: int, job_id: int
) -> StreamingHttpResponse:
    """Server-sent events: `progress` (status, phase, bytes and rows so far) while
    the import waits or loads, then one `succeeded` (table, rows, bytes), `failed`
    (error_code, message) or `cancelled`. Over the open-stream limit it answers 429
    `agent_stream_limit`: poll `GET /imports/{id}` instead."""
    workspace = writable_workspace(_user(request), workspace_id)
    job = service.get_job(workspace, job_id)
    response = StreamingHttpResponse(
        ImportEventStream(job.pk), content_type="text/event-stream"
    )
    response["Cache-Control"] = "no-cache"
    response["X-Accel-Buffering"] = "no"
    return response


@router.post(
    "/{workspace_id}/imports/{job_id}/cancel",
    response={200: SuccessEnvelope[ImportOut], **IMPORT_ERRORS},
    auth=django_auth,
)
def cancel_import(request: HttpRequest, workspace_id: int, job_id: int) -> dict:
    """Stop an import. A queued job is cancelled at once; a running one stops at
    the next batch and leaves nothing behind. 409 `import_not_cancellable` once it
    has finished."""
    workspace = writable_workspace(_user(request), workspace_id)
    job = service.cancel(service.get_job(workspace, job_id))
    return success(service.job_dict(job), message="Cancel requested.")
