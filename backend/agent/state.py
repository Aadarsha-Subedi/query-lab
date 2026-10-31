"""Working state of an active run, in Redis under `agent:run:{id}` with a TTL.

It is only what the loop needs to carry on after a pause: the plan, the history
the model sees, the SQL waiting for approval. Counters and totals live on the
AgentRun row. If the key is gone (TTL, a Redis flush, a restart) a paused run is
rebuilt from its stored steps, so Redis is a cache of the trace, not its owner.

One writer at a time: a Redis lock per run, held while the loop works or a
decision is applied."""

import json
import logging
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import asdict, dataclass, field
from typing import Any

from django.conf import settings
from redis.exceptions import LockError

from agent.models import AgentRun, AgentStep
from common.redis import get_redis

logger = logging.getLogger(__name__)

PHASE_PLAN = "plan"
PHASE_ACT = "act"
PHASE_EXECUTE = "execute"
PHASE_REFLECT = "reflect"
PHASE_FINISH = "finish"


@dataclass
class RunState:
    run_id: int
    phase: str = PHASE_PLAN
    plan: str = ""
    assumptions: list[str] = field(default_factory=list)
    history: list[str] = field(default_factory=list)
    # SQL waiting for approval (or for execution, once approved) and why.
    pending_sql: str = ""
    pending_rationale: str = ""
    pending_rewrites: list[str] = field(default_factory=list)
    edited: bool = False
    # Who approved the SQL that will run or ran: "user" (or "eval").
    decided_by: str = ""
    proposals: int = 0
    executed: bool = False
    samples_checked: list[str] = field(default_factory=list)
    # None until the first look at a result; then whether that look passed.
    reflect_ok: bool | None = None
    last_error: str = ""
    last_summary: str = ""
    truncated: bool = False
    # Why the last result went to reflect (empty, truncated, single_value, always).
    trigger: str = ""
    answer: str = ""


def run_key(run_id: int) -> str:
    return f"agent:run:{run_id}"


def lock_key(run_id: int) -> str:
    return f"agent:lock:{run_id}"


def save(state: RunState) -> None:
    get_redis().set(
        run_key(state.run_id),
        json.dumps(asdict(state)),
        ex=settings.AGENT_STATE_TTL_SECONDS,
    )


def delete(run_id: int) -> None:
    get_redis().delete(run_key(run_id))


def _from_json(raw: bytes | str) -> RunState:
    data: dict[str, Any] = json.loads(raw)
    return RunState(**data)


def load(run: AgentRun) -> RunState:
    """The run's state from Redis, rebuilt from its steps when the key is gone,
    or a fresh one for a run that has not started."""
    if run.step_count == 0:  # not started: any key under this id is not ours
        return RunState(run_id=run.pk)
    raw = get_redis().get(run_key(run.pk))
    if raw is not None:
        return _from_json(raw)
    logger.warning("Run %s state missing in Redis; rebuilding from steps", run.pk)
    return rebuild(run)


def rebuild(run: AgentRun) -> RunState:
    """Rebuild a paused run (or one just approved) from its stored steps. A run
    that was mid-turn when its worker died cannot be rebuilt: the reaper fails it."""
    from agent import prompts  # local import: prompts imports tools

    limit = settings.AGENT_STEP_OUTPUT_MAX_CHARS
    state = RunState(run_id=run.pk, phase=PHASE_ACT)
    for step in run.steps.order_by("index"):
        if step.kind == AgentStep.KIND_PLAN:
            state.plan = step.output
            state.assumptions = list(step.input.get("assumptions", []))
        elif step.kind == AgentStep.KIND_TOOL:
            label = step.tool_name
            if step.status == AgentStep.STATUS_ERROR:
                state.history.append(
                    prompts.history_entry(f"{label} error", step.output, limit)
                )
            else:
                state.history.append(prompts.history_entry(label, step.output, limit))
            if step.status == AgentStep.STATUS_OK:
                if step.tool_name == "sample_values":
                    state.samples_checked.append(
                        f"{step.input.get('table')}.{step.input.get('column')}"
                    )
                if step.tool_name == "propose_sql":
                    state.proposals += 1
        elif step.kind == AgentStep.KIND_APPROVAL:
            if step.actor == AgentStep.ACTOR_AGENT:
                state.pending_sql = step.input.get("sql", "")
                state.pending_rationale = step.input.get("rationale", "")
                state.pending_rewrites = list(step.input.get("guard_rewrites", []))
            elif step.input.get("decision") in ("approve", "edit"):
                state.pending_sql = step.input.get("sql", "")
                state.edited = bool(step.input.get("edited"))
                state.decided_by = step.actor
                state.phase = PHASE_EXECUTE
        elif step.kind == AgentStep.KIND_EXECUTE and step.status == AgentStep.STATUS_OK:
            state.executed = True
    return state


@contextmanager
def run_lock(run_id: int) -> Iterator[bool]:
    """Try to take the run's lock without waiting; yields whether it was taken.
    The lock expires on its own after twice the run timeout, in case a worker dies."""
    lock = get_redis().lock(
        lock_key(run_id),
        timeout=2 * settings.AGENT_RUN_TIMEOUT_SECONDS,
        blocking=False,
    )
    acquired = lock.acquire()
    try:
        yield acquired
    finally:
        if acquired:
            try:
                lock.release()
            except LockError:  # expired under us; nothing left to release
                logger.warning("Run %s lock had already expired", run_id)
