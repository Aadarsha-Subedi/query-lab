"""The one place a request's `workspace` parameter becomes a workspace to use.

Every endpoint that takes a workspace calls `workspace_for` once. No parameter
means the shared demo. A number means one of the caller's own ready workspaces;
anyone else's, a missing one and a deleted one are the same 404."""

from accounts.models import User
from workspaces import service
from workspaces.context import DEMO, WorkspaceRef
from workspaces.errors import WorkspaceNotReady
from workspaces.models import Workspace


def workspace_for(user: User, workspace_id: int | None) -> WorkspaceRef:
    if workspace_id is None:
        return DEMO
    workspace = service.get_owned(user, workspace_id)
    if workspace.status != Workspace.STATUS_READY:
        raise WorkspaceNotReady()
    return workspace.ref


def writable_workspace(user: User, workspace_id: int) -> Workspace:
    """The caller's own ready workspace, for the endpoints that change it or read
    it by id (the schema and ask endpoints use `workspace_for`)."""
    workspace = service.get_owned(user, workspace_id)
    if workspace.status != Workspace.STATUS_READY:
        raise WorkspaceNotReady()
    return workspace
