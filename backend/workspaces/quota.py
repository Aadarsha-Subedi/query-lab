"""How much a workspace and a user may store, and the checks that enforce it.

Size is `pg_total_relation_size` (tables, indexes, TOAST) summed over the
workspace's schema: catalog numbers, no row is read. A fresh measure runs inside
the writer's own transaction after it wrote, so an over-cap write rolls back; the
cheap cached figure is only for the check before a write and for listings."""

import psycopg
from django.conf import settings

from accounts.models import User
from common.redis import get_redis
from workspaces import usage
from workspaces.errors import UserStorageFull, WorkspaceFull
from workspaces.models import Workspace

SIZE_SQL = """
SELECT COALESCE(sum(pg_total_relation_size(c.oid)), 0)::bigint
FROM pg_class c JOIN pg_namespace n ON n.oid = c.relnamespace
WHERE n.nspname = %s AND c.relkind IN ('r', 'p', 'm')
"""


def _key(workspace_id: int) -> str:
    return f"workspace:bytes:{workspace_id}"


def measure(connection: psycopg.Connection, schema_name: str) -> int:
    """The schema's size now, on a connection that may see it (inside a transaction
    this includes the transaction's own writes)."""
    row = connection.execute(SIZE_SQL, [schema_name]).fetchone()
    return int(row[0]) if row else 0


def cached_bytes(workspace: Workspace) -> int:
    """The size from a short cache, measured on the owner connection on a miss."""
    if settings.QUOTA_CACHE_SECONDS <= 0:  # caching off
        return usage.schema_usage([workspace.schema_name])[workspace.schema_name].bytes
    redis = get_redis()
    value = redis.get(_key(workspace.pk))
    if value is not None:
        return int(value)
    size = usage.schema_usage([workspace.schema_name])[workspace.schema_name].bytes
    redis.set(_key(workspace.pk), size, ex=settings.QUOTA_CACHE_SECONDS)
    return size


def forget(workspace_id: int) -> None:
    get_redis().delete(_key(workspace_id))


def user_bytes(
    user: User, *, fresh_for: Workspace | None = None, fresh: int = 0
) -> int:
    """All of the user's workspaces together; `fresh` replaces one workspace's
    cached figure with a number measured just now."""
    total = 0
    for workspace in Workspace.objects.filter(owner=user):
        if fresh_for is not None and workspace.pk == fresh_for.pk:
            total += fresh
        else:
            total += cached_bytes(workspace)
    return total


def ensure_room(workspace: Workspace) -> None:
    """Before a write: refuse when the workspace or the user is already at a cap."""
    if cached_bytes(workspace) >= settings.WORKSPACE_MAX_BYTES:
        raise WorkspaceFull()
    if user_bytes(workspace.owner) >= settings.USER_MAX_BYTES:
        raise UserStorageFull()


def ensure_within(connection: psycopg.Connection, workspace: Workspace) -> int:
    """After a write, in the writer's transaction: measure fresh and raise (so the
    transaction rolls back) when the workspace or the user is over a cap. Returns
    the measured size."""
    size = measure(connection, workspace.schema_name)
    if size > settings.WORKSPACE_MAX_BYTES:
        raise WorkspaceFull()
    if (
        user_bytes(workspace.owner, fresh_for=workspace, fresh=size)
        > settings.USER_MAX_BYTES
    ):
        raise UserStorageFull()
    if settings.QUOTA_CACHE_SECONDS > 0:
        get_redis().set(_key(workspace.pk), size, ex=settings.QUOTA_CACHE_SECONDS)
    return size
