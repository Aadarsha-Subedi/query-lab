"""What a workspace holds: table count and bytes (tables, indexes, TOAST), read
from the catalog on the owner connection. Catalog metadata only; no user rows."""

from dataclasses import dataclass

from workspaces import connections

STATS_SQL = """
SELECT n.nspname,
       count(c.oid) FILTER (WHERE c.relkind IN ('r', 'p')),
       COALESCE(sum(pg_total_relation_size(c.oid))
                FILTER (WHERE c.relkind IN ('r', 'p', 'm')), 0)::bigint
FROM pg_namespace n
LEFT JOIN pg_class c ON c.relnamespace = n.oid
WHERE n.nspname = ANY(%s)
GROUP BY n.nspname
"""


@dataclass(frozen=True)
class Usage:
    tables: int
    bytes: int


def schema_usage(schema_names: list[str]) -> dict[str, Usage]:
    """Usage per schema; a schema that does not exist reads as empty."""
    found: dict[str, Usage] = {}
    if schema_names:
        with connections.owner_connection() as connection:
            for name, tables, size in connection.execute(
                STATS_SQL, [schema_names]
            ).fetchall():
                found[name] = Usage(tables=tables, bytes=size)
    return {name: found.get(name, Usage(0, 0)) for name in schema_names}
