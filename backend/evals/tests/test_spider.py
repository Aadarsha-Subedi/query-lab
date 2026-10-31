"""Spider target on a tiny fixture database (no real Spider needed)."""

import json
import sqlite3
from pathlib import Path

import pytest
from django.test import override_settings

from ask.errors import QueryFailed, QueryTimeout
from evals.models import EvalRun
from evals.targets import spider

DEV = [
    {
        "db_id": "shop",
        "question": "How many items?",
        "query": "SELECT count(*) FROM item",
    },
    {"db_id": "zoo", "question": "List animals", "query": "SELECT name FROM animal"},
]


@pytest.fixture
def spider_dir(tmp_path: Path):
    for db_id, ddl in {
        "shop": [
            "CREATE TABLE item (id INTEGER PRIMARY KEY, name TEXT NOT NULL, kind TEXT)",
            "CREATE TABLE sale (id INTEGER PRIMARY KEY, item_id INTEGER, "
            "FOREIGN KEY (item_id) REFERENCES item(id))",
            "INSERT INTO item (name, kind) VALUES ('a', 'x'), ('b', 'x'), ('c', 'y')",
        ],
        "zoo": [
            "CREATE TABLE animal (name TEXT)",
            "INSERT INTO animal VALUES ('lion')",
        ],
    }.items():
        folder = tmp_path / "database" / db_id
        folder.mkdir(parents=True)
        connection = sqlite3.connect(folder / f"{db_id}.sqlite")
        for statement in ddl:
            connection.execute(statement)
        connection.commit()
        connection.close()
    (tmp_path / "dev.json").write_text(json.dumps(DEV))
    with override_settings(EVAL_SPIDER_DIR=tmp_path):
        yield tmp_path


def test_schema_text_has_tables_keys_and_samples(spider_dir: Path) -> None:
    text = spider.SpiderTarget().schema_text(spider.load_questions()[0])
    assert "CREATE TABLE item (" in text
    assert "demo." not in text and "main." not in text
    assert "id INTEGER NOT NULL" not in text
    assert "name TEXT NOT NULL" in text
    assert "FOREIGN KEY (item_id) REFERENCES item (id)" in text
    assert "Values: 'x', 'y'" in text


def test_execute_returns_rows_and_columns(spider_dir: Path) -> None:
    result = spider.execute_sql("shop", "SELECT name FROM item ORDER BY name")
    assert result.columns == ["name"]
    assert result.rows == [["a"], ["b"], ["c"]]
    assert not result.truncated


@override_settings(EVAL_MAX_COMPARE_ROWS=2)
def test_row_cap_truncates(spider_dir: Path) -> None:
    result = spider.execute_sql("shop", "SELECT name FROM item")
    assert result.row_count == 2
    assert result.truncated


@pytest.mark.parametrize(
    "sql",
    [
        "INSERT INTO item (name) VALUES ('z')",
        "DROP TABLE item",
        "CREATE TABLE t (a int)",
        "ATTACH DATABASE ':memory:' AS other",
        "PRAGMA writable_schema = ON",
        "SELECT 1; SELECT 2",
        "SELECT nope FROM item",
    ],
)
def test_nothing_but_reads_runs(spider_dir: Path, sql: str) -> None:
    with pytest.raises(QueryFailed):
        spider.execute_sql("shop", sql)
    assert spider.execute_sql("shop", "SELECT count(*) FROM item").rows == [[3]]


@override_settings(EVAL_QUERY_TIMEOUT_MS=50)
def test_slow_query_times_out(spider_dir: Path) -> None:
    sql = (
        "WITH RECURSIVE c(x) AS (SELECT 1 UNION ALL SELECT x + 1 FROM c "
        "WHERE x < 100000000) SELECT count(*) FROM c"
    )
    with pytest.raises(QueryTimeout):
        spider.execute_sql("shop", sql)


def test_missing_database_is_reported(spider_dir: Path) -> None:
    with pytest.raises(spider.SpiderNotFound):
        spider.execute_sql("ghost", "SELECT 1")


def test_missing_spider_is_reported(tmp_path: Path) -> None:
    with (
        override_settings(EVAL_SPIDER_DIR=tmp_path),
        pytest.raises(spider.SpiderNotFound),
    ):
        spider.load_questions()


def test_committed_split_is_disjoint_and_has_two_halves() -> None:
    assignment = spider.load_split()
    assert set(assignment.values()) == {EvalRun.SPLIT_TUNE, EvalRun.SPLIT_HELD_OUT}
    data = json.loads(spider.SPLIT_FILE.read_text())
    assert not set(data["tune"]) & set(data["held-out"])
    assert len(assignment) == 20


def test_questions_follow_the_split(
    spider_dir: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(
        spider, "load_split", lambda: {"shop": "tune", "zoo": "held-out"}
    )
    target = spider.SpiderTarget()
    assert [q.db_id for q in target.questions("tune")] == ["shop"]
    assert [q.db_id for q in target.questions("held-out")] == ["zoo"]
    assert len(target.questions("all")) == 2


def test_a_database_missing_from_the_split_is_an_error(
    spider_dir: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(spider, "load_split", lambda: {"shop": "tune"})
    with pytest.raises(ValueError, match="zoo"):
        spider.SpiderTarget().questions("all")


def test_build_split_balances_sizes() -> None:
    split = spider.build_split({"a": 100, "b": 90, "c": 10, "d": 5})
    assert split["tune"] == ["a", "c"]
    assert split["held-out"] == ["b", "d"]
