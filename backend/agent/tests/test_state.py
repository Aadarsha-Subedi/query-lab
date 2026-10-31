import pytest
from django.test import override_settings

from accounts.models import User
from agent import loop, service, state
from agent.errors import RunLimitReached, RunNotFound
from agent.models import AgentRun
from agent.tests.conftest import PROPOSE, Scripted, plan_reply
from common.redis import get_redis

pytestmark = pytest.mark.django_db


def test_state_round_trip(run: AgentRun) -> None:
    run.step_count = 1  # a started run reads its saved state
    saved = state.RunState(
        run_id=run.pk,
        phase=state.PHASE_EXECUTE,
        plan="1. look",
        history=["[tool] x"],
        pending_sql="SELECT 1",
        samples_checked=["orders.order_status"],
        reflect_ok=True,
    )
    state.save(saved)
    assert state.load(run) == saved
    state.delete(run.pk)
    assert get_redis().get(state.run_key(run.pk)) is None


def test_state_key_expires() -> None:
    with override_settings(AGENT_STATE_TTL_SECONDS=100):
        state.save(state.RunState(run_id=999_001))
    ttl = get_redis().ttl(state.run_key(999_001))
    assert 0 < ttl <= 100


def test_a_new_run_ignores_a_leftover_key(run: AgentRun) -> None:
    state.save(
        state.RunState(run_id=run.pk, phase=state.PHASE_EXECUTE, pending_sql="x")
    )
    assert run.step_count == 0
    assert state.load(run).phase == state.PHASE_PLAN


def test_the_lock_admits_one_holder(run: AgentRun) -> None:
    with state.run_lock(run.pk) as first:
        assert first
        with state.run_lock(run.pk) as second:
            assert not second
    with state.run_lock(run.pk) as again:
        assert again


def test_advance_does_nothing_while_the_lock_is_held(
    run: AgentRun, scripted: Scripted
) -> None:
    scripted.answers(plan_reply(), PROPOSE)
    with state.run_lock(run.pk):
        loop.advance(run.pk)
    run.refresh_from_db()
    assert run.step_count == 0 and scripted.llm.requests == []


def test_two_approvals_run_the_sql_once(run: AgentRun, scripted: Scripted) -> None:
    scripted.answers(plan_reply(), PROPOSE)
    loop.advance(run.pk)
    run.refresh_from_db()
    service.decide(run, service.DECISION_APPROVE)
    with pytest.raises(service.RunNotAwaitingApproval):
        service.decide(run, service.DECISION_APPROVE)
    # Two workers get the same resume task: only one gets the lock and the status.
    with state.run_lock(run.pk):
        loop.advance(run.pk)
    loop.advance(run.pk)
    loop.advance(run.pk)
    assert len(scripted.executed) == 1


def test_a_decision_while_the_worker_holds_the_lock_is_busy(run: AgentRun) -> None:
    run.status = AgentRun.STATUS_AWAITING_APPROVAL
    run.save()
    with state.run_lock(run.pk), pytest.raises(service.RunBusy):
        service.decide(run, service.DECISION_APPROVE)


def test_a_lost_state_is_rebuilt_from_the_steps(
    run: AgentRun, scripted: Scripted
) -> None:
    scripted.answers(plan_reply(assumptions=("all time",)), PROPOSE)
    loop.advance(run.pk)
    run.refresh_from_db()
    state.delete(run.pk)  # TTL, a Redis flush or a restart
    service.decide(run, service.DECISION_APPROVE)
    loop.advance(run.pk)
    run.refresh_from_db()
    assert run.status == AgentRun.STATUS_SUCCEEDED
    assert len(scripted.executed) == 1


def test_expire_stale_ends_paused_and_orphaned_runs(run: AgentRun, user: User) -> None:
    orphan = AgentRun.objects.create(
        user=user,
        question="q",
        provider="g",
        model="m",
        key_source="default",
        prompt_version="v",
    )
    run.status = AgentRun.STATUS_AWAITING_APPROVAL
    run.save()
    old = "2000-01-01T00:00:00Z"
    AgentRun.objects.filter(pk__in=[run.pk, orphan.pk]).update(updated_at=old)
    assert service.expire_stale() == 2
    run.refresh_from_db()
    orphan.refresh_from_db()
    assert run.status == AgentRun.STATUS_EXPIRED
    assert (orphan.status, orphan.error_code) == (
        AgentRun.STATUS_FAILED,
        "agent_worker_lost",
    )
    assert service.expire_stale() == 0


def test_per_user_cap_refuses_the_extra_run(
    user: User, other_user: User, scripted: Scripted
) -> None:
    for _ in range(2):
        service.create_run(user, "How many orders?")
    with pytest.raises(RunLimitReached):
        service.create_run(user, "How many orders?")
    service.create_run(other_user, "How many orders?")  # the cap is per user
    first = AgentRun.objects.filter(user=user).first()
    assert first is not None
    first.status = AgentRun.STATUS_CANCELLED
    first.save()
    service.create_run(user, "How many orders?")  # a finished run frees a slot


def test_create_run_spends_the_default_key_once(user: User, scripted: Scripted) -> None:
    with override_settings(ASK_DEFAULT_KEY_DAILY_LIMIT=1):
        service.create_run(user, "How many orders?")
        from ask.errors import DefaultKeyLimitReached

        with pytest.raises(DefaultKeyLimitReached):
            service.create_run(user, "How many orders?")
    assert AgentRun.objects.filter(user=user).count() == 1


def test_get_run_hides_other_users_runs(run: AgentRun, other_user: User) -> None:
    assert service.get_run(run.user, run.pk) == run
    with pytest.raises(RunNotFound):
        service.get_run(other_user, run.pk)
