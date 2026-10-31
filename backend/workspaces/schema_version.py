"""A counter per workspace in Redis that changes whenever its shape changes
(a table, a column, a description, an import, user DDL). The cached schema's key
includes it, so the next read re-introspects. The demo never changes: version 0."""

from common.redis import get_redis
from workspaces.context import WorkspaceRef


def _key(workspace_id: int) -> str:
    return f"workspace:schema_version:{workspace_id}"


def current(workspace: WorkspaceRef) -> int:
    if workspace.id is None:
        return 0
    value = get_redis().get(_key(workspace.id))
    return int(value) if value else 0


def bump(workspace: WorkspaceRef | int) -> int:
    workspace_id = workspace if isinstance(workspace, int) else workspace.id
    assert workspace_id is not None, "the demo schema never changes"
    return int(get_redis().incr(_key(workspace_id)))


def forget(workspace_id: int) -> None:
    get_redis().delete(_key(workspace_id))
