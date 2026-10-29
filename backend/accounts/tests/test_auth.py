"""Email signup, mandatory verification, login rate limits and /api/me, through
allauth's headless (JSON) API as the React app uses it."""

import re
from typing import Any
from urllib.parse import unquote

import pytest
from allauth.account.models import EmailAddress
from allauth.core.context import request_context
from allauth.socialaccount.adapter import get_adapter as get_social_adapter
from allauth.socialaccount.models import SocialAccount
from allauth.socialaccount.providers.google.provider import GoogleProvider
from django.conf import settings
from django.contrib.sessions.middleware import SessionMiddleware
from django.core import mail
from django.http import HttpResponse
from django.test import Client, RequestFactory

from accounts.models import User

AUTH = "/_allauth/browser/v1/auth"
PASSWORD = "Correct-Horse-9"


def signup(client: Client, email: str = "ada@example.com") -> dict[str, Any]:
    response = client.post(
        f"{AUTH}/signup",
        {"email": email, "password": PASSWORD},
        content_type="application/json",
    )
    return {"status": response.status_code, "body": response.json()}


def login_response(client: Client, email: str, password: str = PASSWORD) -> Any:
    return client.post(
        f"{AUTH}/login",
        {"email": email, "password": password},
        content_type="application/json",
    )


def login(client: Client, email: str, password: str = PASSWORD) -> int:
    return int(login_response(client, email, password).status_code)


def verification_key() -> str:
    match = re.search(r"/verify-email/([^\s]+)", str(mail.outbox[-1].body))
    assert match, mail.outbox[-1].body
    # The link carries the key URL-encoded; the frontend gets it decoded.
    return unquote(match.group(1))


@pytest.mark.django_db
def test_signup_sends_a_verification_email(client: Client) -> None:
    result = signup(client)
    # Not signed in yet: the pending flow is email verification.
    assert result["status"] == 401
    flows = {flow["id"]: flow for flow in result["body"]["data"]["flows"]}
    assert flows["verify_email"]["is_pending"]
    assert len(mail.outbox) == 1
    assert mail.outbox[0].to == ["ada@example.com"]
    assert f"{settings.FRONTEND_URL}/verify-email/" in mail.outbox[0].body
    assert getattr(mail.outbox[0], "alternatives", None)  # styled HTML version


@pytest.mark.django_db
def test_login_is_blocked_until_verified(client: Client) -> None:
    signup(client)
    other = Client()
    assert login(other, "ada@example.com") == 401
    assert other.get("/api/me").status_code == 401

    response = client.post(
        f"{AUTH}/email/verify",
        {"key": verification_key()},
        content_type="application/json",
    )
    assert response.status_code == 200
    assert EmailAddress.objects.get(email="ada@example.com").verified
    assert login(other, "ada@example.com") == 200
    assert other.get("/api/me").status_code == 200


@pytest.mark.django_db
def test_disposable_email_is_refused(client: Client) -> None:
    assert signup(client, "x@mailinator.com")["status"] == 400


@pytest.mark.django_db
def test_me(client: Client) -> None:
    assert client.get("/api/me").status_code == 401
    user = User.objects.create_user(email="ada@example.com", password=PASSWORD)
    client.force_login(user)
    response = client.get("/api/me")
    assert response.status_code == 200
    body = response.json()
    assert body["success"] is True
    assert body["data"]["email"] == "ada@example.com"


@pytest.mark.django_db
def test_sixth_failed_login_inside_the_window_is_blocked(client: Client) -> None:
    user = User.objects.create_user(email="ada@example.com", password=PASSWORD)
    EmailAddress.objects.create(
        user=user, email=user.email, verified=True, primary=True
    )
    for _ in range(5):
        response = login_response(client, "ada@example.com", "Wrong-Password-1")
        assert response.json()["errors"][0]["code"] == "email_password_mismatch"
    # allauth answers the 6th with 400 and a dedicated code (not 429).
    for password in ("Wrong-Password-1", PASSWORD):  # even the right one, for now
        response = login_response(client, "ada@example.com", password)
        assert response.status_code == 400
        assert response.json()["errors"][0]["code"] == "too_many_login_attempts"


def test_social_providers_are_configured_from_settings() -> None:
    providers: dict[str, Any] = settings.SOCIALACCOUNT_PROVIDERS
    assert providers["google"]["APPS"][0]["client_id"] == "test-google-client-id"
    assert providers["github"]["APPS"][0]["client_id"] == "test-github-client-id"
    assert settings.SOCIALACCOUNT_EMAIL_AUTHENTICATION_AUTO_CONNECT


@pytest.mark.django_db
def test_social_login_links_to_the_existing_account_by_verified_email() -> None:
    """A Google sign-in with the verified address of an existing account lands
    in that account (and connects Google to it) instead of creating a second."""
    user = User.objects.create_user(email="ada@example.com", password=PASSWORD)
    EmailAddress.objects.create(
        user=user, email=user.email, verified=True, primary=True
    )

    request = RequestFactory().get("/")
    SessionMiddleware(lambda r: HttpResponse()).process_request(request)
    with request_context(request):
        provider = get_social_adapter().get_provider(request, GoogleProvider.id)
        sociallogin = provider.sociallogin_from_response(
            request,
            {"sub": "google-123", "email": "ada@example.com", "email_verified": True},
        )
        sociallogin.lookup()
        assert sociallogin.user == user
        sociallogin._accept_login(request)

    account = SocialAccount.objects.get(provider="google", uid="google-123")
    assert account.user == user
    assert User.objects.count() == 1
