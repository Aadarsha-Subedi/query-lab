"""Which LLM key an ask uses. The user picks a source: QueryLab's default Gemini key
from .env (daily cap per user) or their own active key (one OpenAI, one Gemini)."""

from dataclasses import dataclass
from datetime import UTC, datetime

from django.conf import settings
from django.core.cache import cache
from django.db import transaction

from accounts.models import User
from ask.errors import DefaultKeyLimitReached
from ask.models import UserAISetting, UserLLMKey
from common import crypto
from common.exception.domain import BadRequestException
from common.llm import LLMError, LLMProvider, allowed_models, create_provider
from common.llm.constants import PROVIDER_GEMINI, PROVIDERS

KEY_MIN_CHARS = 8
KEY_MAX_CHARS = 512
DAY_SECONDS = 24 * 60 * 60

KEY_OWN = "own"
KEY_DEFAULT = "default"


@dataclass(frozen=True)
class ResolvedProvider:
    provider: LLMProvider
    provider_name: str
    key_source: str


def save_key(user: User, provider: str, api_key: str, model: str | None) -> UserLLMKey:
    """Check the key with the provider, then store it encrypted (replacing any
    earlier key for the same provider)."""
    if provider not in PROVIDERS:
        raise BadRequestException("Unknown provider.", error_code="unknown_provider")
    api_key = api_key.strip()
    if not KEY_MIN_CHARS <= len(api_key) <= KEY_MAX_CHARS:
        raise BadRequestException("The key looks invalid.", error_code="key_invalid")
    model = model or allowed_models(provider)[0]
    if model not in allowed_models(provider):
        raise BadRequestException(
            "That model is not available.", error_code="model_invalid"
        )
    try:
        create_provider(provider, api_key, model).validate_key()
    except LLMError as error:
        raise BadRequestException(error.message, error_code=error.code) from None
    row, _ = UserLLMKey.objects.update_or_create(
        user=user,
        provider=provider,
        defaults={
            "encrypted_key": crypto.encrypt(api_key),
            "key_last4": api_key[-4:],
            "model": model,
        },
    )
    if not UserLLMKey.objects.filter(user=user, is_active=True).exists():
        row.is_active = True
        row.save(update_fields=["is_active", "updated_at"])
    return row


def change_model(user: User, provider: str, model: str) -> UserLLMKey:
    """Switch the model of a saved key without sending the key again."""
    row = _own_key(user, provider)
    if model not in allowed_models(provider):
        raise BadRequestException(
            "That model is not available.", error_code="model_invalid"
        )
    row.model = model
    row.save(update_fields=["model", "updated_at"])
    return row


def activate_key(user: User, provider: str) -> UserLLMKey:
    """Make this provider's key the one asks use (only one is active at a time)."""
    row = _own_key(user, provider)
    with transaction.atomic():
        UserLLMKey.objects.filter(user=user, is_active=True).update(is_active=False)
        row.is_active = True
        row.save(update_fields=["is_active", "updated_at"])
    return row


def delete_key(user: User, provider: str) -> None:
    """Remove a key. If it was the active one, the remaining key (if any) takes over."""
    with transaction.atomic():
        removed = UserLLMKey.objects.filter(user=user, provider=provider).first()
        if removed is None:
            return
        was_active = removed.is_active
        removed.delete()
        if was_active:
            other = UserLLMKey.objects.filter(user=user).first()
            if other is not None:
                other.is_active = True
                other.save(update_fields=["is_active", "updated_at"])


def _own_key(user: User, provider: str) -> UserLLMKey:
    if provider not in PROVIDERS:
        raise BadRequestException("Unknown provider.", error_code="unknown_provider")
    row = UserLLMKey.objects.filter(user=user, provider=provider).first()
    if row is None:
        raise BadRequestException(
            "Save a key for that provider first.", error_code="no_key_for_provider"
        )
    return row


def ai_source(user: User) -> str:
    setting = UserAISetting.objects.filter(user=user).first()
    return setting.source if setting else UserAISetting.SOURCE_QUERYLAB


def set_ai_source(user: User, source: str) -> str:
    if source not in UserAISetting.SOURCES:
        raise BadRequestException("Unknown AI source.", error_code="unknown_ai_source")
    UserAISetting.objects.update_or_create(user=user, defaults={"source": source})
    return source


def resolve_provider(user: User) -> ResolvedProvider:
    """The key this user's asks run on, by their chosen source. "Own" with no active
    key is refused with a clear message instead of quietly spending QueryLab's key."""
    if ai_source(user) == UserAISetting.SOURCE_OWN:
        own = UserLLMKey.objects.filter(user=user, is_active=True).first()
        if own is None:
            raise BadRequestException(
                "You chose your own AI but have no active key.",
                error_code="no_active_key",
            )
        provider = create_provider(
            own.provider, crypto.decrypt(own.encrypted_key), own.model
        )
        return ResolvedProvider(provider, own.provider, KEY_OWN)
    provider = create_provider(
        PROVIDER_GEMINI,
        settings.LLM_DEFAULT_GEMINI_API_KEY,
        settings.LLM_DEFAULT_MODEL,
    )
    return ResolvedProvider(provider, PROVIDER_GEMINI, KEY_DEFAULT)


def _day_key(user: User) -> str:
    return f"ask:default-key:{user.pk}:{datetime.now(UTC):%Y%m%d}"


def spend_default_key(user: User) -> None:
    """Count one ask on QueryLab's key; raise once the daily limit is passed."""
    key = _day_key(user)
    cache.add(key, 0, DAY_SECONDS)
    if cache.incr(key) > settings.ASK_DEFAULT_KEY_DAILY_LIMIT:
        raise DefaultKeyLimitReached()


def default_key_spent_today(user: User) -> int:
    """Asks counted on QueryLab's key today (UTC), at most the daily limit. Read only."""
    return min(cache.get(_day_key(user), 0), settings.ASK_DEFAULT_KEY_DAILY_LIMIT)
