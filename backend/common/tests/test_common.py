from datetime import date

import pytest
from django.core.exceptions import ValidationError
from django.test import override_settings

from accounts.models import User
from common import crypto
from common.cache.manager import CacheManager
from common.email.utils import mask_email, normalize_email
from common.exception.domain import ServiceUnavailableException, ValidationException
from common.logger.redaction import redact_sensitive_data
from common.logger.request_id import accept_request_id
from common.response.domain import ErrorEnvelope, SuccessEnvelope, error_body, success
from common.validators.date import validate_date_range
from common.validators.disposable import is_disposable
from common.validators.password import (
    PasswordValidator,
    validate_password_strength,
)


class TestPasswordValidator:
    def test_accepts_strong_password(self) -> None:
        PasswordValidator()("Correct-Horse-9")

    @pytest.mark.parametrize(
        "bad", ["Sh0rt-Pw", "password1234", "alllowercase-123", "ALLUPPERCASE-123"]
    )
    def test_rejects_short_common_and_single_case(self, bad: str) -> None:
        with pytest.raises(ValidationError):
            PasswordValidator()(bad)

    def test_rejects_password_similar_to_email(self) -> None:
        candidate = User(email="grace.hopper@example.com")
        with pytest.raises(ValidationError):
            PasswordValidator(user=candidate)("Grace.Hopper@Example.com1")

    @override_settings(PASSWORD_MIN_LENGTH=20)
    def test_minimum_length_comes_from_settings(self) -> None:
        with pytest.raises(ValidationError):
            PasswordValidator()("Correct-Horse-9")

    def test_api_variant_points_at_the_field(self) -> None:
        with pytest.raises(ValidationException) as exc:
            validate_password_strength("short", field="password1")
        assert {error["field"] for error in exc.value.errors} == {"password1"}


def test_date_range() -> None:
    validate_date_range(date(2026, 1, 1), date(2026, 1, 1))
    with pytest.raises(ValidationException):
        validate_date_range(date(2026, 1, 2), date(2026, 1, 1))


def test_disposable_domains_and_subdomains() -> None:
    assert is_disposable("x@mailinator.com")
    assert is_disposable("x@mx.mailinator.com")
    assert not is_disposable("x@gmail.com")


def test_email_helpers() -> None:
    assert normalize_email("  Ada@Example.COM ") == "ada@example.com"
    assert mask_email("ada@example.com") == "a***@example.com"


def test_redaction_is_recursive_and_case_insensitive() -> None:
    data = {"Password": "x", "nested": [{"api_key": "y", "name": "ok"}]}
    assert redact_sensitive_data(data) == {
        "Password": "***REDACTED***",
        "nested": [{"api_key": "***REDACTED***", "name": "ok"}],
    }


def test_request_id_rejects_odd_input() -> None:
    assert accept_request_id("abc12345") == "abc12345"
    assert accept_request_id("bad id\n with spaces") != "bad id\n with spaces"


class TestCrypto:
    def test_round_trip_and_rotation(self, settings: object) -> None:
        token = crypto.encrypt("sk-user-key")
        assert token != "sk-user-key"
        assert crypto.decrypt(token) == "sk-user-key"
        assert crypto.decrypt(crypto.rotate(token)) == "sk-user-key"

    @override_settings(ENCRYPTION_KEYS=[])
    def test_unconfigured_is_a_clear_error(self) -> None:
        with pytest.raises(ServiceUnavailableException):
            crypto.encrypt("x")

    @override_settings(ENCRYPTION_KEYS=["not-a-fernet-key"])
    def test_invalid_key_never_echoed(self) -> None:
        with pytest.raises(ServiceUnavailableException) as exc:
            crypto.encrypt("x")
        assert "not-a-fernet-key" not in str(exc.value)


class TestCacheManager:
    @override_settings(CACHE_DEFAULT_TIMEOUT_SECONDS=42)
    def test_timeout_comes_from_settings(self) -> None:
        assert CacheManager().timeout == 42
        assert CacheManager(timeout=7).timeout == 7

    def test_get_or_set_loads_once(self) -> None:
        manager = CacheManager()
        calls = []

        def loader() -> int:
            calls.append(1)
            return 5

        assert manager.get_or_set("k", loader) == 5
        assert manager.get_or_set("k", loader) == 5
        assert len(calls) == 1

    def test_scoped_keys_are_hashed(self) -> None:
        key = CacheManager().build_scoped_key("schema", "workspace", "1")
        assert key.startswith("schema:") and "workspace" not in key


def test_envelopes_validate() -> None:
    assert SuccessEnvelope[int].model_validate(success(3, "done")).data == 3
    assert ErrorEnvelope.model_validate(error_body("no", "bad", 400)).code == "bad"
