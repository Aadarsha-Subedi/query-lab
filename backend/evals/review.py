"""A person's decisions on drafted trace cases (step 6).

Only `approve` makes gold: the SQL is guarded and run on the reader again, so a
reviewer's edit is held to the same rules as the model's draft. Rows are checked
for a run and dropped, never stored on the case."""

from typing import Any

from django.conf import settings
from django.utils import timezone

from accounts.models import User
from ask import guard, prompt, runner, schema
from ask.errors import GuardRejected
from evals.errors import CaseNotFound, CaseNotReviewable, DraftUnusable
from evals.models import TraceCase


def get_case(case_id: int) -> TraceCase:
    case = TraceCase.objects.filter(pk=case_id).first()
    if case is None:
        raise CaseNotFound()
    return case


def _reviewable(case_id: int) -> TraceCase:
    case = get_case(case_id)
    if case.status != TraceCase.STATUS_DRAFTED:
        raise CaseNotReviewable()
    return case


def checked_sql(sql: str) -> str:
    """Guard `sql` and run it on the reader; return the SQL as the guard wrote it.
    A refusal says why in `errors[0]`, like editing a run's SQL does."""
    known = schema.get_schema(include_samples=True)
    try:
        checked = guard.check(sql, known)
    except GuardRejected as refusal:
        reason = GuardRejected(refusal.detail)
        reason.errors = [{"field": "sql", "message": refusal.detail}]
        raise reason from None
    runner.run(checked.sql)
    return checked.sql


def approve(
    user: User, case_id: int, *, question: str | None = None, sql: str | None = None
) -> TraceCase:
    case = _reviewable(case_id)
    if sql is None and case.draft_error:
        raise DraftUnusable()
    gold = checked_sql(case.draft_sql if sql is None else sql)
    if question is not None:
        case.question = prompt.validate_question(question)
    case.gold_sql = gold
    case.answerable = True
    case.status = TraceCase.STATUS_APPROVED
    return _decided(case, user)


def reject(user: User, case_id: int, reason: str) -> TraceCase:
    case = _reviewable(case_id)
    case.note = reason.strip()[: TraceCase._meta.get_field("note").max_length]
    case.status = TraceCase.STATUS_REJECTED
    return _decided(case, user)


def mark_unanswerable(user: User, case_id: int, note: str) -> TraceCase:
    """The right answer is to decline: approved, with no gold SQL."""
    case = _reviewable(case_id)
    case.answerable = False
    case.gold_sql = ""
    case.note = note.strip()[: TraceCase._meta.get_field("note").max_length]
    case.status = TraceCase.STATUS_APPROVED
    return _decided(case, user)


def _decided(case: TraceCase, user: User) -> TraceCase:
    case.reviewer = user
    case.reviewed_at = timezone.now()
    case.save()
    return case


def preview(case: TraceCase) -> dict[str, Any] | None:
    """The first rows of the draft (or the gold, once approved), for the reviewer.
    Run now and returned, never stored."""
    sql = case.gold_sql or case.draft_sql
    if not sql or not case.answerable:
        return None
    try:
        result = runner.run(checked_sql_only(sql))
    except Exception as error:  # noqa: BLE001 - shown to staff as a short message
        return {"error": prompt.first_line(str(getattr(error, "detail", error)))}
    limit = settings.AGENT_RESULT_PREVIEW_ROWS
    return {
        "columns": result.columns,
        "rows": result.rows[:limit],
        "row_count": result.row_count,
        "truncated": result.truncated or result.row_count > limit,
        "error": "",
    }


def checked_sql_only(sql: str) -> str:
    return guard.check(sql, schema.get_schema(include_samples=True)).sql
