"""Connections for the workspace paths. The login identity is the boundary:
a workspace connection is opened as `ws_<id>_rw` (primary) or `ws_<id>_ro`
(reader, the replica in production) and nothing here ever calls SET ROLE.

One connection per request, closed at the end. In production the hosts are
Neon's PgBouncer endpoints in transaction mode, which keeps the server
connections, so connecting per request is cheap; locally it is a plain
connection. Because of transaction pooling nothing relies on session state:
no SET ROLE and no session SET, prepared statements are off, and every use
ends with its transaction committed or rolled back.
"""

from collections.abc import Iterator
from contextlib import contextmanager

import psycopg
from django.conf import settings
from psycopg.conninfo import make_conninfo

from workspaces import credentials


def owner_conninfo() -> str:
    """The platform owner role on the data database (provisioning only)."""
    db = settings.DATABASES[settings.DATA_DB_ALIAS]
    return make_conninfo(
        host=db["HOST"],
        port=db["PORT"],
        dbname=db["NAME"],
        user=db["USER"],
        password=db["PASSWORD"],
    )


def role_conninfo(workspace_id: int, kind: credentials.Kind, version: int) -> str:
    base = (
        settings.WORKSPACE_PRIMARY_CONNINFO
        if kind == "rw"
        else settings.WORKSPACE_READER_CONNINFO
    )
    return make_conninfo(
        base,
        user=credentials.role_name(workspace_id, kind),
        password=credentials.role_password(workspace_id, kind, version),
    )


@contextmanager
def owner_connection() -> Iterator[psycopg.Connection]:
    """A transaction on the owner role: committed on success, rolled back on error."""
    with psycopg.connect(owner_conninfo(), prepare_threshold=None) as connection:
        yield connection


@contextmanager
def workspace_connection(
    workspace_id: int, kind: credentials.Kind, version: int
) -> Iterator[psycopg.Connection]:
    """A transaction as this workspace's own role. The id is the one on the
    Workspace row the caller already checked; the role cannot reach any other
    workspace's schema whatever the SQL says."""
    conninfo = role_conninfo(workspace_id, kind, version)
    with psycopg.connect(conninfo, prepare_threshold=None) as connection:
        yield connection
