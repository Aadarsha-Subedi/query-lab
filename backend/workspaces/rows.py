"""Reading and editing the rows of a user table through the API.

Rows are addressed by the hidden `_row_id`. Nothing from the request is ever SQL:
column names are looked up in the catalog first, values are coerced to the
column's type and bound as parameters, ids are integers, and the request never
supplies a WHERE clause. Writes run as the workspace's own `_rw` role in one
transaction (all or nothing); reads use the `_ro` role."""

from typing import Any

from django.conf import settings
from psycopg import errors as pg_errors
from psycopg import sql

from accounts.models import User
from ask import schema as ask_schema
from ask.runner import to_json_safe
from workspaces import connections, naming, quota, schema_version, values
from workspaces.changes import Changes, changes
from workspaces.errors import (
    ConstraintViolated,
    InvalidSpec,
    RowInvalid,
    RowNotFound,
    RowRequestTooBig,
    TableNotFound,
)
from workspaces.models import Workspace
from workspaces.tables import API_TYPE, _existing_table

OPERATORS = {"eq", "contains"}
CONSTRAINT_ERRORS = (
    pg_errors.UniqueViolation,
    pg_errors.NotNullViolation,
    pg_errors.ForeignKeyViolation,
    pg_errors.CheckViolation,
    pg_errors.ExclusionViolation,
)


# ── reading ───────────────────────────────────────────────────────────────


def _like(text: str) -> str:
    return (
        "%" + text.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_") + "%"
    )


def _filter_clause(
    table: ask_schema.Table, filters: list[str]
) -> tuple[sql.Composable, list[Any]]:
    clauses: list[sql.Composable] = []
    params: list[Any] = []
    for raw in filters:
        column, _, rest = raw.partition(":")
        operator, _, text = rest.partition(":")
        spec = table.column(column)
        if spec is None or operator not in OPERATORS:
            raise InvalidSpec("A filter is column:eq:value or column:contains:value.")
        ident = sql.Identifier(column)
        if operator == "contains":
            clauses.append(sql.SQL("{}::text ILIKE %s").format(ident))
            params.append(_like(text))
            continue
        try:
            coerced = values.coerce(text, API_TYPE.get(spec.type, spec.type))
        except values.BadValue as error:
            raise RowInvalid(
                errors=[{"field": column, "message": str(error)}]
            ) from None
        if coerced is None:
            clauses.append(sql.SQL("{} IS NULL").format(ident))
        else:
            clauses.append(sql.SQL("{} = %s").format(ident))
            params.append(coerced)
    where = sql.SQL(" AND ").join(clauses) if clauses else sql.SQL("TRUE")
    return where, params


def list_rows(
    workspace: Workspace,
    table_name: str,
    *,
    limit: int,
    offset: int,
    order_by: str | None,
    descending: bool,
    filters: list[str],
) -> dict[str, Any]:
    with connections.workspace_connection(
        workspace.pk, "ro", workspace.credential_version
    ) as connection:
        with connection.cursor() as cursor:
            known = ask_schema.schema_from_cursor(
                cursor, workspace.schema_name, show_hidden=True
            )
        table = known.table(table_name)
        if table is None:
            raise TableNotFound()
        key = order_by or naming.ROW_ID
        if table.column(key) is None:
            raise InvalidSpec("Order by one of the table's columns.")
        where, params = _filter_clause(table, filters)
        target = sql.SQL("{}.{}").format(
            sql.Identifier(workspace.schema_name), sql.Identifier(table_name)
        )
        total = connection.execute(
            sql.SQL("SELECT count(*) FROM {table} WHERE {where}").format(
                table=target, where=where
            ),
            params,
        ).fetchone()
        cursor = connection.execute(
            sql.SQL(
                "SELECT * FROM {table} WHERE {where} ORDER BY {key} {direction}, {row} "
                "LIMIT %s OFFSET %s"
            ).format(
                table=target,
                where=where,
                key=sql.Identifier(key),
                direction=sql.SQL("DESC" if descending else "ASC"),
                row=sql.Identifier(naming.ROW_ID),
            ),
            [*params, limit, offset],
        )
        rows = [[_cell(v) for v in row] for row in cursor.fetchall()]
    return {
        "columns": [
            {"name": c.name, "type": API_TYPE.get(c.type, c.type)}
            for c in table.columns
        ],
        "rows": rows,
        "total": int(total[0]) if total else 0,
    }


