"""The boundary proof (5.3): connected as a real workspace role, nothing outside
that workspace is reachable, and nothing dangerous is allowed. Two real
workspaces, each with a `customer` table holding different rows. No guard is
involved: this is what the roles themselves allow."""

from collections.abc import Callable, Iterator

import psycopg
import pytest
from django.test import override_settings

from workspaces import credentials
from workspaces.tests.conftest import connect

A, B = 990101, 990102


@pytest.fixture
def two(provision: Callable[[int], int]) -> tuple[int, int]:
    for workspace_id, name in ((A, "alice"), (B, "bob")):
        provision(workspace_id)
        with connect(workspace_id, "rw") as rw:
            rw.execute("CREATE TABLE customer (id int, name text)")
            rw.execute("INSERT INTO customer VALUES (1, %s)", [name])
    return A, B


@pytest.fixture(params=["rw", "ro"])
def conn(
    two: tuple[int, int], request: pytest.FixtureRequest
) -> Iterator[psycopg.Connection]:
    with connect(A, request.param) as connection:
        yield connection


def refused(connection: psycopg.Connection, statement: str) -> None:
    """The statement must fail (any database error) and leave the session usable."""
    with pytest.raises(psycopg.Error):
        connection.execute(statement)
    assert connection.execute("SELECT 1").fetchone() == (1,)


def test_unqualified_names_mean_this_workspace(conn: psycopg.Connection) -> None:
    assert conn.execute("SELECT name FROM customer").fetchall() == [("alice",)]
    assert conn.execute("SELECT current_schema()").fetchone() == (f"ws_{A}",)


@pytest.mark.parametrize(
    "statement",
    [
        f"SELECT * FROM ws_{B}.customer",
        f'SELECT * FROM "ws_{B}"."customer"',
        "SELECT * FROM demo.orders",
        "SELECT * FROM public.anything",
        "SELECT * FROM querylab_app.public.accounts_user",
        f"CREATE TABLE ws_{B}.x (id int)",
        f"INSERT INTO ws_{B}.customer VALUES (9, 'mallory')",
        f"DROP TABLE ws_{B}.customer",
        f"DROP SCHEMA ws_{B} CASCADE",
        f"GRANT USAGE ON SCHEMA ws_{B} TO ws_{A}_rw",
        f"GRANT SELECT ON ALL TABLES IN SCHEMA ws_{B} TO ws_{A}_ro",
        "GRANT USAGE ON SCHEMA demo TO PUBLIC",
        "GRANT USAGE ON SCHEMA public TO PUBLIC",
    ],
)
def test_other_schemas_are_closed(conn: psycopg.Connection, statement: str) -> None:
    refused(conn, statement)


def test_the_other_workspaces_rows_never_show(conn: psycopg.Connection) -> None:
    rows = conn.execute("SELECT name FROM customer").fetchall()
    assert ("bob",) not in rows


@pytest.mark.parametrize(
    "statement",
    [
        f"SET ROLE ws_{B}_rw",
        f"SET ROLE ws_{B}_ro",
        "SET ROLE querylab",
        "SET ROLE querylab_reader",
        f"SET SESSION AUTHORIZATION ws_{B}_rw",
        "SET SESSION AUTHORIZATION querylab",
    ],
)
def test_there_is_no_way_to_become_another_role(
    conn: psycopg.Connection, statement: str
) -> None:
    refused(conn, statement)


def test_reset_role_and_search_path_give_no_access(conn: psycopg.Connection) -> None:
    conn.execute("RESET ROLE")
    assert conn.execute("SELECT current_user").fetchone()[0].startswith(f"ws_{A}_")  # type: ignore[index]
    conn.execute(f"SET search_path = ws_{B}")
    with pytest.raises(psycopg.errors.Error):
        conn.execute("SELECT * FROM customer")
    conn.execute("RESET search_path")
    assert conn.execute("SELECT name FROM customer").fetchall() == [("alice",)]


def test_the_ro_role_cannot_write_or_change_anything(two: tuple[int, int]) -> None:
    with connect(A, "ro") as ro:
        for statement in [
            "INSERT INTO customer VALUES (2, 'x')",
            "UPDATE customer SET name = 'x'",
            "DELETE FROM customer",
            "TRUNCATE customer",
            "CREATE TABLE t (id int)",
            "DROP TABLE customer",
            "ALTER TABLE customer ADD COLUMN x int",
            "CREATE VIEW v AS SELECT 1",
            "CREATE INDEX i ON customer (id)",
        ]:
            refused(ro, statement)
        # even after asking for a read-write transaction, the privileges say no
        ro.execute("SET default_transaction_read_only = off")
        with pytest.raises(psycopg.errors.InsufficientPrivilege):
            ro.execute("INSERT INTO customer VALUES (2, 'x')")
        with pytest.raises(psycopg.errors.InsufficientPrivilege):
            ro.execute("CREATE TABLE t (id int)")


