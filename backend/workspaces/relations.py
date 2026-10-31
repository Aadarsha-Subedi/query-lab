"""Primary keys and relations of a user workspace, stored as real Postgres
constraints in the workspace schema, so `ask.schema.get_schema` (and with it the
agent and the schema panel) sees the joins with no extra metadata.

A relation can only join two tables of the same workspace: the request names
tables, never schemas, and a name with a schema in it is simply not a table here.
Existing rows are checked when a constraint is added; a violation names the first
offending row id and changes nothing."""

from typing import Any

from django.conf import settings
from psycopg import errors as pg_errors
from psycopg import sql

from accounts.models import User
from workspaces import naming
from workspaces.changes import Changes, changes
from workspaces.errors import (
    ColumnNotFound,
    ConstraintViolated,
    InvalidSpec,
    RelationInvalid,
    RelationLimitReached,
    RelationNotFound,
)
from workspaces.models import Workspace
from workspaces.tables import _existing_table, first_bad_row, table_dict

ON_DELETE = {"NO ACTION": "a", "CASCADE": "c"}
ON_DELETE_NAME = {"a": "NO ACTION", "r": "NO ACTION", "c": "CASCADE"}

RELATIONS_SQL = """
SELECT con.conname,
       c.relname,
       (SELECT array_agg(att.attname ORDER BY k.ord)
          FROM unnest(con.conkey) WITH ORDINALITY k(attnum, ord)
          JOIN pg_attribute att ON att.attrelid = con.conrelid AND att.attnum = k.attnum),
       fc.relname,
       (SELECT array_agg(att.attname ORDER BY k.ord)
          FROM unnest(con.confkey) WITH ORDINALITY k(attnum, ord)
          JOIN pg_attribute att ON att.attrelid = con.confrelid AND att.attnum = k.attnum),
       con.confdeltype
FROM pg_constraint con
JOIN pg_class c ON c.oid = con.conrelid
JOIN pg_class fc ON fc.oid = con.confrelid
JOIN pg_namespace n ON n.oid = c.relnamespace
WHERE n.nspname = %s AND con.contype = 'f'
ORDER BY con.conname
"""

PRIMARY_KEY_SQL = """
SELECT con.conname FROM pg_constraint con
JOIN pg_class c ON c.oid = con.conrelid
JOIN pg_namespace n ON n.oid = c.relnamespace
WHERE n.nspname = %s AND c.relname = %s AND con.contype = 'p'
"""


def _columns(table: Any, names: list[str]) -> list[str]:
    if not names:
        raise InvalidSpec("Name at least one column.")
    if len(set(names)) != len(names):
        raise InvalidSpec("A column is named twice.")
    for name in names:
        if name == naming.ROW_ID or table.column(name) is None:
            raise ColumnNotFound()
    return names


def _id_list(names: list[str]) -> sql.Composed:
    return sql.SQL(", ").join(sql.Identifier(n) for n in names)


def set_primary_key(
    workspace: Workspace, actor: User, table_name: str, columns: list[str]
) -> dict[str, Any]:
    with changes(workspace, actor) as c:
        table = _existing_table(c, table_name)
        names = _columns(table, columns)
        null_row = first_bad_row(
            c,
            table_name,
            names[0],
            sql.SQL(" OR ").join(
                sql.SQL("{} IS NULL").format(sql.Identifier(n)) for n in names
            ),
        )
        if null_row is not None:
            raise ConstraintViolated(
                "A key column has empty values.",
                errors=[
                    {
                        "field": "columns",
                        "message": f"First empty value: row {null_row}.",
                    }
                ],
            )
        keys = _id_list(names)
        duplicate = c.query(
            sql.SQL(
                "SELECT {row} FROM (SELECT {row}, row_number() OVER "
                "(PARTITION BY {keys} ORDER BY {row}) AS n FROM {table}) t "
                "WHERE n > 1 ORDER BY {row} LIMIT 1"
            ).format(
                row=sql.Identifier(naming.ROW_ID), keys=keys, table=c.table(table_name)
            )
        ).fetchone()
        if duplicate is not None:
            raise ConstraintViolated(
                "The key columns are not unique.",
                errors=[
                    {
                        "field": "columns",
                        "message": f"First repeated value: row {duplicate[0]}.",
                    }
                ],
            )
        for (existing,) in c.query(
            PRIMARY_KEY_SQL, [c.schema_name, table_name]
        ).fetchall():
            try:
                c.run(
                    sql.SQL("ALTER TABLE {table} DROP CONSTRAINT {name}").format(
                        table=c.table(table_name), name=sql.Identifier(existing)
                    )
                )
            except pg_errors.DependentObjectsStillExist:
                raise ConstraintViolated(
                    "A relation depends on the current key. Delete that relation first."
                ) from None
        try:
            c.run(
                sql.SQL("ALTER TABLE {table} ADD PRIMARY KEY ({keys})").format(
                    table=c.table(table_name), keys=keys
                )
            )
        except pg_errors.DependentObjectsStillExist:
            raise ConstraintViolated("The key could not be added.") from None
        return table_dict(_existing_table(c, table_name))


