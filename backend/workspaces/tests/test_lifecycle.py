"""Cap, ownership and cleanup under real concurrency and real schemas."""

import json
import threading
from typing import Any

import psycopg
import pytest
from django.db import connection as django_connection
from django.test import Client, override_settings

from accounts.models import User
from workspaces.models import Workspace

BASE = "/api/workspaces"


def post(client: Client, body: dict[str, Any]) -> Any:
    return client.post(BASE, json.dumps(body), content_type="application/json")


@pytest.mark.django_db
def test_the_demo_cannot_be_renamed_or_deleted(client: Client, user: User) -> None:
    client.force_login(user)
    renamed = client.patch(
        f"{BASE}/demo", json.dumps({"name": "x"}), content_type="application/json"
    )
    deleted = client.delete(f"{BASE}/demo")
    assert renamed.status_code == deleted.status_code == 409
    assert renamed.json()["code"] == "demo_workspace_read_only"
    listing = client.get(BASE).json()["data"]
    assert listing[0]["kind"] == "demo" and listing[0]["name"].startswith("Olist")


@pytest.mark.django_db
def test_create_then_delete_leaves_no_schema_or_role(
    client: Client, user: User, owner: psycopg.Connection
) -> None:
    client.force_login(user)
    before = owner.execute(
        "SELECT (SELECT count(*) FROM pg_namespace WHERE nspname LIKE 'ws\\_%'),"
        " (SELECT count(*) FROM pg_roles WHERE rolname LIKE 'ws\\_%')"
    ).fetchone()
    for name in ("a", "b", "c"):
        workspace_id = post(client, {"name": name}).json()["data"]["id"]
        assert client.delete(f"{BASE}/{workspace_id}").status_code == 200
    after = owner.execute(
        "SELECT (SELECT count(*) FROM pg_namespace WHERE nspname LIKE 'ws\\_%'),"
        " (SELECT count(*) FROM pg_roles WHERE rolname LIKE 'ws\\_%')"
    ).fetchone()
    assert before == after


@pytest.mark.django_db(transaction=True)
@override_settings(MAX_WORKSPACES_PER_USER=2, THROTTLE_WORKSPACE_RATE="100/m")
def test_concurrent_creates_cannot_exceed_the_cap() -> None:
    user = User.objects.create_user("racer@example.com")
    statuses: list[int] = []

    def create(index: int) -> None:
        try:
            client = Client()
            client.force_login(user)
            statuses.append(post(client, {"name": f"w{index}"}).status_code)
        finally:
            django_connection.close()

    threads = [threading.Thread(target=create, args=(i,)) for i in range(6)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()
    assert sorted(statuses) == [200, 200, 409, 409, 409, 409]
    assert Workspace.objects.filter(owner=user).count() == 2
