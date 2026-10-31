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
