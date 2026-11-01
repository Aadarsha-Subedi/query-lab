"""Read-only eval results for the workbench (step 6). Staff only, like every
`/api/workbench/` route. Nothing here starts a run: evals run in the dev
container (`make eval`)."""

from typing import Annotated, Any, ClassVar

from django.db.models import Count, Q, QuerySet, Sum
from django.http import HttpRequest
from ninja import FilterLookup, FilterSchema, Query, Router

from common.order.domain import OrderingSchema
from common.permissions import staff_only
from common.response.domain import SuccessEnvelope, errors, success
from evals import run_compare
from evals.errors import EvalRunNotFound, EvalRunsNotComparable
from evals.eval_schemas import (
    ComparisonOut,
    EvalRunDetailOut,
    EvalRunOut,
    comparison_dict,
    result_dict,
    run_summary_dict,
)
from evals.models import EvalResult, EvalRun
from evals.workbench_api import WorkbenchPageIn

router = Router(tags=["workbench"], auth=staff_only)


class EvalRunFilter(FilterSchema):
    """`?target=traces&runner=agent&model=...&prompt_version=v2-agent`"""

    target: Annotated[str | None, FilterLookup("target")] = None
    runner: Annotated[str | None, FilterLookup("runner")] = None
    model: Annotated[str | None, FilterLookup("model")] = None
    prompt_version: Annotated[str | None, FilterLookup("prompt_version")] = None
    status: Annotated[str | None, FilterLookup("status")] = None


class EvalRunOrdering(OrderingSchema):
    allowed_fields: ClassVar[list[str]] = [
        "started_at",
        "finished_at",
        "question_count",
    ]


def _annotated() -> QuerySet[EvalRun]:
    """Runs with their token totals, so cost per question needs no query per row."""
    return EvalRun.objects.annotate(
        tokens_in=Sum("results__input_tokens"),
        tokens_out=Sum("results__output_tokens"),
        scored=Count("results"),
        right=Count("results", filter=Q(results__outcome=EvalResult.OUTCOME_CORRECT)),
    )


def _run(run_id: int) -> EvalRun:
    run = _annotated().filter(pk=run_id).first()
    if run is None:
        raise EvalRunNotFound()
    return run


@router.get(
    "/eval/runs",
    response={200: SuccessEnvelope[list[EvalRunOut]], **errors(401, 403, 422, 429)},
)
def list_eval_runs(
    request: HttpRequest,
    page: Query[WorkbenchPageIn],
    filters: Query[EvalRunFilter],
    ordering: Query[EvalRunOrdering],
) -> dict:
    """Staff only. Eval runs, newest first, with accuracy, cost per question (null
    when the model has no price in EVAL_MODEL_PRICES) and finish time. Filter by
    `target`, `runner`, `model`, `prompt_version` and `status`."""
    limit = page.size()
    runs = ordering.apply(filters.filter(_annotated()))
    runs = runs.order_by(*(runs.query.order_by or ("-started_at",)), "-id")
    items = [run_summary_dict(r) for r in runs[page.offset : page.offset + limit]]
    return success(
        items, meta={"count": runs.count(), "limit": limit, "offset": page.offset}
    )


@router.get(
    "/eval/compare",
    response={200: SuccessEnvelope[ComparisonOut], **errors(401, 403, 404, 422, 429)},
)
def compare_eval_runs(request: HttpRequest, base: int, other: int) -> dict:
    """Staff only. Two runs on the same target, case by case: the shared cases,
    which flipped to wrong or to correct, the accuracy difference in percentage
    points (on the shared cases) and the difference per cluster. 422
    `eval_runs_not_comparable` when the targets differ."""
    first, second = _run(base), _run(other)
    if not run_compare.comparable(first, second):
        raise EvalRunsNotComparable()
    return success(
        comparison_dict(first, second, run_compare.compare_runs(first, second))
    )


@router.get(
    "/eval/runs/{run_id}",
    response={
        200: SuccessEnvelope[EvalRunDetailOut],
        **errors(401, 403, 404, 422, 429),
    },
)
def get_eval_run(
    request: HttpRequest, run_id: int, page: Query[WorkbenchPageIn]
) -> dict:
    """Staff only. One run with its per-case results (question, gold SQL, predicted
    SQL, outcome, reason, and a link to the source trace) and accuracy per cluster.
    `meta.count` is the number of results; page through them with `limit`/`offset`."""
    run = _run(run_id)
    limit = page.size()
    results = run.results.all()
    data: dict[str, Any] = {
        **run_summary_dict(run),
        "by_cluster": by_cluster(run),
        "results": [result_dict(r) for r in results[page.offset : page.offset + limit]],
    }
    return success(
        data,
        meta={"count": results.count(), "limit": limit, "offset": page.offset},
    )


def by_cluster(run: EvalRun) -> list[dict[str, Any]]:
    rows = (
        run.results.values("cluster_key")
        .annotate(
            total=Count("id"),
            correct=Count("id", filter=Q(outcome=EvalResult.OUTCOME_CORRECT)),
        )
        .order_by("cluster_key")
    )
    return [
        {
            "cluster_key": row["cluster_key"] or run_compare.UNCLUSTERED,
            "total": row["total"],
            "correct": row["correct"],
            "accuracy": round(row["correct"] / row["total"], 4),
        }
        for row in rows
    ]
