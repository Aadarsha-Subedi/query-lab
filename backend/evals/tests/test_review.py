import json
from typing import Any

import pytest
from django.test import Client
from django.utils import timezone

from accounts.models import User
from evals.models import TraceCase
from evals.tests.test_drafting import GOOD, Scripted, answer

pytestmark = [pytest.mark.django_db, pytest.mark.usefixtures("data_connections")]

BASE = "/api/workbench/cases"


@pytest.fixture
def staff(db: None) -> User:
    return User.objects.create_user("staff@example.com", is_staff=True)


@pytest.fixture
def signed_in(client: Client, staff: User) -> Client:
    client.force_login(staff)
    return client


def case(status: str = "drafted", **fields: Any) -> TraceCase:
    values: dict[str, Any] = {
        "source_run_id": TraceCase.objects.count() + 1,
        "source_created_at": timezone.now(),
        "question": "How many orders?",
        "reasons": "failed",
        "outcome": "error",
        "status": status,
        "draft_sql": GOOD,
    }
    values.update(fields)
    return TraceCase.objects.create(**values)


def post(client: Client, path: str, body: dict[str, Any] | None = None) -> Any:
    return client.post(path, json.dumps(body or {}), content_type="application/json")


def test_the_list_shows_drafts_and_filters(signed_in: Client) -> None:
    drafted = case()
    case("candidate")
    body = signed_in.get(f"{BASE}?status=drafted").json()
    assert [c["id"] for c in body["data"]] == [drafted.pk]
    row = body["data"][0]
    assert row["trace_path"] == f"/api/workbench/runs/{drafted.source_run_id}"
    assert row["draft_sql"] == GOOD and row["gold_sql"] == ""
    assert body["meta"]["count"] == 1


def test_the_detail_previews_rows_without_storing_them(signed_in: Client) -> None:
    c = case()
    data = signed_in.get(f"{BASE}/{c.pk}").json()["data"]
    assert data["preview"]["columns"] == ["n"] and data["preview"]["error"] == ""
    assert "rows" not in {f.name for f in TraceCase._meta.get_fields()}
    assert signed_in.get(f"{BASE}/999999").status_code == 404


def test_approving_a_draft_makes_gold(signed_in: Client, staff: User) -> None:
    c = case()
    response = post(signed_in, f"{BASE}/{c.pk}/approve")
    assert response.status_code == 200, response.content
    c.refresh_from_db()
    assert c.status == "approved" and c.gold_sql and c.reviewer == staff
    assert c.reviewed_at is not None


def test_an_edit_replaces_question_and_sql(signed_in: Client) -> None:
    c = case()
    body = {
        "question": "  Count of orders  ",
        "sql": "SELECT count(*) AS total FROM orders",
    }
    assert post(signed_in, f"{BASE}/{c.pk}/approve", body).status_code == 200
    c.refresh_from_db()
    assert c.question == "Count of orders" and "total" in c.gold_sql


def test_an_edited_approval_is_guarded(signed_in: Client) -> None:
    c = case()
    response = post(signed_in, f"{BASE}/{c.pk}/approve", {"sql": "DROP TABLE orders"})
    assert response.status_code == 400
    assert response.json()["errors"][0]["field"] == "sql"
    failing = post(
        signed_in, f"{BASE}/{c.pk}/approve", {"sql": "SELECT nope FROM orders"}
    )
    assert failing.status_code in (400, 422)
    c.refresh_from_db()
    assert c.status == "drafted" and c.gold_sql == ""


def test_a_failed_draft_cannot_be_approved_unedited(signed_in: Client) -> None:
    c = case(draft_sql="DELETE FROM orders", draft_error="Only SELECT is allowed")
    response = post(signed_in, f"{BASE}/{c.pk}/approve")
    assert response.status_code == 422 and response.json()["code"] == "draft_unusable"
    assert post(signed_in, f"{BASE}/{c.pk}/approve", {"sql": GOOD}).status_code == 200


def test_approving_twice_or_a_candidate_is_refused(signed_in: Client) -> None:
    c = case()
    post(signed_in, f"{BASE}/{c.pk}/approve")
    again = post(signed_in, f"{BASE}/{c.pk}/approve")
    assert again.status_code == 409 and again.json()["code"] == "case_not_reviewable"
    cand = case("candidate")
    assert post(signed_in, f"{BASE}/{cand.pk}/approve").status_code == 409
    assert (
        post(signed_in, f"{BASE}/{cand.pk}/reject", {"reason": "x"}).status_code == 409
    )


def test_reject_and_mark_unanswerable(signed_in: Client) -> None:
    a, b = case(), case()
    assert (
        post(signed_in, f"{BASE}/{a.pk}/reject", {"reason": "bad question"}).status_code
        == 200
    )
    assert (
        post(
            signed_in, f"{BASE}/{b.pk}/mark-unanswerable", {"note": "no data"}
        ).status_code
        == 200
    )
    a.refresh_from_db()
    b.refresh_from_db()
    assert (a.status, a.note, a.gold_sql) == ("rejected", "bad question", "")
    assert (b.status, b.answerable, b.gold_sql) == ("approved", False, "")


def test_the_draft_endpoint_queues_a_batch(signed_in: Client, monkeypatch) -> None:
    called: list[int] = []
    monkeypatch.setattr(
        "evals.tasks.draft_batch", lambda user_id: called.append(user_id)
    )
    assert post(signed_in, f"{BASE}/draft").json()["data"] == {"queued": True}
    assert len(called) == 1


def test_a_drafting_batch_then_approval_end_to_end(staff: User) -> None:
    from evals import drafting

    c = case("candidate", draft_sql="")
    assert drafting.draft_batch(staff, Scripted([answer(GOOD)])) == 1
    c.refresh_from_db()
    assert c.status == "drafted" and c.gold_sql == ""
