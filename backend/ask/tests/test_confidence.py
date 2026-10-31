import pytest
from django.test import override_settings

from ask.confidence import score
from ask.guard import GuardReport

CLEAN = GuardReport()
DIRTY = GuardReport(("qualified_tables",))


def best(**changes: object) -> float:
    args = {
        "self_confidence": 1.0,
        "guard": CLEAN,
        "attempts": 1,
        "row_count": 10,
        "truncated": False,
    }
    return score(**{**args, **changes})  # type: ignore[arg-type]


def test_everything_good_scores_one() -> None:
    assert best() == 1.0


@pytest.mark.parametrize(
    "change",
    [
        {"self_confidence": 0.2},
        {"guard": DIRTY},
        {"attempts": 2},
        {"row_count": 0},
        {"truncated": True},
    ],
)
def test_each_factor_lowers_the_score(change: dict[str, object]) -> None:
    assert best(**change) < best()


def test_worst_case_is_clamped_to_zero() -> None:
    assert (
        best(self_confidence=0, guard=DIRTY, attempts=3, row_count=0, truncated=True)
        == 0.0
    )


@override_settings(CONFIDENCE_WEIGHT_SELF=0.0, CONFIDENCE_WEIGHT_NON_EMPTY=0.0)
def test_weights_come_from_settings() -> None:
    assert best(self_confidence=0.0) == 0.4
