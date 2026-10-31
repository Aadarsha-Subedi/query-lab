"""The guard for a user workspace: the only schema qualifier allowed is the
workspace's own. This is the second line; the `ws_<id>_ro` role is the real wall."""

import pytest

from ask import guard
from ask.errors import GuardRejected
from ask.schema import Column, Schema, Table

SCHEMA = Schema(
    name="ws_5",
    tables=(
        Table(
            "customer",
            None,
            (Column("id", "integer", False), Column("name", "text", True)),
        ),
    ),
)

GOOD = [
    "SELECT name FROM customer",
    "SELECT name FROM ws_5.customer",
    'SELECT name FROM "ws_5"."customer"',
    "SELECT c.name FROM customer c JOIN ws_5.customer d ON d.id = c.id",
    "WITH x AS (SELECT * FROM customer) SELECT * FROM x",
]

BAD = [
    "SELECT * FROM ws_6.customer",
    'SELECT * FROM "WS_5".customer',
    'SELECT * FROM "ws_5 ".customer',
    "SELECT * FROM WS_6.customer",
    "SELECT * FROM demo.orders",
    "SELECT * FROM public.customer",
    "SELECT * FROM pg_catalog.pg_class",
    "SELECT * FROM pg_class",
    "SELECT * FROM information_schema.tables",
    "SELECT * FROM information_schema.columns WHERE table_schema = 'ws_6'",
    "SELECT * FROM pg_catalog.pg_namespace",
    "SELECT * FROM querylab.ws_5.customer",
    "SELECT * FROM customer, ws_6.customer",
    "SELECT (SELECT count(*) FROM ws_6.customer)",
    "SELECT * FROM customer WHERE id IN (SELECT id FROM ws_6.customer)",
    "SET ROLE ws_6_ro",
    "SET search_path = ws_6",
    "SET LOCAL statement_timeout = 0",
    "RESET ROLE",
    "RESET ALL",
    "SET SESSION AUTHORIZATION postgres",
    "SELECT 1; SET ROLE ws_6_ro",
    "SELECT set_config('search_path', 'ws_6', false)",
    "SELECT * FROM customer; DROP TABLE customer",
    "SHOW search_path",
]


@pytest.mark.parametrize("sql", GOOD)
def test_the_workspace_own_tables_pass(sql: str) -> None:
    result = guard.check(sql, SCHEMA)
    assert "ws_5.customer" in result.sql or "customer" in result.sql


@pytest.mark.parametrize("sql", BAD)
def test_everything_else_is_refused(sql: str) -> None:
    with pytest.raises(GuardRejected):
        guard.check(sql, SCHEMA)


def test_unqualified_names_get_this_workspaces_schema() -> None:
    assert "ws_5.customer" in guard.check("SELECT name FROM customer", SCHEMA).sql


def test_the_refusal_names_no_other_workspace_data() -> None:
    with pytest.raises(GuardRejected) as caught:
        guard.check("SELECT * FROM ws_6.customer", SCHEMA)
    assert "not available" in caught.value.detail
