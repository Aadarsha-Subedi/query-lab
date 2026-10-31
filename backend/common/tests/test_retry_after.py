"""Every 429 tells the screen how long to wait, or says that waiting will not help."""

from collections.abc import Callable
from datetime import UTC, datetime

import pytest
from django.test import Client, override_settings

from accounts.models import User
from ask import keys
from common.throttling import scoped
from core import health

pytestmark = pytest.mark.django_db

OK = dict.fromkeys(
    ["app_db", "data_db", "data_reader", "redis", "worker"], lambda: None
)


@pytest.fixture
def user() -> User:
    return User.objects.create_user("ada@example.com")


def all_throttles() -> set[type[scoped.SettingsRateThrottle]]:
    found: set[type[scoped.SettingsRateThrottle]] = set()
    pending = [scoped.SettingsRateThrottle]
    while pending:
        for sub in pending.pop().__subclasses__():
            found.add(sub)
            pending.append(sub)
    return found


def hit_health(client: Client) -> object:
    return client.get("/api/health")


def hit_me(client: Client) -> object:
    return client.get("/api/me")


def hit_ask(client: Client) -> object:
    return client.post("/api/ask", "{}", content_type="application/json")


def hit_agent(client: Client) -> object:
    return client.post("/api/agent/runs", "{}", content_type="application/json")


def hit_result(client: Client) -> object:
    return client.get("/api/agent/runs/1/result")


def hit_workspace_sql(client: Client) -> object:
    return client.post(
        "/api/workspaces/1/sql", '{"sql": "select 1"}', content_type="application/json"
    )


def hit_workspace(client: Client) -> object:
    return client.delete("/api/workspaces/1")  # counts, and changes nothing


# throttle class -> (setting, a request that counts against it, signed in?)
CASES: dict[type, tuple[str, Callable[[Client], object], bool]] = {
    scoped.AnonThrottle: ("THROTTLE_ANON_RATE", hit_health, False),
    scoped.UserThrottle: ("THROTTLE_USER_RATE", hit_me, True),
    scoped.AskThrottle: ("THROTTLE_ASK_RATE", hit_ask, True),
    scoped.AgentThrottle: ("THROTTLE_AGENT_RATE", hit_agent, True),
    scoped.ResultThrottle: ("THROTTLE_RESULT_RATE", hit_result, True),
    scoped.WorkspaceThrottle: ("THROTTLE_WORKSPACE_RATE", hit_workspace, True),
    scoped.WorkspaceSqlThrottle: (
        "THROTTLE_WORKSPACE_SQL_RATE",
        hit_workspace_sql,
        True,
    ),
}


def test_every_throttle_class_is_covered_here() -> None:
    assert all_throttles() == set(CASES)


@pytest.mark.parametrize("throttle", list(CASES), ids=lambda t: t.__name__)
def test_throttle_429_carries_retry_after_seconds(
    throttle: type,
    client: Client,
    user: User,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(health, "checks", lambda: OK)
    setting, hit, signed_in = CASES[throttle]
    if signed_in:
        client.force_login(user)
    with override_settings(**{setting: "1/m"}):
        hit(client)
        response = hit(client)
    assert response.status_code == 429  # type: ignore[attr-defined]
    body = response.json()  # type: ignore[attr-defined]
    assert body["code"] == "throttled"
    assert 0 < body["retry_after_seconds"] <= 60
    assert response["Retry-After"] == str(body["retry_after_seconds"])  # type: ignore[index]


@override_settings(ASK_DEFAULT_KEY_DAILY_LIMIT=1)
def test_default_key_limit_waits_until_midnight_utc(user: User) -> None:
    keys.spend_default_key(user)
    with pytest.raises(Exception) as caught:
        keys.spend_default_key(user)
    error = caught.value
    assert error.error_code == "default_key_limit"  # type: ignore[attr-defined]
    seconds_left = (
        24 * 3600
        - (
            datetime.now(UTC) - datetime.now(UTC).replace(hour=0, minute=0, second=0)
        ).total_seconds()
    )
    assert abs(error.retry_after - seconds_left) < 5  # type: ignore[attr-defined]


def test_limits_that_time_does_not_fix_say_null(client: Client, user: User) -> None:
    from agent.errors import RunLimitReached, StreamLimitReached

    assert RunLimitReached().retry_after is None
    assert StreamLimitReached().retry_after is None
    from workspaces.errors import ImportBusy, SqlBusy

    assert SqlBusy().retry_after is None
    assert ImportBusy().retry_after is None
