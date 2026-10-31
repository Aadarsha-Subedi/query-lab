import json
from typing import Any

import pytest
from django.test import Client, override_settings

from accounts.models import User
from agent import stream
from agent.models import AgentRun
from agent.tests.conftest import PROPOSE, Scripted, plan_reply
from ask import runner

pytestmark = pytest.mark.django_db

BASE = "/api/agent/runs"


def post(client: Client, path: str, body: dict[str, Any] | None = None) -> Any:
    return client.post(path, json.dumps(body or {}), content_type="application/json")


def start(client: Client, scripted: Scripted, user: User) -> dict[str, Any]:
    scripted.answers(plan_reply(assumptions=("all time",)), PROPOSE)
    client.force_login(user)
    response = post(client, BASE, {"question": "Orders by status?"})
    assert response.status_code == 200, response.content
    return response.json()["data"]


@pytest.mark.parametrize(
    ("method", "path"),
    [
        ("post", BASE),
        ("get", BASE),
        ("get", f"{BASE}/1"),
        ("post", f"{BASE}/1/approve"),
        ("post", f"{BASE}/1/edit"),
        ("post", f"{BASE}/1/cancel"),
        ("get", f"{BASE}/1/replay"),
        ("get", f"{BASE}/1/events"),
    ],
)
def test_every_route_needs_sign_in(client: Client, method: str, path: str) -> None:
    response = getattr(client, method)(path)
    assert response.status_code == 401


def test_run_from_start_to_approved(
    client: Client, user: User, scripted: Scripted
) -> None:
    data = start(client, scripted, user)
    # Huey runs inline in tests: the run is already paused at the checkpoint.
    assert data["status"] == "awaiting_approval"
    assert data["plan"].startswith("1. ")
    assert data["confidence"] is None and data["check"] == ""
    assert scripted.executed == []
    run_id = data["id"]

    detail = client.get(f"{BASE}/{run_id}").json()
    assert detail["success"] is True and detail["status_code"] == 200
    steps = detail["data"]["steps"]
    assert [s["kind"] for s in steps] == ["plan", "tool", "approval"]
    assert steps[2]["input"]["assumptions"] == ["all time"]
    assert set(steps[0]) >= {"index", "kind", "output", "actor", "latency_ms"}

    approved = post(client, f"{BASE}/{run_id}/approve")
    assert approved.status_code == 200
    body = approved.json()["data"]
    assert body["status"] == "succeeded" and body["row_count"] == 2
    assert body["check"] == "checked"
    assert body["confidence"] is None  # CONFIDENCE_SHOW_SCORE is off
    assert len(scripted.executed) == 1
    again = post(client, f"{BASE}/{run_id}/approve")
    assert again.status_code == 409
    assert again.json()["code"] == "run_not_awaiting_approval"


@override_settings(CONFIDENCE_SHOW_SCORE=True)
def test_score_shows_when_the_setting_allows(
    client: Client, user: User, scripted: Scripted
) -> None:
    run_id = start(client, scripted, user)["id"]
    body = post(client, f"{BASE}/{run_id}/approve").json()["data"]
    assert 0 < body["confidence"] <= 1


def test_edit_and_cancel_and_guard_refusal(
    client: Client, user: User, scripted: Scripted
) -> None:
    run_id = start(client, scripted, user)["id"]
    refused = post(client, f"{BASE}/{run_id}/edit", {"sql": "DROP TABLE demo.orders"})
    assert refused.status_code == 400
    assert refused.json()["code"] == "guard_rejected"
    assert (
        client.get(f"{BASE}/{run_id}").json()["data"]["status"] == "awaiting_approval"
    )

    edited = post(
        client, f"{BASE}/{run_id}/edit", {"sql": "SELECT 1 AS one FROM demo.orders"}
    )
    assert edited.json()["data"]["status"] == "succeeded"
    assert "1 AS one" in scripted.executed[0]

    second = start(client, scripted, user)["id"]
    cancelled = post(client, f"{BASE}/{second}/cancel").json()["data"]
    assert cancelled["status"] == "cancelled"
    assert len(scripted.executed) == 1


