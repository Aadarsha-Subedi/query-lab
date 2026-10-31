import pytest
from django.db import IntegrityError, transaction
from django.utils import timezone

from evals.models import TraceCase

pytestmark = pytest.mark.django_db


def make(source_run_id: int | None) -> TraceCase:
    return TraceCase.objects.create(
        source_run_id=source_run_id,
        source_created_at=timezone.now(),
        question="How many orders?",
        reasons="failed",
        outcome=TraceCase.OUTCOME_ERROR,
    )


def test_a_run_becomes_one_case_only() -> None:
    make(5)
    with pytest.raises(IntegrityError), transaction.atomic():
        make(5)


def test_cases_without_a_run_do_not_clash() -> None:
    make(None)
    make(None)
    assert TraceCase.objects.count() == 2


def test_a_new_case_is_a_candidate_with_no_gold() -> None:
    case = make(1)
    assert case.status == TraceCase.STATUS_CANDIDATE
    assert case.gold_sql == "" and case.draft_sql == "" and case.answerable
