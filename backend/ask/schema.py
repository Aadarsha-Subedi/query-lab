"""The schema the model sees: tables, columns, keys and COMMENT ON text, read
through the reader connection only (the role can only see what it may SELECT).

Example values for low-cardinality text columns come from pg_stats (the most
common values Postgres already keeps), not from scanning the tables, so reading
the schema stays cheap on the small instance.
"""

from dataclasses import dataclass, field

from django.conf import settings
from django.core.cache import cache

from workspaces import schema_version
from workspaces.context import DEMO, WorkspaceRef
from workspaces.reader import read_cursor

TEXT_TYPES = ("text", "character varying", "character")

COLUMNS_SQL = """
SELECT c.relname,
       obj_description(c.oid, 'pg_class'),
       a.attname,
       format_type(a.atttypid, a.atttypmod),
       a.attnotnull,
       col_description(c.oid, a.attnum),
       c.reltuples::bigint
FROM pg_attribute a
JOIN pg_class c ON c.oid = a.attrelid
JOIN pg_namespace n ON n.oid = c.relnamespace
WHERE n.nspname = %s
  AND c.relkind IN ('r', 'p', 'v')
  AND a.attnum > 0
  AND NOT a.attisdropped
  AND has_table_privilege(c.oid, 'SELECT')
ORDER BY c.relname, a.attnum
"""

KEYS_SQL = """
SELECT c.relname,
       con.contype,
       (SELECT array_agg(att.attname ORDER BY k.ord)
          FROM unnest(con.conkey) WITH ORDINALITY k(attnum, ord)
          JOIN pg_attribute att
            ON att.attrelid = con.conrelid AND att.attnum = k.attnum),
       fc.relname,
       (SELECT array_agg(att.attname ORDER BY k.ord)
          FROM unnest(con.confkey) WITH ORDINALITY k(attnum, ord)
          JOIN pg_attribute att
            ON att.attrelid = con.confrelid AND att.attnum = k.attnum)
FROM pg_constraint con
JOIN pg_class c ON c.oid = con.conrelid
JOIN pg_namespace n ON n.oid = c.relnamespace
LEFT JOIN pg_class fc ON fc.oid = con.confrelid
WHERE n.nspname = %s AND con.contype IN ('p', 'f')
ORDER BY c.relname, con.contype DESC, con.conname
"""

SAMPLES_SQL = """
SELECT tablename, attname, n_distinct, most_common_vals::text::text[]
FROM pg_stats
WHERE schemaname = %s
  AND most_common_vals IS NOT NULL
  AND n_distinct > 0
  AND n_distinct <= %s
"""


@dataclass(frozen=True)
class Column:
    name: str
    type: str
    nullable: bool
    comment: str | None = None
    samples: tuple[str, ...] = ()


@dataclass(frozen=True)
class ForeignKey:
    columns: tuple[str, ...]
    ref_table: str
    ref_columns: tuple[str, ...]


@dataclass(frozen=True)
class Table:
    name: str
    comment: str | None
    columns: tuple[Column, ...]
    primary_key: tuple[str, ...] = ()
    foreign_keys: tuple[ForeignKey, ...] = ()
    # Postgres's own estimate (pg_class.reltuples); None until the table is analyzed.
    row_estimate: int | None = None

    def column(self, name: str) -> Column | None:
        return next((c for c in self.columns if c.name == name), None)


@dataclass(frozen=True)
class Schema:
    name: str
    tables: tuple[Table, ...] = field(default_factory=tuple)

    def table(self, name: str) -> Table | None:
        return next((t for t in self.tables if t.name == name), None)


