"""The guard, with no database: valid queries pass (and come back normalised),
and every kind of hostile or wrong query is refused."""

import pytest
from django.test import override_settings

from ask import guard
from ask.errors import GuardRejected
from ask.schema import Schema

GOOD = [
    "SELECT count(*) FROM demo.orders",
    "SELECT count(*) FROM orders",
    "SELECT order_status, count(*) AS n FROM demo.orders GROUP BY order_status ORDER BY n DESC",
    "SELECT o.order_id, c.customer_city FROM demo.orders o JOIN demo.customers c ON c.customer_id = o.customer_id",
    "SELECT customer_state, count(*) FROM demo.customers GROUP BY 1 HAVING count(*) > 10",
    "WITH big AS (SELECT order_id, sum(price) AS total FROM demo.order_items GROUP BY order_id) SELECT * FROM big WHERE total > 100",
    "SELECT date_trunc('month', order_purchase_timestamp) AS m, count(*) FROM demo.orders GROUP BY m ORDER BY m",
    "SELECT order_id, row_number() OVER (PARTITION BY customer_id ORDER BY order_purchase_timestamp) FROM demo.orders",
    "SELECT order_id FROM demo.orders UNION SELECT order_id FROM demo.order_items",
    "SELECT order_id FROM demo.orders WHERE order_id IN (SELECT order_id FROM demo.order_items)",
    "SELECT * FROM demo.customers LIMIT 5",
    "SELECT avg(price)::numeric(10,2) FROM demo.order_items",
    "SELECT EXTRACT(year FROM order_purchase_timestamp) AS y FROM demo.orders GROUP BY y",
    "SELECT count(*) FROM generate_series(1, 5)",
    "SELECT 1 -- trailing comment",
]

BAD = [
    ("", "empty"),
    ("   ", "empty"),
    ("SELEC nonsense (", "syntax"),
    ("SELECT 1; DROP TABLE demo.orders", "stacked statement"),
    ("SELECT 1; SELECT 2", "two statements"),
    ("INSERT INTO demo.orders (order_id) VALUES ('x')", "insert"),
    ("UPDATE demo.orders SET order_status = 'x'", "update"),
    ("DELETE FROM demo.orders", "delete"),
    ("DROP TABLE demo.orders", "drop"),
    ("CREATE TABLE demo.x (a int)", "create"),
    ("ALTER TABLE demo.orders ADD COLUMN x int", "alter"),
    ("TRUNCATE demo.orders", "truncate"),
    ("COPY demo.orders TO '/tmp/x'", "copy"),
    ("SET statement_timeout = 0", "set"),
    ("CALL do_something()", "call"),
    ("EXPLAIN ANALYZE SELECT 1", "explain analyze"),
    ("BEGIN", "transaction"),
    ("GRANT ALL ON demo.orders TO public", "grant"),
    ("SELECT * INTO demo.copy FROM demo.orders", "select into"),
    ("WITH d AS (DELETE FROM demo.orders RETURNING *) SELECT * FROM d", "writing CTE"),
    ("SELECT * FROM demo.orders FOR UPDATE", "row lock"),
    ("SELECT * FROM pg_catalog.pg_user", "catalog"),
    ("SELECT * FROM pg_user", "catalog unqualified"),
    ("SELECT * FROM information_schema.tables", "information schema"),
    ("SELECT * FROM public.users", "other schema"),
    ("SELECT * FROM querylab_app.public.users", "other database"),
    ("SELECT * FROM demo.nothing", "unknown table"),
    ("SELECT nope FROM demo.orders", "unknown column"),
    ("SELECT o.nope FROM demo.orders o", "unknown qualified column"),
    ("SELECT pg_sleep(10)", "sleep"),
    ("SELECT PG_SLEEP(10)", "sleep upper case"),
    ("SELECT pg_catalog.pg_sleep(10)", "sleep qualified"),
    ("SELECT * FROM demo.orders WHERE pg_sleep(1) IS NULL", "sleep in where"),
    ("SELECT pg_read_file('/etc/passwd')", "read file"),
    ("SELECT * FROM pg_ls_dir('/')", "ls dir in FROM"),
    ("SELECT set_config('statement_timeout', '0', false)", "set_config"),
    ("SELECT current_setting('server_version')", "current_setting"),
    ("SELECT dblink('host=x', 'select 1')", "dblink"),
    ("SELECT nextval('demo.seq')", "nextval"),
    ("SELECT lo_import('/etc/passwd')", "large object"),
    ('SELECT * FROM "Demo"."Orders"', "quoted case-sensitive names"),
    ("SELECT * FROM d\u0435mo.orders", "unicode lookalike schema"),
]


