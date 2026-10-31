"""Tables and columns of a user workspace: create, rename, describe, add, retype
and drop, all as the workspace's own `_rw` role and all through `psycopg.sql`.

Names the caller sends are slugged by `naming` before they get anywhere near SQL,
and names of existing tables and columns are looked up in the catalog first (so an
unknown name is a 404, never an error message from the database). Every user table
gets a hidden identity key `_row_id`, which rows are edited and deleted by.
"""

from dataclasses import dataclass, field
from typing import Any

from django.conf import settings
from psycopg import errors as pg_errors
from psycopg import sql

from accounts.models import User
from ask import schema as ask_schema
from workspaces import credentials, naming
from workspaces.changes import Changes, changes, import_timeout_ms
from workspaces.errors import (
    CastFailed,
    ColumnLimitReached,
    ColumnNameTaken,
    ColumnNotFound,
    ConstraintViolated,
    InvalidName,
    InvalidSpec,
    TableLimitReached,
    TableNameTaken,
    TableNotFound,
)
from workspaces.models import Workspace

# Postgres type -> the API's type name (the reverse of naming.COLUMN_TYPES).
API_TYPE = {pg: api for api, pg in naming.COLUMN_TYPES.items()}


@dataclass
class ColumnSpec:
    name: str
    type: str
    nullable: bool = True
    description: str = ""
    default: str | None = None


@dataclass
class TableSpec:
    name: str
    description: str = ""
    columns: list[ColumnSpec] = field(default_factory=list)


def clean_description(text: str | None) -> str:
    text = " ".join((text or "").split())
    if len(text) > settings.WORKSPACE_DESCRIPTION_MAX_LENGTH:
        raise InvalidName(
            "A description has at most "
            f"{settings.WORKSPACE_DESCRIPTION_MAX_LENGTH} characters."
        )
    return text


def _comment(c: Changes, kind: str, target: sql.Composable, text: str) -> None:
    c.run(
        sql.SQL("COMMENT ON {kind} {target} IS {text}").format(
            kind=sql.SQL(kind),
            target=target,
            text=sql.Literal(text) if text else sql.SQL("NULL"),
        )
    )


# ── reading ───────────────────────────────────────────────────────────────


def _read(c: Changes) -> ask_schema.Schema:
    with c.connection.cursor() as cursor:
        return ask_schema.schema_from_cursor(cursor, c.schema_name, show_hidden=True)


def table_dict(table: ask_schema.Table) -> dict[str, Any]:
    return {
        "name": table.name,
        "description": ask_schema.clean_comment(table.comment),
        "row_estimate": table.row_estimate,
        "primary_key": list(table.primary_key),
        "columns": [
            {
                "name": column.name,
                "type": API_TYPE.get(column.type, column.type),
                "nullable": column.nullable,
                "description": ask_schema.clean_comment(column.comment),
                "hidden": column.name == naming.ROW_ID,
            }
            for column in table.columns
        ],
    }


def list_tables(workspace: Workspace) -> list[dict[str, Any]]:
    with changes(workspace, None) as c:
        return [table_dict(t) for t in _read(c).tables]


def get_table(workspace: Workspace, name: str) -> dict[str, Any]:
    with changes(workspace, None) as c:
        return table_dict(_existing_table(c, name))


def _existing_table(c: Changes, name: str) -> ask_schema.Table:
    table = _read(c).table(name)
    if table is None:
        raise TableNotFound()
    return table


def _existing_column(table: ask_schema.Table, name: str) -> ask_schema.Column:
    column = table.column(name)
    if column is None or name == naming.ROW_ID:
        raise ColumnNotFound()
    return column


# ── tables ────────────────────────────────────────────────────────────────


def _column_definition(spec: ColumnSpec) -> sql.Composed:
    parts: list[sql.Composable] = [
        sql.Identifier(spec.name),
        sql.SQL(naming.column_type(spec.type)),
    ]
    if not spec.nullable:
        parts.append(sql.SQL("NOT NULL"))
    if spec.default is not None:
        parts.append(sql.SQL("DEFAULT ") + sql.Literal(spec.default))
    return sql.SQL(" ").join(parts)


