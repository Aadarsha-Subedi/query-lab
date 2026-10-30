from django.http import HttpRequest
from django.views.decorators.csrf import ensure_csrf_cookie
from ninja import Router, Schema
from ninja.decorators import decorate_view
from ninja.security import django_auth

from common.response.domain import SuccessEnvelope, success

router = Router(tags=["accounts"])


class UserOut(Schema):
    id: int
    email: str
    first_name: str
    last_name: str


@router.get("/me", response=SuccessEnvelope[UserOut], auth=django_auth)
@decorate_view(ensure_csrf_cookie)
def me(request: HttpRequest) -> dict:
    """The signed-in user, or 401. The frontend's route guards use this.

    Also sets the csrftoken cookie (signed in or not): the app calls this
    first on every load, so its first POST already has a token to send."""
    return success(UserOut.from_orm(request.user).dict())
