"""Schema, ask and agent endpoints with a `workspace`: only the caller's own
workspace is reachable, and what runs is that workspace's schema."""

import json
from collections.abc import Callable
from typing import Any

import pytest
from django.test import Client

from accounts.models import User
from agent.models import AgentRun
from agent.tests.conftest import plan_reply, tool_reply
from ask import keys
from common.llm.fake import FakeProvider
from workspaces.models import Workspace
from workspaces.tests.conftest import connect

pytestmark = [pytest.mark.django_db, pytest.mark.usefixtures("data_connections")]


@pytest.fixture
def llm(monkeypatch: pytest.MonkeyPatch) -> FakeProvider:
    fake = FakeProvider(model="fake-model")
    monkeypatch.setattr(
        keys,
        "resolve_provider",
        lambda user: keys.ResolvedProvider(fake, "gemini", keys.KEY_OWN),
    )
    return fake


@pytest.fixture
def mine(user: User, provision: Callable[[int], int]) -> Workspace:
    """A ready workspace of `user` with a customer table (real schema and roles)."""
    workspace = Workspace.objects.create(
        owner=user, name="Mine", status=Workspace.STATUS_READY
    )
    provision(workspace.pk)
    with connect(workspace.pk, "rw") as rw:
        rw.execute("CREATE TABLE customer (id int, name text)")
        rw.execute("INSERT INTO customer VALUES (1, 'alice'), (2, 'bob')")
    return workspace


@pytest.fixture
def theirs(other_user: User, provision: Callable[[int], int]) -> Workspace:
    workspace = Workspace.objects.create(
        owner=other_user, name="Theirs", status=Workspace.STATUS_READY
    )
    provision(workspace.pk)
    with connect(workspace.pk, "rw") as rw:
        rw.execute("CREATE TABLE secret (id int)")
    return workspace


def post(client: Client, path: str, body: dict[str, Any]) -> Any:
    return client.post(path, json.dumps(body), content_type="application/json")


def test_the_schema_endpoint_takes_a_workspace(
    client: Client, user: User, mine: Workspace
) -> None:
    client.force_login(user)
    own = client.get(f"/api/schema?workspace={mine.pk}").json()["data"]
    assert own["name"] == mine.schema_name
    assert [t["name"] for t in own["tables"]] == ["customer"]
    demo = client.get("/api/schema").json()["data"]
    assert demo["name"] == "demo" and len(demo["tables"]) > 5
    one = client.get(f"/api/schema/tables/customer?workspace={mine.pk}")
    assert one.status_code == 200
    assert client.get("/api/schema/tables/customer").status_code == 404


def test_another_users_workspace_is_a_404_everywhere(
    client: Client, user: User, theirs: Workspace
) -> None:
    client.force_login(user)
    w = theirs.pk
    assert client.get(f"/api/schema?workspace={w}").status_code == 404
    assert client.get(f"/api/schema/tables/secret?workspace={w}").status_code == 404
    assert (
        post(client, "/api/ask", {"question": "q", "workspace": w}).status_code == 404
    )
    assert (
        post(client, "/api/agent/runs", {"question": "q", "workspace": w}).status_code
        == 404
    )
    assert client.get(f"/api/agent/limits?workspace={w}").status_code == 404
    assert client.get("/api/schema?workspace=999999999").status_code == 404
    assert not AgentRun.objects.exists()


def test_a_workspace_that_is_not_ready_cannot_be_used(
    client: Client, user: User, mine: Workspace
) -> None:
    Workspace.objects.filter(pk=mine.pk).update(status=Workspace.STATUS_DELETING)
    client.force_login(user)
    response = client.get(f"/api/schema?workspace={mine.pk}")
    assert response.status_code == 409
    assert response.json()["code"] == "workspace_not_ready"


def test_ask_answers_from_the_workspace_schema(
    client: Client, user: User, mine: Workspace, llm: FakeProvider
) -> None:
    llm.answers = [
        json.dumps(
            {
                "answerable": True,
                "sql": "SELECT name FROM customer ORDER BY id",
                "rationale": "r",
                "self_confidence": 0.9,
            }
        )
    ]
    client.force_login(user)
    response = post(client, "/api/ask", {"question": "Names?", "workspace": mine.pk})
    assert response.status_code == 200, response.content
    data = response.json()["data"]
    assert data["rows"] == [["alice"], ["bob"]]
    assert f"ws_{mine.pk}.customer" in data["sql"]
    # the prompt named this workspace's schema, not the demo
    assert f"ws_{mine.pk}" in llm.requests[0].system
    assert "demo.orders" not in llm.requests[0].system


