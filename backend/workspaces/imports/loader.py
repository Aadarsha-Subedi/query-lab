"""Loading one spooled CSV into a new table, as the workspace's own `_rw` role.

Two passes over the file, neither holding it in memory:

1. scan: count rows against the caps, widen inferred column types to what every
   value fits (or fail with the row number for a type the user set), notice a
   cancel request;
2. load: in ONE transaction create the table and `COPY` the rows in batches of
   `IMPORT_BATCH_ROWS`, then add the key and relations, check the size caps, and
   commit. Any error rolls the whole transaction back, so a bad file leaves no
   half-made table.

Progress goes to Redis after every batch. Cell values are only ever COPY data."""

import csv
import io
import os
from collections.abc import Iterator
from typing import Any

from django.conf import settings
from psycopg import sql

from workspaces import quota, values
from workspaces.changes import changes
from workspaces.errors import (
    ImportBadRow,
    ImportEmpty,
    ImportTooManyRows,
)
from workspaces.imports import plan as planning
from workspaces.imports import progress, sniff
from workspaces.models import ImportJob
from workspaces.relations import apply_primary_key, apply_relation
from workspaces.tables import ColumnSpec, create_table_in


class ImportCancelled(Exception):
    pass


class Rows:
    """The data rows of the file as lists of strings, padded to the header's width.
    Tracks the row number in the file (1-based, the header is row 1) and the
    bytes read so far."""

    def __init__(self, path: str, sniffed: sniff.Sniffed):
        self.path = path
        self.sniffed = sniffed
        self.row_number = 1 if sniffed.has_header else 0
        self.raw = open(path, "rb")  # noqa: SIM115 (closed by close())
        self.text = io.TextIOWrapper(self.raw, encoding="utf-8-sig", newline="")

    @property
    def bytes_read(self) -> int:
        return self.raw.tell()

    def close(self) -> None:
        self.text.close()

    def __iter__(self) -> Iterator[list[str]]:
        reader = csv.reader(self.text, delimiter=self.sniffed.delimiter)
        width = self.sniffed.column_count
        first = True
        while True:
            try:
                row = next(reader)
            except StopIteration:
                return
            except csv.Error:
                self.row_number += 1
                raise ImportBadRow(
                    errors=[
                        {
                            "field": "file",
                            "message": f"Row {self.row_number}: a cell is too large or a quote is not closed.",
                        }
                    ]
                ) from None
            if first:
                first = False
                if self.sniffed.has_header:
                    continue
            self.row_number += 1
            if not any(cell.strip() for cell in row):
                continue
            if len(row) > width:
                raise ImportBadRow(
                    errors=[
                        {
                            "field": "file",
                            "message": f"Row {self.row_number} has {len(row)} cells but the header has {width}.",
                        }
                    ]
                )
            if len(row) < width:
                row = [*row, *[""] * (width - len(row))]
            yield row


def _bad_value(
    row_number: int, column: planning.PlannedColumn, error: str
) -> ImportBadRow:
    return ImportBadRow(
        errors=[
            {
                "field": column.name,
                "message": f"Row {row_number}, column {column.name}: {error}",
            }
        ]
    )


def _check_cancel(job: ImportJob) -> None:
    if progress.cancel_requested(job.pk):
        raise ImportCancelled()


def scan(job: ImportJob, rows: Rows, plan: planning.Plan) -> int:
    """Pass 1. Decides every inferred type and returns the row count."""
    guesses = {c.index: sniff.TypeGuess() for c in plan.columns if not c.strict}
    strict = [c for c in plan.columns if c.strict]
    count = 0
    for row in rows:
        count += 1
        if count > settings.IMPORT_MAX_ROWS:
            raise ImportTooManyRows(
                f"The file has more than {settings.IMPORT_MAX_ROWS} rows."
            )
        for index, guess in guesses.items():
            guess.add(row[index])
        for column in strict:
            try:
                values.coerce(row[column.index], column.type or "text")
            except values.BadValue as error:
                raise _bad_value(rows.row_number, column, str(error)) from None
        if count % settings.IMPORT_BATCH_ROWS == 0:
            _check_cancel(job)
            progress.report(
                job.pk,
                phase="scanning",
                bytes_read=rows.bytes_read,
                bytes_total=job.bytes_total,
                rows=count,
            )
    if count == 0:
        raise ImportEmpty("The file has a header but no rows.")
    for column in plan.columns:
        if not column.strict:
            column.type = guesses[column.index].result()
    return count


