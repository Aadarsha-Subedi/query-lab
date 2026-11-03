"""Typed errors for workspaces. Messages are generic and never carry SQL, other
schemas' names or another user's data."""

from common.exception.domain import (
    BadRequestException,
    ConflictException,
    NotFoundException,
    ServiceUnavailableException,
    ThrottledException,
    UnprocessableEntityException,
)


class WorkspaceNotFound(NotFoundException):
    """Also the answer for a workspace that belongs to someone else."""

    message = "Workspace not found."
    error_code = "workspace_not_found"


class WorkspaceLimitReached(ConflictException):
    message = "You have reached the maximum number of workspaces."
    error_code = "workspace_limit_reached"


class WorkspaceNameTaken(ConflictException):
    message = "You already have a workspace with this name."
    error_code = "workspace_name_taken"


class WorkspaceNotReady(ConflictException):
    message = "This workspace is not ready."
    error_code = "workspace_not_ready"


class InvalidName(UnprocessableEntityException):
    message = "This name cannot be used."
    error_code = "invalid_name"


class DemoWorkspaceReadOnly(ConflictException):
    message = "The demo workspace cannot be changed."
    error_code = "demo_workspace_read_only"


class WorkspaceProvisioningFailed(ServiceUnavailableException):
    message = "The workspace could not be created. Nothing was kept; try again."
    error_code = "workspace_provisioning_failed"


class WorkspaceGone(NotFoundException):
    """A run points at a workspace that was deleted: its trace stays readable,
    but nothing can run against it any more."""

    message = "The workspace this run used no longer exists."
    error_code = "workspace_gone"


# ── tables, columns, keys (5.5) ───────────────────────────────────────────


class TableNotFound(NotFoundException):
    message = "Table not found."
    error_code = "table_not_found"


# ── storage (5.8) ─────────────────────────────────────────────────────────


class WorkspaceFull(ConflictException):
    message = "This workspace is full. Delete data or tables to make room."
    error_code = "workspace_full"


class UserStorageFull(ConflictException):
    message = (
        "Your workspaces together are full. Delete data or a workspace to make room."
    )
    error_code = "user_storage_full"


# ── the SQL console (5.6a) ────────────────────────────────────────────────


class SqlInvalid(BadRequestException):
    message = "This SQL cannot be run here."
    error_code = "sql_invalid"


class SqlFailed(UnprocessableEntityException):
    """A statement failed; the whole request was rolled back. `errors[0].message`
    is the Postgres SQLSTATE code and message, with other workspaces' names
    removed."""

    message = "The SQL failed. Nothing was changed."
    error_code = "sql_failed"


class SqlBusy(ThrottledException):
    message = "A SQL request of yours is still running. Wait for it to finish."
    error_code = "sql_busy"


# ── rows (5.6) ────────────────────────────────────────────────────────────


# ── dump import ───────────────────────────────────────────────────────────


class DumpTooLarge(UnprocessableEntityException):
    message = "The dump is too large."
    error_code = "dump_too_large"


class DumpUploadMissing(UnprocessableEntityException):
    message = "The uploaded file was not found. Upload it again."
    error_code = "dump_upload_missing"


class WorkspaceNotEmpty(ConflictException):
    message = "This workspace already has tables. Use Replace data to import over them."
    error_code = "workspace_not_empty"


class ImportInProgress(ConflictException):
    message = "A dump import is already running for you. Wait for it to finish."
    error_code = "import_in_progress"


class ImportNotFound(NotFoundException):
    message = "Import not found."
    error_code = "import_not_found"


class ImportNotReady(ConflictException):
    message = "This import is not waiting for an upload."
    error_code = "import_not_ready"
