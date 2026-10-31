"""Dev-only OAuth test page (mounted by config/urls_local.py, never in prod).

OAuth can only finish in a browser, and the session cookie is HttpOnly, so
Postman has no way to sign in on its own. `/dev/` starts the real allauth
sign-in with Google or GitHub, and `/dev/session` hands the resulting
`sessionid` back to the page so it can be copied into Postman."""

from django.http import HttpRequest, HttpResponse, JsonResponse
from django.shortcuts import render
from django.views.decorators.csrf import ensure_csrf_cookie
from django.views.decorators.http import require_GET


@require_GET
@ensure_csrf_cookie
def index(request: HttpRequest) -> HttpResponse:
    return render(request, "dev/index.html")


@require_GET
def session(request: HttpRequest) -> JsonResponse:
    if not request.user.is_authenticated or request.session.session_key is None:
        return JsonResponse({"authenticated": False})
    return JsonResponse(
        {
            "authenticated": True,
            "session_key": request.session.session_key,
            "email": request.user.email,
        }
    )