def create_table(workspace: Workspace, actor: User, spec: TableSpec) -> dict[str, Any]:
    if not spec.columns:
        raise InvalidSpec("A table needs at least one column.")
    if len(spec.columns) > settings.IMPORT_MAX_COLUMNS:
        raise ColumnLimitReached()
    name = naming.table_name(spec.name)
    description = clean_description(spec.description)
    columns: list[ColumnSpec] = []
    for column in spec.columns:
        slug = naming.column_name(column.name, [c.name for c in columns])
        if slug != naming.identifier_slug(column.name, kind="column"):
            raise ColumnNameTaken()
        columns.append(
            ColumnSpec(
                slug,
                column.type,
                column.nullable,
                clean_description(column.description),
                column.default,
            )
        )
    with changes(workspace, actor) as c:
        existing = _read(c)
        if existing.table(name) is not None:
            raise TableNameTaken()
        if len(existing.tables) >= settings.WORKSPACE_MAX_TABLES:
            raise TableLimitReached()
        definitions = [
            sql.SQL("{key} bigint GENERATED ALWAYS AS IDENTITY NOT NULL UNIQUE").format(
                key=sql.Identifier(naming.ROW_ID)
            ),
            *(_column_definition(column) for column in columns),
        ]
        c.run(
            sql.SQL("CREATE TABLE {table} ({columns})").format(
                table=c.table(name), columns=sql.SQL(", ").join(definitions)
            )
        )
        c.run(
            sql.SQL("GRANT SELECT ON {table} TO {ro}").format(
                table=c.table(name),
                ro=sql.Identifier(credentials.role_name(workspace.pk, "ro")),
            )
        )
        if description:
            _comment(c, "TABLE", c.table(name), description)
        for column in columns:
            if column.description:
                _comment(
                    c,
                    "COLUMN",
                    sql.SQL("{}.{}").format(c.table(name), sql.Identifier(column.name)),
                    column.description,
                )
        return table_dict(_existing_table(c, name))


def update_table(
    workspace: Workspace,
    actor: User,
    name: str,
    *,
    new_name: str | None,
    description: str | None,
) -> dict[str, Any]:
    with changes(workspace, actor) as c:
        _existing_table(c, name)
        final = name
        if new_name is not None:
            slug = naming.identifier_slug(new_name, kind="table")
            if slug != name:
                if _read(c).table(slug) is not None:
                    raise TableNameTaken()
                c.run(
                    sql.SQL("ALTER TABLE {old} RENAME TO {new}").format(
                        old=c.table(name), new=sql.Identifier(slug)
                    )
                )
                final = slug
        if description is not None:
            _comment(c, "TABLE", c.table(final), clean_description(description))
        return table_dict(_existing_table(c, final))


def drop_table(workspace: Workspace, actor: User, name: str) -> None:
    with changes(workspace, actor) as c:
        _existing_table(c, name)
        # CASCADE removes relations that point at this table (never other tables).
        c.run(sql.SQL("DROP TABLE {table} CASCADE").format(table=c.table(name)))


# ── columns ───────────────────────────────────────────────────────────────


def add_column(
    workspace: Workspace, actor: User, table_name: str, spec: ColumnSpec
) -> dict[str, Any]:
    with changes(workspace, actor) as c:
        table = _existing_table(c, table_name)
        visible = [col.name for col in table.columns if col.name != naming.ROW_ID]
        if len(visible) >= settings.IMPORT_MAX_COLUMNS:
            raise ColumnLimitReached()
        slug = naming.identifier_slug(spec.name, kind="column")
        if slug in [col.name for col in table.columns] or slug == naming.ROW_ID:
            raise ColumnNameTaken()
        column = ColumnSpec(
            slug,
            spec.type,
            spec.nullable,
            clean_description(spec.description),
            spec.default,
        )
        try:
            c.run(
                sql.SQL("ALTER TABLE {table} ADD COLUMN {definition}").format(
                    table=c.table(table_name),
                    definition=_column_definition(column),
                )
            )
        except (pg_errors.NotNullViolation, pg_errors.InvalidTextRepresentation):
            raise ConstraintViolated(
                "A NOT NULL column on a table with rows needs a default that fits its type.",
                errors=[{"field": "default", "message": "Give a default."}],
            ) from None
        if column.description:
            _comment(
                c,
                "COLUMN",
                sql.SQL("{}.{}").format(c.table(table_name), sql.Identifier(slug)),
                column.description,
            )
        return table_dict(_existing_table(c, table_name))


def first_bad_row(
    c: Changes, table: str, column: str, condition: sql.Composable
) -> int | None:
    row = c.query(
        sql.SQL(
            "SELECT {key} FROM {table} WHERE {condition} ORDER BY {key} LIMIT 1"
        ).format(
            key=sql.Identifier(naming.ROW_ID),
            table=c.table(table),
            condition=condition,
        )
    ).fetchone()
    return None if row is None else int(row[0])


