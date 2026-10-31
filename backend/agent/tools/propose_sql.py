from pydantic import BaseModel, Field

from agent.errors import ToolError
from agent.tools.base import Tool, ToolContext, ToolInput
from ask import guard
from ask.errors import GuardRejected


class Input(ToolInput):
    sql: str = Field(min_length=1, max_length=10_000)
    rationale: str = Field(default="", max_length=1_000)


class Output(BaseModel):
    # The SQL after the guard: what would run if the user approves.
    sql: str
    rationale: str
    guard_rewrites: list[str]


class ProposeSql(Tool):
    name = "propose_sql"
    description = (
        "Propose the SQL that answers the question. It is checked, then the user "
        "reviews it before it runs. Nothing runs from this call."
    )
    Input = Input
    Output = Output
    needs_approval = True

    @classmethod
    def run(cls, context: ToolContext, data: ToolInput) -> BaseModel:
        assert isinstance(data, Input)
        try:
            checked = guard.check(data.sql, context.schema)
        except GuardRejected as error:
            raise ToolError(f"The query was refused: {error.detail}") from None
        return Output(
            sql=checked.sql,
            rationale=data.rationale,
            guard_rewrites=list(checked.report.rewrites),
        )
