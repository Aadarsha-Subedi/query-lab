from typing import Literal, cast

from django.http import HttpRequest
from ninja import Router, Schema
from ninja.security import django_auth

from accounts.models import User
from ask import keys
from ask.models import UserLLMKey
from common.response.domain import SuccessEnvelope, success

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


@router.get("/llm-keys", response=SuccessEnvelope[list[LLMKeyOut]], auth=django_auth)
def list_llm_keys(request: HttpRequest) -> dict:
    """The signed-in user's saved keys: provider, last four characters, model.
    The key itself is never returned."""
    user = cast(User, request.user)
    rows = UserLLMKey.objects.filter(user=user).order_by("provider")
    return success([_out(row) for row in rows])


@router.put(
    "/llm-keys/{provider}", response=SuccessEnvelope[LLMKeyOut], auth=django_auth
)
def save_llm_key(request: HttpRequest, provider: Provider, payload: LLMKeyIn) -> dict:
    """Check the key with the provider and save it encrypted."""
    row = keys.save_key(
        cast(User, request.user), provider, payload.api_key, payload.model
    )
    return success(_out(row), message="Key saved.")


@router.delete("/llm-keys/{provider}", response=SuccessEnvelope[None], auth=django_auth)
def delete_llm_key(request: HttpRequest, provider: Provider) -> dict:
    UserLLMKey.objects.filter(user=cast(User, request.user), provider=provider).delete()
    return success(None, message="Key removed.")
