"""What every tool has: a name, a description for the prompt, a Pydantic input and
output model, and a pure `run(context, data)`. A tool never executes SQL; running
a query is the loop's job, after approval (agent/loop.py)."""

from dataclasses import dataclass
from typing import ClassVar

from pydantic import BaseModel, ConfigDict

from ask.schema import Schema


class ToolInput(BaseModel):
    """Inputs reject unknown keys, so a made-up argument is an error, not ignored."""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


@dataclass(frozen=True)
class ToolContext:
    schema: Schema
    # True once an approved query has run in this run; `finish` needs it.
    executed: bool = False


class Tool:
    name: ClassVar[str]
    description: ClassVar[str]
    Input: ClassVar[type[ToolInput]]
    Output: ClassVar[type[BaseModel]]
    # The run pauses for the user after this tool (only propose_sql).
    needs_approval: ClassVar[bool] = False
    # The run ends on the agent's side after this tool (finish, give_up).
    terminal: ClassVar[bool] = False

    @classmethod
    def run(cls, context: ToolContext, data: ToolInput) -> BaseModel:
        raise NotImplementedError
