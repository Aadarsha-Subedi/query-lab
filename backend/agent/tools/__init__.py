"""The tool registry: the only list of things the model can ask for. Names outside
it are a ToolError. There is deliberately no tool that executes SQL."""

import json
from typing import Any

from pydantic import ValidationError

from agent.errors import ToolError
from agent.tools.base import Tool, ToolContext
from agent.tools.describe_table import DescribeTable
from agent.tools.finish import Finish
from agent.tools.give_up import GiveUp
from agent.tools.list_tables import ListTables
from agent.tools.propose_sql import ProposeSql
from agent.tools.sample_values import SampleValues

TOOLS: tuple[type[Tool], ...] = (
    ListTables,
    DescribeTable,
    SampleValues,
    ProposeSql,
    Finish,
    GiveUp,
)
REGISTRY: dict[str, type[Tool]] = {tool.name: tool for tool in TOOLS}


def get(name: str) -> type[Tool]:
    tool = REGISTRY.get(name)
    if tool is None:
        raise ToolError(f"Unknown tool {name!r}. Tools: {', '.join(REGISTRY)}.")
    return tool


def call(name: str, raw_input: object, context: ToolContext) -> tuple[type[Tool], Any]:
    """Validate the model's input and run the tool; the output is the tool's Output
    model. Raises ToolError on any problem."""
    tool = get(name)
    try:
        data = tool.Input.model_validate(raw_input if raw_input is not None else {})
    except ValidationError as error:
        first = error.errors()[0]
        where = ".".join(str(part) for part in first["loc"]) or "input"
        raise ToolError(f"Bad input for {name}: {where}: {first['msg']}.") from None
    return tool, tool.run(context, data)


def describe_for_prompt() -> str:
    """One line per tool: its name, what it does and its input as JSON."""
    lines = []
    for tool in TOOLS:
        properties = tool.Input.model_json_schema().get("properties", {})
        args = {key: spec.get("type", "string") for key, spec in properties.items()}
        lines.append(f"- {tool.name} {json.dumps(args)}: {tool.description}")
    return "\n".join(lines)
