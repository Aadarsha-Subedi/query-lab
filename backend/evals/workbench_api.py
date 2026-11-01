"""The trace workbench API (step 6), for staff only: every route sits behind
`common.permissions.staff_only`, set once on the router."""

from datetime import datetime
from typing import Annotated, ClassVar, Literal, cast

from django.conf import settings
from django.http import HttpRequest
from ninja import FilterLookup, FilterSchema, Query, Router, Schema
from pydantic import Field

from accounts.models import User
from agent import schemas as agent_schemas
from common.exception.domain import NotFoundException
from common.order.domain import OrderingSchema
from common.permissions import staff_only
from common.response.domain import SuccessEnvelope, errors, success
from common.throttling.scoped import ResultThrottle
from evals import clustering, review, tasks, traces
from evals.models import TraceCase
from evals.workbench_schemas import (
    ApproveIn,
    CaseDetailOut,
    CaseOut,
    ClusterOut,
    DraftQueuedOut,
    RejectIn,
    TraceDetailOut,
    UnanswerableIn,
    case_dict,
    trace_detail_dict,
)

router = Router(tags=["workbench"], auth=staff_only)


class WorkbenchPageIn(Schema):
    limit: int | None = Field(None, ge=1)
    offset: int = Field(0, ge=0)

    def size(self) -> int:
        return min(
            self.limit or settings.PAGINATION_DEFAULT_LIMIT,
            settings.TRACES_PAGE_SIZE_MAX,
        )


RunStatus = Literal[
    "running", "awaiting_approval", "succeeded", "failed", "cancelled", "expired"
]


class TraceFilter(FilterSchema):
    """`?status=failed&edited=true&check=needs_look&q=orders&revisions_min=1`"""

    status: Annotated[list[RunStatus] | None, FilterLookup("status__in")] = None
    error_code: Annotated[str | None, FilterLookup("error_code")] = None
    check: Annotated[
        Literal["checked", "needs_look"] | None, FilterLookup("check_label")
    ] = None
    key_source: Annotated[str | None, FilterLookup("key_source")] = None
    revisions_min: Annotated[int | None, FilterLookup("revisions__gte")] = None
    edited: Annotated[bool | None, FilterLookup("edited_flag")] = None
    # The owner's vote: `up` or `down`.
    feedback: Annotated[Literal["up", "down"] | None, FilterLookup("feedback_vote")] = (
        None
    )
    q: Annotated[str | None, FilterLookup("question__icontains")] = None
    created_after: Annotated[datetime | None, FilterLookup("created_at__gte")] = None
    created_before: Annotated[datetime | None, FilterLookup("created_at__lte")] = None


class TraceOrdering(OrderingSchema):
    """`?ordering=-latency_ms`; the default is newest first."""

    allowed_fields: ClassVar[list[str]] = [
        "created_at",
        "latency_ms",
        "revisions",
        "llm_calls",
        "row_count",
    ]


@router.get(
    "/runs",
    response={
        200: SuccessEnvelope[list[agent_schemas.RunOut]],
        **errors(401, 403, 422, 429),
    },
)
def list_trace_runs(
    request: HttpRequest,
    page: Query[WorkbenchPageIn],
    filters: Query[TraceFilter],
    ordering: Query[TraceOrdering],
) -> dict:
    """Staff only. Runs on the shared demo that are allowed in evals (runs on a
    user workspace never appear). Filter by `status`, `error_code`, `check`
    (`checked` / `needs_look`), `key_source`, `revisions_min`, `edited`, `feedback` (`up`/`down`), `q` (text
    in the question) and `created_after` / `created_before`. Order by
    `created_at`, `latency_ms`, `revisions`, `llm_calls` or `row_count`, newest
    first by default. `meta.count` is the number of matches."""
    limit = page.size()
    runs = agent_schemas.with_feedback(
        agent_schemas.with_edited(traces.workbench_runs())
    )
    runs = ordering.apply(filters.filter(runs))
    runs = runs.order_by(*(runs.query.order_by or ("-created_at",)), "-id")
    items = [agent_schemas.run_dict(r) for r in runs[page.offset : page.offset + limit]]
    return success(
        items, meta={"count": runs.count(), "limit": limit, "offset": page.offset}
    )


@router.get(
    "/runs/{run_id}",
    response={200: SuccessEnvelope[TraceDetailOut], **errors(401, 403, 404, 429)},
)
def get_trace_run(request: HttpRequest, run_id: int) -> dict:
    """Staff only. One run in full: every step (plan, tools, approval, execute
    preview, reflect), the SQL the agent proposed first, the SQL finally approved
    and `diff` when the person edited it. Result rows are not stored, so none are
    shown beyond the stored preview. A workspace run is a 404."""
    run = traces.workbench_runs().filter(pk=run_id).first()
    if run is None:
        raise NotFoundException("Run not found.")
    return success(trace_detail_dict(run))


