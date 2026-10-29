from unittest import mock

import httpx2
import openai
import pytest
from django.test import override_settings

from common.llm import (
    LLMInvalidKeyError,
    LLMRateLimitedError,
    LLMRequest,
    LLMTimeoutError,
    allowed_models,
    create_provider,
)
from common.llm.base import LLMInsufficientQuotaError
from common.llm.fake import FakeProvider
from common.llm.gemini import GeminiProvider
from common.llm.openai_provider import OpenAIProvider
from common.llm.openai_provider import _map_error as map_openai_error


class TestFactory:
    @override_settings(LLM_OPENAI_MODELS=["gpt-x", "gpt-y"])
    def test_default_model_is_the_first_allowed(self) -> None:
        provider = create_provider("openai", "key")
        assert isinstance(provider, OpenAIProvider)
        assert provider.model == "gpt-x"
        assert allowed_models("openai") == ["gpt-x", "gpt-y"]

    def test_gemini_provider(self) -> None:
        assert isinstance(create_provider("gemini", "key"), GeminiProvider)

    def test_unknown_provider_and_model_are_refused(self) -> None:
        with pytest.raises(ValueError):
            create_provider("unknown", "key")
        with pytest.raises(ValueError):
            create_provider("openai", "key", "not-allowed")


@override_settings(LLM_MAX_OUTPUT_TOKENS=77, LLM_TEMPERATURE=0.5)
def test_request_limits_come_from_settings() -> None:
    request = LLMRequest(prompt="hi")
    assert request.max_output_tokens == 77
    assert request.temperature == 0.5


def test_fake_provider_queues_answers_and_errors() -> None:
    fake = FakeProvider(answers=["SELECT 1"])
    assert fake.generate(LLMRequest(prompt="q")).text == "SELECT 1"
    fake.fail_with = LLMTimeoutError()
    with pytest.raises(LLMTimeoutError):
        fake.generate(LLMRequest(prompt="q"))
    fake.key_valid = False
    with pytest.raises(LLMInvalidKeyError):
        fake.validate_key()


def _openai_error(
    cls: type[openai.APIStatusError], status: int, code: str | None = None
) -> openai.APIStatusError:
    response = httpx2.Response(
        status, request=httpx2.Request("POST", "https://api.openai.com")
    )
    return cls("failed", response=response, body={"code": code} if code else None)


def test_openai_errors_map_to_llm_errors() -> None:
    assert isinstance(
        map_openai_error(_openai_error(openai.AuthenticationError, 401)),
        LLMInvalidKeyError,
    )
    assert isinstance(
        map_openai_error(_openai_error(openai.RateLimitError, 429)), LLMRateLimitedError
    )
    quota = _openai_error(openai.RateLimitError, 429, "insufficient_quota")
    quota.code = "insufficient_quota"
    assert isinstance(map_openai_error(quota), LLMInsufficientQuotaError)
    timeout = openai.APITimeoutError(request=httpx2.Request("POST", "https://x"))
    assert isinstance(map_openai_error(timeout), LLMTimeoutError)


def test_openai_reasoning_models_get_more_room() -> None:
    provider = OpenAIProvider(api_key="key", model="gpt-5-mini")
    completion = mock.Mock()
    completion.choices = [mock.Mock(message=mock.Mock(content="ok"))]
    completion.usage = mock.Mock(prompt_tokens=1, completion_tokens=2)
    with mock.patch.object(
        provider._client.chat.completions, "create", return_value=completion
    ) as create:
        provider.generate(LLMRequest(prompt="hi", max_output_tokens=10))
    assert create.call_args.kwargs["max_completion_tokens"] == 40
    assert create.call_args.kwargs["reasoning_effort"] == "minimal"