def _cell(value: Any) -> Any:
    if isinstance(value, bytes | bytearray | memoryview):
        return "\\x" + bytes(value).hex()
    return to_json_safe(value)


# ── writing ───────────────────────────────────────────────────────────────


def _coerce_row(
    index: int, row: dict[str, Any], table: ask_schema.Table
) -> dict[str, Any]:
    cleaned: dict[str, Any] = {}
    for name, raw in row.items():
        column = table.column(name)
        field = f"rows[{index}].{name}"
        if column is None or name == naming.ROW_ID:
            raise RowInvalid(errors=[{"field": field, "message": "No such column."}])
        try:
            cleaned[name] = values.coerce(raw, API_TYPE.get(column.type, column.type))
        except values.BadValue as error:
            raise RowInvalid(errors=[{"field": field, "message": str(error)}]) from None
    return cleaned


def _constraint(error: pg_errors.IntegrityError) -> ConstraintViolated:
    diag = getattr(error, "diag", None)
    name = getattr(diag, "constraint_name", None) or getattr(diag, "column_name", None)
    kind = {
        pg_errors.UniqueViolation: "A value must be unique",
        pg_errors.NotNullViolation: "A value is required",
        pg_errors.ForeignKeyViolation: "A relation would be broken",
        pg_errors.CheckViolation: "A check failed",
    }.get(type(error), "A constraint failed")
    return ConstraintViolated(
        f"{kind}.",
        errors=[
            {"field": "rows", "message": f"{kind} ({name})." if name else f"{kind}."}
        ],
    )


def _size_class(count: int) -> int:
    """Row counts in orders of magnitude: the schema text says "about N rows", so
    only a change of order of magnitude is worth a fresh schema read."""
    return len(str(max(count, 0)))


def _count(c: Changes, table: str) -> int:
    row = c.query(sql.SQL("SELECT count(*) FROM {}").format(c.table(table))).fetchone()
    return int(row[0]) if row else 0


def _settle(
    c: Changes, workspace: Workspace, table: str, before: int, size_before: int
) -> None:
    """After a write, in its transaction: stay under the size caps, and move the
    schema version only when the table's row count changed its order of magnitude."""
    quota.ensure_within(c.connection, workspace, grew_from=size_before)
    if _size_class(_count(c, table)) != _size_class(before):
        c.after_commit(lambda: schema_version.bump(workspace.pk))


def insert_rows(
    workspace: Workspace, actor: User, table_name: str, rows: list[dict[str, Any]]
) -> dict[str, Any]:
    if not rows:
        raise InvalidSpec("Send at least one row.")
    if len(rows) > settings.WORKSPACE_MAX_ROWS_PER_EDIT:
        raise RowRequestTooBig(
            f"At most {settings.WORKSPACE_MAX_ROWS_PER_EDIT} rows per request."
        )
    quota.ensure_room(workspace)
    with changes(workspace, actor) as c:
        table = _existing_table(c, table_name)
        cleaned = [_coerce_row(i, row, table) for i, row in enumerate(rows)]
        names = [
            n
            for n in (col.name for col in table.columns)
            if any(n in r for r in cleaned)
        ]
        before = _count(c, table_name)
        size_before = quota.measure(c.connection, workspace.schema_name)
        if names:
            tuples = []
            params: list[Any] = []
            for row in cleaned:
                cells: list[sql.Composable] = []
                for name in names:
                    if name in row:
                        cells.append(sql.Placeholder())
                        params.append(row[name])
                    else:
                        cells.append(sql.SQL("DEFAULT"))
                tuples.append(sql.SQL("({})").format(sql.SQL(", ").join(cells)))
            statement = sql.SQL(
                "INSERT INTO {table} ({cols}) VALUES {values} RETURNING {row}"
            ).format(
                table=c.table(table_name),
                cols=sql.SQL(", ").join(sql.Identifier(n) for n in names),
                values=sql.SQL(", ").join(tuples),
                row=sql.Identifier(naming.ROW_ID),
            )
        else:  # every row is empty: all defaults
            statement = sql.SQL(
                "INSERT INTO {table} SELECT FROM generate_series(1, %s) RETURNING {row}"
            ).format(table=c.table(table_name), row=sql.Identifier(naming.ROW_ID))
            params = [len(cleaned)]
        try:
            ids = [int(r[0]) for r in c.query(statement, params).fetchall()]
        except CONSTRAINT_ERRORS as error:
            raise _constraint(error) from None
        _settle(c, workspace, table_name, before, size_before)
    return {"inserted": len(ids), "ids": ids}


