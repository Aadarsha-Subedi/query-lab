import json
from typing import Any

import pytest
from django.test import Client

from accounts.models import User
from workspaces import service
from workspaces.models import Workspace
from workspaces.tests.conftest import connect

pytestmark = [pytest.mark.django_db, pytest.mark.usefixtures("data_connections")]


def post(client: Client, path: str, body: Any) -> Any:
    return client.post(path, json.dumps(body), content_type="application/json")


def test_requires_sign_in(client: Client) -> None:
    assert client.get("/api/workspaces/limits").status_code == 401


def test_limits_report_what_is_used_and_allowed(client: Client, user: User) -> None:
    client.force_login(user)
    empty = client.get("/api/workspaces/limits").json()["data"]
    assert empty["workspaces"] == {"used": 0, "allowed": 3}
    assert empty["bytes"]["used"] == 0
    ws = post(client, "/api/workspaces", {"name": "L"}).json()["data"]["id"]
    with connect(ws, "rw") as rw:  # what an import does
        rw.execute("CREATE TABLE t (v text)")
        rw.execute(
            "INSERT INTO t SELECT repeat('x', 1000) FROM generate_series(1, 100)"
        )
    data = client.get("/api/workspaces/limits").json()["data"]
    assert data["workspaces"]["used"] == 1
    assert data["bytes"]["used"] > 50_000
    assert (
        data["bytes"]["per_workspace"] == 52428800
        and data["bytes"]["allowed"] == 262144000
    )
    assert {
        "max_tables",
        "max_columns",
        "max_relations",
        "max_dump_bytes",
    } <= set(data)
    assert data["max_dump_bytes"] == 52428800
    listed = client.get("/api/workspaces").json()["data"][1]
    assert (
        listed["bytes_used"] == data["bytes"]["used"]
        and listed["bytes_allowed"] == 52428800
    )
    assert listed["tables"] == 1


def test_limits_are_per_user(client: Client, user: User, other_user: User) -> None:
    client.force_login(other_user)
    post(client, "/api/workspaces", {"name": "O"})
    client.force_login(user)
    assert (
        client.get("/api/workspaces/limits").json()["data"]["workspaces"]["used"] == 0
    )


def test_the_delete_service_removes_the_workspace(user: User) -> None:
    workspace = service.create(user, "R")
    service.delete(workspace, user)
    assert not Workspace.objects.filter(pk=workspace.pk).exists()
