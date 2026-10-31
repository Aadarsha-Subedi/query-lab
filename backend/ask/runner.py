"""Runs guarded SQL on the reader connection, and only there.

Layers here: a read-only transaction, a statement timeout (on top of the
role's own), and a cap on the rows and bytes read. Values are turned into
JSON-safe types before they leave."""

import datetime
import json
from dataclasses import dataclass
from decimal import Decimal
from typing import Any
from uuid import UUID

import psycopg
from django.conf import settings
from django.db import DatabaseError
from psycopg import errors as pg_errors

from ask.errors import QueryFailed, QueryTimeout
from ask.prompt import first_line
from workspaces.context import DEMO, WorkspaceRef
from workspaces.reader import read_cursor

FETCH_BATCH = 100


@dataclass(frozen=True)
class QueryResult:
    columns: list[str]
    rows: list[list[Any]]
    row_count: int
    truncated: bool


def to_json_safe(value: Any) -> Any:
    if value is None or isinstance(value, bool | int | str):
        return value
    if isinstance(value, float):
        return value if value == value and abs(value) != float("inf") else str(value)
    if isinstance(value, Decimal | UUID):
        return str(value)
    if isinstance(value, datetime.datetime | datetime.date | datetime.time):
        return value.isoformat()
    if isinstance(value, datetime.timedelta):
        return str(value)
    if isinstance(value, bytes | bytearray | memoryview):
        raise QueryFailed("Binary values are not supported.")
    if isinstance(value, list | tuple):
        return [to_json_safe(item) for item in value]
    if isinstance(value, dict):
        return {str(key): to_json_safe(item) for key, item in value.items()}
    return str(value)


def run(
    sql: str, workspace: WorkspaceRef = DEMO, *, json_safe: bool = True
) -> QueryResult:
    """Run guarded SQL for a workspace. The demo runs on the reader connection; a
    user workspace on a connection opened as its own `ws_<id>_ro` role. There is no
    SET ROLE: the login identity is the boundary, so a workspace connection can
    never be handed to another workspace. `json_safe=False` keeps native Python
    values (the eval harness compares numbers, so it needs Decimals, not strings)."""
    max_rows = settings.ASK_MAX_ROWS
    max_bytes = settings.ASK_MAX_RESULT_BYTES
    rows: list[list[Any]] = []
    size = 0
    truncated = False
    try:
        with read_cursor(workspace, chunked=True) as cursor:
            cursor.execute(sql)
            columns: list[str] = []
            while not truncated:
                batch = cursor.fetchmany(FETCH_BATCH)
                if not columns:
                    columns = [col[0] for col in cursor.description or []]
                if not batch:
                    break
                for raw in batch:
                    row = [to_json_safe(value) if json_safe else value for value in raw]
                    size += len(json.dumps(row, default=str))
                    if len(rows) >= max_rows or size > max_bytes:
                        truncated = True
                        break
                    rows.append(row)
    except DatabaseError as error:
        raise _translate(error, error.__cause__) from None
    except psycopg.Error as error:
        raise _translate(error, error) from None
    return QueryResult(
        columns=columns,
        rows=rows,
        row_count=len(rows),
        truncated=truncated or len(rows) >= max_rows,
    )


def _translate(error: Exception, cause: BaseException | None) -> Exception:
    if isinstance(cause, pg_errors.QueryCanceled):
        return QueryTimeout()
    return QueryFailed(first_line(str(error)))
