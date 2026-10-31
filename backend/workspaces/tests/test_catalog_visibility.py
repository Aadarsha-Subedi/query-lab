"""What a workspace role can learn about other workspaces from the catalogs
(5.3.2). Postgres lets every role read pg_catalog, so NAMES leak; data does not.
These tests pin the current facts so a change shows up; DECISION.md says why
the names are accepted."""

from collections.abc import Callable

import psycopg
import pytest

from workspaces.tests.conftest import connect

A, B = 990111, 990112


@pytest.fixture
def two(provision: Callable[[int], int]) -> None:
    for workspace_id in (A, B):
        provision(workspace_id)
    with connect(B, "rw") as rw:
        rw.execute("CREATE TABLE secret_plans (launch_date date, codename text)")
        rw.execute("INSERT INTO secret_plans VALUES ('2030-01-01', 'falcon')")
        rw.execute("COMMENT ON TABLE secret_plans IS 'confidential'")


@pytest.fixture(params=["rw", "ro"])
def seen(two: None, request: pytest.FixtureRequest) -> psycopg.Connection:
    return connect(A, request.param)


def test_information_schema_shows_only_what_the_role_may_use(
    seen: psycopg.Connection,
) -> None:
    tables = seen.execute(
        "SELECT table_schema, table_name FROM information_schema.tables"
        " WHERE table_schema NOT IN ('pg_catalog', 'information_schema')"
    ).fetchall()
    assert tables == []  # nothing of B's, nothing of the demo
    columns = seen.execute(
        "SELECT count(*) FROM information_schema.columns WHERE table_schema = %s",
        [f"ws_{B}"],
    ).fetchone()
    assert columns == (0,)


def test_the_stats_of_other_tables_are_hidden(seen: psycopg.Connection) -> None:
    assert seen.execute(
        "SELECT count(*) FROM pg_stats WHERE schemaname = %s", [f"ws_{B}"]
    ).fetchone() == (0,)
    with pytest.raises(psycopg.errors.InsufficientPrivilege):
        seen.execute("SELECT * FROM pg_statistic")


def test_other_sessions_and_their_queries_are_hidden(
    seen: psycopg.Connection, owner: psycopg.Connection
) -> None:
    rows = seen.execute(
        "SELECT query FROM pg_stat_activity WHERE pid <> pg_backend_pid()"
        " AND query <> ''"
    ).fetchall()
    assert all(query == "<insufficient privilege>" for (query,) in rows)


def test_roles_hashes_are_unreadable(seen: psycopg.Connection) -> None:
    with pytest.raises(psycopg.errors.InsufficientPrivilege):
        seen.execute("SELECT rolpassword FROM pg_authid")
    values = {r[0] for r in seen.execute("SELECT rolpassword FROM pg_roles")}
    assert values <= {"********", None}  # pg_roles masks it


def test_what_remains_visible_is_names_and_comments(seen: psycopg.Connection) -> None:
    schemas = {r[0] for r in seen.execute("SELECT nspname FROM pg_namespace")}
    assert f"ws_{B}" in schemas  # schema and role names: visible
    tables = seen.execute(
        "SELECT relname FROM pg_class c JOIN pg_namespace n ON n.oid = c.relnamespace"
        " WHERE n.nspname = %s AND c.relkind = 'r'",
        [f"ws_{B}"],
    ).fetchall()
    assert tables == [("secret_plans",)]  # table names: visible
    columns = seen.execute(
        "SELECT attname FROM pg_attribute a JOIN pg_class c ON c.oid = a.attrelid"
        " JOIN pg_namespace n ON n.oid = c.relnamespace"
        " WHERE n.nspname = %s AND c.relname = 'secret_plans' AND a.attnum > 0",
        [f"ws_{B}"],
    ).fetchall()
    assert columns == [("launch_date",), ("codename",)]  # column names: visible
    comment = seen.execute(
        "SELECT obj_description(c.oid, 'pg_class') FROM pg_class c"
        " JOIN pg_namespace n ON n.oid = c.relnamespace"
        " WHERE n.nspname = %s AND c.relname = 'secret_plans'",
        [f"ws_{B}"],
    ).fetchone()
    assert comment == ("confidential",)  # descriptions: visible (see DECISION.md)
    # ...but never a single row
    with pytest.raises(psycopg.errors.InsufficientPrivilege):
        seen.execute(f"SELECT * FROM ws_{B}.secret_plans")
