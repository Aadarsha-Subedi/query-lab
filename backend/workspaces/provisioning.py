"""Creating and dropping a workspace's schema and roles, as the platform owner.

The owner role is used for workspaces here and nowhere else: imports, the SQL
console and the row and table APIs connect as the workspace's own `_rw` role.
Everything here is one transaction on the owner connection, built
with `psycopg.sql`: identifiers through `Identifier`, passwords and numbers
through `Literal`; the schema and role names come from the workspace id.

Per workspace:

    ws_<id>      the schema, owned by ws_<id>_rw
    ws_<id>_rw   LOGIN, the user's own SQL, imports and row/table APIs (primary)
    ws_<id>_ro   LOGIN, SELECT on the schema only, read-only (the agent; replica)

Both roles are members of nothing, are not inheriting, are not super users and
may not create databases, roles or temp tables. Their `search_path` is the one
schema. The owner role stays the only member of either role (and only when it is
not a superuser, because it then needs the membership to administer them).
"""

import psycopg
from django.conf import settings
from psycopg import sql

from workspaces import credentials
from workspaces.context import schema_name_for

ROLE_ATTRIBUTES = sql.SQL(
    "NOSUPERUSER NOCREATEDB NOCREATEROLE NOINHERIT NOREPLICATION NOBYPASSRLS LOGIN"
)


def _ids(workspace_id: int) -> tuple[sql.Identifier, sql.Identifier, sql.Identifier]:
    return (
        sql.Identifier(schema_name_for(workspace_id)),
        sql.Identifier(credentials.role_name(workspace_id, "rw")),
        sql.Identifier(credentials.role_name(workspace_id, "ro")),
    )


def _role_exists(connection: psycopg.Connection, name: str) -> bool:
    row = connection.execute(
        "SELECT 1 FROM pg_roles WHERE rolname = %s", [name]
    ).fetchone()
    return row is not None


def _is_superuser(connection: psycopg.Connection) -> bool:
    row = connection.execute(
        "SELECT rolsuper FROM pg_roles WHERE rolname = current_user"
    ).fetchone()
    return bool(row and row[0])


def _upsert_role(
    connection: psycopg.Connection,
    name: str,
    role: sql.Identifier,
    password: str,
    limit: int,
) -> None:
    verb = "ALTER" if _role_exists(connection, name) else "CREATE"
    connection.execute(
        sql.SQL(
            "{verb} ROLE {role} {attributes} PASSWORD {password} CONNECTION LIMIT {limit}"
        ).format(
            verb=sql.SQL(verb),
            role=role,
            attributes=ROLE_ATTRIBUTES,
            password=sql.Literal(password),
            limit=sql.Literal(limit),
        )
    )


def _set_defaults(
    connection: psycopg.Connection,
    role: sql.Identifier,
    schema: sql.Identifier,
    *,
    statement_timeout_ms: int,
    read_only: bool,
) -> None:
    for name, value in (
        ("statement_timeout", sql.Literal(str(statement_timeout_ms))),
        (
            "idle_in_transaction_session_timeout",
            sql.Literal(str(settings.WORKSPACE_IDLE_TX_TIMEOUT_MS)),
        ),
        ("search_path", schema),
        ("default_transaction_read_only", sql.Literal("on" if read_only else "off")),
    ):
        connection.execute(
            sql.SQL("ALTER ROLE {role} SET {name} = {value}").format(
                role=role, name=sql.Identifier(name), value=value
            )
        )


def create_workspace_schema(
    connection: psycopg.Connection, workspace_id: int, version: int = 1
) -> None:
    """Create (or repair) the schema and both roles. Idempotent. The caller owns
    the transaction: commit on success, roll back on any error."""
    schema, rw, ro = _ids(workspace_id)
    rw_name = credentials.role_name(workspace_id, "rw")
    ro_name = credentials.role_name(workspace_id, "ro")
    database = sql.Identifier(connection.info.dbname)

    _upsert_role(
        connection,
        rw_name,
        rw,
        credentials.role_password(workspace_id, "rw", version),
        settings.WORKSPACE_RW_CONNECTION_LIMIT,
    )
    _upsert_role(
        connection,
        ro_name,
        ro,
        credentials.role_password(workspace_id, "ro", version),
        settings.WORKSPACE_RO_CONNECTION_LIMIT,
    )
    if not _is_superuser(connection):
        # A role without SUPERUSER (Neon's project owner) can only administer a
        # role it is a member of. The owner is the only member of either role.
        for role in (rw, ro):
            connection.execute(
                sql.SQL(
                    "GRANT {role} TO CURRENT_USER WITH INHERIT TRUE, SET TRUE"
                ).format(role=role)
            )
    _set_defaults(
        connection,
        rw,
        schema,
        statement_timeout_ms=settings.WORKSPACE_STATEMENT_TIMEOUT_MS,
        read_only=False,
    )
    _set_defaults(
        connection,
        ro,
        schema,
        statement_timeout_ms=settings.READER_STATEMENT_TIMEOUT_MS,
        read_only=True,
    )

    statements = [
        "GRANT CONNECT ON DATABASE {database} TO {rw}, {ro}",
        "REVOKE TEMPORARY, CREATE ON DATABASE {database} FROM {rw}, {ro}",
        "CREATE SCHEMA IF NOT EXISTS {schema} AUTHORIZATION {rw}",
        "ALTER SCHEMA {schema} OWNER TO {rw}",
        "REVOKE ALL ON SCHEMA {schema} FROM PUBLIC",
        "GRANT USAGE ON SCHEMA {schema} TO {ro}",
        "GRANT SELECT ON ALL TABLES IN SCHEMA {schema} TO {ro}",
        "ALTER DEFAULT PRIVILEGES FOR ROLE {rw} IN SCHEMA {schema} "
        "GRANT SELECT ON TABLES TO {ro}",
    ]
    for statement in statements:
        connection.execute(
            sql.SQL(statement).format(database=database, schema=schema, rw=rw, ro=ro)
        )


def drop_workspace_schema(connection: psycopg.Connection, workspace_id: int) -> None:
    """Drop the schema, both roles and every grant. Idempotent: a workspace that
    was only half created drops cleanly. Open sessions of either role are ended
    first, so the roles can go."""
    schema, rw, ro = _ids(workspace_id)
    names = [
        credentials.role_name(workspace_id, "rw"),
        credentials.role_name(workspace_id, "ro"),
    ]
    connection.execute(
        "SELECT pg_terminate_backend(pid) FROM pg_stat_activity "
        "WHERE usename = ANY(%s) AND pid <> pg_backend_pid()",
        [names],
    )
    connection.execute(
        sql.SQL("DROP SCHEMA IF EXISTS {schema} CASCADE").format(schema=schema)
    )
    for name, role in ((names[1], ro), (names[0], rw)):
        if _role_exists(connection, name):
            connection.execute(sql.SQL("DROP OWNED BY {role}").format(role=role))
            connection.execute(sql.SQL("DROP ROLE {role}").format(role=role))
