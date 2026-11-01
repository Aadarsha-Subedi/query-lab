"""What a question set must provide so the runner can score a model on it."""

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any, Protocol

from ask import runner
from ask.guard import GuardResult


@dataclass(frozen=True)
class EvalQuestion:
    id: str
    question: str
    gold_sql: str
    tags: str = ""
    db_id: str = ""
    # False for a question the schema cannot answer: the right move is to decline.
    answerable: bool = True
    # Trace cases only: the TraceCase and the cluster it belongs to.
    case_id: int | None = None
    cluster: str = ""


class Target(Protocol):
    name: str
    dialect: str  # a prompt.DIALECT_* value, also the sqlglot dialect
    compare_as_set: bool  # ignore duplicate rows when comparing (Spider)

    def questions(self, split: str) -> list[EvalQuestion]: ...

    def schema_text(self, question: EvalQuestion) -> str: ...

    def check(self, question: EvalQuestion) -> Callable[[str], GuardResult]: ...

    def execute(
        self, question: EvalQuestion
    ) -> Callable[[str], runner.QueryResult]: ...

    def gold_rows(self, question: EvalQuestion) -> list[list[Any]]: ...
