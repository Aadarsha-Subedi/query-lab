import pytest

from accounts.models import User
from agent.models import AgentRun

pytestmark = pytest.mark.django_db


def test_a_run_is_on_the_demo_and_in_evals_by_default(user: User) -> None:
    run = AgentRun.objects.create(
        user=user,
        question="q",
        provider="g",
        model="m",
        key_source="default",
        prompt_version="v",
    )
    assert run.workspace_id is None and run.excluded_from_evals is False


def test_a_run_keeps_its_workspace_id_after_the_workspace_is_gone(user: User) -> None:
    run = AgentRun.objects.create(
        user=user,
        question="q",
        provider="g",
        model="m",
        key_source="default",
        prompt_version="v",
        workspace_id=424242,
        excluded_from_evals=True,
    )
    run.refresh_from_db()
    assert run.workspace_id == 424242 and run.excluded_from_evals
