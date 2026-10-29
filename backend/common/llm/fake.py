"""In-memory provider for tests. Queue answers or an error, inspect `requests`."""

from common.llm.base import (
    LLMError,
    LLMInvalidKeyError,
    LLMProvider,
    LLMRequest,
    LLMResponse,
)
from common.llm.constants import PROVIDER_GEMINI


class FakeProvider(LLMProvider):
    provider = PROVIDER_GEMINI

    def __init__(self, model: str = "fake-model", answers: list[str] | None = None):
        self.model = model
        self.answers = list(answers or [])
        self.requests: list[LLMRequest] = []
        self.fail_with: LLMError | None = None  # raised by the next call
        self.key_valid = True

    def generate(self, request: LLMRequest) -> LLMResponse:
        self.requests.append(request)
        if self.fail_with is not None:
            error, self.fail_with = self.fail_with, None
            raise error
        text = self.answers.pop(0) if self.answers else "ok"
        return LLMResponse(text=text, model=self.model, input_tokens=1, output_tokens=1)

    def validate_key(self) -> None:
        if not self.key_valid:
            raise LLMInvalidKeyError()
