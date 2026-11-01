"""Instruction data for the LoRA fine-tune (step 7). Offline only: the web app
never imports this package.

Every example is the product's own prompt: the SQLite system prompt, the schema
text rendered the way the eval does, and the question, answered with the JSON
reply `ask.prompt.parse_reply` reads. Pure functions; the caller supplies the
schema renderer so nothing here touches a database."""

import hashlib
import json
import random
import re
from collections.abc import Callable, Iterable
from dataclasses import dataclass

from ask import prompt


class LeakageError(Exception):
    """Training data would include something the benchmark scores on."""


@dataclass(frozen=True)
class Example:
    id: str
    db_id: str
    question: str
    sql: str
    source: str  # "spider-train", "spider-tune" or "traces"


def normalize(text: str) -> str:
    return re.sub(r"\s+", " ", text.strip().lower())


def reply_for(sql: str) -> str:
    """The assistant turn: the JSON object the product asks for, with no rationale
    (fewer tokens to learn and generate; `parse_reply` accepts an empty one)."""
    return json.dumps(
        {
            "answerable": True,
            "sql": sql.strip().rstrip(";"),
            "rationale": "",
            "self_confidence": 1.0,
        }
    )


def to_record(example: Example, schema_text: str) -> dict[str, object]:
    return {
        "id": example.id,
        "db_id": example.db_id,
        "source": example.source,
        "messages": [
            {
                "role": "system",
                "content": prompt.system_prompt(prompt.DIALECT_SQLITE),
            },
            {
                "role": "user",
                "content": prompt.build_prompt(
                    prompt.clean_question(example.question), schema_text
                ),
            },
            {"role": "assistant", "content": reply_for(example.sql)},
        ],
    }


def examples_from_spider(items: Iterable[dict], *, source: str) -> list[Example]:
    """Spider's JSON rows (`db_id`, `question`, `query`)."""
    return [
        Example(
            id=f"{source}-{index:05d}",
            db_id=item["db_id"],
            question=item["question"],
            sql=item["query"],
            source=source,
        )
        for index, item in enumerate(items)
    ]


def dedupe(examples: Iterable[Example]) -> list[Example]:
    """Keep the first example for each (database, normalized question)."""
    seen: set[tuple[str, str]] = set()
    kept = []
    for example in examples:
        key = (example.db_id, normalize(example.question))
        if key not in seen:
            seen.add(key)
            kept.append(example)
    return kept


def drop_benchmark_questions(
    examples: list[Example], banned_questions: Iterable[str]
) -> tuple[list[Example], int]:
    """Examples whose question text is also a benchmark question are dropped (Spider
    repeats generic questions across databases); returns the rest and the count."""
    banned = {normalize(q) for q in banned_questions}
    kept = [e for e in examples if normalize(e.question) not in banned]
    return kept, len(examples) - len(kept)


def assert_no_leakage(
    examples: Iterable[Example],
    *,
    banned_dbs: Iterable[str],
    banned_questions: Iterable[str],
) -> None:
    """Fail when a held-out database or a benchmark question is in the data."""
    dbs = set(banned_dbs)
    questions = {normalize(q) for q in banned_questions}
    for example in examples:
        if example.db_id in dbs:
            raise LeakageError(
                f"{example.id}: database {example.db_id!r} is held out for the benchmark."
            )
        if normalize(example.question) in questions:
            raise LeakageError(f"{example.id}: question is in the benchmark.")


def split_by_database(
    examples: list[Example], fraction: float, seed: int
) -> tuple[list[Example], list[Example]]:
    """Validation is whole databases, so it measures unseen schemas, not rows."""
    databases = sorted({e.db_id for e in examples})
    count = min(max(1, round(len(databases) * fraction)), len(databases) - 1)
    chosen = set(random.Random(seed).sample(databases, count)) if count > 0 else set()
    train = [e for e in examples if e.db_id not in chosen]
    validation = [e for e in examples if e.db_id in chosen]
    return train, validation


def shuffled(examples: list[Example], seed: int) -> list[Example]:
    ordered = sorted(examples, key=lambda e: e.id)
    random.Random(seed).shuffle(ordered)
    return ordered


def build_records(
    examples: Iterable[Example], schema_for: Callable[[str], str]
) -> list[dict[str, object]]:
    return [to_record(e, schema_for(e.db_id)) for e in examples]


def dump_jsonl(records: Iterable[dict[str, object]]) -> str:
    return "".join(json.dumps(r, sort_keys=True) + "\n" for r in records)


def sha256(text: str) -> str:
    return hashlib.sha256(text.encode()).hexdigest()
