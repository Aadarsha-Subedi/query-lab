"""Pick the stored runs worth turning into eval cases (step 6).

Fixed rules, each recorded as a reason on the case. A run is skipped when it is on
a user workspace, was marked `excluded_from_evals`, came from the eval harness
itself, is still going, is older than TRACES_CANDIDATE_MAX_AGE_DAYS, or already
is a case. Rows are read and written in batches, never all at once."""

from datetime import timedelta

from django.conf import settings
from django.db.models import OuterRef, Q, QuerySet, Subquery
from django.utils import timezone

from agent import schemas as agent_schemas
from agent.errors import CODE_NOT_ANSWERABLE
from agent.models import AgentRun, AgentStep
from evals import traces
from evals.models import TraceCase

BATCH = 500
KEY_SOURCE_EVAL = "eval"  # the harness's own runs (evals/agent_runner.py)


def outcome_of(run: AgentRun) -> str:
    if run.status == AgentRun.STATUS_SUCCEEDED:
        return TraceCase.OUTCOME_ANSWERED
    if run.status == AgentRun.STATUS_FAILED:
        if run.error_code == CODE_NOT_ANSWERABLE:
            return TraceCase.OUTCOME_DECLINED
        return TraceCase.OUTCOME_ERROR
    return TraceCase.OUTCOME_UNFINISHED


def reasons_of(run: AgentRun) -> list[str]:
    """Which rules pick this run (annotated by `eligible`)."""
    found = []
    if run.edited_flag:  # type: ignore[attr-defined]
        found.append(TraceCase.REASON_EDITED)
    if run.feedback_vote == "down":  # type: ignore[attr-defined]
        found.append(TraceCase.REASON_THUMBS_DOWN)
    if run.status == AgentRun.STATUS_FAILED:
        found.append(TraceCase.REASON_FAILED)
    if run.revisions >= 1:
        found.append(TraceCase.REASON_REVISED)
    if run.error_code == CODE_NOT_ANSWERABLE:
        found.append(TraceCase.REASON_NOT_ANSWERABLE)
    if run.check_label == "needs_look":
        found.append(TraceCase.REASON_NEEDS_LOOK)
    return found


def eligible() -> QuerySet[AgentRun]:
    """Runs a rule picks, newest first, with `edited_flag`, `feedback_vote` and
    `first_proposal` annotated (no query per row)."""
    cutoff = timezone.now() - timedelta(days=settings.TRACES_CANDIDATE_MAX_AGE_DAYS)
    first_proposal = (
        AgentStep.objects.filter(
            run=OuterRef("pk"),
            kind=AgentStep.KIND_APPROVAL,
            actor=AgentStep.ACTOR_AGENT,
        )
        .order_by("index")
        .values("input__sql")[:1]
    )
    runs = agent_schemas.with_feedback(
        agent_schemas.with_edited(traces.workbench_runs())
    )
    return (
        runs.filter(status__in=AgentRun.TERMINAL, created_at__gte=cutoff)
        .exclude(key_source=KEY_SOURCE_EVAL)
        .exclude(
            pk__in=TraceCase.objects.exclude(source_run_id=None).values("source_run_id")
        )
        .filter(
            Q(edited_flag=True)
            | Q(feedback_vote="down")
            | Q(status=AgentRun.STATUS_FAILED)
            | Q(revisions__gte=1)
            | Q(error_code=CODE_NOT_ANSWERABLE)
            | Q(check_label="needs_look")
        )
        .annotate(first_proposal=Subquery(first_proposal))
        .order_by("-created_at", "-id")
    )


def case_from(run: AgentRun) -> TraceCase:
    reasons = reasons_of(run)
    return TraceCase(
        source_run_id=run.pk,
        source_created_at=run.created_at,
        question=run.question,
        reasons=",".join(reasons),
        signals=len(reasons),
        outcome=outcome_of(run),
        source_sql=run.final_sql or (run.first_proposal or ""),  # type: ignore[attr-defined]
        answerable=run.error_code != CODE_NOT_ANSWERABLE,
    )


def build_candidates() -> int:
    """Create a case for every run a rule picks that is not a case yet. Safe to
    run again: it only ever adds. Returns how many cases were made."""
    made = 0
    batch: list[TraceCase] = []
    for run in eligible().iterator(chunk_size=BATCH):
        batch.append(case_from(run))
        if len(batch) >= BATCH:
            made += _save(batch)
            batch = []
    return made + _save(batch)


def _save(batch: list[TraceCase]) -> int:
    if not batch:
        return 0
    before = TraceCase.objects.count()
    TraceCase.objects.bulk_create(batch, ignore_conflicts=True)
    return TraceCase.objects.count() - before