class CaseFilter(FilterSchema):
    """`?status=drafted&status=candidate&cluster=failed/ab12cd34ef`"""

    status: Annotated[
        list[Literal["candidate", "drafted", "approved", "rejected"]] | None,
        FilterLookup("status__in"),
    ] = None
    cluster: Annotated[str | None, FilterLookup("cluster_key")] = None


def _staff(request: HttpRequest) -> User:
    return cast(User, request.user)


@router.get(
    "/cases",
    response={200: SuccessEnvelope[list[CaseOut]], **errors(401, 403, 422, 429)},
)
def list_cases(
    request: HttpRequest, page: Query[WorkbenchPageIn], filters: Query[CaseFilter]
) -> dict:
    """Staff only. Trace cases, newest source run first, with the model's draft (or
    why it failed), the reasons the run was picked and a link to its trace. Filter by
    `status` (repeat it) and `cluster`. `meta.count` is the match count."""
    limit = page.size()
    cases = filters.filter(TraceCase.objects.all())
    items = [case_dict(c) for c in cases[page.offset : page.offset + limit]]
    return success(
        items, meta={"count": cases.count(), "limit": limit, "offset": page.offset}
    )


@router.post(
    "/cases/draft",
    response={200: SuccessEnvelope[DraftQueuedOut], **errors(401, 403, 429)},
)
def draft_cases(request: HttpRequest) -> dict:
    """Staff only. Queue a drafting batch (at most TRACES_DRAFT_MAX_PER_BATCH cases,
    one LLM call each, counted on your daily default-key allowance). Drafts show up
    on `GET /cases` as `drafted`."""
    tasks.draft_batch(_staff(request).pk)
    return success(DraftQueuedOut(queued=True).model_dump(), message="Batch queued.")


@router.get(
    "/cases/{case_id}",
    response={
        200: SuccessEnvelope[CaseDetailOut],
        **errors(401, 403, 404, 429),
    },
    throttle=[ResultThrottle()],
)
def get_case(request: HttpRequest, case_id: int) -> dict:
    """Staff only. One case with a preview of its rows: the draft is guarded and run
    on the reader now (the rows are shown, never stored)."""
    case = review.get_case(case_id)
    return success({**case_dict(case), "preview": review.preview(case)})


@router.post(
    "/cases/{case_id}/approve",
    response={
        200: SuccessEnvelope[CaseOut],
        **errors(400, 401, 403, 404, 409, 422, 429, 504),
    },
)
def approve_case(request: HttpRequest, case_id: int, payload: ApproveIn) -> dict:
    """Staff only. Make a drafted case gold. Send `sql` (and `question`) to correct
    them; either way the SQL is guarded and run again first. A draft that failed its
    checks needs `sql` (422 `draft_unusable`). 409 `case_not_reviewable` unless the
    case is `drafted`."""
    case = review.approve(
        _staff(request), case_id, question=payload.question, sql=payload.sql
    )
    return success(case_dict(case))


@router.post(
    "/cases/{case_id}/reject",
    response={200: SuccessEnvelope[CaseOut], **errors(401, 403, 404, 409, 429)},
)
def reject_case(request: HttpRequest, case_id: int, payload: RejectIn) -> dict:
    """Staff only. Keep a drafted case out of the eval set, with a reason."""
    return success(case_dict(review.reject(_staff(request), case_id, payload.reason)))


@router.post(
    "/cases/{case_id}/mark-unanswerable",
    response={200: SuccessEnvelope[CaseOut], **errors(401, 403, 404, 409, 429)},
)
def mark_case_unanswerable(
    request: HttpRequest, case_id: int, payload: UnanswerableIn
) -> dict:
    """Staff only. The right answer is to decline: approved with no gold SQL."""
    return success(
        case_dict(review.mark_unanswerable(_staff(request), case_id, payload.note))
    )


@router.get(
    "/clusters",
    response={200: SuccessEnvelope[list[ClusterOut]], **errors(401, 403, 429)},
)
def list_clusters(request: HttpRequest) -> dict:
    """Staff only. The trace cases grouped by outcome, tables and SQL shape, then
    merged when their questions overlap. Largest first, each with a label, a
    representative and its case counts per status. Computed from the stored
    `cluster_key`s (`build_trace_cases` and drafting refresh them)."""
    items = [
        ClusterOut(
            key=s.key,
            label=s.label,
            size=s.size,
            representative_id=s.representative_id,
            member_ids=list(s.member_ids),
            status_counts=s.status_counts,
        ).model_dump()
        for s in clustering.summaries()
    ]
    return success(items, meta={"count": len(items)})
