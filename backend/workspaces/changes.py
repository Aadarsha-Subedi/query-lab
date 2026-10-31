"""One structural change to a workspace: a transaction as the workspace's own
`_rw` role, with every statement remembered. When the transaction commits, each
statement goes to the DDL audit log and the schema version moves, so the agent
and the schema panel see the change on their next read. When it fails, nothing
is logged and nothing changed."""

from collections.abc import Callable, Iterator
from contextlib import contextmanager
from dataclasses import dataclass, field
from typing import Any

import psycopg
from django.conf import settings
from psycopg import errors as pg_errors
from psycopg import sql

from accounts.models import User
from ask.errors import QueryTimeout
from common.exception.domain import DatabaseException
from workspaces import connections, ddl_log, schema_version
from workspaces.models import Workspace


@dataclass
class Changes:
    connection: psycopg.Connection
    schema_name: str
    statements: list[str] = field(default_factory=list)
    _after_commit: list[Callable[[], object]] = field(default_factory=list)

    @property
    def schema(self) -> sql.Identifier:
        return sql.Identifier(self.schema_name)

    def run(
        self, statement: sql.SQL | sql.Composed, params: Any = None
    ) -> psycopg.Cursor:
        """Run one DDL statement and keep its text for the audit log."""
        cursor = self.connection.execute(statement, params)
        self.statements.append(statement.as_string(self.connection))
        return cursor

    def query(
        self, statement: str | sql.SQL | sql.Composed, params: Any = None
    ) -> psycopg.Cursor:
        """A read inside the same transaction (not logged)."""
        return self.connection.execute(statement, params)

    def after_commit(self, action: Callable[[], object]) -> None:
        """Run `action` once the transaction has committed (never when it rolled back)."""
        self._after_commit.append(action)

    def table(self, name: str) -> sql.Composed:
        return sql.SQL("{}.{}").format(self.schema, sql.Identifier(name))


@contextmanager
def changes(
    workspace: Workspace, actor: User | None, *, timeout_ms: int | None = None
) -> Iterator[Changes]:
    log: Changes | None = None
    try:
        with connections.workspace_connection(
            workspace.pk, "rw", workspace.credential_version
        ) as connection:
            if timeout_ms is not None:
                connection.execute(
                    "SELECT set_config('statement_timeout', %s, true)",
                    [str(timeout_ms)],
                )
            log = Changes(connection, workspace.schema_name)
            yield log
    except pg_errors.QueryCanceled:
        raise QueryTimeout() from None
    except (pg_errors.OperationalError, pg_errors.InternalError):
        raise DatabaseException() from None
    assert log is not None
    for statement in log.statements:
        ddl_log.record(workspace.pk, actor, statement)
    if log.statements:
        schema_version.bump(workspace.pk)
    for action in log._after_commit:
        action()


def import_timeout_ms() -> int:
    return settings.IMPORT_STATEMENT_TIMEOUT_MS
