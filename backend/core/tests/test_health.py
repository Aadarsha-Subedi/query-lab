import time
from typing import Any

import pytest
from django.test import Client, override_settings

from core import health


@pytest.mark.django_db
def test_all_ok(client: Client, django_db_blocker: Any, data_connections: None) -> None:
    response = client.get("/api/health")
    assert response.status_code == 200, response.json()
    assert response.json() == {
        "status": "ok",
        "app_db": "ok",
        "data_db": "ok",
        "data_reader": "ok",
        "redis": "ok",
        "worker": "ok",
    }


def _boom() -> None:
    raise ConnectionError("down")


def _ok() -> None:
    return None


def test_one_failing_dependency_degrades(
    client: Client, monkeypatch: pytest.MonkeyPatch
) -> None:
    checks = dict.fromkeys(["app_db", "data_db", "data_reader", "redis", "worker"], _ok)
    checks["redis"] = _boom
    monkeypatch.setattr(health, "checks", lambda: checks)
    response = client.get("/api/health")
    assert response.status_code == 503
    body = response.json()
    assert body["status"] == "degraded"
    assert body["redis"] == "fail"
    assert body["app_db"] == "ok"


@override_settings(HEALTH_CHECK_TIMEOUT_SECONDS=0.2)
def test_hung_dependency_times_out(
    client: Client, monkeypatch: pytest.MonkeyPatch
) -> None:
    def hang() -> None:
        time.sleep(1)

    checks = dict.fromkeys(["app_db", "data_db", "data_reader", "redis", "worker"], _ok)
    checks["worker"] = hang
    monkeypatch.setattr(health, "checks", lambda: checks)
    started = time.monotonic()
    response = client.get("/api/health")
    assert time.monotonic() - started < 1
    assert response.status_code == 503
    assert response.json()["worker"] == "fail"
