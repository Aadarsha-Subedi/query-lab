"""The schema browser: a workspace's schema as the analyst screen's schema panel
shows it (the demo, or one of the caller's own with `?workspace=`).

Read from `ask.schema.get_schema`, so it shares the cache the agent's tools use and
never writes."""

import hashlib
import json
from typing import Any, cast

from django.conf import settings
from django.http import HttpRequest, HttpResponse
from ninja import Router, Schema
from ninja.security import django_auth

from accounts.models import User
from ask import runner
from ask import schema as ask_schema
from common.exception.domain import NotFoundException
from common.response.domain import SuccessEnvelope, errors, success
from common.throttling.scoped import ResultThrottle
from workspaces.access import workspace_for

router = Router(tags=["schema"])


class TableNotFound(NotFoundException):
    message = "Table not found."
    error_code = "table_not_found"


class ColumnOut(Schema):
    name: str
    type: str
    nullable: bool
    comment: str
    # Example values for low-cardinality text columns; empty unless
    # SCHEMA_API_INCLUDE_SAMPLES is on.
    samples: list[str]


class ForeignKeyOut(Schema):
    columns: list[str]
    ref_table: str
    ref_columns: list[str]


class TableOut(Schema):
    name: str
    comment: str
    # Postgres's own estimate; null until the table is analyzed.
    row_estimate: int | None
    primary_key: list[str]
    foreign_keys: list[ForeignKeyOut]
    columns: list[ColumnOut]


class SchemaOut(Schema):
    name: str
    tables: list[TableOut]


def table_dict(table: ask_schema.Table, *, samples: bool) -> dict[str, Any]:
    return {
        "name": table.name,
        "comment": ask_schema.clean_comment(table.comment),
        "row_estimate": table.row_estimate,
        "primary_key": list(table.primary_key),
        "foreign_keys": [
            {
                "columns": list(fk.columns),
                "ref_table": fk.ref_table,
                "ref_columns": list(fk.ref_columns),
            }
            for fk in table.foreign_keys
        ],
        "columns": [
            {
                "name": c.name,
                "type": c.type,
                "nullable": c.nullable,
                "comment": ask_schema.clean_comment(c.comment),
                "samples": list(c.samples) if samples else [],
            }
            for c in table.columns
        ],
    }


def _current(
    request: HttpRequest, workspace: int | None
) -> tuple[ask_schema.Schema, bool]:
    samples = settings.SCHEMA_API_INCLUDE_SAMPLES
    ref = workspace_for(cast(User, request.user), workspace)
    return ask_schema.get_schema(ref, include_samples=samples), samples


def _etag(data: Any) -> str:
    digest = hashlib.sha256(
        json.dumps(data, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()
    return f'"{digest[:32]}"'


def _respond(request: HttpRequest, data: Any) -> HttpResponse:
    """The envelope with an ETag, or a bare 304 when the caller already has this
    version. The tag is a hash of the body, so it changes exactly when the schema
    (or the samples setting) does; `no-cache` makes the browser revalidate."""
    etag = _etag(data)
    wanted = [t.strip() for t in request.headers.get("If-None-Match", "").split(",")]
    if etag in wanted:
        response = HttpResponse(status=304)
    else:
        response = HttpResponse(
            json.dumps(success(data)), content_type="application/json"
        )
    response["ETag"] = etag
    response["Cache-Control"] = "private, no-cache"
    return response


@router.get(
    "",
    response={200: SuccessEnvelope[SchemaOut], 304: None, **errors(401, 404, 409, 429)},
    auth=django_auth,
)
def get_schema(request: HttpRequest, workspace: int | None = None) -> HttpResponse:
    """Every table of the demo schema, or of your workspace (`workspace`), with
    columns, keys, comments and row estimates. Send `If-None-Match` with the last
    `ETag` to get a 304 when nothing changed."""
    schema, samples = _current(request, workspace)
    data = {
        "name": schema.name,
        "tables": [table_dict(t, samples=samples) for t in schema.tables],
    }
    return _respond(request, data)


@router.get(
    "/tables/{name}",
    response={200: SuccessEnvelope[TableOut], 304: None, **errors(401, 404, 409, 429)},
    auth=django_auth,
)
def get_table(
    request: HttpRequest, name: str, workspace: int | None = None
) -> HttpResponse:
    """One table, same shape as in the full schema. An unknown name is a 404
    `table_not_found` that says nothing else about the schema."""
    schema, samples = _current(request, workspace)
    table = schema.table(name)
    if table is None:
        raise TableNotFound()
    return _respond(request, table_dict(table, samples=samples))


class TableRowsOut(Schema):
    columns: list[str]
    rows: list[list[Any]]
    offset: int
    limit: int
    # True when at least one more row follows this page.
    has_more: bool
    # Postgres's own estimate of the table's size; null until analyzed.
    row_estimate: int | None


def _quote(identifier: str) -> str:
    return '"' + identifier.replace('"', '""') + '"'


@router.get(
    "/tables/{name}/rows",
    response={200: SuccessEnvelope[TableRowsOut], **errors(401, 404, 409, 429)},
    auth=django_auth,
    throttle=[ResultThrottle()],
)
def get_table_rows(
    request: HttpRequest,
    name: str,
    workspace: int | None = None,
    offset: int = 0,
    limit: int | None = None,
) -> dict:
    """A read-only page of one table's rows, in primary-key order when it has one.
    The table must exist in the schema (an unknown name is a 404 `table_not_found`);
    the SQL is built here from catalog names only, never from the request, and runs on
    the same reader connection as every other read. Page size is capped by
    PAGINATION_MAX_LIMIT."""
    schema, _ = _current(request, workspace)
    table = schema.table(name)
    if table is None:
        raise TableNotFound()
    size = min(
        limit or settings.PAGINATION_DEFAULT_LIMIT, settings.PAGINATION_MAX_LIMIT
    )
    start = max(offset, 0)
    order = (
        " ORDER BY " + ", ".join(_quote(c) for c in table.primary_key)
        if table.primary_key
        else ""
    )
    sql_text = (
        f"SELECT * FROM {_quote(schema.name)}.{_quote(table.name)}{order} "
        f"LIMIT {size + 1} OFFSET {start}"
    )
    ref = workspace_for(cast(User, request.user), workspace)
    result = runner.run(sql_text, ref)
    return success(
        {
            "columns": result.columns,
            "rows": result.rows[:size],
            "offset": start,
            "limit": size,
            "has_more": len(result.rows) > size,
            "row_estimate": table.row_estimate,
        }
    )
