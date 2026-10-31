"""GET /api/agent/runs/{id}/result: the stored SQL, run again."""

import pytest
from django.test import Client, override_settings

from accounts.models import User
from agent.models import AgentRun
from agent.tests.conftest import Scripted
from ask.errors import QueryFailed, QueryTimeout

pytestmark = pytest.mark.django_db

SQL = "SELECT order_status, count(*) AS n FROM demo.orders GROUP BY 1"


def url(run: AgentRun) -> str:
    return f"/api/agent/runs/{run.pk}/result"


@pytest.fixture
def done(run: AgentRun) -> AgentRun:
    run.status = AgentRun.STATUS_SUCCEEDED
    run.final_sql = SQL
    run.save()
    return run


@pytest.fixture
def signed_in(client: Client, user: User) -> Client:
    client.force_login(user)
    return client


def test_needs_sign_in(client: Client, done: AgentRun) -> None:
    assert client.get(url(done)).status_code == 401


def test_returns_the_rows_by_running_the_stored_sql(
    signed_in: Client, done: AgentRun, scripted: Scripted
) -> None:
    body = signed_in.get(url(done)).json()["data"]
    assert body["run_id"] == done.pk
    assert body["columns"] == ["order_status", "n"]
    assert body["rows"] == [["delivered", 5], ["shipped", 2]]
    assert body["row_count"] == 2 and body["truncated"] is False
    assert len(scripted.executed) == 1
    # what ran is the guard's rewrite of the stored SQL (a LIMIT is added)
    assert "LIMIT" in scripted.executed[0] and body["sql"] == scripted.executed[0]


def test_another_users_run_is_a_404(
    client: Client, other_user: User, done: AgentRun, scripted: Scripted
) -> None:
    client.force_login(other_user)
    response = client.get(url(done))
    assert response.status_code == 404
    assert response.json()["code"] == "run_not_found"
    assert scripted.executed == []


@pytest.mark.parametrize(
    "status",
    [
        AgentRun.STATUS_FAILED,
        AgentRun.STATUS_CANCELLED,
        AgentRun.STATUS_AWAITING_APPROVAL,
        AgentRun.STATUS_RUNNING,
    ],
)
def test_only_a_succeeded_run_has_a_result(
    signed_in: Client, run: AgentRun, scripted: Scripted, status: str
) -> None:
    AgentRun.objects.filter(pk=run.pk).update(status=status, final_sql=SQL)
    response = signed_in.get(url(run))
    assert response.status_code == 409
    assert response.json()["code"] == "run_not_succeeded"
    assert scripted.executed == []


def test_sql_the_guard_now_refuses_is_refused(
    signed_in: Client, done: AgentRun, scripted: Scripted
) -> None:
    AgentRun.objects.filter(pk=done.pk).update(final_sql="DELETE FROM demo.orders")
    response = signed_in.get(url(done))
    assert response.status_code == 400
    assert response.json()["code"] == "guard_rejected"
    assert "DELETE" not in response.content.decode()
    assert scripted.executed == []


def test_no_sql_is_taken_from_the_request(
    signed_in: Client, done: AgentRun, scripted: Scripted
) -> None:
    signed_in.get(url(done), {"sql": "SELECT 1", "final_sql": "SELECT 2"})
    assert all("order_status" in sql for sql in scripted.executed)


@pytest.mark.parametrize(
    ("error", "status", "code"),
    [
        (QueryFailed("boom"), 422, "query_failed"),
        (QueryTimeout(), 504, "query_timeout"),
    ],
)
def test_query_errors_are_the_ask_errors_and_leave_the_run_alone(
    signed_in: Client,
    done: AgentRun,
    scripted: Scripted,
    error: Exception,
    status: int,
    code: str,
) -> None:
    before = AgentRun.objects.values().get(pk=done.pk)
    scripted.returns(error)
    response = signed_in.get(url(done))
    assert response.status_code == status and response.json()["code"] == code
    assert "boom" not in response.content.decode()
    assert AgentRun.objects.values().get(pk=done.pk) == before


def test_nothing_is_stored(
    signed_in: Client, done: AgentRun, scripted: Scripted
) -> None:
    before = AgentRun.objects.values().get(pk=done.pk)
    signed_in.get(url(done))
    assert AgentRun.objects.values().get(pk=done.pk) == before
    assert done.steps.count() == 0


@override_settings(THROTTLE_RESULT_RATE="2/m")
def test_throttled(signed_in: Client, done: AgentRun, scripted: Scripted) -> None:
    assert signed_in.get(url(done)).status_code == 200
    assert signed_in.get(url(done)).status_code == 200
    assert signed_in.get(url(done)).status_code == 429


@pytest.mark.usefixtures("data_connections")
@override_settings(ASK_MAX_ROWS=5)
def test_rows_are_capped_by_ask_max_rows(signed_in: Client, done: AgentRun) -> None:
    AgentRun.objects.filter(pk=done.pk).update(
        final_sql="SELECT order_id FROM demo.orders LIMIT 50"
    )
    body = signed_in.get(url(done)).json()["data"]
    assert body["row_count"] == 5 and body["truncated"] is True
