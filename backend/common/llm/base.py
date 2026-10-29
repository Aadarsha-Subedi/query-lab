"""The provider interface and the errors every provider maps its failures to."""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field

from django.conf import settings


class LLMError(Exception):
    """Base class. Messages are generic on purpose: they never contain keys or prompts."""

    code = "llm_error"
    message = "The AI request failed."

    def __init__(self, message: str | None = None):
        super().__init__(message or self.message)


class LLMInvalidKeyError(LLMError):
    code = "llm_invalid_key"
    message = "The API key was rejected."


class LLMRateLimitedError(LLMError):
    code = "llm_rate_limited"
    message = "The provider rate limit or quota was reached."


class LLMInsufficientQuotaError(LLMRateLimitedError):
    """The account itself is out of credit or quota (not a per-minute limit)."""

    code = "llm_insufficient_quota"
    message = "The provider account has no credit or quota left."


class LLMTimeoutError(LLMError):
    code = "llm_timeout"
    message = "The provider did not answer in time."


class LLMUnavailableError(LLMError):
    code = "llm_unavailable"
    message = "The provider is unavailable."


class LLMUnsupportedError(LLMError):
    code = "llm_unsupported"
    message = "The provider does not support this operation."


class LLMBadResponseError(LLMError):
    code = "llm_bad_response"
    message = "The provider returned no usable answer."


@dataclass(frozen=True)
class LLMRequest:
    prompt: str
    system: str = ""
    json_output: bool = False
    # Limits come from settings (LLM_MAX_OUTPUT_TOKENS, LLM_TEMPERATURE) unless set.
    max_output_tokens: int = field(
        default_factory=lambda: settings.LLM_MAX_OUTPUT_TOKENS
    )
    temperature: float = field(default_factory=lambda: settings.LLM_TEMPERATURE)


@dataclass(frozen=True)
class LLMResponse:
    text: str
    model: str
    input_tokens: int = 0
    output_tokens: int = 0


class LLMProvider(ABC):
    provider: str
    model: str

    @abstractmethod
    def generate(self, request: LLMRequest) -> LLMResponse:
        """Return the model's text. Raises an LLMError subclass on any failure."""

    @abstractmethod
    def validate_key(self) -> None:
        """Cheap check that the key works for this model. Raises an LLMError subclass."""
