"""API shapes for runs and steps, and the dicts built from the models."""

from datetime import datetime, timedelta
from typing import Any, Literal

from django.conf import settings
from django.db.models import Exists, OuterRef, QuerySet, Subquery
from ninja import Schema

from agent import confidence
from agent.models import AgentRun, AgentStep, RunFeedback


class RunIn(Schema):
    question: str
    # One of your own workspaces; leave out for the shared demo.
    workspace: int | None = None


class EditIn(Schema):
    sql: str


class FeedbackIn(Schema):
    vote: Literal["up", "down"]
    # Why, in your words (optional, capped by FEEDBACK_NOTE_MAX_CHARS).
    note: str = ""


class FeedbackOut(Schema):
    run_id: int
    # Your vote, or null once you took it back.
    vote: Literal["up", "down"] | None
    note: str


class StepOut(Schema):
    index: int
    kind: str
    tool_name: str
    input: dict[str, Any]
    output: str
    status: str
    error_code: str
    input_tokens: int
    output_tokens: int
    latency_ms: int
    actor: str
    created_at: datetime


class RunOut(Schema):
    id: int
    question: str
    status: str
    error_code: str
    provider: str
    model: str
    key_source: str
    prompt_version: str
    plan: str
    final_sql: str
    row_count: int
    # 0 to 1, or null until the measured separation earns showing it
    # (CONFIDENCE_SHOW_SCORE). `check` is always there: "checked" or "needs_look".
    confidence: float | None
    check: str
    step_count: int
    llm_calls: int
    input_tokens: int
    output_tokens: int
    latency_ms: int
    revisions: int
    # The workspace the run asked about; null is the shared demo. It may name a
    # workspace that has since been deleted (the trace stays).
    workspace_id: int | None
    # True when the run succeeded: `GET /runs/{id}/result` has rows for it.
    has_result: bool
    # True when the person changed the SQL before it ran.
    edited: bool
    # The owner's vote on the run, or null.
    feedback: Literal["up", "down"] | None
    created_at: datetime
    finished_at: datetime | None


class DefaultKeyLimitOut(Schema):
    used: int
    allowed: int
    remaining: int
    # Midnight UTC, when the daily count starts again.
    resets_at: datetime


class CountLimitOut(Schema):
    count: int
    allowed: int


class OpenStreamsOut(Schema):
    # Across all users: the live-stream cap is global (small container).
    open: int
    allowed: int


class AgentLimitsOut(Schema):
    # The workspace asked about; null is the shared demo.
    workspace_id: int | None
    """Used against allowed, so the screen can warn before a 429. A user with
    their own key (`has_own_key`) does not spend the default key."""

    default_key: DefaultKeyLimitOut
    has_own_key: bool
    unfinished_runs: CountLimitOut
    streams: OpenStreamsOut


class PendingOut(Schema):
    """What a person is asked to approve, so the screen needs no step parsing."""

    sql: str
    rationale: str
    assumptions: list[str]
    # What the guard changed in the SQL, as codes: `limit_clamped`, `qualified_tables`.
    guard: list[str]
    # Which proposal this is: 0 for the first, up from there after a revision.
    revision: int
    # After this the run expires (AGENT_APPROVAL_TTL_SECONDS since the pause).
    expires_at: datetime


class RunDetailOut(RunOut):
    # Present only while the run is awaiting approval.
    pending: PendingOut | None
    steps: list[StepOut]


class ResultOut(Schema):
    run_id: int
    # The SQL that ran this time (the stored SQL after the guard's rewrite).
    sql: str
    columns: list[str]
    rows: list[list[Any]]
    row_count: int
    # True when the result was cut at the row or size cap.
    truncated: bool


