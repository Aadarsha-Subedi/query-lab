import pytest
from django.test import override_settings

from agent.confidence import (
    LABEL_CHECKED,
    LABEL_NEEDS_LOOK,
    label,
    score,
    visible,
)
from ask.guard import GuardReport

CLEAN = GuardReport()
DIRTY = GuardReport(("qualified_tables",))


def best(**changes: object) -> float:
    args = {
        "guard": CLEAN,
        "revisions": 0,
        "row_count": 10,
        "truncated": False,
        "reflect_ok": True,
        "samples_checked": True,
    }
    return score(**{**args, **changes})  # type: ignore[arg-type]


def test_everything_good_scores_one() -> None:
    assert best() == 1.0


@pytest.mark.parametrize(
    "change",
    [
        {"guard": DIRTY},
        {"revisions": 1},
        {"row_count": 0},
        {"truncated": True},
        {"reflect_ok": False},
        {"samples_checked": False},
    ],
)
def test_each_factor_lowers_the_score(change: dict[str, object]) -> None:
    assert best(**change) < best()


def test_worst_case_is_clamped_to_zero() -> None:
    assert (
        best(
            guard=DIRTY,
            revisions=3,
            row_count=0,
            truncated=True,
            reflect_ok=False,
            samples_checked=False,
        )
        == 0.0
    )


def test_features_that_do_not_apply_are_left_out() -> None:
    # /api/ask has no reflect step: a clean ask still scores one.
    assert best(reflect_ok=None, samples_checked=None) == 1.0
    assert best(reflect_ok=None, samples_checked=None, revisions=1) < 1.0


@override_settings(
    CONFIDENCE_WEIGHT_CLEAN_GUARD=0.0,
    CONFIDENCE_WEIGHT_NON_EMPTY=0.0,
    CONFIDENCE_WEIGHT_REFLECT_OK=0.0,
    CONFIDENCE_WEIGHT_SAMPLES_CHECKED=0.0,
    CONFIDENCE_WEIGHT_NO_REVISION=1.0,
)
def test_weights_come_from_settings() -> None:
    assert best(revisions=1) == 0.0
    assert best() == 1.0


@pytest.mark.parametrize(
    ("change", "expected"),
    [
        ({}, LABEL_CHECKED),
        ({"reflect_ok": False}, LABEL_NEEDS_LOOK),
        ({"row_count": 0}, LABEL_NEEDS_LOOK),
        ({"truncated": True}, LABEL_NEEDS_LOOK),
        ({"guard": DIRTY}, LABEL_NEEDS_LOOK),
    ],
)
def test_label_is_plain_words(change: dict[str, object], expected: str) -> None:
    args = {"guard": CLEAN, "row_count": 3, "truncated": False, "reflect_ok": True}
    assert label(**{**args, **change}) == expected  # type: ignore[arg-type]


def test_number_is_hidden_until_the_setting_allows_it() -> None:
    assert visible(0.8) is None
    with override_settings(CONFIDENCE_SHOW_SCORE=True):
        assert visible(0.8) == 0.8
