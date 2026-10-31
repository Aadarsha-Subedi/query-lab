"""Spider (dev set) on read-only SQLite files, for offline runs.

The Postgres guard does not apply here. The wall is the way the file is opened
(`mode=ro`, `query_only`), an authorizer that allows only reads, a time limit and
a row cap. Spider is unpacked into EVAL_SPIDER_DIR and never committed."""

import json
import sqlite3
import time
from collections import Counter
from collections.abc import Callable
from contextlib import closing
from pathlib import Path
from typing import Any

from django.conf import settings

from ask import prompt, runner, schema
from ask.errors import QueryFailed, QueryTimeout
from ask.guard import GuardReport, GuardResult
from evals.models import EvalRun
from evals.targets.base import EvalQuestion

SPLIT_FILE = Path(__file__).with_name("spider_split.json")
NAME = "spider"
PROGRESS_STEP = 10_000  # SQLite VM instructions between time-limit checks

ALLOWED_ACTIONS = {
    sqlite3.SQLITE_SELECT,
    sqlite3.SQLITE_READ,
    sqlite3.SQLITE_FUNCTION,
    sqlite3.SQLITE_RECURSIVE,
}


class SpiderNotFound(Exception):
    """Spider is not unpacked where EVAL_SPIDER_DIR says."""


def root() -> Path:
    return Path(settings.EVAL_SPIDER_DIR)


def database_path(db_id: str) -> Path:
    return root() / "database" / db_id / f"{db_id}.sqlite"


def load_split() -> dict[str, str]:
    """db_id -> `tune` or `held-out`, from the committed file."""
    data = json.loads(SPLIT_FILE.read_text())
    split = dict.fromkeys(data["tune"], EvalRun.SPLIT_TUNE)
    split.update(dict.fromkeys(data["held-out"], EvalRun.SPLIT_HELD_OUT))
    if len(split) != len(data["tune"]) + len(data["held-out"]):
        raise ValueError("A database is in both halves of the Spider split.")
    return split


def build_split(question_counts: dict[str, int]) -> dict[str, list[str]]:
    """Split databases into halves of similar size: largest first, alternating."""
    ordered = sorted(question_counts, key=lambda db: (-question_counts[db], db))
    return {
        EvalRun.SPLIT_TUNE: sorted(ordered[0::2]),
        EvalRun.SPLIT_HELD_OUT: sorted(ordered[1::2]),
    }


def load_questions() -> list[EvalQuestion]:
    path = root() / "dev.json"
    if not path.exists():
        raise SpiderNotFound(
            f"Spider dev set not found at {path}. Download Spider, unpack it into "
            "infra/data/spider/ (it must contain dev.json and database/)."
        )
    items = json.loads(path.read_text())
    return [
        EvalQuestion(
            id=f"dev-{index:04d}",
            question=item["question"],
            gold_sql=item["query"],
            db_id=item["db_id"],
        )
        for index, item in enumerate(items)
    ]


def _authorizer(action: int, *_: Any) -> int:
    return sqlite3.SQLITE_OK if action in ALLOWED_ACTIONS else sqlite3.SQLITE_DENY


def connect(db_id: str, *, reads_only: bool = True) -> sqlite3.Connection:
    """Read-only open. `reads_only` adds the authorizer that the model's SQL runs
    under; our own schema queries (PRAGMA) turn it off."""
    path = database_path(db_id)
    if not path.exists():
        raise SpiderNotFound(f"Spider database file missing: {path}")
    connection = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
    connection.text_factory = lambda raw: raw.decode("utf-8", errors="replace")
    connection.execute("PRAGMA query_only = ON")
    if reads_only:
        connection.set_authorizer(_authorizer)
    return connection


def execute_sql(db_id: str, sql: str) -> runner.QueryResult:
    """Run `sql` on one Spider database under the limits above."""
    deadline = time.monotonic() + settings.EVAL_QUERY_TIMEOUT_MS / 1000
    max_rows = settings.EVAL_MAX_COMPARE_ROWS
    with closing(connect(db_id)) as connection:
        connection.set_progress_handler(
            lambda: int(time.monotonic() > deadline), PROGRESS_STEP
        )
        try:
            cursor = connection.execute(sql)
            columns = [col[0] for col in cursor.description or []]
            rows = [list(row) for row in cursor.fetchmany(max_rows + 1)]
        except sqlite3.OperationalError as error:
            if "interrupted" in str(error):
                raise QueryTimeout() from None
            raise QueryFailed(prompt.first_line(str(error))) from None
        except (sqlite3.Error, ValueError) as error:
            raise QueryFailed(prompt.first_line(str(error))) from None
    truncated = len(rows) > max_rows
    rows = rows[:max_rows]
    return runner.QueryResult(
        columns=columns, rows=rows, row_count=len(rows), truncated=truncated
    )


