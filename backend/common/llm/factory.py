"""Builds the provider a call should use. This is the only place that knows the vendors.

Querylab is bring-your-own-key: every provider is built from a user's own key.
"""

from django.conf import settings

from common.llm.base import LLMProvider
from common.llm.constants import PROVIDER_GEMINI, PROVIDER_OPENAI
from common.llm.gemini import GeminiProvider
from common.llm.openai_provider import OpenAIProvider

_PROVIDER_CLASSES: dict[str, type[GeminiProvider] | type[OpenAIProvider]] = {
    PROVIDER_GEMINI: GeminiProvider,
    PROVIDER_OPENAI: OpenAIProvider,
}


def allowed_models(provider: str) -> list[str]:
    """Models a user may pick for `provider`; the first is the default."""
    return {
        PROVIDER_GEMINI: settings.LLM_GEMINI_MODELS,
        PROVIDER_OPENAI: settings.LLM_OPENAI_MODELS,
    }[provider]


def create_provider(
    provider: str, api_key: str, model: str | None = None
) -> LLMProvider:
    """A provider for the user's own key. Unknown providers and models are refused."""
    if provider not in _PROVIDER_CLASSES:
        raise ValueError(f"Unknown LLM provider: {provider}")
    models = allowed_models(provider)
    model = model or models[0]
    if model not in models:
        raise ValueError(f"Model not allowed for {provider}: {model}")
    return _PROVIDER_CLASSES[provider](api_key=api_key, model=model)
