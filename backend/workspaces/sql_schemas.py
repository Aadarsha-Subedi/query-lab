from ninja import Schema


class SqlIn(Schema):
    sql: str


class SqlStatementOut(Schema):
    index: int
    # The Postgres command tag, for example "SELECT 3".
    command: str
    row_count: int
    columns: list[str]
    rows: list[list]
    truncated: bool


class SqlOut(Schema):
    statements: list[SqlStatementOut]
    elapsed_ms: int