def test_ask_cannot_reach_the_demo_or_another_workspace_from_a_workspace(
    client: Client, user: User, mine: Workspace, theirs: Workspace, llm: FakeProvider
) -> None:
    from ask.errors import GuardRejected  # noqa: F401

    for sql in (
        "SELECT * FROM demo.orders",
        f"SELECT * FROM ws_{theirs.pk}.secret",
    ):
        llm.answers = [
            json.dumps(
                {"answerable": True, "sql": sql, "rationale": "r", "self_confidence": 1}
            )
        ] * 2
        client.force_login(user)
        response = post(client, "/api/ask", {"question": "x", "workspace": mine.pk})
        assert response.status_code == 400
        assert response.json()["code"] == "guard_rejected"


def test_an_agent_run_on_a_workspace_is_flagged_filtered_and_scoped(
    client: Client, user: User, mine: Workspace, llm: FakeProvider
) -> None:
    llm.answers = [
        plan_reply(),
        tool_reply("list_tables"),
        tool_reply(
            "propose_sql", sql="SELECT name FROM customer ORDER BY id", rationale="r"
        ),
    ]
    client.force_login(user)
    started = post(
        client, "/api/agent/runs", {"question": "Names?", "workspace": mine.pk}
    )
    assert started.status_code == 200, started.content
    data = started.json()["data"]
    assert data["workspace_id"] == mine.pk
    assert data["status"] == "awaiting_approval"
    run = AgentRun.objects.get(pk=data["id"])
    assert run.workspace_id == mine.pk and run.excluded_from_evals is True
    # a demo run is not flagged
    demo_run = AgentRun.objects.create(
        user=user,
        question="d",
        provider="g",
        model="m",
        key_source="own",
        prompt_version="v",
    )
    assert demo_run.excluded_from_evals is False
    listing = client.get(f"/api/agent/runs?workspace={mine.pk}").json()["data"]
    assert [r["id"] for r in listing] == [run.pk]
    assert [
        r["id"] for r in client.get("/api/agent/runs?workspace=demo").json()["data"]
    ] == [demo_run.pk]
    assert len(client.get("/api/agent/runs").json()["data"]) == 2
    assert client.get("/api/agent/runs?workspace=abc").status_code == 400
    # the tools were given this workspace's tables
    assert "customer" in llm.requests[2].prompt
    assert "orders" not in llm.requests[1].prompt.split("<history>")[0]
    approved = client.post(f"/api/agent/runs/{run.pk}/approve")
    assert approved.json()["data"]["status"] == "succeeded", approved.content
    rows = client.get(f"/api/agent/runs/{run.pk}/result").json()["data"]["rows"]
    assert rows == [["alice"], ["bob"]]


def test_tools_say_no_such_table_for_another_schema(
    user: User, mine: Workspace
) -> None:
    from agent import tools
    from agent.errors import ToolError
    from agent.tools.base import ToolContext
    from ask import schema
    from workspaces.context import ref_for

    context = ToolContext(
        schema=schema.get_schema(ref_for(mine.pk), include_samples=True)
    )
    for name in ("demo.orders", "orders", "ws_999.customer", "pg_catalog.pg_class"):
        with pytest.raises(ToolError, match="No table named"):
            tools.call("describe_table", {"table": name}, context)
    _, output = tools.call(
        "describe_table", {"table": f"ws_{mine.pk}.customer"}, context
    )
    assert output.table == "customer"
    _, listed = tools.call("list_tables", {}, context)
    assert [t.name for t in listed.tables] == ["customer"]


def test_a_deleted_workspace_keeps_its_trace_but_not_its_result(
    client: Client, user: User, mine: Workspace, llm: FakeProvider
) -> None:
    llm.answers = [
        plan_reply(),
        tool_reply("propose_sql", sql="SELECT name FROM customer ORDER BY id"),
    ]
    client.force_login(user)
    run_id = post(
        client, "/api/agent/runs", {"question": "Names?", "workspace": mine.pk}
    ).json()["data"]["id"]
    client.post(f"/api/agent/runs/{run_id}/approve")
    assert client.delete(f"/api/workspaces/{mine.pk}").status_code == 200
    replay = client.get(f"/api/agent/runs/{run_id}/replay")
    assert replay.status_code == 200
    assert replay.json()["data"]["workspace_id"] == mine.pk
    assert len(replay.json()["data"]["steps"]) > 0
    gone = client.get(f"/api/agent/runs/{run_id}/result")
    assert (gone.status_code, gone.json()["code"]) == (404, "workspace_gone")
    assert AgentRun.objects.get(pk=run_id).workspace_id == mine.pk
