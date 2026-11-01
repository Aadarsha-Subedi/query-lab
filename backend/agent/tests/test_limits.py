"""GET /api/agent/limits."""

from datetime import datetime, timedelta

import pytest
from django.test import Client, override_settings
from django.utils import timezone

from accounts.models import User
from agent import stream
from agent.models import AgentRun
from ask import keys
from ask.models import UserLLMKey

pytestmark = pytest.mark.django_db

URL = "/api/agent/limits"


def test_needs_sign_in(client: Client) -> None:
    assert client.get(URL).status_code == 401


@override_settings(
    ASK_DEFAULT_KEY_DAILY_LIMIT=5,
    AGENT_MAX_CONCURRENT_RUNS_PER_USER=2,
    AGENT_MAX_OPEN_STREAMS=3,
)
def test_nothing_used_yet(client: Client, user: User) -> None:
    client.force_login(user)
    data = client.get(URL).json()["data"]
    assert data["default_key"]["used"] == 0
    assert data["default_key"]["allowed"] == 5 and data["default_key"]["remaining"] == 5
    assert (
        datetime.fromisoformat(data["default_key"]["resets_at"])
        > datetime.now().astimezone()
    )
    assert data["has_own_key"] is False
    assert data["unfinished_runs"] == {"count": 0, "allowed": 2}
    assert data["streams"] == {"open": 0, "allowed": 3}


@override_settings(ASK_DEFAULT_KEY_DAILY_LIMIT=2)
def test_counts_spends_without_spending(client: Client, user: User) -> None:
    keys.spend_default_key(user)
    client.force_login(user)
    for _ in range(3):  # reading does not change the count
        assert client.get(URL).json()["data"]["default_key"]["used"] == 1
    keys.spend_default_key(user)
    with pytest.raises(Exception):  # noqa: B017
        keys.spend_default_key(user)  # over the limit; the counter keeps counting
    data = client.get(URL).json()["data"]["default_key"]
    assert data == {**data, "used": 2, "remaining": 0}


def test_other_users_spends_are_not_mine(
    client: Client, user: User, other_user: User
) -> None:
    keys.spend_default_key(other_user)
    client.force_login(user)
    assert client.get(URL).json()["data"]["default_key"]["used"] == 0


def test_unfinished_runs_skip_finished_and_expired_pauses(
    client: Client, user: User, other_user: User, run: AgentRun
) -> None:
    def add(status: str, owner: User = user) -> AgentRun:
        return AgentRun.objects.create(
            user=owner,
            question="q",
            status=status,
            provider="gemini",
            model="m",
            key_source="default",
            prompt_version="v",
        )

    add(AgentRun.STATUS_SUCCEEDED)
    add(AgentRun.STATUS_AWAITING_APPROVAL, other_user)
    stale = add(AgentRun.STATUS_AWAITING_APPROVAL)
    AgentRun.objects.filter(pk=stale.pk).update(
        updated_at=timezone.now() - timedelta(days=1)
    )
    client.force_login(user)
    # `run` (running) counts; the old pause, the finished run and the other user's do not
    assert client.get(URL).json()["data"]["unfinished_runs"]["count"] == 1


def test_own_key_flag(client: Client, user: User) -> None:
    UserLLMKey.objects.create(
        user=user,
        provider="gemini",
        encrypted_key="x",
        key_last4="abcd",
        model="m",
        is_active=True,
    )
    client.force_login(user)
    # A saved key is not enough: the user must also have chosen their own AI.
    assert client.get(URL).json()["data"]["has_own_key"] is False
    keys.set_ai_source(user, "own")
    assert client.get(URL).json()["data"]["has_own_key"] is True


def test_open_streams_come_from_redis(client: Client, user: User) -> None:
    stream.acquire_slot()
    try:
        client.force_login(user)
        assert client.get(URL).json()["data"]["streams"]["open"] == 1
    finally:
        stream.release_slot()
