from dataclasses import asdict
from typing import Any, Literal, cast

from django.http import HttpRequest
from ninja import Router, Schema
from ninja.security import django_auth

from accounts.models import User
from agent import confidence
from ask import keys, service
from ask.models import UserLLMKey
from common.response.domain import SuccessEnvelope, errors, success
from common.throttling.scoped import AskThrottle

router = Router(tags=["ask"])

Provider = Literal["gemini", "openai"]


class LLMKeyIn(Schema):
    api_key: str
    model: str | None = None


class LLMKeyOut(Schema):
    provider: str
    key_last4: str
    model: str


def _out(row: UserLLMKey) -> dict:
    return LLMKeyOut(
        provider=row.provider, key_last4=row.key_last4, model=row.model
    ).dict()


@router.get(
    "/llm-keys",
    response={200: SuccessEnvelope[list[LLMKeyOut]], **errors(401, 429)},
    auth=django_auth,
)
def list_llm_keys(request: HttpRequest) -> dict:
    """The signed-in user's saved keys: provider, last four characters, model.
    The key itself is never returned."""
    user = cast(User, request.user)
    rows = UserLLMKey.objects.filter(user=user).order_by("provider")
    return success([_out(row) for row in rows])


@router.put(
    "/llm-keys/{provider}",
    response={200: SuccessEnvelope[LLMKeyOut], **errors(400, 401, 422, 429, 502)},
    auth=django_auth,
)
def save_llm_key(request: HttpRequest, provider: Provider, payload: LLMKeyIn) -> dict:
    """Check the key with the provider and save it encrypted."""
    row = keys.save_key(
        cast(User, request.user), provider, payload.api_key, payload.model
    )
    return success(_out(row), message="Key saved.")


@router.delete(
    "/llm-keys/{provider}",
    response={200: SuccessEnvelope[None], **errors(401, 429)},
    auth=django_auth,
)
def delete_llm_key(request: HttpRequest, provider: Provider) -> dict:
    UserLLMKey.objects.filter(user=cast(User, request.user), provider=provider).delete()
    return success(None, message="Key removed.")


class AskIn(Schema):
    question: str


class AskOut(Schema):
    question: str
    sql: str
    columns: list[str]
    rows: list[list[Any]]
    row_count: int
    # True when the result was cut at the row or size cap.
    truncated: bool
    # 0 to 1, a heuristic and not a probability (agent/confidence.py). Null until
    # the measured separation earns showing it (CONFIDENCE_SHOW_SCORE).
    confidence: float | None
    # "checked" or "needs_look": plain words that are always present.
    check: str
    rationale: str
    model: str
    latency_ms: int


@router.post(
    "/ask",
    response={200: SuccessEnvelope[AskOut], **errors(400, 401, 422, 429, 502, 504)},
    auth=django_auth,
    throttle=[AskThrottle()],
)
def ask(request: HttpRequest, payload: AskIn) -> dict:
    """Answer a question about the demo database: the SQL that ran, the result
    table and a confidence score. The SQL is checked before it runs and runs on
    the read-only connection only."""
    result = service.answer(cast(User, request.user), payload.question)
    data = asdict(result)
    data["confidence"] = confidence.visible(result.confidence)
    return success(data)
