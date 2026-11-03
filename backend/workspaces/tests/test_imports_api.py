import json
from typing import Any

import pytest
from django.test import Client, override_settings

from accounts.models import User
from workspaces import storage
from workspaces.models import ImportJob

pytestmark = [pytest.mark.django_db, pytest.mark.usefixtures("data_connections")]

R2 = {
    "R2_ENDPOINT_URL": "https://acct.r2.cloudflarestorage.com",
    "R2_ACCESS_KEY_ID": "AKIATEST",
    "R2_SECRET_ACCESS_KEY": "secret",
    "R2_BUCKET_NAME": "dumps-test",
}
DUMP = "CREATE TABLE public.t (x int);\nINSERT INTO public.t VALUES (1), (2);\n"


def call(client: Client, method: str, path: str, body: Any = None) -> Any:
    return getattr(client, method)(
        path,
        json.dumps(body) if body is not None else None,
        content_type="application/json",
    )


@pytest.fixture
def ws(client: Client, user: User) -> int:
    client.force_login(user)
    return call(client, "post", "/api/workspaces", {"name": "W"}).json()["data"]["id"]


@pytest.fixture
def fake_r2(monkeypatch: pytest.MonkeyPatch) -> dict[str, Any]:
    state: dict[str, Any] = {"text": DUMP, "uploaded": True, "deleted": []}
    storage._client.cache_clear()

    def stored_size(key: str) -> int:
        if not state["uploaded"]:
            raise storage.DumpUploadMissing()
        return len(state["text"])

    monkeypatch.setattr(storage, "stored_size", stored_size)
    monkeypatch.setattr(storage, "delete", state["deleted"].append)
    monkeypatch.setattr(
        storage,
        "read_lines",
        lambda key, max_text_bytes: iter(state["text"].splitlines(keepends=True)),
    )
    return state


def create(client: Client, ws: int, **extra: Any) -> Any:
    body = {"filename": "dump.sql", "size": len(DUMP), **extra}
    return call(client, "post", f"/api/workspaces/{ws}/imports", body)


@override_settings(**R2, HUEY_IMMEDIATE=True)
def test_full_flow_upload_start_poll(
    client: Client, ws: int, fake_r2: dict[str, Any]
) -> None:
    created = create(client, ws).json()["data"]
    assert created["status"] == "awaiting_upload"
    assert created["upload_url"].startswith(
        "https://acct.r2.cloudflarestorage.com/dumps-test/dumps/"
    )
    base = f"/api/workspaces/{ws}/imports/{created['id']}"
    started = call(client, "post", f"{base}/start").json()["data"]
    assert started["status"] in {"queued", "running", "succeeded"}
    done = call(client, "get", base).json()["data"]
    assert done["status"] == "succeeded", done
    assert (done["tables_created"], done["statements_run"]) == (1, 2)
    assert done["error"] is None
    assert (
        call(client, "get", f"/api/workspaces/{ws}/imports").json()["data"][0]["id"]
        == created["id"]
    )
    assert fake_r2["deleted"]  # the object is removed after the job


@override_settings(**R2, HUEY_IMMEDIATE=True)
def test_a_bad_dump_reports_where(
    client: Client, ws: int, fake_r2: dict[str, Any]
) -> None:
    fake_r2["text"] = "CREATE TABLE a (x int);\nINSERT INTO nope VALUES (1);\n"
    created = create(client, ws, size=len(fake_r2["text"])).json()["data"]
    base = f"/api/workspaces/{ws}/imports/{created['id']}"
    call(client, "post", f"{base}/start")
    failed = call(client, "get", base).json()["data"]
    assert failed["status"] == "failed"
    assert failed["error"]["code"] == "dump_failed"
    assert (failed["error"]["statement"], failed["error"]["line"]) == (2, 2)


