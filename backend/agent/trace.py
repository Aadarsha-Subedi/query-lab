"""The durable trace. Every step is written to Postgres first and only then
published as an event, so the stored steps are the source of truth and an event
is just a nudge to read them (agent/events.py)."""

import json
from typing import Any

from django.conf import settings
from django.db import transaction
from django.utils import timezone

from agent import events
from agent.models import AgentRun, AgentStep


def trim(text: str, limit: int | None = None) -> str:
    limit = limit or settings.AGENT_STEP_OUTPUT_MAX_CHARS
    return text if len(text) <= limit else text[: limit - 1] + "…"


def dump(value: Any) -> str:
    return json.dumps(value, default=str, separators=(",", ":"), ensure_ascii=False)


def record_step(
    run: AgentRun,
    kind: str,
    *,
    tool_name: str = "",
    input: dict[str, Any] | None = None,
    output: str = "",
    status: str = AgentStep.STATUS_OK,
    error_code: str = "",
    input_tokens: int = 0,
    output_tokens: int = 0,
    latency_ms: int = 0,
    actor: str = AgentStep.ACTOR_AGENT,
) -> AgentStep:
    """Append the next step to the run and publish it. Output is trimmed."""
    with transaction.atomic():
        step = AgentStep.objects.create(
            run=run,
            index=run.step_count,
            kind=kind,
            tool_name=tool_name[:40],
            input=input or {},
            output=trim(output),
            status=status,
            error_code=error_code,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            latency_ms=latency_ms,
            actor=actor,
        )
        run.step_count += 1
        run.save(update_fields=["step_count", "updated_at"])
    events.publish_step(run.pk, step.index)
    return step


def close_run(
    run: AgentRun,
    status: str,
    *,
    output: str = "",
    error_code: str = "",
    actor: str = AgentStep.ACTOR_AGENT,
    detail: dict[str, Any] | None = None,
) -> AgentRun:
    """Write the `final` step, set the terminal status and publish both."""
    record_step(
        run,
        AgentStep.KIND_FINAL,
        input={"status": status, **(detail or {})},
        output=output,
        status=AgentStep.STATUS_OK
        if status == AgentRun.STATUS_SUCCEEDED
        else AgentStep.STATUS_ERROR,
        error_code=error_code,
        actor=actor,
    )
    run.status = status
    run.error_code = error_code
    run.finished_at = timezone.now()
    run.save()
    events.publish_status(run.pk)
    return run
