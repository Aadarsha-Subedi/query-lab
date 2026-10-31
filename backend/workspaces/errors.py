"""Typed errors for workspaces. Messages are generic and never carry SQL, other
schemas' names or another user's data."""

from common.exception.domain import (
    ConflictException,
    NotFoundException,
    ServiceUnavailableException,
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


class ColumnNotFound(NotFoundException):
    message = "Column not found."
    error_code = "column_not_found"


class RelationNotFound(NotFoundException):
    message = "Relation not found."
    error_code = "relation_not_found"


class InvalidSpec(UnprocessableEntityException):
    message = "The request does not describe a usable table or column."
    error_code = "invalid_spec"


class TableNameTaken(ConflictException):
    message = "This workspace already has a table with this name."
    error_code = "table_name_taken"


class ColumnNameTaken(ConflictException):
    message = "This table already has a column with this name."
    error_code = "column_name_taken"


class TableLimitReached(ConflictException):
    message = "This workspace has the maximum number of tables."
    error_code = "table_limit_reached"


class ColumnLimitReached(ConflictException):
    message = "This table has the maximum number of columns."
    error_code = "column_limit_reached"


class RelationLimitReached(ConflictException):
    message = "This workspace has the maximum number of relations."
    error_code = "relation_limit_reached"


class CastFailed(UnprocessableEntityException):
    """Retyping a column found a value that does not convert. Nothing changed;
    `errors[0]` names the first bad row id."""

    message = "A value in this column cannot be converted to the new type."
    error_code = "cast_failed"


class ConstraintViolated(ConflictException):
    """A key, relation or NOT NULL cannot be added or kept because of existing
    rows, or a row edit would break one. `errors[0]` names the constraint and,
    when there is one, the first row id involved. Nothing changed."""

    message = "The data does not satisfy this constraint."
    error_code = "constraint_violation"


class RelationInvalid(UnprocessableEntityException):
    message = "These columns cannot be related."
    error_code = "relation_invalid"


# ── storage (5.8) ─────────────────────────────────────────────────────────


class WorkspaceFull(ConflictException):
    message = "This workspace is full. Delete data or tables to make room."
    error_code = "workspace_full"


class UserStorageFull(ConflictException):
    message = (
        "Your workspaces together are full. Delete data or a workspace to make room."
    )
    error_code = "user_storage_full"
