from dataclasses import asdict
from datetime import datetime
from typing import Any, Literal, cast

from django.http import HttpRequest
from ninja import Router, Schema
from ninja.security import django_auth

from accounts.models import User
from agent import confidence
from ask import keys, service
from ask.models import UserLLMKey
from common.llm import allowed_models
from common.response.domain import SuccessEnvelope, errors, success
from common.throttling.scoped import AskThrottle
from workspaces.access import workspace_for

router = Router(tags=["ask"])

Provider = Literal["gemini", "openai"]


class LLMKeyIn(Schema):
    api_key: str
    model: str | None = None


class LLMKeyOut(Schema):
    provider: str
    key_last4: str
    model: str
    # The key asks use when the AI source is "own".
    is_active: bool
    updated_at: datetime


class LLMModelIn(Schema):
    model: str


class LLMModelsOut(Schema):
    """The models a user may pick, per provider; the first of each list is the default."""

    gemini: list[str]
    openai: list[str]


class AISettingOut(Schema):
    # "querylab" (shared key, daily limit) or "own" (your active key).
    source: Literal["querylab", "own"]


def _out(row: UserLLMKey) -> dict:
    return LLMKeyOut(
        provider=row.provider,
        key_last4=row.key_last4,
        model=row.model,
        is_active=row.is_active,
        updated_at=row.updated_at,
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
    keys.delete_key(cast(User, request.user), provider)
    return success(None, message="Key removed.")


@router.get(
    "/llm-keys-models",
    response={200: SuccessEnvelope[LLMModelsOut], **errors(401, 429)},
    auth=django_auth,
)
def list_llm_models(request: HttpRequest) -> dict:
    """The models allowed per provider (from settings)."""
    return success(
        LLMModelsOut(
            gemini=allowed_models("gemini"), openai=allowed_models("openai")
        ).dict()
    )


@router.put(
    "/llm-keys/{provider}/model",
    response={200: SuccessEnvelope[LLMKeyOut], **errors(400, 401, 422, 429)},
    auth=django_auth,
)
def change_llm_model(
    request: HttpRequest, provider: Provider, payload: LLMModelIn
) -> dict:
    """Switch the model of a saved key; the key is not sent again."""
    row = keys.change_model(cast(User, request.user), provider, payload.model)
    return success(_out(row), message="Model changed.")


@router.put(
    "/llm-keys/{provider}/activate",
    response={200: SuccessEnvelope[LLMKeyOut], **errors(400, 401, 429)},
    auth=django_auth,
)
def activate_llm_key(request: HttpRequest, provider: Provider) -> dict:
    """Make this key the one your asks use (the other one stops being active)."""
    row = keys.activate_key(cast(User, request.user), provider)
    return success(_out(row), message="Key activated.")


@router.get(
    "/llm-settings",
    response={200: SuccessEnvelope[AISettingOut], **errors(401, 429)},
    auth=django_auth,
)
def get_ai_setting(request: HttpRequest) -> dict:
    return success({"source": keys.ai_source(cast(User, request.user))})


@router.put(
    "/llm-settings",
    response={200: SuccessEnvelope[AISettingOut], **errors(400, 401, 422, 429)},
    auth=django_auth,
)
def set_ai_setting(request: HttpRequest, payload: AISettingOut) -> dict:
    """Choose QueryLab's AI or your own."""
    source = keys.set_ai_source(cast(User, request.user), payload.source)
    return success({"source": source}, message="AI source saved.")


class AskIn(Schema):
    question: str
    # One of your own workspaces; leave out for the shared demo.
    workspace: int | None = None


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
    response={
        200: SuccessEnvelope[AskOut],
        **errors(400, 401, 404, 409, 422, 429, 502, 504),
    },
    auth=django_auth,
    throttle=[AskThrottle()],
)
def ask(request: HttpRequest, payload: AskIn) -> dict:
    """Answer a question about the demo database, or about one of your own
    workspaces (`workspace`): the SQL that ran, the result table and a confidence
    score. The SQL is checked before it runs and runs on the read-only connection
    of that workspace only."""
    user = cast(User, request.user)
    workspace = workspace_for(user, payload.workspace)
    result = service.answer(user, payload.question, workspace)
    data = asdict(result)
    data["confidence"] = confidence.visible(result.confidence)
    return success(data)
