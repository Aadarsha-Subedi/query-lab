"""Execution-accuracy comparison: do two result sets hold the same answer?

Pure functions, no database. Column names are ignored (the model may alias
differently); values are normalised so `12`, `12.0` and `Decimal('12.00')` match;
rows are compared as an unordered multiset unless the gold SQL orders its result.
The rows themselves are never returned, logged or stored: a verdict carries only
a short reason."""

import datetime
import itertools
from collections import Counter
from dataclasses import dataclass
from decimal import Decimal
from typing import Any

import sqlglot
from django.conf import settings
from sqlglot.errors import SqlglotError

MATCH = "match"
DIFFERENT_ROW_COUNT = "different_row_count"
DIFFERENT_COLUMNS = "different_columns"
DIFFERENT_VALUES = "different_values"

# Matching columns by their values tries at most this many orderings.
MAX_COLUMN_ORDERINGS = 120

Row = tuple[Any, ...]


@dataclass(frozen=True)
class Verdict:
    match: bool
    reason: str


def normalise(value: Any) -> Any:
    """A hashable form of one cell. Booleans stay apart from numbers."""
    if value is None:
        return None
    if isinstance(value, bool):
        return ("bool", value)
    if isinstance(value, int | float | Decimal):
        number = float(value)
        if number != number:
            return ("nan",)
        return ("num", round(number, settings.EVAL_ROW_COMPARE_PRECISION) + 0.0)
    if isinstance(value, datetime.datetime | datetime.date | datetime.time):
        return ("text", value.isoformat())
    if isinstance(value, bytes | bytearray | memoryview):
        return ("bytes", bytes(value))
    return ("text", str(value).strip())


def normalise_rows(rows: list[list[Any]] | list[Row]) -> list[Row]:
    return [tuple(normalise(cell) for cell in row) for row in rows]


def gold_is_ordered(gold_sql: str, dialect: str) -> bool:
    """True when the gold query has a top-level ORDER BY (so order must match)."""
    try:
        tree = sqlglot.parse_one(gold_sql, read=dialect)
    except SqlglotError:
        return False
    return tree is not None and tree.args.get("order") is not None


def _column_orderings(gold: list[Row], predicted: list[Row]) -> list[tuple[int, ...]]:
    """Ways to read the predicted columns so each lines up with a gold column by
    its values alone. Empty when no consistent reading exists."""
    width = len(gold[0])
    gold_columns = [Counter(row[i] for row in gold) for i in range(width)]
    pred_columns = [Counter(row[i] for row in predicted) for i in range(width)]
    options = [
        [j for j in range(width) if pred_columns[j] == gold_columns[i]]
        for i in range(width)
    ]
    found: list[tuple[int, ...]] = []
    for choice in itertools.product(*options):
        if len(set(choice)) == width:
            found.append(choice)
            if len(found) >= MAX_COLUMN_ORDERINGS:
                break
    return found


def _same_rows(gold: list[Row], predicted: list[Row], ordered: bool) -> bool:
    if ordered:
        return gold == predicted
    return Counter(gold) == Counter(predicted)


def compare(
    gold_rows: list[list[Any]] | list[Row],
    predicted_rows: list[list[Any]] | list[Row],
    *,
    ordered: bool = False,
) -> Verdict:
    gold = normalise_rows(gold_rows)
    predicted = normalise_rows(predicted_rows)
    if len(gold) != len(predicted):
        return Verdict(False, DIFFERENT_ROW_COUNT)
    if not gold:
        return Verdict(True, MATCH)
    if len(gold[0]) != len(predicted[0]):
        return Verdict(False, DIFFERENT_COLUMNS)
    if _same_rows(gold, predicted, ordered):
        return Verdict(True, MATCH)
    for choice in _column_orderings(gold, predicted):
        shuffled = [tuple(row[j] for j in choice) for row in predicted]
        if _same_rows(gold, shuffled, ordered):
            return Verdict(True, MATCH)
    return Verdict(False, DIFFERENT_VALUES)