def step_dict(step: AgentStep) -> dict[str, Any]:
    return StepOut(
        index=step.index,
        kind=step.kind,
        tool_name=step.tool_name,
        input=step.input,
        output=step.output,
        status=step.status,
        error_code=step.error_code,
        input_tokens=step.input_tokens,
        output_tokens=step.output_tokens,
        latency_ms=step.latency_ms,
        actor=step.actor,
        created_at=step.created_at,
    ).model_dump(mode="json")


def with_edited(runs: QuerySet[AgentRun]) -> QuerySet[AgentRun]:
    """Annotate runs with `edited_flag`, so a list needs no query per row."""
    return runs.annotate(
        edited_flag=Exists(
            AgentStep.objects.filter(
                run=OuterRef("pk"), kind=AgentStep.KIND_APPROVAL, input__edited=True
            )
        )
    )


def with_feedback(runs: QuerySet[AgentRun]) -> QuerySet[AgentRun]:
    """Annotate runs with `feedback_vote` (the owner's vote), so a list needs no
    query per row."""
    return runs.annotate(
        feedback_vote=Subquery(
            RunFeedback.objects.filter(run=OuterRef("pk"), user=OuterRef("user"))
            .order_by("-id")
            .values("vote")[:1]
        )
    )


def _vote(run: AgentRun) -> str | None:
    if hasattr(run, "feedback_vote"):
        return run.feedback_vote or None
    row = run.feedback.filter(user_id=run.user_id).values_list("vote", flat=True)
    return row.first()


def _edited(run: AgentRun) -> bool:
    flag = getattr(run, "edited_flag", None)
    if flag is not None:
        return bool(flag)
    return run.steps.filter(kind=AgentStep.KIND_APPROVAL, input__edited=True).exists()


def run_dict(run: AgentRun) -> dict[str, Any]:
    return {
        "id": run.pk,
        "question": run.question,
        "status": run.status,
        "error_code": run.error_code,
        "provider": run.provider,
        "model": run.model,
        "key_source": run.key_source,
        "prompt_version": run.prompt_version,
        "plan": run.plan,
        "final_sql": run.final_sql,
        "row_count": run.row_count,
        "confidence": None
        if run.confidence is None
        else confidence.visible(run.confidence),
        "check": run.check_label,
        "step_count": run.step_count,
        "llm_calls": run.llm_calls,
        "input_tokens": run.input_tokens,
        "output_tokens": run.output_tokens,
        "latency_ms": run.latency_ms,
        "revisions": run.revisions,
        "workspace_id": run.workspace_id,
        "has_result": run.status == AgentRun.STATUS_SUCCEEDED,
        "edited": _edited(run),
        "feedback": _vote(run),
        "created_at": run.created_at,
        "finished_at": run.finished_at,
    }


def pending_dict(run: AgentRun) -> dict[str, Any] | None:
    """The proposal the run waits on, read from its newest agent `approval` step
    (agent/loop.py `_pause` writes sql, rationale, assumptions, guard_rewrites and
    revision there). None unless the run is awaiting approval."""
    if run.status != AgentRun.STATUS_AWAITING_APPROVAL:
        return None
    step = (
        run.steps.filter(kind=AgentStep.KIND_APPROVAL, actor=AgentStep.ACTOR_AGENT)
        .order_by("-index")
        .first()
    )
    if step is None:
        return None
    data = step.input
    return PendingOut(
        sql=data.get("sql", ""),
        rationale=data.get("rationale", ""),
        assumptions=list(data.get("assumptions", [])),
        guard=list(data.get("guard_rewrites", [])),
        revision=int(data.get("revision", 0)),
        # `updated_at` is when the pause was saved; service._expired measures from it.
        expires_at=run.updated_at
        + timedelta(seconds=settings.AGENT_APPROVAL_TTL_SECONDS),
    ).model_dump(mode="json")


def run_detail_dict(run: AgentRun) -> dict[str, Any]:
    return {
        **run_dict(run),
        "pending": pending_dict(run),
        "steps": [step_dict(s) for s in run.steps.order_by("index")],
    }
