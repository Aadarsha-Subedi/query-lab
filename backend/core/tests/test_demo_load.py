"""load_demo on the small fixture CSVs, in a throwaway schema so the real demo
data is never touched."""

import uuid
from collections.abc import Iterator
from datetime import datetime, timedelta
from pathlib import Path

import psycopg
import pytest
from django.conf import settings
from django.core.management import call_command
from psycopg import sql

from core import datadb, demo

FIXTURES = Path(__file__).parent / "fixtures" / "olist"
SHIFT_DAYS = 2922

# (child table, column, parent table, column) for every foreign key.
FOREIGN_KEYS = [
    ("orders", "customer_id", "customers", "customer_id"),
    ("order_items", "order_id", "orders", "order_id"),
    ("order_items", "product_id", "products", "product_id"),
    ("order_items", "seller_id", "sellers", "seller_id"),
    ("order_payments", "order_id", "orders", "order_id"),
    ("order_reviews", "order_id", "orders", "order_id"),
]


@pytest.fixture
def schema(owner: psycopg.Connection, data_connections: None) -> Iterator[str]:
    name = f"test_demo_{uuid.uuid4().hex[:8]}"
    owner.execute(sql.SQL("CREATE SCHEMA {}").format(sql.Identifier(name)))
    owner.execute(
        datadb.render(
            Path(settings.DATA_SQL_DIR) / "010_demo_schema.sql",
            {"schema": sql.Identifier(name)},
        )
    )
    yield name
    owner.execute(sql.SQL("DROP SCHEMA {} CASCADE").format(sql.Identifier(name)))


def count(owner: psycopg.Connection, query: sql.Composed) -> int:
    row = owner.execute(query).fetchone()
    assert row is not None
    return int(row[0])


def test_row_counts_match_the_csvs(schema: str, owner: psycopg.Connection) -> None:
    counts = demo.load(FIXTURES, SHIFT_DAYS, schema=schema)
    for table in demo.TABLES:
        expected = demo.csv_row_count(FIXTURES / table.csv_file)
        assert counts[table.name] == expected, table.name
        assert (
            count(
                owner,
                sql.SQL("SELECT count(*) FROM {}").format(
                    sql.Identifier(schema, table.name)
                ),
            )
            == expected
        )


def test_no_orphaned_foreign_keys(schema: str, owner: psycopg.Connection) -> None:
    demo.load(FIXTURES, SHIFT_DAYS, schema=schema)
    for child, child_col, parent, parent_col in FOREIGN_KEYS:
        orphans = count(
            owner,
            sql.SQL(
                "SELECT count(*) FROM {child} c LEFT JOIN {parent} p"
                " ON p.{pcol} = c.{ccol} WHERE p.{pcol} IS NULL"
            ).format(
                child=sql.Identifier(schema, child),
                parent=sql.Identifier(schema, parent),
                pcol=sql.Identifier(parent_col),
                ccol=sql.Identifier(child_col),
            ),
        )
        assert orphans == 0, f"{child}.{child_col}"


def test_categories_are_translated(schema: str, owner: psycopg.Connection) -> None:
    demo.load(FIXTURES, SHIFT_DAYS, schema=schema)
    rows: dict[str, str | None] = dict(
        owner.execute(
            sql.SQL("SELECT product_id, product_category_name FROM {}").format(
                sql.Identifier(schema, "products")
            )
        ).fetchall()
    )
    assert rows["p1"] == "perfumery"
    assert rows["p2"] == "health_beauty"
    assert rows["p3"] == "pc_gamer"  # no translation: Portuguese name kept
    assert rows["p4"] is None


def test_dates_are_shifted(schema: str, owner: psycopg.Connection) -> None:
    demo.load(FIXTURES, SHIFT_DAYS, schema=schema)
    row = owner.execute(
        sql.SQL(
            "SELECT order_purchase_timestamp, order_delivered_customer_date FROM {}"
            " WHERE order_id = 'o2'"
        ).format(sql.Identifier(schema, "orders"))
    ).fetchone()
    assert row is not None
    assert row[0] == datetime(2018, 10, 17, 17, 30, 18) + timedelta(days=SHIFT_DAYS)
    assert row[1] is None  # empty stays NULL


def test_reload_replaces_the_data(schema: str, owner: psycopg.Connection) -> None:
    demo.load(FIXTURES, SHIFT_DAYS, schema=schema)
    counts = demo.load(FIXTURES, SHIFT_DAYS, schema=schema)
    assert counts["geolocation"] == demo.csv_row_count(
        FIXTURES / "olist_geolocation_dataset.csv"
    )


def test_missing_csv_is_reported(tmp_path: Path, data_connections: None) -> None:
    with pytest.raises(FileNotFoundError, match=r"olist_orders_dataset\.csv"):
        demo.load(tmp_path, SHIFT_DAYS, schema="unused")


def test_command_reports_counts(
    schema: str, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    original = demo.load
    monkeypatch.setattr(
        demo,
        "load",
        lambda source, shift: original(source, shift, schema=schema),
    )
    call_command("load_demo", "--source", str(FIXTURES))
    assert "orders: 3 rows" in capsys.readouterr().out
