"""Workspace roles have no access to demo, public or the platform database
(5.3.3); the Olist demo is queried only as the reader role."""

from collections.abc import Callable

import psycopg
import pytest

from workspaces.tests.conftest import connect

A = 990121


@pytest.fixture(params=["rw", "ro"])
def conn(
    provision: Callable[[int], int], request: pytest.FixtureRequest
) -> psycopg.Connection:
    provision(A)
    return connect(A, request.param)


@pytest.mark.parametrize(
    "statement",
    [
        "SELECT * FROM demo.orders",
        "SELECT count(*) FROM demo.customers",
        "ALTER TABLE demo.orders ADD COLUMN x int",
        "DROP TABLE demo.orders",
        "DELETE FROM demo.orders",
        "CREATE TABLE demo.x (id int)",
        "CREATE TABLE public.x (id int)",
        "SELECT * FROM public.x",
        "GRANT SELECT ON demo.orders TO CURRENT_USER",
        "GRANT USAGE ON SCHEMA demo TO CURRENT_USER",
        "ALTER SCHEMA demo OWNER TO CURRENT_USER",
    ],
)
def test_demo_and_public_are_closed(conn: psycopg.Connection, statement: str) -> None:
    with pytest.raises(psycopg.Error):
        conn.execute(statement)


def test_public_holds_no_privilege_on_the_shared_schemas(
    owner: psycopg.Connection,
) -> None:
    for schema in ("demo", "public"):
        row = owner.execute(
            "SELECT has_schema_privilege('public', %s, 'USAGE'),"
            " has_schema_privilege('public', %s, 'CREATE')",
            [schema, schema],
        ).fetchone()
        assert row == (False, False), schema
    assert owner.execute(
        "SELECT has_table_privilege('public', 'demo.orders', 'SELECT')"
    ).fetchone() == (False,)
    assert owner.execute(
        "SELECT has_database_privilege('public', 'querylab', 'CONNECT'),"
        " has_database_privilege('public', 'querylab_app', 'CONNECT'),"
        " has_database_privilege('public', 'querylab', 'TEMPORARY')"
    ).fetchone() == (False, False, False)


def test_the_reader_still_reads_the_demo(reader: psycopg.Connection) -> None:
    assert reader.execute("SELECT count(*) FROM demo.orders").fetchone() is not None
