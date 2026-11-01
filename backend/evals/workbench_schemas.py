"""API shapes of the staff-only trace workbench."""

from datetime import datetime
from typing import Any

from ninja import Schema

from agent import schemas as agent_schemas
from agent.models import AgentRun
from evals import traces
from evals.models import TraceCase


class TraceDetailOut(agent_schemas.RunDetailOut):
    # The SQL the agent proposed first, and the SQL that finally ran.
    proposed_sql: str
    approved_sql: str
    # True when the person changed the SQL before it ran.
    diff: bool


def trace_detail_dict(run: AgentRun) -> dict[str, Any]:
    base = agent_schemas.run_detail_dict(run)
    return {
        **base,
        "proposed_sql": traces.proposed_sql(run),
        "approved_sql": run.final_sql,
        "diff": base["edited"],
    }


class CaseOut(Schema):
    id: int
    # The run this came from, and where to read its trace (null if it is gone).
    run_id: int | None
    trace_path: str | None
    question: str
    reasons: list[str]
    signals: int
    outcome: str
    source_sql: str
    status: str
    cluster_key: str
    draft_sql: str
    draft_model: str
    draft_error: str
    drafted_at: datetime | None
    # Set on approval only; empty for a case whose right answer is to decline.
    gold_sql: str
    answerable: bool
    reviewer_id: int | None
    reviewed_at: datetime | None
    note: str
    created_at: datetime


class CasePreviewOut(Schema):
    columns: list[str] = []
    rows: list[list[Any]] = []
    row_count: int = 0
    truncated: bool = False
    error: str = ""


class CaseDetailOut(CaseOut):
    # The first rows of the draft or the gold, run now; null when there is no SQL.
    preview: CasePreviewOut | None


class ApproveIn(Schema):
    # Edit either one before approving; leave out to take the draft as it is.
    question: str | None = None
    sql: str | None = None


class RejectIn(Schema):
    reason: str


class UnanswerableIn(Schema):
    note: str = ""


class DraftQueuedOut(Schema):
    queued: bool


def case_dict(case: TraceCase) -> dict[str, Any]:
    return CaseOut(
        id=case.pk,
        run_id=case.source_run_id,
        trace_path=(
            f"/api/workbench/runs/{case.source_run_id}" if case.source_run_id else None
        ),
        question=case.question,
        reasons=[r for r in case.reasons.split(",") if r],
        signals=case.signals,
        outcome=case.outcome,
        source_sql=case.source_sql,
        status=case.status,
        cluster_key=case.cluster_key,
        draft_sql=case.draft_sql,
        draft_model=case.draft_model,
        draft_error=case.draft_error,
        drafted_at=case.drafted_at,
        gold_sql=case.gold_sql,
        answerable=case.answerable,
        reviewer_id=case.reviewer_id,
        reviewed_at=case.reviewed_at,
        note=case.note,
        created_at=case.created_at,
    ).model_dump(mode="json")


class ClusterOut(Schema):
    # Stable while the cases stay the same; also the tag on eval results.
    key: str
    label: str
    size: int
    # The case that stands for the cluster (most signals, then newest).
    representative_id: int
    member_ids: list[int]
    # Cases per status: candidate, drafted, approved, rejected.
    status_counts: dict[str, int]
