import json
from typing import Any

import psycopg
import pytest
from django.test import Client, override_settings

from accounts.models import User
from workspaces import credentials
from workspaces.models import Workspace

pytestmark = pytest.mark.django_db

BASE = "/api/workspaces"


def post(client: Client, path: str, body: dict[str, Any]) -> Any:
    return client.post(path, json.dumps(body), content_type="application/json")


def patch(client: Client, path: str, body: dict[str, Any]) -> Any:
    return client.patch(path, json.dumps(body), content_type="application/json")


@pytest.mark.parametrize(
    ("method", "path"),
    [("get", BASE), ("post", BASE), ("get", f"{BASE}/1"), ("patch", f"{BASE}/1")],
)
def test_every_route_needs_sign_in(client: Client, method: str, path: str) -> None:
    assert getattr(client, method)(path).status_code == 401


def test_create_then_list_with_the_demo_first(client: Client, user: User) -> None:
    client.force_login(user)
    created = post(client, BASE, {"name": "  Sales  data "})
    assert created.status_code == 200, created.content
    data = created.json()["data"]
    assert data["name"] == "Sales data" and data["status"] == "ready"
    assert data["tables"] == 0 and data["kind"] == "user"
    listing = client.get(BASE).json()
    kinds = [w["kind"] for w in listing["data"]]
    assert kinds == ["demo", "user"]
    assert listing["data"][0]["id"] is None and listing["data"][0]["read_only"]
    assert listing["data"][0]["tables"] > 0
    assert listing["meta"]["max_workspaces"] == 3
    assert client.get(f"{BASE}/{data['id']}").json()["data"]["id"] == data["id"]


def test_create_provisions_a_usable_schema_and_logs_it(
    client: Client, user: User
) -> None:
    client.force_login(user)
    workspace_id = post(client, BASE, {"name": "A"}).json()["data"]["id"]
    from workspaces import connections
    from workspaces.models import WorkspaceDDLLog

    with connections.workspace_connection(workspace_id, "rw", 1) as connection:
        assert connection.execute("SELECT current_schema()").fetchone() == (
            f"ws_{workspace_id}",
        )
    assert WorkspaceDDLLog.objects.filter(workspace_id=workspace_id).count() == 1


@override_settings(MAX_WORKSPACES_PER_USER=2)
def test_the_cap_is_enforced_with_a_typed_error(client: Client, user: User) -> None:
    client.force_login(user)
    assert post(client, BASE, {"name": "One"}).status_code == 200
    assert post(client, BASE, {"name": "Two"}).status_code == 200
    response = post(client, BASE, {"name": "Three"})
    assert response.status_code == 409
    assert response.json()["code"] == "workspace_limit_reached"
    assert Workspace.objects.filter(owner=user).count() == 2


def test_names_are_unique_per_user_and_validated(
    client: Client, user: User, other_user: User
) -> None:
    client.force_login(user)
    assert post(client, BASE, {"name": "Sales"}).status_code == 200
    taken = post(client, BASE, {"name": "Sales"})
    assert (taken.status_code, taken.json()["code"]) == (409, "workspace_name_taken")
    assert post(client, BASE, {"name": "   "}).json()["code"] == "invalid_name"
    client.force_login(other_user)
    assert post(client, BASE, {"name": "Sales"}).status_code == 200


def test_rename(client: Client, user: User) -> None:
    client.force_login(user)
    first = post(client, BASE, {"name": "One"}).json()["data"]["id"]
    post(client, BASE, {"name": "Two"})
    assert (
        patch(client, f"{BASE}/{first}", {"name": "Uno"}).json()["data"]["name"]
        == "Uno"
    )
    clash = patch(client, f"{BASE}/{first}", {"name": "Two"})
    assert clash.json()["code"] == "workspace_name_taken"


def test_someone_elses_workspace_is_the_same_404_as_a_missing_one(
    client: Client, user: User, other_user: User
) -> None:
    client.force_login(other_user)
    theirs = post(client, BASE, {"name": "Private"}).json()["data"]["id"]
    client.force_login(user)
    missing = client.get(f"{BASE}/999999999")
    stolen = client.get(f"{BASE}/{theirs}")
    assert missing.status_code == stolen.status_code == 404
    assert missing.json() == stolen.json()
    assert missing.json()["code"] == "workspace_not_found"
    assert patch(client, f"{BASE}/{theirs}", {"name": "mine"}).status_code == 404
    assert [w["kind"] for w in client.get(BASE).json()["data"]] == ["demo"]


def test_a_provisioning_failure_leaves_nothing_behind(
    client: Client,
    user: User,
    monkeypatch: pytest.MonkeyPatch,
    owner: psycopg.Connection,
) -> None:
    from workspaces import provisioning

    def broken(connection: Any, workspace_id: int, version: int = 1) -> None:
        connection.execute("CREATE ROLE ws_broken_half LOGIN")
        raise RuntimeError("boom")

    monkeypatch.setattr(provisioning, "create_workspace_schema", broken)
    client.force_login(user)
    response = post(client, BASE, {"name": "Doomed"})
    assert response.status_code == 503
    assert response.json()["code"] == "workspace_provisioning_failed"
    assert not Workspace.objects.filter(owner=user).exists()
    # the half-made role was part of the rolled-back transaction
    assert owner.execute(
        "SELECT count(*) FROM pg_roles WHERE rolname = 'ws_broken_half'"
    ).fetchone() == (0,)
    assert credentials.role_name(1, "rw") == "ws_1_rw"
