import json
from typing import Any

import pytest
from django.core.cache import cache
from django.test import Client, override_settings

from accounts.models import User
from ask import keys
from ask.errors import DefaultKeyLimitReached
from ask.models import UserLLMKey
from common import crypto
from common.exception.domain import BadRequestException
from common.llm import LLMInvalidKeyError
from common.llm.fake import FakeProvider

pytestmark = pytest.mark.django_db

SECRET = "sk-test-secret-1234"


class Calls:
    def __init__(self) -> None:
        self.built: list[tuple[str, str, str | None]] = []
        self.valid = True


@pytest.fixture
def calls(monkeypatch: pytest.MonkeyPatch) -> Calls:
    recorded = Calls()

    def fake_create(
        provider: str, api_key: str, model: str | None = None
    ) -> FakeProvider:
        recorded.built.append((provider, api_key, model))
        fake = FakeProvider(model=model or "m")
        fake.key_valid = recorded.valid
        return fake

    monkeypatch.setattr(keys, "create_provider", fake_create)
    return recorded


def put(client: Client, provider: str, body: dict[str, Any]) -> Any:
    return client.put(
        f"/api/llm-keys/{provider}", json.dumps(body), content_type="application/json"
    )


def test_signed_out_is_refused(client: Client) -> None:
    assert client.get("/api/llm-keys").status_code == 401
    assert put(client, "openai", {"api_key": SECRET}).status_code == 401


def test_save_list_delete(client: Client, user: User, calls: Calls) -> None:
    client.force_login(user)
    response = put(client, "openai", {"api_key": SECRET, "model": "gpt-5-nano"})
    assert response.status_code == 200
    saved = response.json()["data"]
    assert saved["provider"] == "openai"
    assert saved["key_last4"] == "1234"
    assert saved["model"] == "gpt-5-nano"
    assert saved["is_active"] is True  # the first key becomes the active one
    listing = client.get("/api/llm-keys")
    assert [row["provider"] for row in listing.json()["data"]] == ["openai"]
    assert SECRET not in listing.content.decode()
    assert SECRET not in response.content.decode()
    assert client.delete("/api/llm-keys/openai").status_code == 200
    assert client.get("/api/llm-keys").json()["data"] == []


def test_key_is_stored_encrypted(client: Client, user: User, calls: Calls) -> None:
    client.force_login(user)
    put(client, "gemini", {"api_key": SECRET})
    row = UserLLMKey.objects.get(user=user)
    assert SECRET not in row.encrypted_key
    assert crypto.decrypt(row.encrypted_key) == SECRET


def test_saving_again_replaces_the_key(
    client: Client, user: User, calls: Calls
) -> None:
    client.force_login(user)
    put(client, "openai", {"api_key": SECRET})
    put(client, "openai", {"api_key": "sk-another-key-9999"})
    assert UserLLMKey.objects.filter(user=user).count() == 1
    assert UserLLMKey.objects.get(user=user).key_last4 == "9999"


@pytest.mark.parametrize(
    ("provider", "body", "code"),
    [
        ("openai", {"api_key": "short"}, "key_invalid"),
        ("openai", {"api_key": SECRET, "model": "no-such-model"}, "model_invalid"),
    ],
)
def test_bad_input_is_refused(
    client: Client, user, calls: Calls, provider, body, code
) -> None:
    client.force_login(user)
    response = put(client, provider, body)
    assert response.status_code == 400
    assert response.json()["code"] == code
    assert UserLLMKey.objects.count() == 0


def test_unknown_provider_is_refused(client: Client, user: User, calls: Calls) -> None:
    client.force_login(user)
    assert put(client, "claude", {"api_key": SECRET}).status_code == 422


def test_rejected_key_is_not_saved_and_not_echoed(
    client: Client, user, calls: Calls
) -> None:
    calls.valid = False
    client.force_login(user)
    response = put(client, "openai", {"api_key": SECRET})
    assert response.status_code == 400
    assert response.json()["code"] == LLMInvalidKeyError.code
    assert SECRET not in response.content.decode()
    assert UserLLMKey.objects.count() == 0


def test_users_only_see_their_own_keys(
    client: Client, user: User, other_user: User, calls: Calls
) -> None:
    client.force_login(user)
    put(client, "openai", {"api_key": SECRET})
    client.force_login(other_user)
    assert client.get("/api/llm-keys").json()["data"] == []
    client.delete("/api/llm-keys/openai")
    assert UserLLMKey.objects.filter(user=user).count() == 1


