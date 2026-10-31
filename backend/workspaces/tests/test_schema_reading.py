"""ask.schema for a user workspace: introspection as ws_<id>_ro, the cache key,
and the isolation of two workspaces that both have a `customer` table."""

from collections.abc import Callable

import pytest
from django.core.cache import cache

from ask import schema
from workspaces import schema_version
from workspaces.context import DEMO, ref_for
from workspaces.tests.conftest import connect

A, B = 990201, 990202


@pytest.fixture
def two(provision: Callable[[int], int]) -> None:
    for workspace_id, columns in (
        (A, "id int, name text"),
        (B, "id int, email text, age int"),
    ):
        provision(workspace_id)
        with connect(workspace_id, "rw") as rw:
            rw.execute(f"CREATE TABLE customer ({columns})")
            rw.execute("COMMENT ON TABLE customer IS 'Who buys things'")
            rw.execute("COMMENT ON COLUMN customer.id IS 'The id'")
            rw.execute("CREATE TABLE orders (id int PRIMARY KEY, customer_id int)")
            rw.execute("ALTER TABLE customer ADD PRIMARY KEY (id)")
            rw.execute(
                "ALTER TABLE orders ADD FOREIGN KEY (customer_id) REFERENCES customer (id)"
            )


def test_each_workspace_sees_only_its_own_tables(two: None) -> None:
    first = schema.read_schema(ref_for(A))
    second = schema.read_schema(ref_for(B))
    assert first.name == f"ws_{A}" and second.name == f"ws_{B}"
    assert {t.name for t in first.tables} == {"customer", "orders"}
    customer_a = first.table("customer")
    customer_b = second.table("customer")
    assert customer_a and customer_b
    assert [c.name for c in customer_a.columns] == ["id", "name"]
    assert [c.name for c in customer_b.columns] == ["id", "email", "age"]
    assert customer_a.comment == "Who buys things"
    assert customer_a.column("id").comment == "The id"  # type: ignore[union-attr]
    orders = first.table("orders")
    assert orders and orders.primary_key == ("id",)
    assert orders.foreign_keys[0].ref_table == "customer"


@pytest.mark.usefixtures("data_connections")
def test_the_demo_is_not_mixed_in(two: None) -> None:
    demo = schema.read_schema(DEMO)
    assert demo.name == "demo" and demo.table("orders") is not None
    assert demo.table("customer") is None


def test_the_cache_key_holds_the_workspace_and_its_version(two: None) -> None:
    key_a = schema.cache_key(ref_for(A), True)
    assert key_a != schema.cache_key(ref_for(B), True)
    assert key_a != schema.cache_key(ref_for(A), False)
    assert schema.cache_key(DEMO, True) == "ask:schema:demo:v0:1"
    schema_version.bump(A)
    assert schema.cache_key(ref_for(A), True) != key_a


def test_a_cached_schema_is_per_workspace(two: None) -> None:
    schema.get_schema(ref_for(A))
    assert cache.get(schema.cache_key(ref_for(A), False)) is not None
    assert cache.get(schema.cache_key(ref_for(B), False)) is None
    other = schema.get_schema(ref_for(B))
    assert other.name == f"ws_{B}"


def test_a_bump_makes_the_next_read_fresh_and_nothing_else_does(
    provision: Callable[[int], int],
) -> None:
    provision(A)
    ref = ref_for(A)
    assert schema.get_schema(ref).tables == ()
    with connect(A, "rw") as rw:
        rw.execute("CREATE TABLE added (id int)")
    assert schema.get_schema(ref).tables == ()  # still the cached one
    schema_version.bump(A)
    assert [t.name for t in schema.get_schema(ref).tables] == ["added"]
    with connect(A, "rw") as rw:
        rw.execute("ALTER TABLE added ADD COLUMN note text")
        rw.execute("COMMENT ON TABLE added IS 'now described'")
    schema_version.bump(A)
    table = schema.get_schema(ref).table("added")
    assert table and [c.name for c in table.columns] == ["id", "note"]
    assert table.comment == "now described"
    schema_version.forget(A)
    assert schema_version.current(ref) == 0
