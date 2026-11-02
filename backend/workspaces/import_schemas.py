from datetime import datetime
from typing import Literal

from ninja import Schema

from workspaces.models import ImportJob


class ImportIn(Schema):
    # Only the extension is read (.sql or .sql.gz); the name is never stored.
    filename: str
    size: int
    # Drop this workspace's tables first (inside the import's own transaction).
    replace: bool = False


class ImportFailure(Schema):
    code: str
    message: str
    # Where in the dump it went wrong, when that is known.
    statement: int | None
    line: int | None


class ImportOut(Schema):
    id: int
    workspace_id: int
    status: Literal["awaiting_upload", "queued", "running", "succeeded", "failed"]
    replace: bool
    size_bytes: int
    statements_run: int
    tables_created: int
    error: ImportFailure | None
    created_at: datetime
    updated_at: datetime


class ImportCreatedOut(ImportOut):
    """Returned once, when the import is created: where to PUT the file."""

    upload_url: str
    upload_expires_in: int
    max_bytes: int


def import_dict(job: ImportJob) -> dict:
    return ImportOut(
        id=job.pk,
        workspace_id=job.workspace_id,
        status=job.status,  # type: ignore[arg-type]
        replace=job.replace,
        size_bytes=job.size_bytes,
        statements_run=job.statements_run,
        tables_created=job.tables_created,
        error=ImportFailure(
            code=job.error_code,
            message=job.error_message,
            statement=job.error_statement,
            line=job.error_line,
        )
        if job.status == ImportJob.FAILED
        else None,
        created_at=job.created_at,
        updated_at=job.updated_at,
    ).model_dump(mode="json")
