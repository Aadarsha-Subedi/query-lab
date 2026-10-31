import json

import httpx
import pytest

from common.llm import (
    LLMBadResponseError,
    LLMInvalidKeyError,
    LLMRateLimitedError,
    LLMRequest,
    LLMTimeoutError,
    LLMUnavailableError,
    allowed_models,
    create_provider,
)
from common.llm.anthropic_provider import AnthropicProvider
from common.llm.base import LLMInsufficientQuotaError
from common.llm.constants import PROVIDERS


def provider_for(handler) -> AnthropicProvider:
    return AnthropicProvider(
        "sk-ant-secret", "claude-haiku-5-5", transport=httpx.MockTransport(handler)
    )


def reply(status: int, body: dict) -> httpx.Response:
    return httpx.Response(status, json=body)


def test_generate_sends_the_request_and_reads_text_and_usage() -> None:
    seen: dict = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["url"] = str(request.url)
        seen["headers"] = request.headers
        seen["body"] = json.loads(request.content)
        return reply(
            200,
            {
                "content": [
                    {"type": "text", "text": '{"sql": '},
                    {"type": "text", "text": '"SELECT 1"}'},
                ],
                "usage": {"input_tokens": 12, "output_tokens": 7},
            },
        )

    result = provider_for(handler).generate(
        LLMRequest(prompt="the question", system="the rules", max_output_tokens=99)
    )
    assert result.text == '{"sql": "SELECT 1"}'
    assert (result.input_tokens, result.output_tokens) == (12, 7)
    assert seen["url"] == "https://api.anthropic.com/v1/messages"
    assert seen["headers"]["x-api-key"] == "sk-ant-secret"
    assert seen["headers"]["anthropic-version"] == "2023-06-01"
    assert seen["body"] == {
        "model": "claude-haiku-5-5",
        "max_tokens": 99,
        "system": "the rules",
        "messages": [{"role": "user", "content": "the question"}],
    }


@pytest.mark.parametrize(
    ("status", "body", "expected"),
    [
        (401, {"error": {"type": "authentication_error"}}, LLMInvalidKeyError),
        (403, {"error": {"type": "permission_error"}}, LLMInvalidKeyError),
        (429, {"error": {"type": "rate_limit_error"}}, LLMRateLimitedError),
        (402, {"error": {"type": "billing_error"}}, LLMInsufficientQuotaError),
        (529, {"error": {"type": "overloaded_error"}}, LLMUnavailableError),
        (500, {"error": {"type": "api_error"}}, LLMUnavailableError),
        (500, {}, LLMUnavailableError),
    ],
)
def test_http_errors_map_to_typed_errors(status, body, expected) -> None:
    provider = provider_for(lambda request: reply(status, body))
    with pytest.raises(expected):
        provider.generate(LLMRequest(prompt="q"))


def test_timeout_and_network_failures_map() -> None:
    def times_out(request: httpx.Request) -> httpx.Response:
        raise httpx.ReadTimeout("slow")

    def breaks(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("down")

    with pytest.raises(LLMTimeoutError):
        provider_for(times_out).generate(LLMRequest(prompt="q"))
    with pytest.raises(LLMUnavailableError):
        provider_for(breaks).generate(LLMRequest(prompt="q"))


def test_empty_answer_is_a_bad_response() -> None:
    provider = provider_for(lambda request: reply(200, {"content": [], "usage": {}}))
    with pytest.raises(LLMBadResponseError):
        provider.generate(LLMRequest(prompt="q"))


def test_validate_key_checks_the_model_endpoint() -> None:
    seen = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append((request.method, request.url.path))
        return reply(200, {"id": "claude-haiku-5-5"})

    provider_for(handler).validate_key()
    assert seen == [("GET", "/v1/models/claude-haiku-5-5")]
    with pytest.raises(LLMInvalidKeyError):
        provider_for(lambda r: reply(401, {})).validate_key()


def test_the_key_never_appears_in_an_error_or_a_log(caplog) -> None:
    body = {
        "error": {"type": "authentication_error", "message": "bad key sk-ant-secret"}
    }
    provider = provider_for(lambda request: reply(401, body))
    with pytest.raises(LLMInvalidKeyError) as info:
        provider.generate(LLMRequest(prompt="q"))
    assert "sk-ant-secret" not in str(info.value)
    assert "sk-ant-secret" not in caplog.text


def test_factory_knows_claude_but_users_cannot_save_a_claude_key() -> None:
    assert allowed_models("anthropic") == ["claude-haiku-5-5", "claude-sonnet-5-5"]
    assert isinstance(create_provider("anthropic", "key"), AnthropicProvider)
    assert "anthropic" not in PROVIDERS