@pytest.mark.parametrize("sql", GOOD)
def test_valid_queries_pass(sql: str, small_schema: Schema) -> None:
    result = guard.check(sql, small_schema)
    assert result.sql.upper().startswith(("SELECT", "WITH"))
    assert "LIMIT" in result.sql.upper()


@pytest.mark.parametrize(("sql", "why"), BAD, ids=[why for _, why in BAD])
def test_bad_queries_are_refused(sql: str, why: str, small_schema: Schema) -> None:
    with pytest.raises(GuardRejected):
        guard.check(sql, small_schema)


def test_unqualified_table_gets_the_schema(small_schema: Schema) -> None:
    result = guard.check("SELECT count(*) FROM orders", small_schema)
    assert "demo.orders" in result.sql
    assert result.report.rewrites == ("qualified_tables",)
    assert not result.report.clean


def test_missing_limit_is_added_without_losing_cleanliness(
    small_schema: Schema,
) -> None:
    result = guard.check("SELECT order_id FROM demo.orders", small_schema)
    assert result.sql.endswith("LIMIT 200")
    assert result.report.clean


@override_settings(ASK_MAX_ROWS=50)
def test_large_limit_is_clamped(small_schema: Schema) -> None:
    result = guard.check("SELECT order_id FROM demo.orders LIMIT 100000", small_schema)
    assert result.sql.endswith("LIMIT 50")
    assert result.report.rewrites == ("limit_clamped",)


def test_small_limit_is_kept(small_schema: Schema) -> None:
    result = guard.check("SELECT order_id FROM demo.orders LIMIT 5", small_schema)
    assert result.sql.endswith("LIMIT 5")
    assert result.report.clean


def test_non_numeric_limit_is_replaced(small_schema: Schema) -> None:
    result = guard.check(
        "SELECT order_id FROM demo.orders LIMIT (SELECT count(*) FROM demo.orders)",
        small_schema,
    )
    assert result.sql.endswith("LIMIT 200")


def test_union_gets_one_outer_limit(small_schema: Schema) -> None:
    result = guard.check(
        "SELECT order_id FROM demo.orders UNION SELECT order_id FROM demo.order_items",
        small_schema,
    )
    assert result.sql.count("LIMIT") == 1


def test_comments_are_stripped(small_schema: Schema) -> None:
    result = guard.check("SELECT /* sneaky */ 1 -- more", small_schema)
    assert "sneaky" not in result.sql and "more" not in result.sql


def test_rejection_detail_is_safe_and_short(small_schema: Schema) -> None:
    with pytest.raises(GuardRejected) as caught:
        guard.check("SELECT nope FROM demo.orders", small_schema)
    assert caught.value.detail
    assert "\n" not in caught.value.detail
    # The client-facing message never repeats the model's SQL.
    assert "nope" not in caught.value.message


def test_fetch_first_cannot_dodge_the_cap(small_schema: Schema) -> None:
    result = guard.check(
        "SELECT order_id FROM demo.orders FETCH FIRST 5 ROWS ONLY", small_schema
    )
    assert result.sql.endswith("LIMIT 200")
