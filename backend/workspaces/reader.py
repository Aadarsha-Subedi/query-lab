"""The one place the agent's read path opens a database cursor.

Demo: the Django `data_reader` connection (querylab_reader; the replica in
production). A user workspace: a connection opened as its own `ws_<id>_ro` role
for this call and closed after. The login identity is the boundary; there is no
SET ROLE. Both are read-only transactions with a statement timeout.
"""

from collections.abc import Iterator
from contextlib import contextmanager
from typing import Any

from django.conf import settings
from django.db import connections, transaction

from workspaces import connections as workspace_connections
from workspaces.context import WorkspaceRef


@contextmanager
def read_cursor(workspace: WorkspaceRef, *, chunked: bool = False) -> Iterator[Any]:
    timeout = str(settings.READER_STATEMENT_TIMEOUT_MS)
    if workspace.id is None:
        alias = settings.DATA_READER_DB_ALIAS
        django_connection = connections[alias]
        with transaction.atomic(using=alias):
            with django_connection.cursor() as setup:
                setup.execute("SET TRANSACTION READ ONLY")
                setup.execute(
                    "SELECT set_config('statement_timeout', %s, true)", [timeout]
                )
            demo_cursor = (
                django_connection.chunked_cursor()
                if chunked
                else django_connection.cursor()
            )
            try:
                yield demo_cursor
            finally:
                demo_cursor.close()
        return
    with workspace_connections.workspace_connection(
        workspace.id, "ro", workspace.credential_version
    ) as connection:
        connection.execute("SET TRANSACTION READ ONLY")
        connection.execute(
            "SELECT set_config('statement_timeout', %s, true)", [timeout]
        )
        if chunked:
            with connection.cursor(name="ask_result") as cursor:
                yield cursor
        else:
            with connection.cursor() as cursor:
                yield cursor
