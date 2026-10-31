"""The Olist golden set, run through the real ask pipeline.

Predicted SQL goes through the sqlglot guard and the reader connection exactly as
a user's question does. Gold SQL is ours, but it still runs on the reader role."""

import functools
import json
from collections.abc import Callable
from pathlib import Path
from typing import Any

from ask import guard, prompt, runner, schema
from ask.guard import GuardResult
from evals.models import EvalRun
from evals.targets.base import EvalQuestion

GOLDEN_FILE = Path(__file__).with_name("olist_golden.jsonl")
NAME = "olist"


def read_golden() -> list[dict[str, Any]]:
    return [
        json.loads(line)
        for line in GOLDEN_FILE.read_text().splitlines()
        if line.strip()
    ]


def mark_reviewed(path: Path = GOLDEN_FILE) -> int:
    """Set `reviewed` on every question once the owner has checked the gold SQL."""
    items = read_golden()
    for item in items:
        item["reviewed"] = True
    path.write_text("".join(json.dumps(item) + "\n" for item in items))
    return len(items)


class OlistTarget:
    name = NAME
    dialect = prompt.DIALECT_POSTGRES
    compare_as_set = False

    def __init__(self, include_unreviewed: bool = False) -> None:
        self.include_unreviewed = include_unreviewed
        self._schema: schema.Schema | None = None

    def questions(self, split: str) -> list[EvalQuestion]:
        # There is one split: the golden set is small and never used for tuning.
        if split != EvalRun.SPLIT_ALL:
            raise ValueError("The Olist golden set has no splits; use --split all.")
        return [
            EvalQuestion(
                id=item["id"],
                question=item["question"],
                gold_sql=item["gold_sql"],
                tags=item["tags"],
                answerable=item["answerable"],
            )
            for item in read_golden()
            if item["reviewed"] or self.include_unreviewed
        ]

    def _known(self) -> schema.Schema:
        if self._schema is None:
            self._schema = schema.get_schema(include_samples=True)
        return self._schema

    def schema_text(self, question: EvalQuestion) -> str:
        return schema.render(self._known())

    def check(self, question: EvalQuestion) -> Callable[[str], GuardResult]:
        known = self._known()
        return lambda sql: guard.check(sql, known)

    def execute(self, question: EvalQuestion) -> Callable[[str], runner.QueryResult]:
        # Native values, so numbers compare as numbers rather than as strings.
        return functools.partial(runner.run, json_safe=False)

    def gold_rows(self, question: EvalQuestion) -> list[list[Any]]:
        return runner.run(question.gold_sql, json_safe=False).rows