def _first_orphan(
    c: Changes,
    child_table: str,
    child_names: list[str],
    parent_table: str,
    parent_names: list[str],
) -> int | None:
    """The lowest `_row_id` of a child row whose (non-empty) key has no parent."""
    match = sql.SQL(" AND ").join(
        sql.SQL("p.{p} = child.{c}").format(p=sql.Identifier(p), c=sql.Identifier(k))
        for k, p in zip(child_names, parent_names, strict=True)
    )
    filled = sql.SQL(" AND ").join(
        sql.SQL("child.{c} IS NOT NULL").format(c=sql.Identifier(k))
        for k in child_names
    )
    try:
        row = c.query(
            sql.SQL(
                "SELECT child.{row} FROM {child} child WHERE {filled} AND NOT EXISTS "
                "(SELECT 1 FROM {parent} p WHERE {match}) ORDER BY child.{row} LIMIT 1"
            ).format(
                row=sql.Identifier(naming.ROW_ID),
                child=c.table(child_table),
                parent=c.table(parent_table),
                filled=filled,
                match=match,
            )
        ).fetchone()
    except (pg_errors.UndefinedFunction, pg_errors.DatatypeMismatch):
        raise RelationInvalid("The two sides have different types.") from None
    return None if row is None else int(row[0])


def _relation_dicts(c: Changes) -> list[dict[str, Any]]:
    return [
        {
            "name": name,
            "child_table": child,
            "child_columns": list(child_cols),
            "parent_table": parent,
            "parent_columns": list(parent_cols),
            "on_delete": ON_DELETE_NAME.get(delete, "NO ACTION"),
        }
        for name, child, child_cols, parent, parent_cols, delete in c.query(
            RELATIONS_SQL, [c.schema_name]
        ).fetchall()
    ]


def list_relations(workspace: Workspace) -> list[dict[str, Any]]:
    with changes(workspace, None) as c:
        return _relation_dicts(c)


def add_relation(
    workspace: Workspace,
    actor: User,
    *,
    child_table: str,
    child_columns: list[str],
    parent_table: str,
    parent_columns: list[str],
    on_delete: str,
) -> dict[str, Any]:
    if on_delete not in ON_DELETE:
        raise InvalidSpec("on_delete is NO ACTION or CASCADE.")
    with changes(workspace, actor) as c:
        existing = _relation_dicts(c)
        if len(existing) >= settings.WORKSPACE_MAX_RELATIONS:
            raise RelationLimitReached()
        child = _existing_table(c, child_table)
        parent = _existing_table(c, parent_table)
        child_names = _columns(child, child_columns)
        parent_names = _columns(parent, parent_columns)
        if len(child_names) != len(parent_names):
            raise InvalidSpec("Both sides need the same number of columns.")
        constraint = naming.unique(
            naming.identifier_slug(
                f"fk_{child_table}_{'_'.join(child_names)}_{parent_table}",
                kind="relation",
            ),
            [r["name"] for r in existing],
        )
        orphan = _first_orphan(c, child_table, child_names, parent_table, parent_names)
        if orphan is not None:
            raise ConstraintViolated(
                "Some rows point at a row that does not exist.",
                errors=[
                    {
                        "field": "child_columns",
                        "message": f"First row with no matching parent: row {orphan}.",
                    }
                ],
            )
        try:
            c.run(
                sql.SQL(
                    "ALTER TABLE {child} ADD CONSTRAINT {name} FOREIGN KEY ({cols}) "
                    "REFERENCES {parent} ({pcols}) ON DELETE {action}"
                ).format(
                    child=c.table(child_table),
                    name=sql.Identifier(constraint),
                    cols=_id_list(child_names),
                    parent=c.table(parent_table),
                    pcols=_id_list(parent_names),
                    action=sql.SQL(on_delete),
                )
            )
        except pg_errors.InvalidForeignKey:
            raise RelationInvalid(
                "The parent columns must be the table's primary key or unique."
            ) from None
        except (pg_errors.DatatypeMismatch, pg_errors.UndefinedFunction):
            raise RelationInvalid("The two sides have different types.") from None
        return next(r for r in _relation_dicts(c) if r["name"] == constraint)


def delete_relation(workspace: Workspace, actor: User, name: str) -> None:
    with changes(workspace, actor) as c:
        found = next((r for r in _relation_dicts(c) if r["name"] == name), None)
        if found is None:
            raise RelationNotFound()
        c.run(
            sql.SQL("ALTER TABLE {table} DROP CONSTRAINT {name}").format(
                table=c.table(found["child_table"]), name=sql.Identifier(name)
            )
        )
