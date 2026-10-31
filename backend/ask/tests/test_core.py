"""The user-free core of an ask, as the eval harness drives it."""

import json

import pytest

from ask import prompt, runner, service
from ask.errors import QueryFailed
from ask.guard import GuardReport, GuardResult
from common.llm.fake import FakeProvider


def reply(sql: str) -> str:
    return json.dumps({"sql": sql, "rationale": "r", "self_confidence": 0.9})


def run_core(fake: FakeProvider, execute, dialect: str = prompt.DIALECT_SQLITE):
    trace = service.Trace(question="q")
    done = service.generate_and_run(
        fake,
        "How many?",
        "CREATE TABLE t (a int);",
        check=lambda sql: GuardResult(sql, GuardReport()),
        execute=execute,
        trace=trace,
        dialect=dialect,
    )
    return done, trace


def ok_result() -> runner.QueryResult:
    return runner.QueryResult(["n"], [[1]], 1, False)


def test_core_needs_no_user_and_uses_the_given_dialect() -> None:
    fake = FakeProvider(answers=[reply("SELECT 1 AS n")])
    done, trace = run_core(fake, lambda sql: ok_result())
    assert done.sql == "SELECT 1 AS n"
    assert trace.attempts == 1
    assert "SQLite" in fake.requests[0].system
    assert "demo." not in fake.requests[0].system


def test_core_repairs_once_then_gives_up() -> None:
    calls = []

    def execute(sql: str) -> runner.QueryResult:
        calls.append(sql)
        raise QueryFailed("no such column: x")

    fake = FakeProvider(answers=[reply("SELECT x"), reply("SELECT y")])
    with pytest.raises(QueryFailed):
        run_core(fake, execute)
    assert calls == ["SELECT x", "SELECT y"]
    assert "no such column: x" in fake.requests[1].prompt


def test_postgres_prompt_is_unchanged() -> None:
    text = prompt.system_prompt(prompt.DIALECT_POSTGRES)
    assert text == prompt.SYSTEM_PROMPT
    assert "PostgreSQL" in text
    assert "schema-qualified names (demo.orders)" in text


def test_sqlite_prompt_names_sqlite() -> None:
    text = prompt.system_prompt(prompt.DIALECT_SQLITE)
    assert "SQLite" in text
    assert "PostgreSQL" not in text