def read_schema(db_id: str) -> schema.Schema:
    """The database's tables, keys and a few example values, read from the file."""
    sample_max = settings.ASK_SAMPLE_VALUES_MAX
    distinct_max = settings.ASK_SAMPLE_VALUES_MAX_DISTINCT
    tables = []
    with closing(connect(db_id, reads_only=False)) as connection:
        names = [
            row[0]
            for row in connection.execute(
                "SELECT name FROM sqlite_master WHERE type = 'table' "
                "AND name NOT LIKE 'sqlite_%' ORDER BY name"
            )
        ]
        for name in names:
            quoted = '"' + name.replace('"', '""') + '"'
            info = connection.execute(f"PRAGMA table_info({quoted})").fetchall()
            columns = []
            for _, col, col_type, notnull, _, _ in info:
                samples: tuple[str, ...] = ()
                if "char" in col_type.lower() or "text" in col_type.lower():
                    cq = '"' + col.replace('"', '""') + '"'
                    values = [
                        row[0]
                        for row in connection.execute(
                            f"SELECT DISTINCT {cq} FROM {quoted} "
                            f"WHERE {cq} IS NOT NULL LIMIT ?",
                            [distinct_max + 1],
                        )
                    ]
                    if 0 < len(values) <= distinct_max:
                        samples = tuple(str(v) for v in values[:sample_max])
                columns.append(
                    schema.Column(col, col_type or "text", not notnull, None, samples)
                )
            primary = tuple(
                col for _, col, _, _, pk, *_ in sorted(info, key=lambda r: r[5]) if pk
            )
            grouped: dict[int, list[tuple[str, str, str]]] = {}
            for row in connection.execute(f"PRAGMA foreign_key_list({quoted})"):
                grouped.setdefault(row[0], []).append((row[2], row[3], row[4]))
            keys = tuple(
                schema.ForeignKey(
                    tuple(part[1] for part in parts),
                    parts[0][0],
                    tuple(part[2] for part in parts),
                )
                for parts in grouped.values()
            )
            tables.append(schema.Table(name, None, tuple(columns), primary, keys))
    return schema.Schema(name="main", tables=tuple(tables))


class SpiderTarget:
    name = NAME
    dialect = prompt.DIALECT_SQLITE
    # Spider's official scorer compares unordered results as sets.
    compare_as_set = True

    def __init__(self) -> None:
        self.skipped: list[str] = []
        self._schemas: dict[str, str] = {}

    def questions(self, split: str) -> list[EvalQuestion]:
        assignment = load_split()
        found = load_questions()
        unknown = {q.db_id for q in found} - set(assignment)
        if unknown:
            raise ValueError(
                f"Databases missing from spider_split.json: {sorted(unknown)}. "
                "Rebuild it from the counts with evals.targets.spider.build_split."
            )
        if split == EvalRun.SPLIT_ALL:
            return found
        return [q for q in found if assignment[q.db_id] == split]

    def question_counts(self) -> dict[str, int]:
        return dict(Counter(q.db_id for q in load_questions()))

    def schema_text(self, question: EvalQuestion) -> str:
        if question.db_id not in self._schemas:
            self._schemas[question.db_id] = schema.render(
                read_schema(question.db_id), qualify=False
            )
        return self._schemas[question.db_id]

    def check(self, question: EvalQuestion) -> Callable[[str], GuardResult]:
        return lambda sql: GuardResult(sql.strip().rstrip(";"), GuardReport())

    def execute(self, question: EvalQuestion) -> Callable[[str], runner.QueryResult]:
        return lambda sql: execute_sql(question.db_id, sql)

    def gold_rows(self, question: EvalQuestion) -> list[list[Any]]:
        return execute_sql(question.db_id, question.gold_sql).rows
