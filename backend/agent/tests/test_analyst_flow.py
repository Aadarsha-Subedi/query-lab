"""The analyst screen's whole path through the API, with the fake LLM."""

import pytest
from django.test import Client

from accounts.models import User
from agent.tests.conftest import Scripted, plan_reply, tool_reply
from agent.tests.test_api import BASE, post

pytestmark = pytest.mark.django_db

EDITED_SQL = "SELECT customer_state, count(*) AS n FROM demo.customers GROUP BY 1"


def test_sign_in_schema_ask_edit_result_history_replay(
    client: Client, user: User, scripted: Scripted
) -> None:
    assert client.get("/api/me").status_code == 401
    client.force_login(user)
    assert client.get("/api/me").json()["data"]["email"] == user.email

    # the schema panel
    tables = {t["name"] for t in client.get("/api/schema").json()["data"]["tables"]}
    assert {"orders", "customers"} <= tables
    assert client.get("/api/schema/tables/orders").status_code == 200
    limits = client.get("/api/agent/limits").json()["data"]
    assert limits["unfinished_runs"]["count"] == 0

    # ask: the agent proposes SQL and the run pauses with a pending block
    scripted.answers(
        plan_reply("count orders", assumptions=("all time",)),
        tool_reply(
            "propose_sql",
            sql="SELECT order_status, count(*) AS n FROM demo.orders GROUP BY 1",
            rationale="orders by status",
        ),
    )
    run = post(client, BASE, {"question": "How many orders per status?"}).json()["data"]
    run_id = run["id"]
    assert run["status"] == "awaiting_approval" and run["has_result"] is False
    detail = client.get(f"{BASE}/{run_id}").json()["data"]
    assert detail["pending"]["rationale"] == "orders by status"
    assert detail["pending"]["assumptions"] == ["all time"]
    assert client.get(f"{BASE}/{run_id}/result").status_code == 409
    assert (
        client.get("/api/agent/limits").json()["data"]["unfinished_runs"]["count"] == 1
    )

    # edit: a refused statement says why and changes nothing; a good one runs
    refused = post(client, f"{BASE}/{run_id}/edit", {"sql": "DROP TABLE demo.orders"})
    assert refused.status_code == 400
    assert refused.json()["errors"][0]["field"] == "sql"
    assert client.get(f"{BASE}/{run_id}").json()["data"]["pending"] is not None
    assert scripted.executed == []

    edited = post(client, f"{BASE}/{run_id}/edit", {"sql": EDITED_SQL}).json()["data"]
    assert edited["status"] == "succeeded"
    assert edited["edited"] is True and edited["has_result"] is True
    assert client.get(f"{BASE}/{run_id}").json()["data"]["pending"] is None

    # the result table: the stored SQL, run again
    result = client.get(f"{BASE}/{run_id}/result").json()["data"]
    assert result["columns"] == ["order_status", "n"]
    assert result["rows"] == [["delivered", 5], ["shipped", 2]]
    assert len(scripted.executed) == 2  # once for the run, once for the result

    # history: filtered, searched, ordered
    found = client.get(f"{BASE}?status=succeeded&q=PER STATUS&ordering=-created_at")
    body = found.json()
    assert [r["id"] for r in body["data"]] == [run_id]
    assert body["meta"]["count"] == 1
    assert body["data"][0]["edited"] is True
    assert client.get(f"{BASE}?status=failed").json()["meta"]["count"] == 0

    # replay: the stored trace, no new query
    queries = len(scripted.executed)
    calls = len(scripted.llm.requests)
    replay = client.get(f"{BASE}/{run_id}/replay").json()["data"]
    assert [s["kind"] for s in replay["steps"]][-3:] == ["approval", "execute", "final"]
    assert len(scripted.executed) == queries and len(scripted.llm.requests) == calls

    # the run is finished, so nothing counts against the cap any more
    assert (
        client.get("/api/agent/limits").json()["data"]["unfinished_runs"]["count"] == 0
    )


def test_approve_path_reaches_the_same_result(
    client: Client, user: User, scripted: Scripted
) -> None:
    from agent.tests.conftest import PROPOSE

    client.force_login(user)
    scripted.answers(plan_reply(), PROPOSE)
    run_id = post(client, BASE, {"question": "orders by status"}).json()["data"]["id"]
    approved = post(client, f"{BASE}/{run_id}/approve").json()["data"]
    assert approved["status"] == "succeeded" and approved["edited"] is False
    rows = client.get(f"{BASE}/{run_id}/result").json()["data"]["rows"]
    assert rows == [["delivered", 5], ["shipped", 2]]
