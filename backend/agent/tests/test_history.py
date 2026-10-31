"""GET /api/agent/runs: filters, search, ordering and the list-row flags."""

from datetime import timedelta

import pytest
from django.test import Client
from django.utils import timezone

from accounts.models import User
from agent.models import AgentRun, AgentStep

pytestmark = pytest.mark.django_db

URL = "/api/agent/runs"


def make(user: User, question: str, status: str, **fields: object) -> AgentRun:
    run = AgentRun.objects.create(
        user=user,
        question=question,
        status=status,
        provider="gemini",
        model="fake-model",
        key_source="default",
        prompt_version="v2-agent",
    )
    if "created_at" in fields:  # auto_now_add: set it afterwards
        AgentRun.objects.filter(pk=run.pk).update(**fields)
        run.refresh_from_db()
    elif fields:
        AgentRun.objects.filter(pk=run.pk).update(**fields)
    return run


@pytest.fixture
def runs(user: User, other_user: User) -> dict[str, AgentRun]:
    now = timezone.now()
    made = {
        "old": make(
            user, "Orders per STATE", "succeeded",
            created_at=now - timedelta(days=3), latency_ms=900,
        ),
        "mid": make(
            user, "Top sellers", "failed",
            created_at=now - timedelta(days=2), latency_ms=100,
        ),
        "new": make(
            user, "Late orders", "expired",
            created_at=now - timedelta(days=1), latency_ms=500,
        ),
        "paused": make(user, "Revenue", "awaiting_approval"),
    }
    make(other_user, "Orders per state, theirs", "succeeded")
    return made


@pytest.fixture
def signed_in(client: Client, user: User) -> Client:
    client.force_login(user)
    return client


def ids(client: Client, **params: object) -> list[int]:
    response = client.get(URL, params)
    assert response.status_code == 200, response.content
    return [r["id"] for r in response.json()["data"]]


def test_default_is_newest_first_and_only_mine(
    signed_in: Client, runs: dict[str, AgentRun]
) -> None:
    assert ids(signed_in) == [runs[k].pk for k in ("paused", "new", "mid", "old")]


def test_status_filter_takes_one_or_several(
    signed_in: Client, runs: dict[str, AgentRun]
) -> None:
    assert ids(signed_in, status="failed") == [runs["mid"].pk]
    assert set(ids(signed_in, status=["failed", "expired"])) == {
        runs["mid"].pk,
        runs["new"].pk,
    }


def test_unknown_status_is_a_validation_error(signed_in: Client) -> None:
    assert signed_in.get(URL, {"status": "bogus"}).status_code == 422


def test_search_is_case_insensitive_and_only_mine(
    signed_in: Client, runs: dict[str, AgentRun]
) -> None:
    assert ids(signed_in, q="orders") == [runs["new"].pk, runs["old"].pk]
    assert ids(signed_in, q="nothing like this") == []


def test_date_filters(signed_in: Client, runs: dict[str, AgentRun]) -> None:
    cutoff = (timezone.now() - timedelta(days=2, hours=12)).isoformat()
    assert set(ids(signed_in, created_after=cutoff)) == {
        runs[k].pk for k in ("mid", "new", "paused")
    }
    assert ids(signed_in, created_before=cutoff) == [runs["old"].pk]


def test_filters_combine(signed_in: Client, runs: dict[str, AgentRun]) -> None:
    cutoff = (timezone.now() - timedelta(days=2, hours=12)).isoformat()
    assert ids(signed_in, q="orders", created_after=cutoff) == [runs["new"].pk]
    assert ids(signed_in, q="orders", status="failed") == []


def test_ordering_by_latency_and_created_at(
    signed_in: Client, runs: dict[str, AgentRun]
) -> None:
    by_latency = ids(signed_in, ordering="-latency_ms")
    assert by_latency[:3] == [runs[k].pk for k in ("old", "new", "mid")]
    assert ids(signed_in, ordering="created_at")[0] == runs["old"].pk


@pytest.mark.parametrize("field", ["question", "user", "id", "-status", "password"])
def test_ordering_allowlist_refuses_other_fields(
    signed_in: Client, field: str
) -> None:
    assert signed_in.get(URL, {"ordering": field}).status_code == 422


def test_count_in_meta_matches_the_filter_not_the_page(
    signed_in: Client, runs: dict[str, AgentRun]
) -> None:
    body = signed_in.get(URL, {"q": "orders", "limit": 1}).json()
    assert body["meta"] == {"count": 2, "limit": 1, "offset": 0}
    assert len(body["data"]) == 1
    second = signed_in.get(URL, {"q": "orders", "limit": 1, "offset": 1}).json()
    assert second["data"][0]["id"] != body["data"][0]["id"]


def test_another_users_runs_never_appear(
    client: Client, other_user: User, runs: dict[str, AgentRun]
) -> None:
    client.force_login(other_user)
    assert len(ids(client)) == 1
    assert ids(client, q="Top sellers") == []


def test_has_result_and_edited_flags(
    signed_in: Client, runs: dict[str, AgentRun]
) -> None:
    for kind, edited in (("old", True), ("mid", False)):
        AgentStep.objects.create(
            run=runs[kind],
            index=0,
            kind=AgentStep.KIND_APPROVAL,
            input={"decision": "edit" if edited else "approve", "edited": edited},
        )
    rows = {r["id"]: r for r in signed_in.get(URL).json()["data"]}
    assert rows[runs["old"].pk]["has_result"] is True
    assert rows[runs["old"].pk]["edited"] is True
    assert rows[runs["mid"].pk]["has_result"] is False
    assert rows[runs["mid"].pk]["edited"] is False
    assert rows[runs["new"].pk]["edited"] is False
    detail = signed_in.get(f"{URL}/{runs['old'].pk}").json()["data"]
    assert detail["edited"] is True and detail["has_result"] is True
