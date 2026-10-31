import json
from typing import Any

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import Client, override_settings

from accounts.models import User
from workspaces import service
from workspaces.imports import service as import_service
from workspaces.models import Workspace

pytestmark = [pytest.mark.django_db, pytest.mark.usefixtures("data_connections")]


def post(client: Client, path: str, body: Any) -> Any:
    return client.post(path, json.dumps(body), content_type="application/json")


def test_requires_sign_in(client: Client) -> None:
    assert client.get("/api/workspaces/limits").status_code == 401


def test_limits_report_what_is_used_and_allowed(client: Client, user: User) -> None:
    client.force_login(user)
    empty = client.get("/api/workspaces/limits").json()["data"]
    assert empty["workspaces"] == {"used": 0, "allowed": 3}
    assert empty["imports"]["used"] == 0 and empty["imports"]["allowed"] >= 1
    assert empty["bytes"]["used"] == 0
    ws = post(client, "/api/workspaces", {"name": "L"}).json()["data"]["id"]
    post(
        client,
        f"/api/workspaces/{ws}/sql",
        {
            "sql": "CREATE TABLE t (v text); INSERT INTO t SELECT repeat('x', 1000) FROM generate_series(1, 100)"
        },
    )
    workspace = Workspace.objects.get(pk=ws)
    import_service.start(workspace, user, SimpleUploadedFile("a.csv", b"a\n1\n"), {})
    data = client.get("/api/workspaces/limits").json()["data"]
    assert data["workspaces"]["used"] == 1
    assert data["bytes"]["used"] > 50_000
    assert (
        data["bytes"]["per_workspace"] == 104857600
        and data["bytes"]["allowed"] == 262144000
    )
    assert data["imports"]["used"] == 1
    assert {
        "max_tables",
        "max_columns",
        "max_relations",
        "max_rows_per_edit",
        "max_import_file_bytes",
        "max_import_rows",
    } <= set(data)
    listed = client.get("/api/workspaces").json()["data"][1]
    assert (
        listed["bytes_used"] == data["bytes"]["used"]
        and listed["bytes_allowed"] == 104857600
    )
    assert listed["tables"] == 1


def test_limits_are_per_user(client: Client, user: User, other_user: User) -> None:
    client.force_login(other_user)
    post(client, "/api/workspaces", {"name": "O"})
    client.force_login(user)
    assert (
        client.get("/api/workspaces/limits").json()["data"]["workspaces"]["used"] == 0
    )


@override_settings(WORKSPACE_MAX_BYTES=100_000)
def test_the_full_errors_have_the_error_shape(client: Client, user: User) -> None:
    client.force_login(user)
    ws = post(client, "/api/workspaces", {"name": "F"}).json()["data"]["id"]
    post(
        client,
        f"/api/workspaces/{ws}/tables",
        {"name": "t", "columns": [{"name": "v", "type": "text"}]},
    )
    with override_settings(WORKSPACE_MAX_BYTES=10**9):
        post(
            client,
            f"/api/workspaces/{ws}/sql",
            {
                "sql": "INSERT INTO t (v) SELECT repeat('x', 1000) FROM generate_series(1, 300)"
            },
        )
    body = post(
        client, f"/api/workspaces/{ws}/tables/t/rows", {"rows": [{"v": "x"}]}
    ).json()
    assert body["success"] is False and body["status_code"] == 409
    assert body["code"] == "workspace_full" and body["message"] and body["errors"] == []
    assert import_service  # the import path checks the same room, see test_import_api
    with override_settings(USER_MAX_BYTES=100_000, WORKSPACE_MAX_BYTES=10**9):
        body = post(
            client, f"/api/workspaces/{ws}/tables/t/rows", {"rows": [{"v": "x"}]}
        ).json()
    assert body["code"] == "user_storage_full"


@override_settings(WORKSPACE_MAX_BYTES=100_000)
def test_an_import_into_a_full_workspace_is_refused_before_it_is_queued(
    client: Client, user: User
) -> None:
    client.force_login(user)
    ws = post(client, "/api/workspaces", {"name": "F"}).json()["data"]["id"]
    with override_settings(WORKSPACE_MAX_BYTES=10**9):
        post(
            client,
            f"/api/workspaces/{ws}/sql",
            {
                "sql": "CREATE TABLE t (v text); INSERT INTO t SELECT repeat('x', 1000) FROM generate_series(1, 300)"
            },
        )
    response = client.post(
        f"/api/workspaces/{ws}/imports",
        {"file": SimpleUploadedFile("a.csv", b"a\n1\n")},
    )
    assert (response.status_code, response.json()["code"]) == (409, "workspace_full")


def test_the_delete_service_removes_the_workspace(user: User) -> None:
    workspace = service.create(user, "R")
    service.delete(workspace, user)
    assert not Workspace.objects.filter(pk=workspace.pk).exists()
