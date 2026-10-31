import json
from typing import Any

import pytest
from django.test import Client

from accounts.models import User
from agent.models import AgentRun, RunFeedback

pytestmark = pytest.mark.django_db

BASE = "/api/agent/runs"


def put(client: Client, run_id: int, body: dict[str, Any]) -> Any:
    return client.put(
        f"{BASE}/{run_id}/feedback", json.dumps(body), content_type="application/json"
    )


@pytest.fixture
def done(run: AgentRun) -> AgentRun:
    run.status = AgentRun.STATUS_SUCCEEDED
    run.save()
    return run


def test_the_owner_votes(client: Client, user: User, done: AgentRun) -> None:
    client.force_login(user)
    response = put(client, done.pk, {"vote": "down", "note": " wrong table "})
    assert response.status_code == 200
    assert response.json()["data"] == {
        "run_id": done.pk,
        "vote": "down",
        "note": "wrong table",
    }
    assert client.get(f"{BASE}/{done.pk}").json()["data"]["feedback"] == "down"
    assert client.get(BASE).json()["data"][0]["feedback"] == "down"


def test_a_vote_changes_instead_of_duplicating(
    client: Client, user: User, done: AgentRun
) -> None:
    client.force_login(user)
    put(client, done.pk, {"vote": "down"})
    put(client, done.pk, {"vote": "up", "note": "fine after all"})
    rows = RunFeedback.objects.filter(run=done)
    assert rows.count() == 1
    assert rows.get().vote == "up" and rows.get().note == "fine after all"


def test_delete_takes_the_vote_back(client: Client, user: User, done: AgentRun) -> None:
    client.force_login(user)
    put(client, done.pk, {"vote": "up"})
    response = client.delete(f"{BASE}/{done.pk}/feedback")
    assert response.status_code == 200 and response.json()["data"]["vote"] is None
    assert RunFeedback.objects.count() == 0
    assert client.get(f"{BASE}/{done.pk}").json()["data"]["feedback"] is None
    assert client.delete(f"{BASE}/{done.pk}/feedback").status_code == 200


def test_only_the_owner_can_vote(
    client: Client, other_user: User, done: AgentRun
) -> None:
    client.force_login(other_user)
    response = put(client, done.pk, {"vote": "up"})
    assert response.status_code == 404 and response.json()["code"] == "run_not_found"
    assert client.delete(f"{BASE}/{done.pk}/feedback").status_code == 404
    assert RunFeedback.objects.count() == 0


def test_signed_out_is_refused(client: Client, done: AgentRun) -> None:
    assert put(client, done.pk, {"vote": "up"}).status_code == 401
    assert client.delete(f"{BASE}/{done.pk}/feedback").status_code == 401


@pytest.mark.parametrize("status", AgentRun.ACTIVE)
def test_an_unfinished_run_is_refused(
    client: Client, user: User, run: AgentRun, status: str
) -> None:
    run.status = status
    run.save()
    client.force_login(user)
    response = put(client, run.pk, {"vote": "up"})
    assert response.status_code == 409
    assert response.json()["code"] == "run_not_finished"
    assert client.delete(f"{BASE}/{run.pk}/feedback").status_code == 409


def test_bad_votes_and_long_notes_are_refused(
    client: Client, user: User, done: AgentRun, settings: Any
) -> None:
    client.force_login(user)
    assert put(client, done.pk, {"vote": "meh"}).status_code == 422
    settings.FEEDBACK_NOTE_MAX_CHARS = 5
    response = put(client, done.pk, {"vote": "up", "note": "too long"})
    assert response.status_code == 400
    assert response.json()["errors"][0]["field"] == "note"


def test_the_workbench_can_filter_by_vote(
    client: Client, user: User, other_user: User, done: AgentRun
) -> None:
    staff = User.objects.create_user("staff@example.com", is_staff=True)
    RunFeedback.objects.create(run=done, user=user, vote="down")
    other = AgentRun.objects.create(
        user=other_user,
        question="x",
        provider="gemini",
        model="m",
        key_source="default",
        prompt_version="v2-agent",
    )
    RunFeedback.objects.create(run=other, user=other_user, vote="up")
    client.force_login(staff)

    def ids(query: str) -> list[int]:
        body = client.get(f"/api/workbench/runs?{query}").json()
        return [r["id"] for r in body["data"]]

    assert ids("feedback=down") == [done.pk]
    assert ids("feedback=up") == [other.pk]
