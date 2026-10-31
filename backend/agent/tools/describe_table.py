from pydantic import BaseModel, Field

from agent.errors import ToolError
from agent.tools.base import Tool, ToolContext, ToolInput
from ask.schema import clean_comment


class Input(ToolInput):
    table: str = Field(min_length=1, max_length=100)


class ColumnInfo(BaseModel):
    name: str
    type: str
    nullable: bool
    comment: str


class Output(BaseModel):
    table: str
    comment: str
    columns: list[ColumnInfo]
    primary_key: list[str]
    foreign_keys: list[str]


def strip_schema(name: str, schema_name: str) -> str:
    """`demo.orders` and `orders` name the same table."""
    prefix = f"{schema_name}."
    return name[len(prefix) :] if name.startswith(prefix) else name


class DescribeTable(Tool):
    name = "describe_table"
    description = (
        "Show one table: its columns with types and descriptions, its primary key "
        "and its foreign keys."
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
        return Output(
            table=table.name,
            comment=clean_comment(table.comment),
            columns=[
                ColumnInfo(
                    name=c.name,
                    type=c.type,
                    nullable=c.nullable,
                    comment=clean_comment(c.comment),
                )
                for c in table.columns
            ],
            primary_key=list(table.primary_key),
            foreign_keys=[
                f"({', '.join(fk.columns)}) -> {fk.ref_table}({', '.join(fk.ref_columns)})"
                for fk in table.foreign_keys
            ],
        )
