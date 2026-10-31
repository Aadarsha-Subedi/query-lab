import pytest
from django.db import IntegrityError

from evals.models import EvalResult, EvalRun

pytestmark = pytest.mark.django_db


def make_run() -> EvalRun:
    return EvalRun.objects.create(
        target=EvalRun.TARGET_OLIST,
        provider="gemini",
        model="m",
        prompt_version="v1",
    )


def test_run_defaults_to_running_all_questions() -> None:
    run = make_run()
    assert run.status == EvalRun.STATUS_RUNNING
    assert run.split == EvalRun.SPLIT_ALL
    assert run.finished_at is None


def test_results_belong_to_a_run_and_ids_are_unique_within_it() -> None:
    run = make_run()
    EvalResult.objects.create(
        run=run, question_id="q1", question="?", gold_sql="SELECT 1", outcome="correct"
    )
    assert run.results.count() == 1
    with pytest.raises(IntegrityError):
        EvalResult.objects.create(
            run=run, question_id="q1", question="?", gold_sql="x", outcome="wrong"
        )


def test_no_field_can_hold_result_rows() -> None:
    names = {field.name for field in EvalResult._meta.get_fields()}
    assert not names & {"rows", "gold_rows", "predicted_rows", "result", "columns"}
