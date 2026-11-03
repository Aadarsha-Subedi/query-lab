"""OpenAI, and Groq through its OpenAI-compatible API, with the official openai SDK."""

import logging
from typing import Any, ClassVar

import openai
from django.conf import settings

from common.llm.base import (
    LLMBadResponseError,
    LLMError,
    LLMInsufficientQuotaError,
    LLMInvalidKeyError,
    LLMProvider,
    LLMRateLimitedError,
    LLMRequest,
    LLMResponse,
    LLMTimeoutError,
    LLMUnavailableError,
)
from common.llm.constants import (
    GROQ_BASE_URL,
    OPENAI_REASONING_EFFORT,
    OPENAI_REASONING_MODEL_PREFIX,
    OPENAI_REASONING_TOKEN_FACTOR,
    PROVIDER_GROQ,
    PROVIDER_OPENAI,
)

logger = logging.getLogger(__name__)


def _log_failure(exc: Exception) -> None:
    """Class, HTTP status and OpenAI's error code only. The message can quote the API key."""
    logger.warning(
        "OpenAI request failed: %s status=%s code=%s",
        type(exc).__name__,
        getattr(exc, "status_code", None),
        getattr(exc, "code", None),
    )


def _map_error(exc: Exception) -> LLMError:
    _log_failure(exc)
    if isinstance(exc, openai.APITimeoutError):
        return LLMTimeoutError()
    if isinstance(exc, (openai.AuthenticationError, openai.PermissionDeniedError)):
        return LLMInvalidKeyError()
    # 413 is Groq's answer when one request alone exceeds its tokens-per-minute limit.
    if getattr(exc, "status_code", None) == 413:
        return LLMRateLimitedError()
    if isinstance(exc, openai.RateLimitError):
        # The same 429 also means the account has run out of credit.
        if getattr(exc, "code", None) == "insufficient_quota":
            return LLMInsufficientQuotaError()
        return LLMRateLimitedError()
    return LLMUnavailableError()


class OpenAIProvider(LLMProvider):
    provider = PROVIDER_OPENAI
    base_url: str | None = None
    json_mode = True
    sends_temperature = False
    extra_options: ClassVar[dict[str, Any]] = {}

    def __init__(self, api_key: str, model: str):
        self.model = model
        self._client = openai.OpenAI(
            api_key=api_key,
            base_url=self.base_url,
            timeout=settings.LLM_REQUEST_TIMEOUT_SECONDS,
            max_retries=0,
        )

    def generate(self, request: LLMRequest) -> LLMResponse:
        messages: list[Any] = []
        if request.system:
            messages.append({"role": "system", "content": request.system})
        messages.append({"role": "user", "content": request.prompt})
        options: dict[str, Any] = {}
        max_tokens = request.max_output_tokens
        if self.model.startswith(OPENAI_REASONING_MODEL_PREFIX):
            options["reasoning_effort"] = OPENAI_REASONING_EFFORT
            max_tokens *= OPENAI_REASONING_TOKEN_FACTOR
        if request.json_output and self.json_mode:
            options["response_format"] = {"type": "json_object"}
        if self.sends_temperature:
            options["temperature"] = request.temperature
        options.update(self.extra_options)
        try:
            # No temperature for OpenAI: its reasoning models reject anything but the default.
            response = self._client.chat.completions.create(
                model=self.model,
                messages=messages,
                max_completion_tokens=max_tokens,
                **options,
            )
        except Exception as exc:  # noqa: BLE001 - any SDK failure maps to an LLMError
            raise _map_error(exc) from None
        choice = response.choices[0] if response.choices else None
        text = choice.message.content if choice else None
        if not text or not text.strip():
            logger.warning(
                "OpenAI returned no text: finish_reason=%s",
                getattr(choice, "finish_reason", None),
            )
            raise LLMBadResponseError()
        usage = response.usage
        return LLMResponse(
            text=text,
            model=self.model,
            input_tokens=usage.prompt_tokens if usage else 0,
            output_tokens=usage.completion_tokens if usage else 0,
        )

    def validate_key(self) -> None:
        try:
            self._client.models.retrieve(self.model)
        except Exception as exc:  # noqa: BLE001 - any SDK failure maps to an LLMError
            raise _map_error(exc) from None


class GroqProvider(OpenAIProvider):
    provider = PROVIDER_GROQ
    base_url = GROQ_BASE_URL
    # Groq's JSON mode fails the whole request with a 400 when the model strays from
    # JSON. Without it a stray reply reaches our parsers, which ask again.
    json_mode = False
    sends_temperature = True
    # The reasoning text would otherwise arrive inside the reply and break the parse.
    extra_options: ClassVar[dict[str, Any]] = {
        "extra_body": {"reasoning_format": "hidden"}
    }
