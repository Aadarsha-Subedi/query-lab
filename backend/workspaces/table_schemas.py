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


class SqlIn(Schema):
    sql: str


class SqlStatementOut(Schema):
    index: int
    # The Postgres command tag, for example "INSERT 0 3" or "CREATE TABLE".
    command: str
    kind: str  # query, data or ddl
    row_count: int
    columns: list[str]
    rows: list[list]
    truncated: bool


class SqlCountsOut(Schema):
    ddl: int
    data: int
    query: int


class SqlOut(Schema):
    statements: list[SqlStatementOut]
    counts: SqlCountsOut
    elapsed_ms: int


class RowsQuery(Schema):
    limit: int | None = None
    offset: int = 0
    # A column of the table (including `_row_id`); default `_row_id`.
    order_by: str | None = None
    descending: bool = False
    # Repeat for several, all must match: `age:eq:36`, `name:contains:ad`.
    filter: list[str] = []


class RowsPageColumn(Schema):
    name: str
    type: str


class RowsPageOut(Schema):
    columns: list[RowsPageColumn]
    # Same order as `columns`; the first is the hidden `_row_id`.
    rows: list[list]
    # Rows matching the filters, before paging.
    total: int


class RowsIn(Schema):
    # Each row is {column: value}; a missing column takes its default.
    rows: list[dict]


class RowsInsertedOut(Schema):
    inserted: int
    ids: list[int]


class RowPatch(Schema):
    values: dict


class RowOut(Schema):
    row: dict


class RowsDeletedOut(Schema):
    deleted: int
    # Rows of other tables removed by ON DELETE CASCADE relations.
    cascaded: int
