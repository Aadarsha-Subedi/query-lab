from typing import cast

from django.http import HttpRequest
from ninja import Router
from ninja.security import django_auth

from accounts.models import User
from common.response.domain import SuccessEnvelope, errors, success
from workspaces import tables
from workspaces.access import writable_workspace
from workspaces.table_schemas import (
    ColumnIn,
    ColumnPatch,
    TableIn,
    TablePatch,
    WorkspaceTableOut,
)

router = Router(tags=["workspace tables"])

TABLE_ERRORS = errors(401, 404, 409, 422, 429, 504)


def _user(request: HttpRequest) -> User:
    return cast(User, request.user)


def _spec(payload: ColumnIn) -> tables.ColumnSpec:
    return tables.ColumnSpec(
        name=payload.name,
        type=payload.type,
        nullable=payload.nullable,
        description=payload.description,
        default=payload.default,
    )


@router.get(
    "/{workspace_id}/tables",
    response={200: SuccessEnvelope[list[WorkspaceTableOut]], **TABLE_ERRORS},
    auth=django_auth,
)
def list_workspace_tables(request: HttpRequest, workspace_id: int) -> dict:
    """The workspace's tables with their columns, including the hidden `_row_id`."""
    workspace = writable_workspace(_user(request), workspace_id)
    return success(tables.list_tables(workspace))


@router.post(
    "/{workspace_id}/tables",
    response={200: SuccessEnvelope[WorkspaceTableOut], **TABLE_ERRORS},
    auth=django_auth,
)
def create_workspace_table(
    request: HttpRequest, workspace_id: int, payload: TableIn
) -> dict:
    """Create an empty table from a column spec. It gets a hidden identity key
    `_row_id`. `table_limit_reached` / `column_limit_reached` name the cap."""
    workspace = writable_workspace(_user(request), workspace_id)
    spec = tables.TableSpec(
        payload.name, payload.description, [_spec(c) for c in payload.columns]
    )
    return success(tables.create_table(workspace, _user(request), spec))


@router.get(
    "/{workspace_id}/tables/{table}",
    response={200: SuccessEnvelope[WorkspaceTableOut], **TABLE_ERRORS},
    auth=django_auth,
)
def get_workspace_table(request: HttpRequest, workspace_id: int, table: str) -> dict:
    workspace = writable_workspace(_user(request), workspace_id)
    return success(tables.get_table(workspace, table))


@router.patch(
    "/{workspace_id}/tables/{table}",
    response={200: SuccessEnvelope[WorkspaceTableOut], **TABLE_ERRORS},
    auth=django_auth,
)
def update_workspace_table(
    request: HttpRequest, workspace_id: int, table: str, payload: TablePatch
) -> dict:
    """Rename a table and/or set its description."""
    workspace = writable_workspace(_user(request), workspace_id)
    return success(
        tables.update_table(
            workspace,
            _user(request),
            table,
            new_name=payload.name,
            description=payload.description,
        )
    )


@router.delete(
    "/{workspace_id}/tables/{table}",
    response={200: SuccessEnvelope[None], **TABLE_ERRORS},
    auth=django_auth,
)
def delete_workspace_table(request: HttpRequest, workspace_id: int, table: str) -> dict:
    """Drop the table and its rows for good, with relations that point at it."""
    workspace = writable_workspace(_user(request), workspace_id)
    tables.drop_table(workspace, _user(request), table)
    return success(None, message="Table dropped.")


@router.post(
    "/{workspace_id}/tables/{table}/columns",
    response={200: SuccessEnvelope[WorkspaceTableOut], **TABLE_ERRORS},
    auth=django_auth,
)
def add_workspace_column(
    request: HttpRequest, workspace_id: int, table: str, payload: ColumnIn
) -> dict:
    """Add a column. A NOT NULL column on a table that has rows needs a default."""
    workspace = writable_workspace(_user(request), workspace_id)
    return success(tables.add_column(workspace, _user(request), table, _spec(payload)))


@router.patch(
    "/{workspace_id}/tables/{table}/columns/{column}",
    response={200: SuccessEnvelope[WorkspaceTableOut], **TABLE_ERRORS},
    auth=django_auth,
)
def update_workspace_column(
    request: HttpRequest,
    workspace_id: int,
    table: str,
    column: str,
    payload: ColumnPatch,
) -> dict:
    """Rename a column, set its description or nullability, or change its type. A
    retype converts every value inside one transaction; a value that does not
    convert is a 422 `cast_failed` naming its row id, and nothing changes."""
    workspace = writable_workspace(_user(request), workspace_id)
    return success(
        tables.update_column(
            workspace,
            _user(request),
            table,
            column,
            new_name=payload.name,
            description=payload.description,
            nullable=payload.nullable,
            type=payload.type,
        )
    )


@router.delete(
    "/{workspace_id}/tables/{table}/columns/{column}",
    response={200: SuccessEnvelope[WorkspaceTableOut], **TABLE_ERRORS},
    auth=django_auth,
)
def delete_workspace_column(
    request: HttpRequest, workspace_id: int, table: str, column: str
) -> dict:
    """Drop a column (and the keys and relations that use it). The last column
    cannot be dropped."""
    workspace = writable_workspace(_user(request), workspace_id)
    tables.drop_column(workspace, _user(request), table, column)
    return success(tables.get_table(workspace, table))
