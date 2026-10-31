"""The runner against the real reader role."""

import datetime
from decimal import Decimal
from uuid import UUID

import pytest
from django.test import override_settings

from ask import runner
from ask.errors import QueryFailed, QueryTimeout

pytestmark = pytest.mark.usefixtures("data_connections")


def test_runs_a_query_and_returns_columns_and_rows() -> None:
    result = runner.run(
        "SELECT order_status, count(*) AS n FROM demo.orders GROUP BY 1 ORDER BY 2 DESC LIMIT 3"
    )
    assert result.columns == ["order_status", "n"]
    assert result.row_count == 3
    assert result.rows[0][0] == "delivered"
    assert not result.truncated


def test_native_values_are_kept_when_asked() -> None:
    sql = "SELECT round(avg(price), 2) AS p FROM demo.order_items"
    assert isinstance(runner.run(sql).rows[0][0], str)
    assert isinstance(runner.run(sql, json_safe=False).rows[0][0], Decimal)


@override_settings(ASK_MAX_ROWS=5)
def test_row_cap_truncates() -> None:
    result = runner.run("SELECT order_id FROM demo.orders LIMIT 50")
    assert result.row_count == 5
    assert result.truncated


@override_settings(ASK_MAX_RESULT_BYTES=100)
def test_byte_cap_truncates() -> None:
    result = runner.run("SELECT order_id FROM demo.orders LIMIT 50")
    assert 0 < result.row_count < 50
    assert result.truncated


@override_settings(READER_STATEMENT_TIMEOUT_MS=200)
def test_slow_query_is_cancelled() -> None:
    with pytest.raises(QueryTimeout):
        runner.run("SELECT count(*) FROM generate_series(1, 100000000) a")


def test_database_error_carries_a_short_detail() -> None:
    with pytest.raises(QueryFailed) as caught:
        runner.run("SELECT 1 / 0")
    assert "division by zero" in caught.value.detail
    assert "\n" not in caught.value.detail


def test_runner_cannot_write_even_if_the_guard_was_bypassed() -> None:
    with pytest.raises(QueryFailed):
        runner.run("DELETE FROM demo.customers")
    assert runner.run("SELECT count(*) FROM demo.customers").rows[0][0] > 0


def test_runner_uses_a_read_only_transaction() -> None:
    result = runner.run("SELECT current_setting('transaction_read_only')")
    assert result.rows == [["on"]]


def test_values_are_json_safe() -> None:
    result = runner.run(
        "SELECT 1.50::numeric AS d, DATE '2026-01-02' AS day, "
        "TIMESTAMP '2026-01-02 03:04:05' AS ts, "
        "'7b0d1b0e-0a3f-4c1e-9d9b-1c2d3e4f5a6b'::uuid AS u, "
        "ARRAY[1,2] AS arr, NULL AS nothing, interval '2 days' AS iv"
    )
    assert result.rows == [
        [
            "1.50",
            "2026-01-02",
            "2026-01-02T03:04:05",
            "7b0d1b0e-0a3f-4c1e-9d9b-1c2d3e4f5a6b",
            [1, 2],
            None,
            "2 days, 0:00:00",
        ]
    ]


def test_binary_values_are_refused() -> None:
    with pytest.raises(QueryFailed):
        runner.run("SELECT 'abc'::bytea")


def test_to_json_safe_types() -> None:
    assert runner.to_json_safe(Decimal("1.5")) == "1.5"
    assert runner.to_json_safe(datetime.time(1, 2)) == "01:02:00"
    assert runner.to_json_safe(UUID(int=1)) == "00000000-0000-0000-0000-000000000001"
    assert runner.to_json_safe(float("nan")) == "nan"
