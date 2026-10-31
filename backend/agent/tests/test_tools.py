import inspect
import sys

import pytest
from django.test import override_settings

from agent import tools
from agent.errors import ToolError
from agent.tools.base import ToolContext
from ask import runner
from ask.schema import Schema


@pytest.fixture
def context(schema: Schema) -> ToolContext:
    return ToolContext(schema=schema)


def test_registry_lists_every_tool_once() -> None:
    assert list(tools.REGISTRY) == [
        "list_tables",
        "describe_table",
        "sample_values",
        "propose_sql",
        "finish",
        "give_up",
    ]
    prompt_text = tools.describe_for_prompt()
    for name in tools.REGISTRY:
        assert f"- {name} " in prompt_text


def test_unknown_tool_is_a_tool_error(context: ToolContext) -> None:
    with pytest.raises(ToolError, match=r"Unknown tool 'run_sql'.*list_tables"):
        tools.call("run_sql", {"sql": "select 1"}, context)


def test_bad_input_is_a_tool_error(context: ToolContext) -> None:
    with pytest.raises(ToolError, match="describe_table: table"):
        tools.call("describe_table", {}, context)
    with pytest.raises(ToolError, match="Bad input"):
        tools.call("describe_table", {"table": "orders", "extra": 1}, context)
    with pytest.raises(ToolError, match="Bad input"):
        tools.call("describe_table", {"table": 5}, context)


def test_list_tables(context: ToolContext) -> None:
    _, out = tools.call("list_tables", {}, context)
    assert out.model_dump() == {
        "tables": [
            {"name": "orders", "comment": "Customer orders.", "row_estimate": 99441},
            {"name": "customers", "comment": "", "row_estimate": None},
        ]
    }


def test_describe_table(context: ToolContext) -> None:
    _, out = tools.call("describe_table", {"table": "demo.orders"}, context)
    data = out.model_dump()
    assert data["table"] == "orders"
    assert [c["name"] for c in data["columns"]][:2] == ["order_id", "customer_id"]
    assert data["columns"][0]["nullable"] is False
    assert data["primary_key"] == ["order_id"]
    assert data["foreign_keys"] == ["(customer_id) -> customers(customer_id)"]


def test_describe_unknown_table_lists_valid_names(context: ToolContext) -> None:
    with pytest.raises(ToolError, match="Tables: orders, customers"):
        tools.call("describe_table", {"table": "nope"}, context)


def test_sample_values_are_capped(context: ToolContext) -> None:
    _, out = tools.call(
        "sample_values", {"table": "orders", "column": "order_status"}, context
    )
    assert out.values == ["delivered", "shipped", "canceled", "created"]
    with override_settings(AGENT_SAMPLE_VALUES_LIMIT=2):
        _, out = tools.call(
            "sample_values", {"table": "orders", "column": "order_status"}, context
        )
    assert out.values == ["delivered", "shipped"]


def test_sample_values_without_samples_or_with_bad_names(context: ToolContext) -> None:
    _, out = tools.call(
        "sample_values", {"table": "orders", "column": "order_id"}, context
    )
    assert out.values == [] and "No sample values" in out.note
    with pytest.raises(ToolError, match="Columns: order_id"):
        tools.call("sample_values", {"table": "orders", "column": "x"}, context)
    with pytest.raises(ToolError, match="No table"):
        tools.call("sample_values", {"table": "x", "column": "y"}, context)


def test_propose_sql_checks_and_returns_the_guarded_sql(context: ToolContext) -> None:
    tool, out = tools.call(
        "propose_sql",
        {"sql": "SELECT count(*) FROM orders", "rationale": "count them"},
        context,
    )
    assert tool.needs_approval
    assert "demo.orders" in out.sql and "LIMIT" in out.sql.upper()
    assert out.rationale == "count them"


@pytest.mark.parametrize(
    "sql",
    [
        "DELETE FROM orders",
        "SELECT * FROM nope",
        "SELECT pg_sleep(5)",
        "SELECT 1; SELECT 2",
    ],
)
def test_propose_sql_refusal_is_a_tool_error(context: ToolContext, sql: str) -> None:
    with pytest.raises(ToolError, match="refused"):
        tools.call("propose_sql", {"sql": sql}, context)


def test_finish_needs_a_result_and_give_up_does_not(context: ToolContext) -> None:
    with pytest.raises(ToolError, match="Nothing has run"):
        tools.call("finish", {"answer": "done"}, context)
    tool, out = tools.call(
        "finish", {"answer": "done"}, ToolContext(context.schema, executed=True)
    )
    assert tool.terminal and out.model_dump() == {"answer": "done"}
    tool, out = tools.call("give_up", {"reason": "no data"}, context)
    assert tool.terminal and out.model_dump() == {"reason": "no data"}


def test_no_tool_can_reach_the_runner(
    context: ToolContext, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Execution is the loop's job after approval. A tool that touched the runner
    would fail here, and none of the tool modules may import it."""

    def boom(*args: object, **kwargs: object) -> None:
        raise AssertionError("a tool executed SQL")

    monkeypatch.setattr(runner, "run", boom)
    calls = {
        "list_tables": {},
        "describe_table": {"table": "orders"},
        "sample_values": {"table": "orders", "column": "order_status"},
        "propose_sql": {"sql": "SELECT 1 FROM orders"},
        "finish": {"answer": "x"},
        "give_up": {"reason": "x"},
    }
    executed = ToolContext(context.schema, executed=True)
    for name, raw in calls.items():
        tools.call(name, raw, executed)
    for tool in tools.TOOLS:
        source = inspect.getsource(sys.modules[tool.__module__])
        assert "runner" not in source
        assert "connections" not in source
