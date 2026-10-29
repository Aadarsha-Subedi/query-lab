"""Gemini through the official google-genai SDK."""

import logging

import httpx
from django.conf import settings
from google import genai
from google.genai import errors, types

from common.llm.base import (
    LLMBadResponseError,
    LLMError,
    LLMInvalidKeyError,
    LLMProvider,
    LLMRateLimitedError,
    LLMRequest,
    LLMResponse,
    LLMTimeoutError,
    LLMUnavailableError,
)
from common.llm.constants import GEMINI_PRO_MIN_THINKING_BUDGET, PROVIDER_GEMINI

logger = logging.getLogger(__name__)


def _map_error(exc: Exception) -> LLMError:
    # Class and status only: Google's message can quote the key.
    logger.warning(
        "Gemini request failed: %s code=%s",
        type(exc).__name__,
        getattr(exc, "code", None),
    )
    if isinstance(exc, httpx.TimeoutException):
        return LLMTimeoutError()
    if isinstance(exc, errors.APIError):
        status = exc.code
        text = (exc.message or "").lower()
        # An unknown key comes back as 400 INVALID_ARGUMENT, not 401.
        if status in (401, 403) or "api key" in text:
            return LLMInvalidKeyError()
        if status == 429:
            return LLMRateLimitedError()
        if status == 408 or status == 504:
            return LLMTimeoutError()
    return LLMUnavailableError()


def _thinking_config(model: str) -> types.ThinkingConfig:
    """Keep reasoning to a minimum. Searching and paraphrasing need none, and the default
    dynamic thinking made each call take 25 to 35 s (and its tokens count against the output cap)."""
    if model.startswith("gemini-2.5"):
        # 2.5 Pro cannot switch thinking off; the smallest budget it accepts is 128.
        return types.ThinkingConfig(
            thinking_budget=GEMINI_PRO_MIN_THINKING_BUDGET if "pro" in model else 0
        )
    # Gemini 3 and later: Pro models do not accept "minimal".
    level = types.ThinkingLevel.LOW if "pro" in model else types.ThinkingLevel.MINIMAL
    return types.ThinkingConfig(thinking_level=level)


class GeminiProvider(LLMProvider):
    provider = PROVIDER_GEMINI

    def __init__(self, api_key: str, model: str):
        self.model = model
        self._client = genai.Client(
            api_key=api_key,
            http_options=types.HttpOptions(
                timeout=settings.LLM_REQUEST_TIMEOUT_SECONDS * 1000,  # milliseconds
                retry_options=types.HttpRetryOptions(attempts=1),  # no retries
            ),
        )

    def generate(self, request: LLMRequest) -> LLMResponse:
        def config(thinking: bool) -> types.GenerateContentConfig:
            return types.GenerateContentConfig(
                system_instruction=request.system or None,
                temperature=request.temperature,
                max_output_tokens=request.max_output_tokens,
                thinking_config=_thinking_config(self.model) if thinking else None,
                response_mime_type="application/json" if request.json_output else None,
            )

        try:
            try:
                response = self._client.models.generate_content(
                    model=self.model, contents=request.prompt, config=config(True)
                )
            except errors.ClientError as exc:
                # A 400 can mean this model rejects the thinking setting. Try once without
                # it; a bad key or an exhausted quota is not a 400 we should retry.
                if exc.code != 400 or "api key" in (exc.message or "").lower():
                    raise
                logger.warning(
                    "Gemini rejected the thinking setting; retrying without it"
                )
                response = self._client.models.generate_content(
                    model=self.model, contents=request.prompt, config=config(False)
                )
            text = response.text
        except Exception as exc:  # noqa: BLE001 - any SDK failure maps to an LLMError
            raise _map_error(exc) from None
        if not text or not text.strip():
            raise LLMBadResponseError()
        usage = response.usage_metadata
        return LLMResponse(
            text=text,
            model=self.model,
            input_tokens=(usage.prompt_token_count or 0) if usage else 0,
            output_tokens=(usage.candidates_token_count or 0) if usage else 0,
        )

    def validate_key(self) -> None:
        try:
            self._client.models.get(model=self.model)
        except Exception as exc:  # noqa: BLE001 - any SDK failure maps to an LLMError
            raise _map_error(exc) from None
