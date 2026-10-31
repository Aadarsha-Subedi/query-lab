from pydantic import BaseModel, Field

from agent.errors import ToolError
from agent.tools.base import Tool, ToolContext, ToolInput


class Input(ToolInput):
    answer: str = Field(min_length=1, max_length=1_000)


class Output(BaseModel):
    answer: str


class Finish(Tool):
    name = "finish"
    description = (
        "End the run with a short plain-language answer. Only after a query has run."
    )
    Input = Input
    Output = Output
    terminal = True

    @classmethod
    def run(cls, context: ToolContext, data: ToolInput) -> BaseModel:
        assert isinstance(data, Input)
        if not context.executed:
            raise ToolError("Nothing has run yet. Propose SQL first, or give_up.")
        return Output(answer=data.answer)
