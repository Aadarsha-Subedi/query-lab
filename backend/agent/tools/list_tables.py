from pydantic import BaseModel

from agent.tools.base import Tool, ToolContext, ToolInput
from ask.schema import clean_comment


class Input(ToolInput):
    pass


class TableInfo(BaseModel):
    name: str
    comment: str
    row_estimate: int | None


class Output(BaseModel):
    tables: list[TableInfo]


def table_infos(context: ToolContext) -> list[TableInfo]:
    return [
        TableInfo(
            name=table.name,
            comment=clean_comment(table.comment),
            row_estimate=table.row_estimate,
        )
        for table in context.schema.tables
    ]


class ListTables(Tool):
    name = "list_tables"
    description = "List every table with its description and row estimate."
    Input = Input
    Output = Output

    @classmethod
    def run(cls, context: ToolContext, data: ToolInput) -> BaseModel:
        return Output(tables=table_infos(context))