def update_column(
    workspace: Workspace,
    actor: User,
    table_name: str,
    column_name: str,
    *,
    new_name: str | None = None,
    description: str | None = None,
    nullable: bool | None = None,
    type: str | None = None,
) -> dict[str, Any]:
    with changes(workspace, actor, timeout_ms=import_timeout_ms()) as c:
        table = _existing_table(c, table_name)
        column = _existing_column(table, column_name)
        reference = sql.SQL("{}.{}")
        current = column_name
        if type is not None and API_TYPE.get(column.type) != type:
            _retype(c, table_name, column_name, type)
        if nullable is not None and nullable != column.nullable:
            if nullable:
                c.run(
                    sql.SQL(
                        "ALTER TABLE {table} ALTER COLUMN {col} DROP NOT NULL"
                    ).format(table=c.table(table_name), col=sql.Identifier(column_name))
                )
            else:
                bad = first_bad_row(
                    c,
                    table_name,
                    column_name,
                    sql.SQL("{col} IS NULL").format(col=sql.Identifier(column_name)),
                )
                if bad is not None:
                    raise ConstraintViolated(
                        "This column has empty values, so it cannot be NOT NULL.",
                        errors=[
                            {
                                "field": "nullable",
                                "message": f"First empty value: row {bad}.",
                            }
                        ],
                    )
                c.run(
                    sql.SQL(
                        "ALTER TABLE {table} ALTER COLUMN {col} SET NOT NULL"
                    ).format(table=c.table(table_name), col=sql.Identifier(column_name))
                )
        if new_name is not None:
            slug = naming.identifier_slug(new_name, kind="column")
            if slug != column_name:
                if slug in [col.name for col in table.columns] or slug == naming.ROW_ID:
                    raise ColumnNameTaken()
                c.run(
                    sql.SQL("ALTER TABLE {table} RENAME COLUMN {old} TO {new}").format(
                        table=c.table(table_name),
                        old=sql.Identifier(column_name),
                        new=sql.Identifier(slug),
                    )
                )
                current = slug
        if description is not None:
            _comment(
                c,
                "COLUMN",
                reference.format(c.table(table_name), sql.Identifier(current)),
                clean_description(description),
            )
        return table_dict(_existing_table(c, table_name))


def _retype(c: Changes, table: str, column: str, api_type: str) -> None:
    """`ALTER COLUMN ... TYPE ... USING col::type` inside this transaction: a
    value that does not convert names its row and changes nothing."""
    pg_type = naming.column_type(api_type)
    col = sql.Identifier(column)
    bad = first_bad_row(
        c,
        table,
        column,
        sql.SQL(
            "{col} IS NOT NULL AND NOT pg_input_is_valid({col}::text, {type})"
        ).format(col=col, type=sql.Literal(pg_type)),
    )
    if bad is not None:
        raise CastFailed(
            "A value in this column cannot be converted to the new type.",
            errors=[
                {
                    "field": "type",
                    "message": f"First value that does not convert: row {bad}.",
                }
            ],
        )
    try:
        c.run(
            sql.SQL(
                "ALTER TABLE {table} ALTER COLUMN {col} TYPE {type} USING {col}::{type}"
            ).format(table=c.table(table), col=col, type=sql.SQL(pg_type))
        )
    except (
        pg_errors.DataError,
        pg_errors.DatatypeMismatch,
        pg_errors.CannotCoerce,
        pg_errors.DependentObjectsStillExist,
        pg_errors.FeatureNotSupported,
    ):
        raise CastFailed(
            "This column cannot be converted to the new type.",
            errors=[{"field": "type", "message": "The conversion was refused."}],
        ) from None


def drop_column(
    workspace: Workspace, actor: User, table_name: str, column_name: str
) -> None:
    with changes(workspace, actor) as c:
        table = _existing_table(c, table_name)
        _existing_column(table, column_name)
        if len([col for col in table.columns if col.name != naming.ROW_ID]) <= 1:
            raise InvalidSpec(
                "A table keeps at least one column. Drop the table instead."
            )
        # CASCADE removes keys and relations that use the column.
        c.run(
            sql.SQL("ALTER TABLE {table} DROP COLUMN {col} CASCADE").format(
                table=c.table(table_name), col=sql.Identifier(column_name)
            )
        )
