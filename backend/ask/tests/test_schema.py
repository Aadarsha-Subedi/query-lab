"""The schema reader against the real demo schema, as the reader role."""

import pytest
from django.conf import settings
from django.core.cache import cache
from django.db import connections

from ask import schema as ask_schema
from workspaces.context import DEMO

pytestmark = pytest.mark.usefixtures("data_connections")

OLIST_TABLES = {
    "customers",
    "geolocation",
    "order_items",
    "order_payments",
    "order_reviews",
    "orders",
    "product_category_translation",
    "products",
    "sellers",
}


@pytest.fixture(autouse=True)
def _analyzed(owner) -> None:
    owner.execute("ANALYZE")


def test_reads_every_demo_table_with_comments_and_keys() -> None:
    schema = ask_schema.read_schema()
    assert {t.name for t in schema.tables} == OLIST_TABLES
    orders = schema.table("orders")
    assert orders is not None
    assert orders.comment
    assert orders.primary_key == ("order_id",)
    assert any(
        fk.ref_table == "customers" and fk.columns == ("customer_id",)
        for fk in orders.foreign_keys
    )
    status = orders.column("order_status")
    assert status is not None and status.comment


def test_samples_only_when_asked() -> None:
    plain = ask_schema.read_schema().table("orders")
    sampled = ask_schema.read_schema(include_samples=True).table("orders")
    assert plain is not None and sampled is not None
    assert plain.column("order_status").samples == ()  # type: ignore[union-attr]
    values = sampled.column("order_status").samples  # type: ignore[union-attr]
    assert "delivered" in values
    assert len(values) <= settings.ASK_SAMPLE_VALUES_MAX
    # An identifier column is high-cardinality: never sampled.
    assert sampled.column("order_id").samples == ()  # type: ignore[union-attr]


def test_render_is_ddl_with_comments_and_is_stable() -> None:
    schema = ask_schema.read_schema(include_samples=True)
    text = ask_schema.render(schema)
    assert "CREATE TABLE demo.orders (" in text
    assert "PRIMARY KEY (order_id)" in text
    assert "REFERENCES demo.customers (customer_id)" in text
    assert "Values: 'delivered'" in text
    assert text == ask_schema.render(schema)


def test_get_schema_uses_the_cache() -> None:
    cache.clear()
    ask_schema.get_schema()
    connection = connections[settings.DATA_READER_DB_ALIAS]
    queries: list[str] = []

    def record(execute, sql, params, many, context):
        queries.append(sql)
        return execute(sql, params, many, context)

    with connection.execute_wrapper(record):
        ask_schema.get_schema()
    assert queries == []
    ask_schema.clear_schema_cache()
    assert cache.get(ask_schema.cache_key(DEMO, False)) is None
