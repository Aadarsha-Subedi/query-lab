"""The user's read-only SQL on their own workspace (the query runner).

It runs as `ws_<id>_ro` (SELECT only, `default_transaction_read_only`) on the
reader connection, in one read-only transaction. Writes are impossible twice
over: the role has no write privilege, and a script is refused up front unless
every statement starts with SELECT, WITH, EXPLAIN, SHOW or VALUES. Structure and
data change only through a dump import (`importer.py`). Limits:

- one transaction per request: any failing statement fails the whole request;
- transaction control and COPY are refused;
- a statement timeout, plus a deadline enforced from outside: the user can
  `SET statement_timeout = 0`, so a watchdog cancels the running statement when
  the request's total time is up;
- caps on script length, statement count and returned rows.
"""

import contextlib
import re
import threading
import time
from typing import Any

import psycopg
from django.conf import settings
from psycopg import errors as pg_errors

from accounts.models import User
from ask.errors import QueryTimeout
from ask.runner import to_json_safe
from common.redis import get_redis
from workspaces import connections, sqltext
from workspaces.errors import SqlBusy, SqlFailed, SqlInvalid
from workspaces.models import Workspace

OTHER_WORKSPACE = re.compile(r"\bws_\d+(?:_ro|_rw)?\b")
READ_WORDS = frozenset(["select", "with", "explain", "show", "values", "table"])
HINT = "Only reading is allowed here (SELECT, WITH, EXPLAIN, SHOW). To change the data, import a new dump."


def _running_key(user: User) -> str:
    return f"workspace_sql:running:{user.pk}"


class _Slot:
    """At most WORKSPACE_SQL_MAX_CONCURRENT console requests per user at once. The
    counter expires on its own, so a crashed worker cannot lock a user out."""

    def __init__(self, user: User):
        self.key = _running_key(user)

    def __enter__(self) -> None:
        redis = get_redis()
        count = redis.incr(self.key)
        redis.expire(
            self.key, 2 * (settings.WORKSPACE_STATEMENT_TIMEOUT_MS // 1000 + 5)
        )
        if count > settings.WORKSPACE_SQL_MAX_CONCURRENT:
            redis.decr(self.key)
            raise SqlBusy()

    def __exit__(self, *exc: object) -> None:
        get_redis().decr(self.key)


def _scrub(message: str, schema_name: str) -> str:
    """Another workspace's name never goes back to the user."""

    def keep(match: re.Match[str]) -> str:
        found = match.group(0)
        mine = found == schema_name or found.startswith(f"{schema_name}_")
        return found if mine else "<other workspace>"

    return OTHER_WORKSPACE.sub(keep, message)


def _check(script: str) -> list[sqltext.Statement]:
    if not script.strip():
        raise SqlInvalid("Write some SQL first.")
    if len(script) > settings.WORKSPACE_SQL_MAX_CHARS:
        raise SqlInvalid(
            f"SQL can have at most {settings.WORKSPACE_SQL_MAX_CHARS} characters."
        )
    statements = sqltext.split(script)
    if not statements:
        raise SqlInvalid("Write some SQL first.")
    if len(statements) > settings.WORKSPACE_SQL_MAX_STATEMENTS:
        raise SqlInvalid(
            f"At most {settings.WORKSPACE_SQL_MAX_STATEMENTS} statements per request."
        )
    for statement in statements:
        if statement.is_transaction_control:
            raise SqlInvalid(
                "Each request is one transaction. BEGIN, COMMIT and ROLLBACK are not needed."
            )
        if statement.keyword not in READ_WORDS:
            raise SqlInvalid(HINT)
    return statements


def _cell(value: Any) -> Any:
    if isinstance(value, bytes | bytearray | memoryview):
        return "\\x" + bytes(value).hex()
    return to_json_safe(value)


def _result(cursor: psycopg.Cursor, index: int) -> dict:
    result: dict[str, Any] = {
        "index": index,
        "command": cursor.statusmessage or "",
        "row_count": max(cursor.rowcount, 0),
        "columns": [],
        "rows": [],
        "truncated": False,
    }
    if cursor.description:
        limit = settings.WORKSPACE_SQL_MAX_ROWS
        result["columns"] = [column.name for column in cursor.description]
        rows = cursor.fetchmany(limit + 1)
        result["truncated"] = len(rows) > limit
        result["rows"] = [[_cell(v) for v in row] for row in rows[:limit]]
        result["row_count"] = len(result["rows"])
    return result


def run_script(workspace: Workspace, actor: User, script: str) -> dict[str, Any]:
    statements = _check(script)
    deadline = settings.WORKSPACE_STATEMENT_TIMEOUT_MS / 1000
    started = time.monotonic()
    results: list[dict[str, Any]] = []
    with _Slot(actor):
        try:
            with connections.workspace_connection(
                workspace.pk, "ro", workspace.credential_version
            ) as connection:
                watchdog = threading.Timer(deadline, _cancel, args=(connection,))
                watchdog.start()
                try:
                    connection.execute(
                        "SELECT set_config('statement_timeout', %s, true)",
                        [str(settings.WORKSPACE_STATEMENT_TIMEOUT_MS)],
                    )
                    for index, statement in enumerate(statements, start=1):
                        try:
                            cursor = connection.execute(statement.text)
                        except pg_errors.QueryCanceled:
                            raise
                        except psycopg.Error as error:
                            raise _failed(error, index, workspace) from None
                        results.append(_result(cursor, index))
                finally:
                    watchdog.cancel()
        except pg_errors.QueryCanceled:
            raise QueryTimeout("The SQL took too long and was stopped.") from None
    return {
        "statements": results,
        "elapsed_ms": int((time.monotonic() - started) * 1000),
    }


def _cancel(connection: psycopg.Connection) -> None:
    with contextlib.suppress(psycopg.Error):  # it already finished or closed
        connection.cancel_safe(timeout=5)


def _failed(error: psycopg.Error, index: int, workspace: Workspace) -> SqlFailed:
    code = error.sqlstate or "XX000"
    message = _scrub(
        str(error).splitlines()[0] if str(error) else "error", workspace.schema_name
    )
    return SqlFailed(
        errors=[{"field": "sql", "message": f"Statement {index}: {code}: {message}"}]
    )
