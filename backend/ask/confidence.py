"""The confidence score (0 to 1) shown with an answer.

A weighted blend of the model's own rating and checks we can measure: the guard
had to change nothing, no repair retry was needed, and the result is not empty;
minus a penalty when the result was cut short. Weights come from .env.

It is a heuristic, not a calibrated probability. Step 2's eval compares it with
real execution accuracy to see how far to trust it."""

from django.conf import settings

from ask.guard import GuardReport


def score(
    *,
    self_confidence: float,
    guard: GuardReport,
    attempts: int,
    row_count: int,
    truncated: bool,
) -> float:
    total = settings.CONFIDENCE_WEIGHT_SELF * self_confidence
    total += settings.CONFIDENCE_WEIGHT_CLEAN_GUARD * guard.clean
    total += settings.CONFIDENCE_WEIGHT_NO_RETRY * (attempts <= 1)
    total += settings.CONFIDENCE_WEIGHT_NON_EMPTY * (row_count > 0)
    if truncated:
        total -= settings.CONFIDENCE_PENALTY_TRUNCATED
    return round(min(1.0, max(0.0, total)), 3)
