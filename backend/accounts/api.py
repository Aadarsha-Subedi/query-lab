from typing import cast

from allauth.socialaccount.models import SocialAccount
from django.http import HttpRequest
from django.views.decorators.csrf import ensure_csrf_cookie
from ninja import Router, Schema
from ninja.decorators import decorate_view
from ninja.security import django_auth

from accounts.models import User
from common.response.domain import SuccessEnvelope, errors, success

router = Router(tags=["accounts"])


class UserOut(Schema):
    id: int
    email: str
    first_name: str
    last_name: str
    # The provider this user signed in with ("google" or "github").
    providers: list[str]
    # True for staff accounts: the screens show the workbench only to them (the API enforces it).
    is_staff: bool


@router.get(
    "/me",
    response={200: SuccessEnvelope[UserOut], **errors(401, 429)},
    auth=django_auth,
)
@decorate_view(ensure_csrf_cookie)
def me(request: HttpRequest) -> dict:
    """The signed-in user, or 401. The frontend's route guards use this.

    Also sets the csrftoken cookie (signed in or not): the app calls this
    first on every load, so its first POST already has a token to send."""
    user = cast(User, request.user)
    providers = sorted(
        SocialAccount.objects.filter(user=user).values_list("provider", flat=True)
    )
    return success(
        UserOut(
            id=user.pk,
            email=user.email,
            first_name=user.first_name,
            last_name=user.last_name,
            providers=providers,
            is_staff=user.is_staff,
        ).dict()
    )
