from django.http import HttpRequest
from ninja import Router, Schema
from ninja.security import django_auth

from common.response.domain import SuccessEnvelope, success

router = Router(tags=["accounts"])


class UserOut(Schema):
    id: int
    email: str
    first_name: str
    last_name: str


@router.get("/me", response=SuccessEnvelope[UserOut], auth=django_auth)
def me(request: HttpRequest) -> dict:
    """The signed-in user, or 401. The frontend's route guards use this."""
    return success(UserOut.from_orm(request.user).dict())
