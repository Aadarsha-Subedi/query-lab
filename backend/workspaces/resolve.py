"""From a workspace id stored on a run (None = the demo) to the reference the data
paths use. A deleted workspace is a typed error, never a fallback to the demo."""

from workspaces.context import DEMO, WorkspaceRef
from workspaces.errors import WorkspaceGone
from workspaces.models import Workspace


def resolve(workspace_id: int | None) -> WorkspaceRef:
    if workspace_id is None:
        return DEMO
    workspace = Workspace.objects.filter(
        pk=workspace_id, status=Workspace.STATUS_READY
    ).first()
    if workspace is None:
        raise WorkspaceGone()
    return workspace.ref