def test_own_source_uses_the_active_key(user: User, calls: Calls) -> None:
    default = keys.resolve_provider(user)
    assert default.key_source == keys.KEY_DEFAULT
    assert calls.built[-1] == ("gemini", "test-gemini-key", "gemini-3.5-flash")
    UserLLMKey.objects.create(
        user=user,
        provider="openai",
        encrypted_key=crypto.encrypt(SECRET),
        key_last4="1234",
        model="gpt-5-nano",
        is_active=True,
    )
    # A saved key alone changes nothing: the source decides.
    assert keys.resolve_provider(user).key_source == keys.KEY_DEFAULT
    keys.set_ai_source(user, "own")
    own = keys.resolve_provider(user)
    assert own.key_source == keys.KEY_OWN
    assert own.provider_name == "openai"
    assert calls.built[-1] == ("openai", SECRET, "gpt-5-nano")


@override_settings(ASK_DEFAULT_KEY_DAILY_LIMIT=2)
def test_default_key_daily_limit_is_per_user(user: User, other_user: User) -> None:
    cache.clear()
    keys.spend_default_key(user)
    keys.spend_default_key(user)
    with pytest.raises(DefaultKeyLimitReached):
        keys.spend_default_key(user)
    keys.spend_default_key(other_user)


def make_two(client: Client, calls: Calls) -> None:
    put(client, "openai", {"api_key": SECRET})
    put(client, "gemini", {"api_key": "gem-test-key-5678"})


def call(
    client: Client, method: str, path: str, body: dict[str, Any] | None = None
) -> Any:
    return getattr(client, method)(
        path, json.dumps(body or {}), content_type="application/json"
    )


def test_only_one_key_is_active_and_it_can_switch(
    client: Client, user: User, calls: Calls
) -> None:
    client.force_login(user)
    make_two(client, calls)
    active = {
        r["provider"]: r["is_active"]
        for r in client.get("/api/llm-keys").json()["data"]
    }
    assert active == {"gemini": False, "openai": True}
    assert call(client, "put", "/api/llm-keys/gemini/activate").status_code == 200
    active = {
        r["provider"]: r["is_active"]
        for r in client.get("/api/llm-keys").json()["data"]
    }
    assert active == {"gemini": True, "openai": False}


def test_activate_needs_a_saved_key(client: Client, user: User, calls: Calls) -> None:
    client.force_login(user)
    response = call(client, "put", "/api/llm-keys/openai/activate")
    assert response.status_code == 400
    assert response.json()["code"] == "no_key_for_provider"


def test_deleting_the_active_key_hands_over_to_the_other(
    client: Client, user: User, calls: Calls
) -> None:
    client.force_login(user)
    make_two(client, calls)
    client.delete("/api/llm-keys/openai")
    rows = client.get("/api/llm-keys").json()["data"]
    assert [(r["provider"], r["is_active"]) for r in rows] == [("gemini", True)]


def test_model_can_change_without_the_key(
    client: Client, user: User, calls: Calls
) -> None:
    client.force_login(user)
    put(client, "openai", {"api_key": SECRET})
    models = client.get("/api/llm-keys-models").json()["data"]
    other = models["openai"][-1]
    response = call(client, "put", "/api/llm-keys/openai/model", {"model": other})
    assert response.status_code == 200
    assert UserLLMKey.objects.get(user=user).model == other
    bad = call(client, "put", "/api/llm-keys/openai/model", {"model": "nope"})
    assert bad.status_code == 400
    assert bad.json()["code"] == "model_invalid"


def test_ai_source_defaults_to_querylab_and_is_saved(
    client: Client, user: User
) -> None:
    client.force_login(user)
    assert client.get("/api/llm-settings").json()["data"] == {"source": "querylab"}
    assert (
        call(client, "put", "/api/llm-settings", {"source": "own"}).status_code == 200
    )
    assert client.get("/api/llm-settings").json()["data"] == {"source": "own"}
    assert call(client, "put", "/api/llm-settings", {"source": "x"}).status_code == 422


def test_own_source_without_an_active_key_is_blocked(
    client: Client, user: User, calls: Calls
) -> None:
    keys.set_ai_source(user, "own")
    with pytest.raises(BadRequestException) as error:
        keys.resolve_provider(user)
    assert error.value.error_code == "no_active_key"
