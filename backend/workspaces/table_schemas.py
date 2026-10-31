from ninja import Schema


class ColumnIn(Schema):
    name: str
    # text, integer, bigint, numeric, boolean, date or timestamp
    type: str
    nullable: bool = True
    description: str = ""
    # A literal value, stored as the column default.
    default: str | None = None


class TableIn(Schema):
    name: str
    description: str = ""
    columns: list[ColumnIn]


class TablePatch(Schema):
    name: str | None = None
    description: str | None = None


class ColumnPatch(Schema):
    name: str | None = None
    description: str | None = None
    nullable: bool | None = None
    # Converts every value; a value that does not convert changes nothing.
    type: str | None = None


class WorkspaceColumnOut(Schema):
    name: str
    type: str
    nullable: bool
    description: str
    # True for `_row_id`, the key rows are edited by; the agent never sees it.
    hidden: bool


class WorkspaceTableOut(Schema):
    name: str
    description: str
    row_estimate: int | None
    primary_key: list[str]
    columns: list[WorkspaceColumnOut]


class PrimaryKeyIn(Schema):
    # One or more columns. They must have no empty or repeated values.
    columns: list[str]


class RelationIn(Schema):
    child_table: str
    child_columns: list[str]
    parent_table: str
    # The primary key or a unique column set of the parent table.
    parent_columns: list[str]
    # NO ACTION (refuse deleting a parent that has children) or CASCADE.
    on_delete: str = "NO ACTION"


class RelationOut(Schema):
    name: str
    child_table: str
    child_columns: list[str]
    parent_table: str
    parent_columns: list[str]
    on_delete: str
