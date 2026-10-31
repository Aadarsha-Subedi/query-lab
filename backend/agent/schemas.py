"""API shapes for runs and steps, and the dicts built from the models."""

from datetime import datetime
from typing import Any

from ninja import Schema

from agent import confidence
from agent.models import AgentRun, AgentStep


class RunIn(Schema):
    question: str


class EditIn(Schema):
    sql: str


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
    created_at: datetime
    finished_at: datetime | None


class RunDetailOut(RunOut):
    steps: list[StepOut]


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
        "created_at": run.created_at,
        "finished_at": run.finished_at,
    }


def run_detail_dict(run: AgentRun) -> dict[str, Any]:
    return {
        **run_dict(run),
        "steps": [step_dict(s) for s in run.steps.order_by("index")],
    }