def update_row(
    workspace: Workspace,
    actor: User,
    table_name: str,
    row_id: int,
    patch: dict[str, Any],
) -> dict[str, Any]:
    if not patch:
        raise InvalidSpec("Send at least one value to change.")
    quota.ensure_room(workspace)
    with changes(workspace, actor) as c:
        table = _existing_table(c, table_name)
        cleaned = _coerce_row(0, patch, table)
        size_before = quota.measure(c.connection, workspace.schema_name)
        assignments = sql.SQL(", ").join(
            sql.SQL("{} = %s").format(sql.Identifier(name)) for name in cleaned
        )
        try:
            cursor = c.query(
                sql.SQL("UPDATE {table} SET {set} WHERE {row} = %s RETURNING *").format(
                    table=c.table(table_name),
                    set=assignments,
                    row=sql.Identifier(naming.ROW_ID),
                ),
                [*cleaned.values(), row_id],
            )
        except CONSTRAINT_ERRORS as error:
            raise _constraint(error) from None
        found = cursor.fetchone()
        if found is None:
            raise RowNotFound()
        names = [d.name for d in cursor.description or []]
        quota.ensure_within(c.connection, workspace, grew_from=size_before)
    return {"row": dict(zip(names, (_cell(v) for v in found), strict=True))}


def _cascade_tables(c: Changes, table: str) -> list[str]:
    """Tables whose rows go when rows of `table` do: children joined by ON DELETE
    CASCADE relations, followed all the way down."""
    found: list[str] = []
    pending = [table]
    while pending:
        parent = pending.pop()
        for (child,) in c.query(
            "SELECT DISTINCT c.relname FROM pg_constraint con "
            "JOIN pg_class c ON c.oid = con.conrelid "
            "JOIN pg_class p ON p.oid = con.confrelid "
            "JOIN pg_namespace n ON n.oid = p.relnamespace "
            "WHERE con.contype = 'f' AND con.confdeltype = 'c' "
            "AND n.nspname = %s AND p.relname = %s",
            [c.schema_name, parent],
        ).fetchall():
            if child != table and child not in found:
                found.append(child)
                pending.append(child)
    return found


def delete_rows(
    workspace: Workspace, actor: User, table_name: str, ids: list[int]
) -> dict[str, Any]:
    if not ids:
        raise InvalidSpec("Send at least one row id.")
    if len(ids) > settings.WORKSPACE_MAX_ROWS_PER_EDIT:
        raise RowRequestTooBig(
            f"At most {settings.WORKSPACE_MAX_ROWS_PER_EDIT} rows per request."
        )
    with changes(workspace, actor) as c:
        _existing_table(c, table_name)
        before = _count(c, table_name)
        children = _cascade_tables(c, table_name)
        child_before = {t: _count(c, t) for t in children}
        try:
            cursor = c.query(
                sql.SQL("DELETE FROM {table} WHERE {row} = ANY(%s)").format(
                    table=c.table(table_name), row=sql.Identifier(naming.ROW_ID)
                ),
                [ids],
            )
        except pg_errors.ForeignKeyViolation as error:
            raise _constraint(error) from None
        deleted = cursor.rowcount
        cascaded = sum(child_before[t] - _count(c, t) for t in children)
        if _size_class(_count(c, table_name)) != _size_class(before):
            c.after_commit(lambda: schema_version.bump(workspace.pk))
    return {"deleted": deleted, "cascaded": cascaded}


def delete_row(
    workspace: Workspace, actor: User, table_name: str, row_id: int
) -> dict[str, Any]:
    result = delete_rows(workspace, actor, table_name, [row_id])
    if result["deleted"] == 0:
        raise RowNotFound()
    return result
