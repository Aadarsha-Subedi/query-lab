"""Which LLM key an ask uses: the user's own (OpenAI or Gemini) if they saved
one, else QueryLab's default Gemini key from .env, with a daily cap per user."""

from dataclasses import dataclass
from datetime import UTC, datetime

from django.conf import settings
from django.core.cache import cache

from accounts.models import User
from ask.errors import DefaultKeyLimitReached
from ask.models import UserLLMKey
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
    return row


def resolve_provider(user: User) -> ResolvedProvider:
    """The user's most recently saved key, else the default key."""
    own = UserLLMKey.objects.filter(user=user).order_by("-updated_at").first()
    if own is not None:
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
