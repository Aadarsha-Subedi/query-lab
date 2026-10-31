"""Typed errors for workspaces. Messages are generic and never carry SQL, other
schemas' names or another user's data."""

from common.exception.domain import (
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


class WorkspaceThrottled(ThrottledException):
    error_code = "workspace_throttled"


class WorkspaceProvisioningFailed(ServiceUnavailableException):
    message = "The workspace could not be created. Nothing was kept; try again."
    error_code = "workspace_provisioning_failed"
