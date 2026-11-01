import pytest
from django.core.management import call_command
from django.core.management.base import CommandError
from django.utils import timezone

from accounts.models import User
from agent.models import AgentRun
from evals import confidence_analysis
from evals.models import TraceCase

pytestmark = pytest.mark.django_db


def fake_rows(sql: str) -> list[list]:
    if "boom" in sql:
        raise RuntimeError("no such column")
    return [[1]] if "good" in sql else [[2]]


@pytest.fixture
def user(db: None) -> User:
    return User.objects.create_user("a@example.com")


def labelled(user: User, n: int, sql: str, label: str, confidence: float, **kw) -> None:
    run = AgentRun.objects.create(
        user=user,
        question="q",
        provider="gemini",
        model="m",
        key_source="default",
        prompt_version="v2-agent",
        status="succeeded",
        final_sql=sql,
        check_label=label,
        confidence=confidence,
        row_count=1,
        revisions=kw.get("revisions", 0),
    )
    TraceCase.objects.create(
        source_run_id=run.pk,
        source_created_at=timezone.now(),
        question="q",
        reasons="failed",
        outcome="answered",
        status=kw.get("status", "approved"),
        gold_sql="SELECT good",
        answerable=kw.get("answerable", True),
    )


def test_labels_features_and_rank_correlation(user: User) -> None:
    labelled(user, 1, "SELECT good 1", "checked", 0.9)
    labelled(user, 2, "SELECT good 2", "checked", 0.8)
    labelled(user, 3, "SELECT bad", "needs_look", 0.3, revisions=1)
    labelled(user, 4, "SELECT boom", "needs_look", 0.4, revisions=2)
    labelled(user, 5, "SELECT good 5", "checked", 0.1, status="drafted")
    labelled(user, 6, "SELECT good 6", "checked", 0.1, answerable=False)
    result = confidence_analysis.analyse_cases(fake_rows)
    assert (result.answered, result.right) == (4, 2)
    by = {row.label: (row.n, row.right) for row in result.labels}
    assert by == {"checked": (2, 2), "needs_look": (2, 0)}
    assert "no_revision" in result.varied
    assert result.rank_correlation is not None and result.rank_correlation > 0.8
    text = confidence_analysis.format_case_analysis(result)
    assert "checked" in text and "Rank correlation" in text


def test_a_run_that_is_gone_is_skipped(user: User) -> None:
    TraceCase.objects.create(
        source_run_id=999999,
        source_created_at=timezone.now(),
        question="q",
        reasons="failed",
        outcome="answered",
        status="approved",
        gold_sql="SELECT good",
    )
    assert confidence_analysis.analyse_cases(fake_rows).answered == 0


def test_the_command_needs_one_source(capsys: pytest.CaptureFixture[str]) -> None:
    with pytest.raises(CommandError, match="exactly one"):
        call_command("confidence_report")
    call_command("confidence_report", cases=True)
    assert "Reviewed trace cases: 0" in capsys.readouterr().out
