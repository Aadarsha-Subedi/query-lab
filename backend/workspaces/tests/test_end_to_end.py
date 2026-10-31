"""The whole workspace story through the HTTP API with the fake LLM: create a
workspace, import a CSV and follow its events, edit a row, describe a column, ask
a question in the workspace (pending, approve, result), see that the run is kept
out of evals, ask in the demo and not see the table, delete the workspace and
replay the old run."""

import json
from typing import Any

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import Client

from accounts.models import User
from agent.models import AgentRun
from agent.tests.conftest import plan_reply, tool_reply
from ask import keys
from common.llm.fake import FakeProvider

pytestmark = [pytest.mark.django_db, pytest.mark.usefixtures("data_connections")]

CSV = "city,visits\nOslo,10\nBergen,25\nTromso,5\n"


@pytest.fixture
def llm(monkeypatch: pytest.MonkeyPatch) -> FakeProvider:
    fake = FakeProvider(model="fake-model")
    monkeypatch.setattr(
        keys,
        "resolve_provider",
        lambda user: keys.ResolvedProvider(fake, "gemini", keys.KEY_OWN),
    )
    return fake


@pytest.fixture(autouse=True)
def _private_upload_dir(tmp_path: Any, settings: Any) -> None:
    settings.UPLOAD_TMP_DIR = tmp_path / "uploads"


def call(client: Client, method: str, path: str, body: Any = None) -> Any:
    return getattr(client, method)(
        path,
        json.dumps(body) if body is not None else None,
        content_type="application/json",
    )


def test_the_whole_workspace_flow(
    client: Client, user: User, llm: FakeProvider
) -> None:
    client.force_login(user)

    # 1. a workspace appears next to the demo
    created = call(client, "post", "/api/workspaces", {"name": "Trips"}).json()["data"]
    ws = created["id"]
    kinds = [w["kind"] for w in client.get("/api/workspaces").json()["data"]]
    assert kinds == ["demo", "user"]

    # 2. import a CSV and follow the events to the end
    response = client.post(
        f"/api/workspaces/{ws}/imports",
        {"file": SimpleUploadedFile("trips.csv", CSV.encode(), "text/csv")},
    )
    assert response.status_code == 202
    job = response.json()["data"]
    stream = client.get(job["events_url"])
    events = b"".join(stream.streaming_content).decode()  # type: ignore[attr-defined]
    assert "event: succeeded" in events and '"rows": 3' in events

    # 3. edit a row, describe a column
    base = f"/api/workspaces/{ws}/tables/trips"
    rows = call(client, "get", f"{base}/rows?order_by=visits").json()["data"]
    oslo = next(r for r in rows["rows"] if r[1] == "Oslo")
    assert (
        call(
            client, "patch", f"{base}/rows/{oslo[0]}", {"values": {"visits": 12}}
        ).status_code
        == 200
    )
    described = call(
        client, "patch", f"{base}/columns/visits", {"description": "Visits per year"}
    )
    assert described.status_code == 200

    # 4. the schema panel shows the description, not the hidden key
    panel = client.get(f"/api/schema?workspace={ws}").json()["data"]
    table = panel["tables"][0]
    assert table["name"] == "trips" and "Visits per year" in {
        c["comment"] for c in table["columns"]
    }
    assert "_row_id" not in {c["name"] for c in table["columns"]}

    # 5. ask in the workspace: the run pauses with SQL, the user approves
    llm.answers = [
        plan_reply("sum the visits"),
        tool_reply(
            "propose_sql",
            sql="SELECT city, visits FROM trips ORDER BY visits DESC",
            rationale="top cities",
        ),
    ]
    started = call(
        client,
        "post",
        "/api/agent/runs",
        {"question": "Which city has the most visits?", "workspace": ws},
    )
    assert started.status_code == 200, started.content
    run = started.json()["data"]
    assert run["status"] == "awaiting_approval" and run["workspace_id"] == ws
    pending = client.get(f"/api/agent/runs/{run['id']}").json()["data"]["pending"]
    assert f"ws_{ws}.trips" in pending["sql"]
    approved = call(client, "post", f"/api/agent/runs/{run['id']}/approve").json()[
        "data"
    ]
    assert approved["status"] == "succeeded"
    result = client.get(f"/api/agent/runs/{run['id']}/result").json()["data"]
    assert (
        result["rows"][0] == ["Bergen", 25] and ["Oslo", 12] in result["rows"]
    )  # the edit shows

    # 6. the run is flagged out of eval data; the demo run is not
    stored = AgentRun.objects.get(pk=run["id"])
    assert stored.workspace_id == ws and stored.excluded_from_evals is True

    # 7. the demo cannot see the user's table, and the user cannot reach the demo from the workspace
    demo_schema = client.get("/api/schema").json()["data"]
    assert "trips" not in {t["name"] for t in demo_schema["tables"]}
    llm.answers = [
        json.dumps(
            {
                "answerable": True,
                "sql": "SELECT * FROM trips",
                "rationale": "r",
                "self_confidence": 1,
            }
        )
    ] * 2
    demo_ask = call(client, "post", "/api/ask", {"question": "trips?"})
    assert demo_ask.status_code == 400 and demo_ask.json()["code"] == "guard_rejected"
    llm.answers = [
        json.dumps(
            {
                "answerable": True,
                "sql": "SELECT * FROM demo.orders",
                "rationale": "r",
                "self_confidence": 1,
            }
        )
    ] * 2
    from_workspace = call(
        client, "post", "/api/ask", {"question": "orders?", "workspace": ws}
    )
    assert (
        from_workspace.status_code == 400
        and from_workspace.json()["code"] == "guard_rejected"
    )
    assert call(client, "get", "/api/agent/runs?workspace=demo").json()["data"] == []

    # 8. delete the workspace: the schema is gone, the old run can still be replayed
    assert call(client, "delete", f"/api/workspaces/{ws}").status_code == 200
    assert client.get(f"/api/schema?workspace={ws}").status_code == 404
    replay = client.get(f"/api/agent/runs/{run['id']}/replay")
    assert replay.status_code == 200 and replay.json()["data"]["status"] == "succeeded"
    assert [s["kind"] for s in replay.json()["data"]["steps"]][-3:] == [
        "approval",
        "execute",
        "final",
    ]
    gone = client.get(f"/api/agent/runs/{run['id']}/result")
    assert (gone.status_code, gone.json()["code"]) == (404, "workspace_gone")
