from typing import cast

from django.conf import settings
from django.http import HttpRequest, StreamingHttpResponse
from ninja import Query, Router, Schema
from ninja.security import django_auth
from pydantic import Field

from accounts.models import User
from agent import result, service, tasks
from agent.models import AgentRun
from agent.schemas import (
    EditIn,
    ResultOut,
    RunDetailOut,
    RunIn,
    RunOut,
    run_detail_dict,
    run_dict,
)
from agent.stream import EventStream
from common.response.domain import SuccessEnvelope, success
from common.throttling.scoped import AgentThrottle, ResultThrottle

router = Router(tags=["agent"])


class PageIn(Schema):
    limit: int | None = Field(None, ge=1)
    offset: int = Field(0, ge=0)


def _user(request: HttpRequest) -> User:
    return cast(User, request.user)


@router.post(
    "/runs",
    response=SuccessEnvelope[RunOut],
    auth=django_auth,
    throttle=[AgentThrottle()],
)
def create_run(request: HttpRequest, payload: RunIn) -> dict:
    """Start a run. The agent plans and proposes SQL, then waits for approval; follow
    it on `/runs/{id}/events`. One run counts as one spend of the shared default key."""
    run = service.create_run(_user(request), payload.question)
    tasks.start_run(run.pk)
    run.refresh_from_db()
    return success(run_dict(run), message="Run started.")


@router.get("/runs", response=SuccessEnvelope[list[RunOut]], auth=django_auth)
def list_runs(request: HttpRequest, page: Query[PageIn]) -> dict:
    """Your runs, newest first."""
    limit = min(
        page.limit or settings.PAGINATION_DEFAULT_LIMIT, settings.PAGINATION_MAX_LIMIT
    )
    runs = AgentRun.objects.filter(user=_user(request))
    items = [run_dict(r) for r in runs[page.offset : page.offset + limit]]
    return success(
        items, meta={"count": runs.count(), "limit": limit, "offset": page.offset}
    )


@router.get("/runs/{run_id}", response=SuccessEnvelope[RunDetailOut], auth=django_auth)
def get_run(request: HttpRequest, run_id: int) -> dict:
    """A run and its steps. Poll this when the live stream is not available."""
    return success(run_detail_dict(service.get_run(_user(request), run_id)))


def _decide(
    request: HttpRequest, run_id: int, decision: str, sql: str | None = None
) -> dict:
    run = service.decide(service.get_run(_user(request), run_id), decision, sql=sql)
    if run.status == AgentRun.STATUS_RUNNING:
        tasks.resume_run(run.pk)
        run.refresh_from_db()
    return success(run_dict(run))


@router.post(
    "/runs/{run_id}/approve", response=SuccessEnvelope[RunOut], auth=django_auth
)
def approve_run(request: HttpRequest, run_id: int) -> dict:
    """Run the SQL the agent proposed. Only while the run waits for approval."""
    return _decide(request, run_id, service.DECISION_APPROVE)


@router.post("/runs/{run_id}/edit", response=SuccessEnvelope[RunOut], auth=django_auth)
def edit_run(request: HttpRequest, run_id: int, payload: EditIn) -> dict:
    """Run your own SQL instead. It goes through the same guard; a refusal is a 400
    and the run stays paused."""
    return _decide(request, run_id, service.DECISION_EDIT, payload.sql)


@router.post(
    "/runs/{run_id}/cancel", response=SuccessEnvelope[RunOut], auth=django_auth
)
def cancel_run(request: HttpRequest, run_id: int) -> dict:
    """End a paused run without running anything."""
    return _decide(request, run_id, service.DECISION_CANCEL)


@router.get(
    "/runs/{run_id}/replay", response=SuccessEnvelope[RunDetailOut], auth=django_auth
)
def replay_run(request: HttpRequest, run_id: int) -> dict:
    """The stored trace in order. No model call and no query on the demo database:
    it is read from the steps alone."""
    return success(run_detail_dict(service.get_run(_user(request), run_id)))


@router.get(
    "/runs/{run_id}/result",
    response=SuccessEnvelope[ResultOut],
    auth=django_auth,
    throttle=[ResultThrottle()],
)
def run_result(request: HttpRequest, run_id: int) -> dict:
    """The rows of a succeeded run, up to the row cap. Rows are not stored: this
    runs the run's stored SQL again, through the guard, on the read-only
    connection. It never takes SQL from the request, so the numbers can differ
    from the first run if the data changed. 409 `run_not_succeeded` otherwise."""
    return success(result.fetch(service.get_run(_user(request), run_id)))


@router.get("/runs/{run_id}/events", auth=django_auth)
def run_events(request: HttpRequest, run_id: int) -> StreamingHttpResponse:
    """Server-sent events: `step` for each step, then one `status` event when the
    run pauses for approval or ends. Event ids are step indexes; reconnect with
    `Last-Event-ID` to continue. Over the open-stream limit it answers 429
    `agent_stream_limit`: poll `GET /runs/{id}` instead."""
    run = service.get_run(_user(request), run_id)
    header = request.headers.get("Last-Event-ID", "")
    last_index = int(header) if header.lstrip("-").isdigit() else -1
    stream = EventStream(run.pk, last_index)
    response = StreamingHttpResponse(stream, content_type="text/event-stream")
    response["Cache-Control"] = "no-cache"
    response["X-Accel-Buffering"] = "no"
    return response