def test_other_users_runs_are_404(
    client: Client, user: User, other_user: User, scripted: Scripted
) -> None:
    run_id = start(client, scripted, user)["id"]
    client.force_login(other_user)
    for method, path in [
        ("get", f"{BASE}/{run_id}"),
        ("get", f"{BASE}/{run_id}/replay"),
        ("get", f"{BASE}/{run_id}/events"),
        ("post", f"{BASE}/{run_id}/approve"),
        ("post", f"{BASE}/{run_id}/edit"),
        ("post", f"{BASE}/{run_id}/cancel"),
    ]:
        kwargs = {
            "data": json.dumps({"sql": "SELECT 1"}),
            "content_type": "application/json",
        }
        response = getattr(client, method)(path, **(kwargs if method == "post" else {}))
        assert response.status_code == 404, path
        assert response.json()["code"] == "run_not_found"
    assert scripted.executed == []
    assert client.get(BASE).json()["data"] == []


def test_list_is_own_runs_newest_first_and_paged(
    client: Client, user: User, other_user: User, scripted: Scripted
) -> None:
    first = start(client, scripted, user)["id"]
    post(client, f"{BASE}/{first}/cancel")
    second = start(client, scripted, user)["id"]
    body = client.get(BASE).json()
    assert [r["id"] for r in body["data"]] == [second, first]
    assert body["meta"] == {"count": 2, "limit": 25, "offset": 0}
    page = client.get(BASE, {"limit": 1, "offset": 1}).json()
    assert [r["id"] for r in page["data"]] == [first]
    client.force_login(other_user)
    assert client.get(BASE).json()["data"] == []


def test_bad_question_is_400_and_creates_nothing(client: Client, user: User) -> None:
    client.force_login(user)
    response = post(client, BASE, {"question": "   "})
    assert response.status_code == 400
    assert response.json()["code"] == "question_invalid"
    assert AgentRun.objects.count() == 0


@override_settings(THROTTLE_AGENT_RATE="2/m", AGENT_MAX_CONCURRENT_RUNS_PER_USER=10)
def test_run_creation_is_throttled(
    client: Client, user: User, scripted: Scripted
) -> None:
    client.force_login(user)
    scripted.answers(*[plan_reply(), PROPOSE] * 3)
    assert post(client, BASE, {"question": "a?"}).status_code == 200
    assert post(client, BASE, {"question": "b?"}).status_code == 200
    limited = post(client, BASE, {"question": "c?"})
    assert limited.status_code == 429
    assert limited.json()["code"] == "throttled"


def test_run_cap_is_429(client: Client, user: User, scripted: Scripted) -> None:
    start(client, scripted, user)
    start(client, scripted, user)
    scripted.answers(plan_reply(), PROPOSE)
    response = post(client, BASE, {"question": "third?"})
    assert response.status_code == 429
    assert response.json()["code"] == "agent_run_limit"


def test_replay_reads_only_the_stored_trace(
    client: Client, user: User, scripted: Scripted, monkeypatch: pytest.MonkeyPatch
) -> None:
    run_id = start(client, scripted, user)["id"]
    post(client, f"{BASE}/{run_id}/approve")
    calls = len(scripted.llm.requests)

    def boom(*args: object, **kwargs: object) -> None:
        raise AssertionError("replay touched the model or the demo database")

    monkeypatch.setattr(runner, "run", boom)
    monkeypatch.setattr(scripted.llm, "generate", boom)
    live = client.get(f"{BASE}/{run_id}").json()["data"]["steps"]
    replay = client.get(f"{BASE}/{run_id}/replay").json()["data"]
    assert [s["index"] for s in replay["steps"]] == list(range(len(live)))
    assert replay["steps"] == live
    assert replay["steps"][4]["kind"] == "execute"
    assert "preview" in replay["steps"][4]["output"]
    assert len(scripted.llm.requests) == calls