@pytest.mark.parametrize(
    "statement",
    [
        "CREATE EXTENSION dblink",
        "CREATE EXTENSION file_fdw",
        "COPY customer TO PROGRAM 'id'",
        "COPY customer FROM PROGRAM 'id'",
        "COPY customer TO '/tmp/leak.csv'",
        "COPY customer FROM '/etc/passwd'",
        "CREATE FUNCTION f() RETURNS int AS '/lib/x.so', 'f' LANGUAGE C",
        "CREATE FUNCTION f() RETURNS int AS 'import os' LANGUAGE plpython3u",
        "SELECT lo_import('/etc/passwd')",
        "SELECT lo_export(1, '/tmp/x')",
        "ALTER SYSTEM SET work_mem = '1GB'",
        "CREATE ROLE evil LOGIN",
        "ALTER ROLE querylab SUPERUSER",
        f"ALTER ROLE ws_{A}_rw SUPERUSER",
        f"ALTER ROLE ws_{A}_rw CREATEROLE",
        f"ALTER ROLE ws_{A}_rw CONNECTION LIMIT -1",
        "CREATE DATABASE evil",
        "CREATE SCHEMA evil",
        "SELECT pg_read_file('/etc/passwd')",
        "SELECT pg_read_binary_file('/etc/passwd')",
        "SELECT pg_ls_dir('/')",
        "SELECT pg_stat_file('/etc/passwd')",
        "SELECT pg_reload_conf()",
        "SELECT pg_switch_wal()",
        "SELECT dblink('host=postgres', 'select 1')",
        "CREATE TEMP TABLE t (id int)",
        "CREATE TEMPORARY TABLE t AS SELECT 1",
        "CREATE PUBLICATION p FOR ALL TABLES",
        "CREATE SERVER s FOREIGN DATA WRAPPER postgres_fdw",
        "CREATE EVENT TRIGGER e ON ddl_command_start EXECUTE FUNCTION f()",
        "LOAD 'auto_explain'",
        "SET session_replication_role = replica",
        "SELECT set_config('log_statement', 'all', false)",
    ],
)
def test_dangerous_features_fail_for_both_roles(
    conn: psycopg.Connection, statement: str
) -> None:
    refused(conn, statement)


def test_another_roles_session_cannot_be_terminated(
    conn: psycopg.Connection, owner: psycopg.Connection
) -> None:
    pid = owner.execute("SELECT pg_backend_pid()").fetchone()[0]  # type: ignore[index]
    with pytest.raises(psycopg.errors.InsufficientPrivilege):
        conn.execute("SELECT pg_terminate_backend(%s)", [pid])
    assert owner.execute("SELECT 1").fetchone() == (1,)


def test_the_owners_membership_is_the_only_one(
    two: tuple[int, int], owner: psycopg.Connection
) -> None:
    rows = owner.execute(
        "SELECT g.rolname, r.rolname FROM pg_auth_members m"
        " JOIN pg_roles r ON r.oid = m.roleid JOIN pg_roles g ON g.oid = m.member"
        " WHERE r.rolname LIKE 'ws\\_%' ESCAPE '\\'"
    ).fetchall()
    # a superuser owner needs no membership; anything here must be the owner
    assert {member for member, _ in rows} <= {"querylab"}
    ws_members = owner.execute(
        "SELECT count(*) FROM pg_auth_members m JOIN pg_roles g ON g.oid = m.member"
        " WHERE g.rolname LIKE 'ws\\_%' ESCAPE '\\'"
    ).fetchone()
    assert ws_members == (0,)


def test_a_security_definer_function_runs_with_the_users_own_rights(
    two: tuple[int, int],
) -> None:
    with connect(A, "rw") as rw:
        rw.execute(
            "CREATE FUNCTION peek() RETURNS text LANGUAGE plpgsql SECURITY DEFINER AS"
            f" $$ BEGIN RETURN (SELECT name FROM ws_{B}.customer LIMIT 1); END $$"
        )
        with pytest.raises(psycopg.errors.InsufficientPrivilege):
            rw.execute("SELECT peek()")
        rw.execute(
            "CREATE FUNCTION whoami() RETURNS text LANGUAGE sql SECURITY DEFINER AS"
            " $$ SELECT current_user::text $$"
        )
        assert rw.execute("SELECT whoami()").fetchone() == (
            credentials.role_name(A, "rw"),
        )


def test_the_rw_role_cannot_connect_to_the_platform_database(
    two: tuple[int, int],
) -> None:
    from django.conf import settings
    from psycopg.conninfo import make_conninfo

    db = settings.DATABASES["default"]
    # The real platform database: during a run with the db fixture, NAME is the
    # throwaway test copy, which Django creates open to PUBLIC.
    platform = "querylab_app"
    with pytest.raises(psycopg.OperationalError, match="permission denied"):
        psycopg.connect(
            make_conninfo(
                host=db["HOST"],
                port=db["PORT"],
                dbname=platform,
                user=credentials.role_name(A, "rw"),
                password=credentials.role_password(A, "rw", 1),
            )
        )


def test_the_default_statement_timeout_cancels_a_runaway_query(
    provision: Callable[[int], int],
) -> None:
    with override_settings(
        WORKSPACE_STATEMENT_TIMEOUT_MS=300, READER_STATEMENT_TIMEOUT_MS=300
    ):
        provision(A)
    for kind in ("rw", "ro"):
        with connect(A, kind) as connection:
            with pytest.raises(psycopg.errors.QueryCanceled):
                connection.execute("SELECT pg_sleep(5)")
            with pytest.raises(psycopg.errors.QueryCanceled):
                connection.execute(
                    "SELECT count(*) FROM generate_series(1, 100000000) a, generate_series(1, 100000) b"
                )


def test_a_session_can_raise_its_own_timeout_so_callers_need_a_watchdog(
    provision: Callable[[int], int],
) -> None:
    """Documents the limit of the role default: statement_timeout is a user-level
    setting, so the SQL console and imports also enforce a deadline from outside
    (a cancel from the application), see workspaces/sql.py."""
    with override_settings(WORKSPACE_STATEMENT_TIMEOUT_MS=300):
        provision(A)
    with connect(A, "rw") as rw:
        rw.execute("SET statement_timeout = 0")
        rw.execute("SELECT pg_sleep(0.6)")