def _cell(value: Any, api_type: str) -> str:
    """A coerced value as COPY text. Empty means NULL for every type."""
    if value is None:
        return ""
    if api_type == "boolean":
        return "t" if value else "f"
    if api_type == "numeric":
        return format(value, "f")
    if api_type == "timestamp":
        return value.isoformat(sep=" ")
    if api_type == "date":
        return value.isoformat()
    return str(value)


def _batch_text(batch: list[list[str]], columns: list[planning.PlannedColumn]) -> str:
    out = io.StringIO()
    writer = csv.writer(out, lineterminator="\n")
    for row in batch:
        writer.writerow(
            [
                _cell(values.coerce(row[c.index], c.type or "text"), c.type or "text")
                for c in columns
            ]
        )
    return out.getvalue()


def load(job: ImportJob, sniffed: sniff.Sniffed, plan: planning.Plan) -> int:
    """Both passes and the transaction. Returns the number of rows loaded."""
    workspace = job.workspace
    csv.field_size_limit(settings.IMPORT_MAX_CELL_CHARS)
    rows = Rows(job.file_path, sniffed)
    try:
        total = scan(job, rows, plan)
    finally:
        rows.close()
    progress.report(job.pk, phase="loading", rows=0, rows_total=total)
    specs = [
        ColumnSpec(c.name, c.type or "text", True, c.description or "")
        for c in plan.columns
    ]
    if plan.header_descriptions:
        for column, spec in zip(plan.columns, specs, strict=True):
            if (
                not spec.description
                and column.header.strip()
                and column.header != column.name
            ):
                spec.description = column.header.strip()[
                    : settings.WORKSPACE_DESCRIPTION_MAX_LENGTH
                ]
    with changes(
        workspace, workspace.owner, timeout_ms=settings.IMPORT_STATEMENT_TIMEOUT_MS
    ) as c:
        size_before = quota.measure(c.connection, workspace.schema_name)
        create_table_in(c, workspace, plan.table_name, specs, plan.description)
        loaded = _copy(c, job, sniffed, plan, total)
        if plan.primary_key:
            apply_primary_key(c, plan.table_name, plan.primary_key)
        for relation in plan.relations:
            apply_relation(
                c,
                child_table=plan.table_name,
                child_columns=relation["columns"],
                parent_table=relation["parent_table"],
                parent_columns=relation["parent_columns"],
                on_delete=relation.get("on_delete", "NO ACTION"),
            )
        quota.ensure_within(c.connection, workspace, grew_from=size_before)
        _check_cancel(job)
    return loaded


def _copy(
    c: Any,
    job: ImportJob,
    sniffed: sniff.Sniffed,
    plan: planning.Plan,
    total: int,
) -> int:
    statement = sql.SQL("COPY {table} ({cols}) FROM STDIN (FORMAT csv)").format(
        table=c.table(plan.table_name),
        cols=sql.SQL(", ").join(sql.Identifier(col.name) for col in plan.columns),
    )
    rows = Rows(job.file_path, sniffed)
    loaded = 0
    batch: list[list[str]] = []
    try:
        with c.connection.cursor() as cursor, cursor.copy(statement) as copy:
            for row in rows:
                batch.append(row)
                if len(batch) >= settings.IMPORT_BATCH_ROWS:
                    copy.write(_batch_text(batch, plan.columns))
                    loaded += len(batch)
                    batch = []
                    _check_cancel(job)
                    progress.report(
                        job.pk,
                        phase="loading",
                        bytes_read=rows.bytes_read,
                        bytes_total=job.bytes_total,
                        rows=loaded,
                        rows_total=total,
                    )
            if batch:
                copy.write(_batch_text(batch, plan.columns))
                loaded += len(batch)
    finally:
        rows.close()
    progress.report(job.pk, phase="finishing", rows=loaded, rows_total=total)
    return loaded


def file_size(path: str) -> int:
    return os.path.getsize(path)
