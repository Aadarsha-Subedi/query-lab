from pydantic import BaseModel, Field

from agent.tools.base import Tool, ToolContext, ToolInput


class Input(ToolInput):
    reason: str = Field(min_length=1, max_length=500)


class Output(BaseModel):
    reason: str


class GiveUp(Tool):
    name = "give_up"
    description = (
        "End the run without a query: the question cannot be answered from this "
        "database, or it asks to change data or break the rules."
    )
    Input = Input
    Output = Output
    terminal = True

    @classmethod
    def run(cls, context: ToolContext, data: ToolInput) -> BaseModel:
        assert isinstance(data, Input)
        return Output(reason=data.reason)
