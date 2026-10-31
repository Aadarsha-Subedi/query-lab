"""Who may call a route beyond being signed in.

`staff_only` is the one check for the workbench (step 6): the traces hold other
people's questions, and the platform has no roles beyond `is_staff`. Set it as
the router's `auth`, so a new route cannot forget it (a test lists every
`/api/workbench/` route and calls it signed out and as a plain user)."""

from typing import Any

from django.conf import settings
from django.http import HttpRequest
from ninja.security.apikey import APIKeyCookie

from common.exception.domain import PermissionDeniedException


class StaffOnly(PermissionDeniedException):
    message = "This is for staff only."
    error_code = "staff_only"


class StaffAuth(APIKeyCookie):
    """Session sign-in (401 when missing, CSRF checked like `django_auth`), then
    `is_staff` (403 `staff_only`)."""

    param_name: str = settings.SESSION_COOKIE_NAME

    def authenticate(self, request: HttpRequest, key: str | None) -> Any | None:
        user = request.user
        if not user.is_authenticated:
            return None
        if not getattr(user, "is_staff", False):
            raise StaffOnly()
        return user


staff_only = StaffAuth()