def read_schema(
    workspace: WorkspaceRef = DEMO, *, include_samples: bool = False
) -> Schema:
    """Read the schema fresh from the database as the workspace's reader role
    (querylab_reader for the demo). The schema name is a bound parameter."""
    schema_name = workspace.schema_name
    with read_cursor(workspace) as cursor:
        cursor.execute(COLUMNS_SQL, [schema_name])
        column_rows = cursor.fetchall()
        cursor.execute(KEYS_SQL, [schema_name])
        key_rows = cursor.fetchall()
        samples: dict[tuple[str, str], tuple[str, ...]] = {}
        if include_samples:
            cursor.execute(
                SAMPLES_SQL, [schema_name, settings.ASK_SAMPLE_VALUES_MAX_DISTINCT]
            )
            for table, column, _distinct, values in cursor.fetchall():
                samples[(table, column)] = tuple(
                    values[: settings.ASK_SAMPLE_VALUES_MAX]
                )

    comments: dict[str, str | None] = {}
    estimates: dict[str, int | None] = {}
    columns: dict[str, list[Column]] = {}
    for (
        table,
        table_comment,
        name,
        type_,
        not_null,
        comment,
        estimate,
    ) in column_rows:
        comments[table] = table_comment
        estimates[table] = estimate if estimate >= 0 else None
        columns.setdefault(table, []).append(
            Column(
                name=name,
                type=type_,
                nullable=not not_null,
                comment=comment,
                samples=samples.get((table, name), ())
                if type_.split("(")[0] in TEXT_TYPES
                else (),
            )
        )

    primary: dict[str, tuple[str, ...]] = {}
    foreign: dict[str, list[ForeignKey]] = {}
    for table, kind, cols, ref_table, ref_cols in key_rows:
        if table not in columns:
            continue
        if kind == "p":
            primary[table] = tuple(cols)
        elif ref_table in columns:
            foreign.setdefault(table, []).append(
                ForeignKey(tuple(cols), ref_table, tuple(ref_cols))
            )

    return Schema(
        name=schema_name,
        tables=tuple(
            Table(
                name=table,
                comment=comments[table],
                columns=tuple(cols),
                primary_key=primary.get(table, ()),
                foreign_keys=tuple(foreign.get(table, ())),
                row_estimate=estimates[table],
            )
            for table, cols in columns.items()
        ),
    )


def clean_comment(text: str | None) -> str:
    return " ".join(text.split()) if text else ""


def render(schema: Schema, *, qualify: bool = True) -> str:
    """Compact DDL-style text: one CREATE TABLE per table, descriptions as comments.
    `qualify=False` leaves table names bare, for databases without schemas (SQLite)."""
    prefix = f"{schema.name}." if qualify else ""
    blocks = []
    for table in schema.tables:
        lines = []
        if table.comment:
            lines.append(f"-- {clean_comment(table.comment)}")
        lines.append(f"CREATE TABLE {prefix}{table.name} (")
        parts = []
        for column in table.columns:
            note = clean_comment(column.comment)
            if column.samples:
                values = ", ".join(repr(v) for v in column.samples)
                note = f"{note} Values: {values}.".strip()
            line = f"  {column.name} {column.type}"
            if not column.nullable:
                line += " NOT NULL"
            parts.append((line, note))
        constraints = []
        if table.primary_key:
            constraints.append(f"  PRIMARY KEY ({', '.join(table.primary_key)})")
        constraints.extend(
            f"  FOREIGN KEY ({', '.join(fk.columns)}) REFERENCES "
            f"{prefix}{fk.ref_table} ({', '.join(fk.ref_columns)})"
            for fk in table.foreign_keys
        )
        total = len(parts) + len(constraints)
        for index, (line, note) in enumerate(parts, start=1):
            comma = "," if index < total else ""
            lines.append(f"{line}{comma}" + (f" -- {note}" if note else ""))
        for index, line in enumerate(constraints, start=len(parts) + 1):
            lines.append(line + ("," if index < total else ""))
        lines.append(");")
        blocks.append("\n".join(lines))
    return "\n\n".join(blocks)


def cache_key(workspace: WorkspaceRef, include_samples: bool) -> str:
    """Per workspace and per schema version, so a change reads fresh."""
    version = schema_version.current(workspace)
    return (
        f"ask:schema:{workspace.id if workspace.id is not None else 'demo'}"
        f":v{version}:{int(include_samples)}"
    )


def get_schema(
    workspace: WorkspaceRef = DEMO, *, include_samples: bool = False
) -> Schema:
    """The schema from the cache, read from the database on a miss."""
    key = cache_key(workspace, include_samples)
    cached = cache.get(key)
    if cached is not None:
        return cached
    schema = read_schema(workspace, include_samples=include_samples)
    cache.set(key, schema, settings.ASK_SCHEMA_CACHE_SECONDS)
    return schema


def clear_schema_cache(workspace: WorkspaceRef = DEMO) -> None:
    cache.delete_many([cache_key(workspace, flag) for flag in (False, True)])