def read_events(response: Any) -> list[dict[str, Any]]:
    text = b"".join(response.streaming_content).decode()
    response.close()
    events = []
    for block in text.split("\n\n"):
        if not block.strip():
            continue
        event: dict[str, Any] = {}
        for line in block.splitlines():
            if line.startswith(":"):
                event["comment"] = line[1:].strip()
            else:
                key, _, value = line.partition(": ")
                event[key] = json.loads(value) if key == "data" else value
        events.append(event)
    return events


def test_stream_replays_stored_steps_and_ends_when_paused(
    client: Client, user: User, scripted: Scripted
) -> None:
    run_id = start(client, scripted, user)["id"]
    response = client.get(f"{BASE}/{run_id}/events")
    assert response.status_code == 200
    assert response["Content-Type"] == "text/event-stream"
    assert response["Cache-Control"] == "no-cache"
    assert response["X-Accel-Buffering"] == "no"
    events = read_events(response)
    assert [e["event"] for e in events] == ["step", "step", "step", "status"]
    assert [e["id"] for e in events[:3]] == ["0", "1", "2"]
    assert events[2]["data"]["kind"] == "approval"
    assert events[3]["data"]["status"] == "awaiting_approval"


def test_stream_resumes_from_last_event_id_and_ends_on_terminal(
    client: Client, user: User, scripted: Scripted
) -> None:
    run_id = start(client, scripted, user)["id"]
    post(client, f"{BASE}/{run_id}/approve")
    response = client.get(f"{BASE}/{run_id}/events", HTTP_LAST_EVENT_ID="2")
    events = read_events(response)
    assert [e["id"] for e in events[:-1]] == ["3", "4", "5"]
    assert [e["data"]["kind"] for e in events[:-1]] == ["approval", "execute", "final"]
    assert events[-1]["event"] == "status"
    assert events[-1]["data"]["status"] == "succeeded"


@override_settings(AGENT_SSE_MAX_SECONDS=2, AGENT_SSE_HEARTBEAT_SECONDS=1)
def test_idle_stream_sends_a_heartbeat_and_then_times_out(
    client: Client, run: AgentRun
) -> None:
    client.force_login(run.user)  # a run that is `running` with nobody working on it
    events = read_events(client.get(f"{BASE}/{run.pk}/events"))
    assert any(e.get("comment") == "heartbeat" for e in events)
    assert events[-1]["event"] == "timeout"


@override_settings(AGENT_MAX_OPEN_STREAMS=2)
def test_open_stream_cap_refuses_the_extra_stream(
    client: Client, run: AgentRun
) -> None:
    client.force_login(run.user)
    first = stream.EventStream(run.pk, -1)
    second = stream.EventStream(run.pk, -1)
    refused = client.get(f"{BASE}/{run.pk}/events")
    assert refused.status_code == 429
    assert refused.json()["code"] == "agent_stream_limit"
    first.close()
    first.close()  # closing twice frees one slot, not two
    with override_settings(AGENT_SSE_MAX_SECONDS=1):
        allowed = client.get(f"{BASE}/{run.pk}/events")
        assert allowed.status_code == 200
        allowed.close()
    second.close()
    assert stream.get_redis().get(stream.STREAMS_KEY) in (b"0", None)


def test_routes_are_in_the_openapi_docs(client: Client) -> None:
    paths = client.get("/api/openapi.json").json()["paths"]
    for path in (
        "/api/agent/runs",
        "/api/agent/runs/{run_id}",
        "/api/agent/runs/{run_id}/approve",
        "/api/agent/runs/{run_id}/edit",
        "/api/agent/runs/{run_id}/cancel",
        "/api/agent/runs/{run_id}/replay",
        "/api/agent/runs/{run_id}/events",
    ):
        assert path in paths
