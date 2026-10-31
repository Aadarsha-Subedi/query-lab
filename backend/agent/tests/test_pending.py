"""The `pending` block: what the screen shows while a run waits for approval."""

from datetime import datetime, timedelta

import pytest
from django.test import Client, override_settings

from accounts.models import User
from agent.models import AgentRun
from agent.tests.conftest import Scripted, plan_reply, tool_reply
from agent.tests.test_api import BASE, post, read_events, start

pytestmark = pytest.mark.django_db


def detail(client: Client, run_id: int) -> dict:
    return client.get(f"{BASE}/{run_id}").json()["data"]


def test_pending_matches_the_approval_step_and_goes_away_after_each_decision(
    client: Client, user: User, scripted: Scripted
) -> None:
    run_id = start(client, scripted, user)["id"]
    body = detail(client, run_id)
    pending = body["pending"]
    approval = next(s for s in body["steps"] if s["kind"] == "approval")
    assert pending["sql"] == approval["input"]["sql"]
    assert pending["rationale"] == "count by status"
    assert pending["assumptions"] == ["all time"]
    assert pending["guard"] == approval["input"]["guard_rewrites"]
    assert pending["revision"] == 0

    post(client, f"{BASE}/{run_id}/approve")
    assert detail(client, run_id)["pending"] is None

    cancelled = start(client, scripted, user)["id"]
    post(client, f"{BASE}/{cancelled}/cancel")
    assert detail(client, cancelled)["pending"] is None

    edited = start(client, scripted, user)["id"]
    post(client, f"{BASE}/{edited}/edit", {"sql": "SELECT 1 AS one FROM demo.orders"})
    assert detail(client, edited)["pending"] is None


def test_guard_changes_are_listed(
    client: Client, user: User, scripted: Scripted
) -> None:
    scripted.answers(
        plan_reply(),
        tool_reply(
            "propose_sql",
            sql="SELECT order_id FROM demo.orders LIMIT 99999999",
            rationale="all orders",
        ),
    )
    client.force_login(user)
    run_id = post(client, BASE, {"question": "q?"}).json()["data"]["id"]
    pending = detail(client, run_id)["pending"]
    assert pending["guard"] == ["limit_clamped"]


def test_expires_at_is_the_pause_plus_the_ttl(
    client: Client, user: User, scripted: Scripted
) -> None:
    run_id = start(client, scripted, user)["id"]
    run = AgentRun.objects.get(pk=run_id)
    with override_settings(AGENT_APPROVAL_TTL_SECONDS=120):
        pending = detail(client, run_id)["pending"]
    expires = datetime.fromisoformat(pending["expires_at"])
    expected = run.updated_at + timedelta(seconds=120)
    assert abs(expires - expected) < timedelta(milliseconds=2)


def test_the_list_rows_do_not_carry_pending(
    client: Client, user: User, scripted: Scripted
) -> None:
    start(client, scripted, user)
    assert "pending" not in client.get(BASE).json()["data"][0]


def test_the_pause_event_carries_pending(
    client: Client, user: User, scripted: Scripted
) -> None:
    run_id = start(client, scripted, user)["id"]
    pending = detail(client, run_id)["pending"]
    status = read_events(client.get(f"{BASE}/{run_id}/events"))[-1]
    assert status["event"] == "status"
    streamed = status["data"]["pending"]
    # the API rounds datetimes to milliseconds, the stream does not
    streamed_expiry = datetime.fromisoformat(streamed.pop("expires_at"))
    api_expiry = datetime.fromisoformat(pending.pop("expires_at"))
    assert abs(streamed_expiry - api_expiry) < timedelta(milliseconds=2)
    assert streamed == pending


def test_the_end_event_has_no_pending(
    client: Client, user: User, scripted: Scripted
) -> None:
    run_id = start(client, scripted, user)["id"]
    post(client, f"{BASE}/{run_id}/approve")
    events = read_events(client.get(f"{BASE}/{run_id}/events", HTTP_LAST_EVENT_ID="2"))
    assert events[-1]["data"]["status"] == "succeeded"
    assert events[-1]["data"]["pending"] is None


def test_an_edit_the_guard_refuses_says_why_and_the_run_stays_paused(
    client: Client, user: User, scripted: Scripted
) -> None:
    run_id = start(client, scripted, user)["id"]
    before = detail(client, run_id)
    sent = "DELETE FROM demo.orders"
    response = post(client, f"{BASE}/{run_id}/edit", {"sql": sent})
    assert response.status_code == 400
    body = response.json()
    assert body["code"] == "guard_rejected"
    assert body["errors"] == [
        {"field": "sql", "message": "Only SELECT queries are allowed."}
    ]
    text = response.content.decode()
    assert sent not in text and "orders" not in text
    after = detail(client, run_id)
    assert after["status"] == "awaiting_approval"
    assert after["pending"] == before["pending"]
    assert after["step_count"] == before["step_count"]


def test_a_refusal_names_only_what_the_user_wrote(
    client: Client, user: User, scripted: Scripted
) -> None:
    run_id = start(client, scripted, user)["id"]
    response = post(
        client, f"{BASE}/{run_id}/edit", {"sql": "SELECT * FROM demo.secret_table"}
    )
    assert (
        response.json()["errors"][0]["message"]
        == "The table secret_table does not exist."
    )
