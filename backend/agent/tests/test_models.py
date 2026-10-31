import pytest
from django.db import IntegrityError, transaction

from agent.models import AgentRun, AgentStep, IllegalTransition

pytestmark = pytest.mark.django_db


def test_run_has_ordered_steps(run: AgentRun) -> None:
    AgentStep.objects.create(run=run, index=1, kind=AgentStep.KIND_TOOL)
    AgentStep.objects.create(run=run, index=0, kind=AgentStep.KIND_PLAN)
    assert [s.index for s in run.steps.all()] == [0, 1]
    assert AgentRun.objects.filter(user=run.user).get() == run


def test_step_index_is_unique_per_run(run: AgentRun, user) -> None:
    AgentStep.objects.create(run=run, index=0, kind=AgentStep.KIND_PLAN)
    with pytest.raises(IntegrityError), transaction.atomic():
        AgentStep.objects.create(run=run, index=0, kind=AgentStep.KIND_TOOL)
    other = AgentRun.objects.create(
        user=user,
        question="q",
        provider="g",
        model="m",
        key_source="own",
        prompt_version="v",
    )
    AgentStep.objects.create(run=other, index=0, kind=AgentStep.KIND_PLAN)


@pytest.mark.parametrize(
    "path",
    [
        [
            AgentRun.STATUS_AWAITING_APPROVAL,
            AgentRun.STATUS_RUNNING,
            AgentRun.STATUS_SUCCEEDED,
        ],
        [AgentRun.STATUS_AWAITING_APPROVAL, AgentRun.STATUS_EXPIRED],
        [AgentRun.STATUS_AWAITING_APPROVAL, AgentRun.STATUS_CANCELLED],
        [AgentRun.STATUS_FAILED],
    ],
)
def test_legal_transitions(run: AgentRun, path: list[str]) -> None:
    for status in path:
        run.status = status
        run.save()
    assert AgentRun.objects.get(pk=run.pk).status == path[-1]


@pytest.mark.parametrize(
    "final",
    [AgentRun.STATUS_SUCCEEDED, AgentRun.STATUS_FAILED, AgentRun.STATUS_CANCELLED],
)
def test_a_finished_run_cannot_start_again(run: AgentRun, final: str) -> None:
    run.status = final
    run.save()
    for status in (AgentRun.STATUS_RUNNING, AgentRun.STATUS_AWAITING_APPROVAL):
        run.status = status
        with pytest.raises(IllegalTransition):
            run.save()
    assert AgentRun.objects.get(pk=run.pk).status == final


def test_running_cannot_expire_and_pause_cannot_succeed(run: AgentRun) -> None:
    run.status = AgentRun.STATUS_EXPIRED
    with pytest.raises(IllegalTransition):
        run.save()
    run.status = AgentRun.STATUS_AWAITING_APPROVAL
    run.save()
    run.status = AgentRun.STATUS_SUCCEEDED
    with pytest.raises(IllegalTransition):
        run.save()


def test_saving_without_a_status_change_is_fine(run: AgentRun) -> None:
    run.status = AgentRun.STATUS_SUCCEEDED
    run.save()
    run.row_count = 3
    run.save()
