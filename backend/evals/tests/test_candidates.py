from datetime import timedelta
from typing import Any

import pytest
from django.core.management import call_command
from django.utils import timezone

from accounts.models import User
from agent.models import AgentRun, AgentStep, RunFeedback
from evals import candidates
from evals.models import TraceCase

pytestmark = pytest.mark.django_db


@pytest.fixture
def user(db: None) -> User:
    return User.objects.create_user("ada@example.com")


def make_run(user: User, **fields: Any) -> AgentRun:
    values: dict[str, Any] = {
        "question": "How many orders?",
        "provider": "gemini",
        "model": "fake-model",
        "key_source": "default",
        "prompt_version": "v2-agent",
        "status": AgentRun.STATUS_SUCCEEDED,
        "final_sql": "SELECT 1",
        "check_label": "checked",
    }
    values.update(fields)
    return AgentRun.objects.create(user=user, **values)


def reasons(run: AgentRun) -> set[str]:
    case = TraceCase.objects.get(source_run_id=run.pk)
    return set(case.reasons.split(","))


def test_each_rule_picks_its_runs_with_the_reason(user: User) -> None:
    plain = make_run(user)
    edited = make_run(user)
    AgentStep.objects.create(
        run=edited, index=0, kind="approval", input={"sql": "SELECT 2", "edited": True}
    )
    down = make_run(user)
    RunFeedback.objects.create(run=down, user=user, vote="down")
    liked = make_run(user)
    RunFeedback.objects.create(run=liked, user=user, vote="up")
    failed = make_run(user, status="failed", error_code="query_failed", final_sql="")
    revised = make_run(user, revisions=1)
    declined = make_run(
        user, status="failed", error_code="not_answerable", final_sql=""
    )
    looked = make_run(user, check_label="needs_look")

    assert candidates.build_candidates() == 6
    picked = set(TraceCase.objects.values_list("source_run_id", flat=True))
    assert picked == {r.pk for r in (edited, down, failed, revised, declined, looked)}
    assert plain.pk not in picked and liked.pk not in picked
    assert reasons(edited) == {"edited"}
    assert reasons(down) == {"thumbs_down"}
    assert reasons(failed) == {"failed"}
    assert reasons(revised) == {"revised"}
    assert reasons(declined) == {"failed", "not_answerable"}
    assert reasons(looked) == {"needs_look"}
    assert TraceCase.objects.get(source_run_id=declined.pk).signals == 2
    assert TraceCase.objects.get(source_run_id=declined.pk).answerable is False
    assert TraceCase.objects.get(source_run_id=declined.pk).outcome == "declined"
    assert TraceCase.objects.get(source_run_id=failed.pk).outcome == "error"
    assert TraceCase.objects.get(source_run_id=revised.pk).outcome == "answered"


def test_a_workspace_run_is_never_a_case(user: User) -> None:
    make_run(user, status="failed", workspace_id=7, excluded_from_evals=True)
    make_run(user, status="failed", excluded_from_evals=True)
    assert candidates.build_candidates() == 0


def test_eval_harness_runs_unfinished_runs_and_old_runs_are_skipped(
    user: User, settings: Any
) -> None:
    make_run(user, status="failed", key_source="eval")
    make_run(user, status=AgentRun.STATUS_RUNNING, revisions=2)
    make_run(user, status=AgentRun.STATUS_AWAITING_APPROVAL, revisions=2)
    old = make_run(user, status="failed")
    AgentRun.objects.filter(pk=old.pk).update(
        created_at=timezone.now()
        - timedelta(days=settings.TRACES_CANDIDATE_MAX_AGE_DAYS + 1)
    )
    assert candidates.build_candidates() == 0


def test_running_it_again_adds_nothing(user: User) -> None:
    make_run(user, status="failed")
    assert candidates.build_candidates() == 1
    assert candidates.build_candidates() == 0
    make_run(user, status="failed")
    assert candidates.build_candidates() == 1
    assert TraceCase.objects.count() == 2


def test_an_existing_case_is_left_alone(user: User) -> None:
    run = make_run(user, status="failed")
    candidates.build_candidates()
    TraceCase.objects.filter(source_run_id=run.pk).update(
        status="rejected", note="not useful"
    )
    candidates.build_candidates()
    case = TraceCase.objects.get()
    assert case.status == "rejected" and case.note == "not useful"


def test_a_failed_run_keeps_the_first_proposal_as_its_sql(user: User) -> None:
    run = make_run(user, status="failed", error_code="query_failed", final_sql="")
    AgentStep.objects.create(
        run=run, index=0, kind="approval", actor="agent", input={"sql": "SELECT bad"}
    )
    candidates.build_candidates()
    assert TraceCase.objects.get().source_sql == "SELECT bad"


def test_batches_cover_every_run(user: User, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(candidates, "BATCH", 2)
    for _ in range(5):
        make_run(user, status="failed")
    assert candidates.build_candidates() == 5


def test_the_command_reports_the_count(
    user: User, capsys: pytest.CaptureFixture
) -> None:
    make_run(user, status="failed")
    call_command("build_trace_cases")
    assert "1 new trace cases" in capsys.readouterr().out
