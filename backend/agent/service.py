"""Starting a run and applying the user's decision on a paused one.

All writes that change a run's course take the run's lock without waiting, so an
approve click and the worker (or two clicks) cannot both act: the second gets a
typed 409."""

import logging
from datetime import timedelta

from django.conf import settings
from django.db import transaction
from django.utils import timezone

from accounts.models import User
from agent import events, prompts, state, trace
from agent.errors import (
    CODE_WORKER_LOST,
    RunExpired,
    RunLimitReached,
    RunNotAwaitingApproval,
    RunNotFound,
)
from agent.models import AgentRun, AgentStep
from ask import guard, keys, schema
from ask import prompt as ask_prompt
from ask.errors import GuardRejected
from common.exception.domain import ConflictException
from workspaces.context import DEMO, WorkspaceRef
from workspaces.resolve import resolve

logger = logging.getLogger(__name__)

DECISION_APPROVE = "approve"
DECISION_EDIT = "edit"
DECISION_CANCEL = "cancel"


class RunBusy(ConflictException):
    message = "This run is being worked on. Try again in a moment."
    error_code = "run_busy"


def get_run(user: User, run_id: int) -> AgentRun:
    """A run of this user; someone else's run looks like a run that does not exist."""
    run = AgentRun.objects.filter(pk=run_id, user=user).first()
    if run is None:
        raise RunNotFound()
    return run


def create_run(user: User, question: str, workspace: WorkspaceRef = DEMO) -> AgentRun:
    """Validate, take the key (one default-key spend per run), store the run.
    The caller enqueues `start_run`."""
    question = ask_prompt.validate_question(question)
    with transaction.atomic():
        # Serialise a user's starts, so two at once cannot both slip under the cap.
        User.objects.select_for_update().get(pk=user.pk)
        expire_stale(user=user)
        active = AgentRun.objects.filter(user=user, status__in=AgentRun.ACTIVE).count()
        if active >= settings.AGENT_MAX_CONCURRENT_RUNS_PER_USER:
            raise RunLimitReached()
        resolved = keys.resolve_provider(user)
        if resolved.key_source == keys.KEY_DEFAULT:
            keys.spend_default_key(user)
        return AgentRun.objects.create(
            user=user,
            question=question,
            provider=resolved.provider_name,
            model=resolved.provider.model,
            key_source=resolved.key_source,
            prompt_version=prompts.PROMPT_VERSION,
            workspace_id=workspace.id,
            excluded_from_evals=not workspace.is_demo,
        )


def _expired(run: AgentRun) -> bool:
    age = timezone.now() - run.updated_at
    return age > timedelta(seconds=settings.AGENT_APPROVAL_TTL_SECONDS)


def _expire(run: AgentRun) -> None:
    trace.close_run(
        run,
        AgentRun.STATUS_EXPIRED,
        output="Nobody approved the SQL in time.",
        error_code=RunExpired.error_code,
    )
    state.delete(run.pk)


def expire_stale(user: User | None = None) -> int:
    """End paused runs nobody answered, and fail running ones whose worker died.
    Called before a user starts a run and by the periodic Huey task."""
    now = timezone.now()
    paused = AgentRun.objects.filter(
        status=AgentRun.STATUS_AWAITING_APPROVAL,
        updated_at__lt=now - timedelta(seconds=settings.AGENT_APPROVAL_TTL_SECONDS),
    )
    stuck = AgentRun.objects.filter(
        status=AgentRun.STATUS_RUNNING,
        updated_at__lt=now - timedelta(seconds=2 * settings.AGENT_RUN_TIMEOUT_SECONDS),
    )
    if user is not None:
        paused, stuck = paused.filter(user=user), stuck.filter(user=user)
    count = 0
    for run in paused:
        with state.run_lock(run.pk) as acquired:
            if acquired:
                run.refresh_from_db()
                if run.status == AgentRun.STATUS_AWAITING_APPROVAL:
                    _expire(run)
                    count += 1
    for run in stuck:
        with state.run_lock(run.pk) as acquired:
            if acquired:
                run.refresh_from_db()
                if run.status == AgentRun.STATUS_RUNNING:
                    trace.close_run(
                        run,
                        AgentRun.STATUS_FAILED,
                        output="The worker stopped before the run finished.",
                        error_code=CODE_WORKER_LOST,
                    )
                    state.delete(run.pk)
                    count += 1
    return count


def decide(
    run: AgentRun,
    decision: str,
    *,
    sql: str | None = None,
    actor: str = AgentStep.ACTOR_USER,
) -> AgentRun:
    """Apply approve, edit or cancel to a paused run. Edited SQL goes through the
    guard first: a refusal raises GuardRejected and the run stays paused. Approve
    and edit only mark the run running again; the caller enqueues `resume_run`,
    which is what executes."""
    with state.run_lock(run.pk) as acquired:
        if not acquired:
            raise RunBusy()
        run.refresh_from_db()
        if run.status != AgentRun.STATUS_AWAITING_APPROVAL:
            raise RunNotAwaitingApproval()
        if _expired(run):
            _expire(run)
            raise RunExpired()
        current = state.load(run)
        if decision == DECISION_CANCEL:
            trace.record_step(
                run,
                AgentStep.KIND_APPROVAL,
                input={"decision": DECISION_CANCEL},
                output="Cancelled by the user.",
                actor=actor,
            )
            trace.close_run(
                run,
                AgentRun.STATUS_CANCELLED,
                output="Cancelled by the user.",
                actor=actor,
            )
            state.delete(run.pk)
            return run
        edited = decision == DECISION_EDIT
        if edited:
            assert sql is not None
            try:
                known = schema.get_schema(
                    resolve(run.workspace_id), include_samples=True
                )
                checked = guard.check(sql, known)
            except GuardRejected as refusal:
                # Say why. The reason only names what the user's own SQL contains
                # (a statement kind, a function, a table or column they wrote).
                reason = GuardRejected(refusal.detail)
                reason.errors = [{"field": "sql", "message": refusal.detail}]
                raise reason from None
            current.pending_sql = checked.sql
            current.pending_rewrites = list(checked.report.rewrites)
            current.edited = True
        current.decided_by = actor
        current.phase = state.PHASE_EXECUTE
        trace.record_step(
            run,
            AgentStep.KIND_APPROVAL,
            input={
                "decision": decision,
                "sql": current.pending_sql,
                "edited": current.edited,
            },
            output="Edited by the user." if edited else "Approved.",
            actor=actor,
        )
        run.status = AgentRun.STATUS_RUNNING
        run.save(update_fields=["status", "updated_at"])
        state.save(current)
        events.publish_status(run.pk)
    return run
