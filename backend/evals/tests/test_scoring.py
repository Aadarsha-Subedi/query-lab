import pytest
from django.test import override_settings

from evals import scoring
from evals.models import EvalResult, EvalRun
from evals.scoring import spearman

pytestmark = pytest.mark.django_db


def add(
    run: EvalRun,
    n: int,
    outcome: str,
    confidence: float | None,
    tags: str = "a",
    latency: int = 100,
) -> None:
    EvalResult.objects.create(
        run=run,
        question_id=f"q{run.results.count()}-{n}",
        tags=tags,
        question="?",
        gold_sql="x",
        outcome=outcome,
        confidence=confidence,
        latency_ms=latency,
        input_tokens=1_000_000,
        output_tokens=500_000,
    )


@pytest.fixture
def run() -> EvalRun:
    run = EvalRun.objects.create(
        target="olist", provider="gemini", model="gemini-3.5-flash", prompt_version="v1"
    )
    for confidence, outcome in [
        (0.95, "correct"),
        (0.9, "correct"),
        (0.88, "wrong"),
        (0.6, "correct"),
        (0.55, "wrong"),
        (0.3, "wrong"),
        (0.2, "wrong"),
    ]:
        add(run, 0, outcome, confidence, tags="join,a" if confidence > 0.5 else "a")
    add(run, 1, "not_answerable", None, latency=900)
    return run


def test_summary_numbers(run: EvalRun) -> None:
    summary = scoring.summarise(run)
    assert summary.total == 8
    assert summary.correct == 3
    assert summary.accuracy == 3 / 8
    assert summary.outcomes == {"correct": 3, "not_answerable": 1, "wrong": 4}
    assert summary.by_tag["join"] == (5, 3)
    assert summary.by_tag["a"] == (8, 3)
    assert summary.mean_latency_ms == 200
    assert summary.p95_latency_ms == 900
    # 8M input and 4M output tokens at 0.30 / 2.50 USD per million.
    assert summary.cost_usd == pytest.approx(8 * 0.30 + 4 * 2.50)


def test_unpriced_model_has_no_cost(run: EvalRun) -> None:
    run.model = "unknown-model"
    assert scoring.summarise(run).cost_usd is None


@override_settings(EVAL_CONFIDENCE_BUCKETS=[0.5, 0.7, 0.85])
def test_calibration_buckets_and_correlation(run: EvalRun) -> None:
    cal = scoring.calibration(run)
    assert cal.scored == 7  # the decline has no confidence
    got = [(b.low, b.high, b.count, b.correct) for b in cal.buckets]
    assert got == [
        (0.0, 0.5, 2, 0),
        (0.5, 0.7, 2, 1),
        (0.7, 0.85, 0, 0),
        (0.85, 1.0, 3, 2),
    ]
    assert cal.buckets[2].accuracy is None
    assert cal.rank_correlation is not None and cal.rank_correlation > 0.5


@override_settings(EVAL_CONFIDENCE_BUCKETS=[0.5])
def test_confidence_of_exactly_one_lands_in_the_top_bucket() -> None:
    run = EvalRun.objects.create(
        target="olist", provider="g", model="m", prompt_version="v1"
    )
    add(run, 0, "correct", 1.0)
    add(run, 1, "wrong", 0.5)
    cal = scoring.calibration(run)
    assert [b.count for b in cal.buckets] == [0, 2]


def test_spearman() -> None:
    assert spearman([1, 2, 3, 4], [0, 0, 1, 1]) == pytest.approx(0.894, abs=0.001)
    assert spearman([1, 2, 3], [1, 1, 1]) is None
    assert spearman([1, 2], [1, 0]) is None


def test_report_text_has_the_headlines(run: EvalRun) -> None:
    text = scoring.format_report(run)
    assert "Execution accuracy: 37.5% (3/8)" in text
    assert "Confidence vs accuracy" in text
    assert "rank correlation" in text
