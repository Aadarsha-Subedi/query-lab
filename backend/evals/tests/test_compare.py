from datetime import date, datetime
from decimal import Decimal

import pytest

from evals.compare import (
    DIFFERENT_COLUMNS,
    DIFFERENT_ROW_COUNT,
    DIFFERENT_VALUES,
    MATCH,
    compare,
    gold_is_ordered,
    normalise,
)

CASES = [
    # id, gold, predicted, ordered, match, reason
    ("equal", [[1, "a"], [2, "b"]], [[1, "a"], [2, "b"]], False, True, MATCH),
    ("reordered rows", [[1], [2], [3]], [[3], [1], [2]], False, True, MATCH),
    (
        "reordered rows but order matters",
        [[1], [2]],
        [[2], [1]],
        True,
        False,
        DIFFERENT_VALUES,
    ),
    ("same order when ordered", [[1], [2]], [[1], [2]], True, True, MATCH),
    (
        "reordered columns",
        [[1, "a"], [2, "b"]],
        [["a", 1], ["b", 2]],
        False,
        True,
        MATCH,
    ),
    (
        "swapped columns, ordered",
        [[1, "a"], [2, "b"]],
        [["a", 1], ["b", 2]],
        True,
        True,
        MATCH,
    ),
    ("int vs float", [[12]], [[12.0]], False, True, MATCH),
    ("decimal vs int", [[Decimal("12.00")]], [[12]], False, True, MATCH),
    ("rounding", [[1.001]], [[1.0]], False, True, MATCH),
    ("beyond rounding", [[1.2]], [[1.3]], False, False, DIFFERENT_VALUES),
    ("bool is not a number", [[True]], [[1]], False, False, DIFFERENT_VALUES),
    ("text trimmed", [["a "]], [["a"]], False, True, MATCH),
    ("text is case sensitive", [["A"]], [["a"]], False, False, DIFFERENT_VALUES),
    ("date vs iso text", [[date(2018, 1, 2)]], [["2018-01-02"]], False, True, MATCH),
    (
        "datetime vs iso text",
        [[datetime(2018, 1, 2, 3, 4)]],
        [["2018-01-02T03:04:00"]],
        False,
        True,
        MATCH,
    ),
    ("null equals null", [[None]], [[None]], False, True, MATCH),
    ("null is not empty text", [[None]], [[""]], False, False, DIFFERENT_VALUES),
    ("null is not zero", [[None]], [[0]], False, False, DIFFERENT_VALUES),
    ("empty vs empty", [], [], False, True, MATCH),
    ("empty vs one row", [], [[1]], False, False, DIFFERENT_ROW_COUNT),
    ("one extra row", [[1]], [[1], [2]], False, False, DIFFERENT_ROW_COUNT),
    (
        "duplicates count",
        [[1], [1], [2]],
        [[1], [2], [2]],
        False,
        False,
        DIFFERENT_VALUES,
    ),
    ("duplicates equal", [[1], [1], [2]], [[2], [1], [1]], False, True, MATCH),
    ("extra column", [[1]], [[1, 2]], False, False, DIFFERENT_COLUMNS),
    ("fewer columns", [[1, 2]], [[1]], False, False, DIFFERENT_COLUMNS),
    ("wrong values", [[1, "a"]], [[1, "b"]], False, False, DIFFERENT_VALUES),
    ("tuples work too", [(1, 2)], [(1, 2)], False, True, MATCH),
    (
        "column mix that is not a permutation",
        [[1, 2], [3, 4]],
        [[1, 4], [3, 2]],
        False,
        False,
        DIFFERENT_VALUES,
    ),
    (
        "identical columns can be read either way",
        [[1, 1], [2, 2]],
        [[2, 2], [1, 1]],
        False,
        True,
        MATCH,
    ),
    ("nan equals nan", [[float("nan")]], [[float("nan")]], False, True, MATCH),
]


@pytest.mark.parametrize(
    ("gold", "predicted", "ordered", "match", "reason"),
    [case[1:] for case in CASES],
    ids=[case[0] for case in CASES],
)
def test_compare(gold, predicted, ordered, match, reason) -> None:
    verdict = compare(gold, predicted, ordered=ordered)
    assert (verdict.match, verdict.reason) == (match, reason)


def test_verdict_never_carries_the_rows() -> None:
    verdict = compare([["secret-value"]], [["other"]])
    assert "secret-value" not in repr(verdict) and "other" not in repr(verdict)


def test_normalise_keeps_bool_and_number_apart() -> None:
    assert normalise(True) != normalise(1)
    assert normalise(2) == normalise(2.0) == normalise(Decimal("2.000"))


@pytest.mark.parametrize(
    ("sql", "dialect", "ordered"),
    [
        ("SELECT a FROM t ORDER BY a", "postgres", True),
        ("SELECT a FROM t ORDER BY a LIMIT 3", "sqlite", True),
        ("SELECT a FROM t", "postgres", False),
        ("SELECT a FROM (SELECT a FROM t ORDER BY a) x", "postgres", False),
        ("WITH c AS (SELECT 1 a) SELECT a FROM c ORDER BY a", "postgres", True),
        ("SELECT a FROM t UNION SELECT a FROM u ORDER BY a", "sqlite", True),
        ("this is not sql )(", "postgres", False),
    ],
)
def test_gold_is_ordered(sql: str, dialect: str, ordered: bool) -> None:
    assert gold_is_ordered(sql, dialect) is ordered
