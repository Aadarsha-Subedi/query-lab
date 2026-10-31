from collections.abc import Callable

import pytest
from django.test import override_settings

from ask import runner
from ask.errors import QueryFailed, QueryTimeout
from workspaces.context import DEMO, ref_for
from workspaces.tests.conftest import connect

A, B = 990301, 990302


@pytest.fixture
def two(provision: Callable[[int], int]) -> None:
    for workspace_id, name in ((A, "alice"), (B, "bob")):
        provision(workspace_id)
        with connect(workspace_id, "rw") as rw:
            rw.execute("CREATE TABLE customer (id int, name text)")
            rw.execute("INSERT INTO customer VALUES (1, %s)", [name])


def test_a_workspace_query_runs_as_its_own_reader_role(two: None) -> None:
    for workspace_id, name in ((A, "alice"), (B, "bob")):
        ref = ref_for(workspace_id)
        who = runner.run("SELECT current_user", ref)
        assert who.rows == [[f"ws_{workspace_id}_ro"]]
        mine = runner.run("SELECT name FROM customer", ref)
        assert (mine.columns, mine.rows) == (["name"], [[name]])


def test_it_cannot_reach_another_workspace_or_write(two: None) -> None:
    ref = ref_for(A)
    with pytest.raises(QueryFailed):
        runner.run(f"SELECT * FROM ws_{B}.customer", ref)
    with pytest.raises(QueryFailed):
        runner.run("INSERT INTO customer VALUES (2, 'x')", ref)
    with pytest.raises(QueryFailed):
        runner.run("SELECT * FROM demo.orders", ref)


def test_the_row_cap_and_json_safe_values_hold(two: None) -> None:
    with override_settings(ASK_MAX_ROWS=3):
        result = runner.run(
            "SELECT g, g::numeric / 3 FROM generate_series(1, 10) g", ref_for(A)
        )
    assert result.truncated and result.row_count == 3
    assert isinstance(result.rows[0][1], str)  # Decimal -> string
    raw = runner.run("SELECT 1::numeric", ref_for(A), json_safe=False)
    assert str(type(raw.rows[0][0])) == "<class 'decimal.Decimal'>"


def test_a_slow_query_is_stopped(two: None) -> None:
    with (
        override_settings(READER_STATEMENT_TIMEOUT_MS=200),
        pytest.raises(QueryTimeout),
    ):
        runner.run("SELECT pg_sleep(3)", ref_for(A))


@pytest.mark.usefixtures("data_connections")
def test_the_demo_still_runs_on_the_reader_connection() -> None:
    result = runner.run(
        "SELECT current_user, count(*) FROM demo.orders GROUP BY 1", DEMO
    )
    assert result.rows[0][0].startswith("querylab_reader")
