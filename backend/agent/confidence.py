"""The confidence score (0 to 1) and the plain label shown with an answer.

The model's own rating is not an input: on Olist it was about 1.0 for every
answer (step 2). What is left are checks we can measure: the guard changed
nothing, no revision was needed, the result is not empty, the reflect step (or
its rule check) passed on the first look, and the agent looked at sample values
before filtering on text. A truncated result costs points. Weights come from .env.

A feature that does not apply (None) is dropped and the other weights are
scaled up, so /api/ask, which has no reflect step, uses the same function.

It is a heuristic, not a probability. Whether it separates right from wrong is
measured offline (`confidence_report`); the API shows the number only when
CONFIDENCE_SHOW_SCORE says it did (rule in DECISION.md), and always shows the label.
"""

from django.conf import settings

from ask.guard import GuardReport

LABEL_CHECKED = "checked"
LABEL_NEEDS_LOOK = "needs_look"


def score(
    *,
    guard: GuardReport,
    revisions: int,
    row_count: int,
    truncated: bool,
    reflect_ok: bool | None = None,
    samples_checked: bool | None = None,
) -> float:
    features: list[tuple[float, bool | None]] = [
        (settings.CONFIDENCE_WEIGHT_CLEAN_GUARD, guard.clean),
        (settings.CONFIDENCE_WEIGHT_NO_REVISION, revisions == 0),
        (settings.CONFIDENCE_WEIGHT_NON_EMPTY, row_count > 0),
        (settings.CONFIDENCE_WEIGHT_REFLECT_OK, reflect_ok),
        (settings.CONFIDENCE_WEIGHT_SAMPLES_CHECKED, samples_checked),
    ]
    applicable = [(weight, flag) for weight, flag in features if flag is not None]
    weights = sum(weight for weight, _ in applicable)
    total = (
        sum(weight for weight, flag in applicable if flag) / weights if weights else 0
    )
    if truncated:
        total -= settings.CONFIDENCE_PENALTY_TRUNCATED
    return round(min(1.0, max(0.0, total)), 3)


def label(
    *,
    guard: GuardReport,
    row_count: int,
    truncated: bool,
    reflect_ok: bool | None = None,
) -> str:
    """ "checked" when nothing raised a flag, else "needs_look". Plain words, not a number."""
    if reflect_ok is False or row_count == 0 or truncated or not guard.clean:
        return LABEL_NEEDS_LOOK
    return LABEL_CHECKED


def visible(value: float) -> float | None:
    """The score, or None while the measured separation has not earned showing it."""
    return value if settings.CONFIDENCE_SHOW_SCORE else None
