"""The trace workbench API (step 6), for staff only: every route sits behind
`common.permissions.staff_only`, set once on the router."""

from datetime import datetime
from typing import Annotated, ClassVar, Literal

from django.conf import settings
from django.http import HttpRequest
from ninja import FilterLookup, FilterSchema, Query, Router, Schema
from pydantic import Field

from agent import schemas as agent_schemas
from common.exception.domain import NotFoundException
from common.order.domain import OrderingSchema
from common.permissions import staff_only
from common.response.domain import SuccessEnvelope, errors, success
from evals import traces
from evals.workbench_schemas import TraceDetailOut, trace_detail_dict

router = Router(tags=["workbench"], auth=staff_only)


class PageIn(Schema):
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
    page: Query[PageIn],
    filters: Query[TraceFilter],
    ordering: Query[TraceOrdering],
) -> dict:
    """Staff only. Runs on the shared demo that are allowed in evals (runs on a
    user workspace never appear). Filter by `status`, `error_code`, `check`
    (`checked` / `needs_look`), `key_source`, `revisions_min`, `edited`, `q` (text
    in the question) and `created_after` / `created_before`. Order by
    `created_at`, `latency_ms`, `revisions`, `llm_calls` or `row_count`, newest
    first by default. `meta.count` is the number of matches."""
    limit = page.size()
    runs = agent_schemas.with_edited(traces.workbench_runs())
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
