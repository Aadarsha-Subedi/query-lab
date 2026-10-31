import json
from typing import Any

import pytest
from django.test import Client, override_settings

from accounts.models import User
from ask import keys
from ask.models import AskLog
from common.llm import LLMInvalidKeyError
from common.llm.fake import FakeProvider

pytestmark = [pytest.mark.django_db, pytest.mark.usefixtures("data_connections")]


def reply(sql: str) -> str:
    return json.dumps({"sql": sql, "rationale": "r", "self_confidence": 0.9})


@pytest.fixture
def llm(monkeypatch: pytest.MonkeyPatch) -> FakeProvider:
    fake = FakeProvider(model="fake-model")
    monkeypatch.setattr(
        keys,
        "resolve_provider",
        lambda user: keys.ResolvedProvider(fake, "gemini", keys.KEY_OWN),
    )
    return fake


def post(client: Client, question: Any) -> Any:
    return client.post(
        "/api/ask", json.dumps({"question": question}), content_type="application/json"
    )


def test_signed_out_gets_401(client: Client) -> None:
    assert post(client, "hi").status_code == 401


def test_success_shape(client: Client, user: User, llm: FakeProvider) -> None:
    llm.answers = [
        reply(
            "SELECT order_status, count(*) AS n FROM demo.orders GROUP BY 1 ORDER BY 2 DESC"
        )
    ]
    client.force_login(user)
    response = post(client, "Orders by status?")
    assert response.status_code == 200
    data = response.json()["data"]
    assert data["columns"] == ["order_status", "n"]
    assert data["rows"][0][0] == "delivered"
    assert data["row_count"] == len(data["rows"])
    assert data["truncated"] is False
    assert data["confidence"] is None  # hidden until CONFIDENCE_SHOW_SCORE
    assert data["check"] == "checked"
    assert data["model"] == "fake-model"
    assert data["sql"].upper().startswith("SELECT")
    assert set(data) == {
        "question",
        "sql",
        "columns",
        "rows",
        "row_count",
        "truncated",
        "confidence",
        "check",
        "rationale",
        "model",
        "latency_ms",
    }


def test_bad_question_is_400(client: Client, user: User, llm: FakeProvider) -> None:
    client.force_login(user)
    response = post(client, "   ")
    assert response.status_code == 400
    assert response.json()["code"] == "question_invalid"


@override_settings(ASK_MAX_REPAIR_ATTEMPTS=0)
def test_guard_rejection_is_400_and_hides_the_sql(
    client: Client, user: User, llm: FakeProvider
) -> None:
    llm.answers = [reply("DROP TABLE demo.orders")]
    client.force_login(user)
    response = post(client, "Drop it")
    assert response.status_code == 400
    assert response.json()["code"] == "guard_rejected"
    assert "DROP" not in response.content.decode()


@override_settings(ASK_MAX_REPAIR_ATTEMPTS=0)
def test_database_error_is_422(client: Client, user: User, llm: FakeProvider) -> None:
    llm.answers = [reply("SELECT 1 / 0")]
    client.force_login(user)
    response = post(client, "Divide")
    assert response.status_code == 422
    assert response.json()["code"] == "query_failed"
    assert "division" not in response.content.decode()


@override_settings(READER_STATEMENT_TIMEOUT_MS=200, ASK_MAX_REPAIR_ATTEMPTS=0)
def test_timeout_is_504(client: Client, user: User, llm: FakeProvider) -> None:
    llm.answers = [reply("SELECT count(*) FROM generate_series(1, 100000000)")]
    client.force_login(user)
    assert post(client, "Slow").status_code == 504


def test_llm_failure_is_502(client: Client, user: User, llm: FakeProvider) -> None:
    llm.fail_with = LLMInvalidKeyError()
    client.force_login(user)
    response = post(client, "x?")
    assert response.status_code == 502
    assert response.json()["code"] == "llm_invalid_key"


@override_settings(THROTTLE_ASK_RATE="2/m")
def test_throttled_after_the_ask_rate(
    client: Client, user: User, llm: FakeProvider
) -> None:
    llm.answers = [reply("SELECT 1")] * 5
    client.force_login(user)
    assert post(client, "a?").status_code == 200
    assert post(client, "b?").status_code == 200
    limited = post(client, "c?")
    assert limited.status_code == 429
    assert limited.headers["Retry-After"]
    assert AskLog.objects.count() == 2


@override_settings(ASK_DEFAULT_KEY_DAILY_LIMIT=1)
def test_default_key_limit_is_429(
    client: Client, user: User, monkeypatch: pytest.MonkeyPatch
) -> None:
    fake = FakeProvider(answers=[reply("SELECT 1")] * 3)
    monkeypatch.setattr(
        keys,
        "resolve_provider",
        lambda u: keys.ResolvedProvider(fake, "gemini", keys.KEY_DEFAULT),
    )
    client.force_login(user)
    assert post(client, "a?").status_code == 200
    response = post(client, "b?")
    assert response.status_code == 429
    assert response.json()["code"] == "default_key_limit"


def test_ask_is_listed_in_the_openapi_docs(client: Client) -> None:
    paths = client.get("/api/openapi.json").json()["paths"]
    assert "post" in paths["/api/ask"]
    assert "put" in paths["/api/llm-keys/{provider}"]


def test_not_answerable_is_422_with_the_models_explanation(
    client: Client, user: User, llm: FakeProvider
) -> None:
    llm.answers = [
        json.dumps(
            {
                "answerable": False,
                "sql": "",
                "rationale": "The data has no weather.",
                "self_confidence": 0,
            }
        )
    ]
    client.force_login(user)
    response = post(client, "What is the weather in Lisbon?")
    assert response.status_code == 422
    body = response.json()
    assert body["code"] == "not_answerable"
    assert body["message"] == "The data has no weather."
