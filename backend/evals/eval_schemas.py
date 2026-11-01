"""API shapes of the eval results endpoints."""

from datetime import datetime
from typing import Any

from django.conf import settings
from ninja import Schema

from evals.models import EvalResult, EvalRun
from evals.run_compare import Comparison


class EvalRunOut(Schema):
    id: int
    target: str
    split: str
    provider: str
    model: str
    prompt_version: str
    runner: str
    status: str
    question_count: int
    correct_count: int
    # correct / questions, 0 to 1.
    accuracy: float
    # USD per question from EVAL_MODEL_PRICES; null when the model has no price.
    cost_per_question_usd: float | None
    started_at: datetime
    finished_at: datetime | None


class ClusterAccuracyOut(Schema):
    cluster_key: str
    total: int
    correct: int
    accuracy: float


class ResultOut(Schema):
    question_id: str
    question: str
    gold_sql: str
    predicted_sql: str
    outcome: str
    reason: str
    cluster_key: str
    # The trace case, and where to read the run it came from (null if gone).
    trace_case_id: int | None
    trace_path: str | None


class EvalRunDetailOut(EvalRunOut):
    by_cluster: list[ClusterAccuracyOut]
    results: list[ResultOut]


class FlipOut(Schema):
    question_id: str
    question: str
    direction: str
    base_outcome: str
    other_outcome: str
    cluster_key: str
    trace_case_id: int | None


class ClusterDeltaOut(Schema):
    cluster_key: str
    shared: int
    base_correct: int
    other_correct: int
    diff_points: float


class ComparisonOut(Schema):
    base: EvalRunOut
    other: EvalRunOut
    shared: int
    only_in_base: int
    only_in_other: int
    base_accuracy: float
    other_accuracy: float
    # other minus base, percentage points, on the shared cases.
    diff_points: float
    flips: list[FlipOut]
    clusters: list[ClusterDeltaOut]


def run_summary_dict(run: EvalRun) -> dict[str, Any]:
    """`run` carries the totals from `eval_api._annotated`."""
    scored = getattr(run, "scored", run.question_count)
    cost = None
    price = settings.EVAL_MODEL_PRICES.get(run.model)
    if price and scored:
        tokens_in = getattr(run, "tokens_in", 0) or 0
        tokens_out = getattr(run, "tokens_out", 0) or 0
        cost = round(
            (tokens_in * price[0] + tokens_out * price[1]) / 1_000_000 / scored, 6
        )
    return EvalRunOut(
        id=run.pk,
        target=run.target,
        split=run.split,
        provider=run.provider,
        model=run.model,
        prompt_version=run.prompt_version,
        runner=run.runner,
        status=run.status,
        question_count=run.question_count,
        correct_count=run.correct_count,
        accuracy=run.correct_count / run.question_count if run.question_count else 0.0,
        cost_per_question_usd=cost,
        started_at=run.started_at,
        finished_at=run.finished_at,
    ).model_dump(mode="json")


def result_dict(result: EvalResult) -> dict[str, Any]:
    return ResultOut(
        question_id=result.question_id,
        question=result.question,
        gold_sql=result.gold_sql,
        predicted_sql=result.predicted_sql,
        outcome=result.outcome,
        reason=result.reason,
        cluster_key=result.cluster_key,
        trace_case_id=result.trace_case_id,
        trace_path=(
            f"/api/workbench/cases/{result.trace_case_id}"
            if result.trace_case_id
            else None
        ),
    ).model_dump(mode="json")


def comparison_dict(base: EvalRun, other: EvalRun, c: Comparison) -> dict[str, Any]:
    return ComparisonOut(
        base=EvalRunOut(**run_summary_dict(base)),
        other=EvalRunOut(**run_summary_dict(other)),
        shared=c.shared,
        only_in_base=c.only_in_base,
        only_in_other=c.only_in_other,
        base_accuracy=c.base_accuracy,
        other_accuracy=c.other_accuracy,
        diff_points=c.diff_points,
        flips=[FlipOut(**vars(f)) for f in c.flips],
        clusters=[
            ClusterDeltaOut(
                cluster_key=d.cluster_key,
                shared=d.shared,
                base_correct=d.base_correct,
                other_correct=d.other_correct,
                diff_points=d.diff_points,
            )
            for d in c.clusters
        ],
    ).model_dump(mode="json")
