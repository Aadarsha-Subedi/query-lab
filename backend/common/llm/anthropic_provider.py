"""Claude through Anthropic's Messages API over httpx (already installed), so the
image needs no extra SDK."""

import logging
from typing import Any

import httpx
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
    ANTHROPIC_API_URL,
    ANTHROPIC_API_VERSION,
    PROVIDER_ANTHROPIC,
)

logger = logging.getLogger(__name__)


def _error_type(response: httpx.Response) -> str | None:
    try:
        return response.json()["error"]["type"]
    except (ValueError, KeyError, TypeError):
        return None


def _map_status(response: httpx.Response) -> LLMError:
    """Status and Anthropic's error type only: the message can quote the key."""
    status = response.status_code
    error_type = _error_type(response)
    logger.warning("Anthropic request failed: status=%s type=%s", status, error_type)
    if status in (401, 403):
        return LLMInvalidKeyError()
    if status == 402 or (status == 400 and error_type == "billing_error"):
        return LLMInsufficientQuotaError()
    if status == 429:
        return LLMRateLimitedError()
    return LLMUnavailableError()  # 5xx, 529 (overloaded) and anything unexpected


class AnthropicProvider(LLMProvider):
    provider = PROVIDER_ANTHROPIC

    def __init__(
        self,
        api_key: str,
        model: str,
        transport: httpx.BaseTransport | None = None,
    ):
        self.model = model
        self._client = httpx.Client(
            base_url=ANTHROPIC_API_URL,
            headers={
                "x-api-key": api_key,
                "anthropic-version": ANTHROPIC_API_VERSION,
            },
            timeout=settings.LLM_REQUEST_TIMEOUT_SECONDS,
            transport=transport,
        )

    def _send(self, method: str, path: str, **kwargs: Any) -> httpx.Response:
        try:
            response = self._client.request(method, path, **kwargs)
        except httpx.TimeoutException:
            logger.warning("Anthropic request timed out")
            raise LLMTimeoutError() from None
        except httpx.HTTPError as exc:
            logger.warning("Anthropic request failed: %s", type(exc).__name__)
            raise LLMUnavailableError() from None
        if response.status_code >= 400:
            raise _map_status(response)
        return response

    def generate(self, request: LLMRequest) -> LLMResponse:
        body: dict[str, Any] = {
            "model": self.model,
            "max_tokens": request.max_output_tokens,
            "messages": [{"role": "user", "content": request.prompt}],
        }
        if request.system:
            body["system"] = request.system
        # No temperature: newer Claude models may reject it; the default is fine.
        data = self._send("POST", "/v1/messages", json=body).json()
        blocks = data.get("content") or []
        text = "".join(b.get("text", "") for b in blocks if b.get("type") == "text")
        if not text.strip():
            logger.warning(
                "Anthropic returned no text: stop_reason=%s", data.get("stop_reason")
            )
            raise LLMBadResponseError()
        usage = data.get("usage") or {}
        return LLMResponse(
            text=text,
            model=self.model,
            input_tokens=int(usage.get("input_tokens", 0)),
            output_tokens=int(usage.get("output_tokens", 0)),
        )

    def validate_key(self) -> None:
        self._send("GET", f"/v1/models/{self.model}")
