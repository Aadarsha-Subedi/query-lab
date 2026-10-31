"""The staff-only trace endpoints (step 6.2)."""

from typing import Any

import pytest
from django.test import Client

from accounts.models import User
from agent.models import AgentRun, AgentStep
from config.api import api

pytestmark = pytest.mark.django_db

BASE = "/api/workbench"


@pytest.fixture
def staff(db: None) -> User:
    return User.objects.create_user("staff@example.com", is_staff=True)


@pytest.fixture
def plain(db: None) -> User:
    return User.objects.create_user("plain@example.com")


def make_run(user: User, **fields: Any) -> AgentRun:
    values: dict[str, Any] = {
        "question": "How many orders?",
        "provider": "gemini",
        "model": "fake-model",
        "key_source": "default",
        "prompt_version": "v2-agent",
        "status": AgentRun.STATUS_SUCCEEDED,
        "final_sql": "SELECT 1",
    }
    values.update(fields)
    return AgentRun.objects.create(user=user, **values)


def add_step(run: AgentRun, index: int, kind: str, **fields: Any) -> AgentStep:
    return AgentStep.objects.create(run=run, index=index, kind=kind, **fields)


def workbench_paths() -> list[tuple[str, str]]:
    """Every method and path the API publishes under /api/workbench/."""
    found = []
    for path, item in api.get_openapi_schema()["paths"].items():
        if path.startswith(f"{BASE}/"):
            for method in item:
                found.append((method, path))
    return found


def test_the_route_list_is_not_empty() -> None:
    assert len(workbench_paths()) >= 2


@pytest.mark.parametrize(("method", "path"), workbench_paths())
def test_every_workbench_route_is_staff_only(
    client: Client, plain: User, staff: User, method: str, path: str
) -> None:
    """The check is set once on the router; this fails when a route escapes it."""
    url = path.replace("{run_id}", "1").replace("{case_id}", "1")
    url = url.replace("{eval_run_id}", "1")
    send = getattr(client, method)
    assert send(url).status_code == 401
    client.force_login(plain)
    denied = send(url)
    assert denied.status_code == 403
    assert denied.json()["code"] == "staff_only"
    client.force_login(staff)
    assert send(url).status_code != 403


def test_staff_sees_demo_runs_only(client: Client, staff: User, plain: User) -> None:
    demo = make_run(plain)
    make_run(plain, workspace_id=7, excluded_from_evals=True)
    make_run(plain, excluded_from_evals=True)
    client.force_login(staff)
    body = client.get(f"{BASE}/runs").json()
    assert [r["id"] for r in body["data"]] == [demo.pk]
    assert body["meta"]["count"] == 1


def test_a_workspace_run_cannot_be_fetched(
    client: Client, staff: User, plain: User
) -> None:
    hidden = make_run(plain, workspace_id=7, excluded_from_evals=True)
    flagged = make_run(plain, excluded_from_evals=True)
    client.force_login(staff)
    assert client.get(f"{BASE}/runs/{hidden.pk}").status_code == 404
    assert client.get(f"{BASE}/runs/{flagged.pk}").status_code == 404
    assert client.get(f"{BASE}/runs/999999").status_code == 404


def test_filters_narrow_the_list(client: Client, staff: User, plain: User) -> None:
    failed = make_run(plain, status="failed", error_code="query_failed", final_sql="")
    needs = make_run(plain, check_label="needs_look", revisions=2)
    edited = make_run(plain, question="Revenue by month?")
    add_step(
        edited, 0, AgentStep.KIND_APPROVAL, input={"sql": "SELECT 2", "edited": True}
    )
    make_run(plain, check_label="checked")
    client.force_login(staff)

    def ids(query: str) -> list[int]:
        body = client.get(f"{BASE}/runs?{query}").json()
        return [r["id"] for r in body["data"]]

    assert ids("status=failed") == [failed.pk]
    assert ids("error_code=query_failed") == [failed.pk]
    assert ids("check=needs_look") == [needs.pk]
    assert ids("revisions_min=1") == [needs.pk]
    assert ids("edited=true") == [edited.pk]
    assert edited.pk not in ids("edited=false")
    assert ids("q=revenue") == [edited.pk]
    assert len(ids("created_after=2000-01-01T00:00:00Z")) == 4
    assert ids("created_before=2000-01-01T00:00:00Z") == []


def test_ordering_is_an_allowlist_and_pages_are_capped(
    client: Client, staff: User, plain: User, settings: Any
) -> None:
    runs = [make_run(plain, latency_ms=ms) for ms in (30, 10, 20)]
    client.force_login(staff)
    ordered = client.get(f"{BASE}/runs?ordering=latency_ms").json()["data"]
    assert [r["latency_ms"] for r in ordered] == [10, 20, 30]
    assert client.get(f"{BASE}/runs?ordering=question").status_code == 422
    settings.TRACES_PAGE_SIZE_MAX = 2
    page = client.get(f"{BASE}/runs?limit=50&ordering=-latency_ms").json()
    assert page["meta"]["limit"] == 2 and len(page["data"]) == 2
    assert page["meta"]["count"] == len(runs)


def test_the_list_takes_a_fixed_number_of_queries(
    client: Client, staff: User, plain: User, django_assert_max_num_queries: Any
) -> None:
    for _ in range(6):
        make_run(plain)
    client.force_login(staff)
    with django_assert_max_num_queries(6):
        assert client.get(f"{BASE}/runs").status_code == 200


def test_the_detail_shows_steps_and_both_sql_strings(
    client: Client, staff: User, plain: User
) -> None:
    run = make_run(plain, final_sql="SELECT 2")
    add_step(run, 0, AgentStep.KIND_PLAN, output="1. count")
    add_step(
        run,
        1,
        AgentStep.KIND_APPROVAL,
        input={"sql": "SELECT 1", "revision": 0},
        actor=AgentStep.ACTOR_AGENT,
    )
    add_step(
        run,
        2,
        AgentStep.KIND_APPROVAL,
        input={"decision": "edit", "sql": "SELECT 2", "edited": True},
        actor=AgentStep.ACTOR_USER,
    )
    add_step(run, 3, AgentStep.KIND_EXECUTE, output="columns: n; 1 row")
    client.force_login(staff)
    data = client.get(f"{BASE}/runs/{run.pk}").json()["data"]
    assert [s["kind"] for s in data["steps"]] == [
        "plan",
        "approval",
        "approval",
        "execute",
    ]
    assert data["proposed_sql"] == "SELECT 1"
    assert data["approved_sql"] == "SELECT 2"
    assert data["diff"] is True
    assert data["steps"][3]["output"] == "columns: n; 1 row"
    assert "rows" not in data


def test_an_unedited_run_has_no_diff(client: Client, staff: User, plain: User) -> None:
    run = make_run(plain, final_sql="SELECT 1")
    add_step(
        run,
        0,
        AgentStep.KIND_APPROVAL,
        input={"sql": "SELECT 1"},
        actor=AgentStep.ACTOR_AGENT,
    )
    client.force_login(staff)
    data = client.get(f"{BASE}/runs/{run.pk}").json()["data"]
    assert data["diff"] is False and data["proposed_sql"] == data["approved_sql"]