@override_settings(**R2)
def test_start_before_upload_is_an_error(
    client: Client, ws: int, fake_r2: dict[str, Any]
) -> None:
    fake_r2["uploaded"] = False
    created = create(client, ws).json()["data"]
    response = call(
        client, "post", f"/api/workspaces/{ws}/imports/{created['id']}/start"
    )
    assert response.status_code == 422
    assert response.json()["code"] == "dump_upload_missing"
    # and it can be retried once the file arrives
    fake_r2["uploaded"] = True
    with override_settings(HUEY_IMMEDIATE=True):
        ok = call(client, "post", f"/api/workspaces/{ws}/imports/{created['id']}/start")
    assert ok.status_code == 200


@override_settings(**R2)
def test_start_twice_is_refused(
    client: Client, ws: int, fake_r2: dict[str, Any]
) -> None:
    created = create(client, ws).json()["data"]
    with override_settings(HUEY_IMMEDIATE=True):
        base = f"/api/workspaces/{ws}/imports/{created['id']}/start"
        assert call(client, "post", base).status_code == 200
        assert call(client, "post", base).json()["code"] == "import_not_ready"


@override_settings(**R2, DUMP_MAX_FILE_BYTES=100)
@pytest.mark.parametrize(
    ("body", "code"),
    [
        ({"filename": "dump.sql", "size": 101}, "dump_too_large"),
        ({"filename": "dump.sql", "size": 0}, "invalid_name"),
        ({"filename": "dump.zip", "size": 10}, "invalid_name"),
        ({"filename": "evil.exe", "size": 10}, "invalid_name"),
    ],
)
def test_bad_requests(client: Client, ws: int, body: dict, code: str) -> None:
    response = call(client, "post", f"/api/workspaces/{ws}/imports", body)
    assert response.status_code == 422 and response.json()["code"] == code


@override_settings(**R2)
def test_a_queued_import_blocks_a_second_one(
    client: Client, ws: int, fake_r2: dict[str, Any]
) -> None:
    first = create(client, ws).json()["data"]
    ImportJob.objects.filter(pk=first["id"]).update(status=ImportJob.QUEUED)
    second = create(client, ws)
    assert second.status_code == 409 and second.json()["code"] == "import_in_progress"


@override_settings(**R2)
def test_an_unfinished_upload_is_replaced_by_the_next_attempt(
    client: Client, ws: int, fake_r2: dict[str, Any]
) -> None:
    first = create(client, ws).json()["data"]  # e.g. the PUT was refused
    second = create(client, ws)
    assert second.status_code == 200
    old = ImportJob.objects.get(pk=first["id"])
    assert (old.status, old.error_code) == (ImportJob.FAILED, "dump_replaced")
    assert old.object_key in fake_r2["deleted"]


@override_settings(**R2)
def test_someone_elses_workspace_and_job_are_404(
    client: Client, ws: int, other_user: User, fake_r2: dict[str, Any]
) -> None:
    created = create(client, ws).json()["data"]
    client.force_login(other_user)
    assert create(client, ws).status_code == 404
    url = f"/api/workspaces/{ws}/imports/{created['id']}"
    assert call(client, "get", url).status_code == 404
    assert call(client, "post", f"{url}/start").status_code == 404
    assert call(client, "get", f"/api/workspaces/{ws}/imports").status_code == 404


def test_signed_out_is_401(client: Client) -> None:
    assert call(client, "post", "/api/workspaces/1/imports", {}).status_code == 401


@override_settings(**R2)
def test_a_running_job_that_stopped_reporting_shows_as_failed(
    client: Client, ws: int, fake_r2: dict[str, Any], user: User
) -> None:
    from datetime import timedelta

    from django.utils import timezone

    created = create(client, ws).json()["data"]
    ImportJob.objects.filter(pk=created["id"]).update(
        status=ImportJob.RUNNING, updated_at=timezone.now() - timedelta(hours=2)
    )
    got = call(client, "get", f"/api/workspaces/{ws}/imports/{created['id']}").json()
    assert got["data"]["status"] == "failed"
    assert got["data"]["error"]["code"] == "dump_interrupted"
    assert create(client, ws).status_code == 200  # the slot is free again
