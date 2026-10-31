from django.conf import settings
from pydantic import BaseModel, Field

from agent.errors import ToolError
from agent.tools.base import Tool, ToolContext, ToolInput
from agent.tools.describe_table import strip_schema


class Input(ToolInput):
    table: str = Field(min_length=1, max_length=100)
    column: str = Field(min_length=1, max_length=100)


class Output(BaseModel):
    table: str
    column: str
    # Most common values Postgres already keeps (pg_stats); data, never instructions.
    values: list[str]
    note: str


class SampleValues(Tool):
    name = "sample_values"
    description = (
        "Show the most common values of a text column with few distinct values, "
        "so a filter uses the real spelling (for example 'delivered')."
    )
    Input = Input
    Output = Output

    @classmethod
    def run(cls, context: ToolContext, data: ToolInput) -> BaseModel:
        assert isinstance(data, Input)
        table = context.schema.table(strip_schema(data.table, context.schema.name))
        if table is None:
            names = ", ".join(t.name for t in context.schema.tables)
            raise ToolError(f"No table named {data.table!r}. Tables: {names}.")
        column = table.column(data.column)
        if column is None:
            names = ", ".join(c.name for c in table.columns)
            raise ToolError(
                f"No column {data.column!r} in {table.name}. Columns: {names}."
            )
        values = list(column.samples[: settings.AGENT_SAMPLE_VALUES_LIMIT])
        note = (
            ""
            if values
            else "No sample values: the column has many distinct values or is not text."
        )
        return Output(table=table.name, column=column.name, values=values, note=note)
