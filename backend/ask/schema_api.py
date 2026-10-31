"""The schema browser: the demo schema as the analyst screen's schema panel shows it.

Read from `ask.schema.get_schema`, so it shares the cache the agent's tools use and
never writes. Demo schema only (step 5 adds a workspace parameter)."""

import hashlib
import json
from typing import Any

from django.conf import settings
from django.http import HttpRequest, HttpResponse
from ninja import Router, Schema
from ninja.security import django_auth

from ask import schema as ask_schema
from common.exception.domain import NotFoundException
from common.response.domain import SuccessEnvelope, success

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


def _current() -> tuple[ask_schema.Schema, bool]:
    samples = settings.SCHEMA_API_INCLUDE_SAMPLES
    return ask_schema.get_schema(include_samples=samples), samples


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
    response={200: SuccessEnvelope[SchemaOut], 304: None},
    auth=django_auth,
)
def get_schema(request: HttpRequest) -> HttpResponse:
    """Every table of the demo schema with columns, keys, comments and row
    estimates. Send `If-None-Match` with the last `ETag` to get a 304 when
    nothing changed."""
    schema, samples = _current()
    data = {
        "name": schema.name,
        "tables": [table_dict(t, samples=samples) for t in schema.tables],
    }
    return _respond(request, data)


@router.get(
    "/tables/{name}",
    response={200: SuccessEnvelope[TableOut], 304: None},
    auth=django_auth,
)
def get_table(request: HttpRequest, name: str) -> HttpResponse:
    """One table, same shape as in the full schema. An unknown name is a 404
    `table_not_found` that says nothing else about the schema."""
    schema, samples = _current()
    table = schema.table(name)
    if table is None:
        raise TableNotFound()
    return _respond(request, table_dict(table, samples=samples))
