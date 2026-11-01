"""Sign-in is Google or GitHub only (allauth social-only, headless). Identity
is the provider account: the same email through Google and through GitHub
gives two separate users, and nothing links accounts by email."""

from typing import Any

import pytest
from allauth.core.context import request_context
from allauth.socialaccount.adapter import get_adapter as get_social_adapter
from allauth.socialaccount.helpers import complete_social_login
from allauth.socialaccount.models import SocialAccount
from allauth.socialaccount.providers.github.provider import GitHubProvider
from allauth.socialaccount.providers.google.provider import GoogleProvider
from django.conf import settings
from django.contrib.auth.models import AnonymousUser
from django.contrib.messages.middleware import MessageMiddleware
from django.contrib.sessions.middleware import SessionMiddleware
from django.http import HttpResponse
from django.test import Client, RequestFactory

from accounts.models import User

AUTH = "/_allauth/browser/v1/auth"
SHARED_EMAIL = "ada@example.com"


def _request() -> Any:
    request = RequestFactory().get("/accounts/login/callback/")
    SessionMiddleware(lambda r: HttpResponse()).process_request(request)
    MessageMiddleware(lambda r: HttpResponse()).process_request(request)
    request.user = AnonymousUser()
    return request


def sign_in_with(provider_id: str, response: dict[str, Any]) -> User:
    """Run allauth's real social-login completion for a provider response,
    as the OAuth callback does, and return the user it signed in."""
    request = _request()
    with request_context(request):
        provider = get_social_adapter().get_provider(request, provider_id)
        sociallogin = provider.sociallogin_from_response(request, response)
        sociallogin.state = {"process": "login"}
        complete_social_login(request, sociallogin)
    account = SocialAccount.objects.get(
        provider=provider_id, uid=sociallogin.account.uid
    )
    return account.user


def google(uid: str, email: str) -> dict[str, Any]:
    return {"sub": uid, "email": email, "email_verified": True, "name": "Ada"}


def github(uid: int, email: str) -> dict[str, Any]:
    return {
        "id": uid,
        "login": "ada",
        "email": email,
        "emails": [{"email": email, "primary": True, "verified": True}],
    }


@pytest.mark.django_db
def test_first_sign_in_creates_a_user() -> None:
    user = sign_in_with(GoogleProvider.id, google("g-1", SHARED_EMAIL))
    assert user.email == SHARED_EMAIL
    assert not user.has_usable_password()


@pytest.mark.django_db
def test_same_email_through_another_provider_is_a_separate_user() -> None:
    via_google = sign_in_with(GoogleProvider.id, google("g-1", SHARED_EMAIL))
    via_github = sign_in_with(GitHubProvider.id, github(42, SHARED_EMAIL))
    assert via_google.pk != via_github.pk
    assert User.objects.filter(email=SHARED_EMAIL).count() == 2
    # Each user has exactly its own provider account; nothing was linked.
    assert list(
        SocialAccount.objects.filter(user=via_google).values_list("provider", flat=True)
    ) == ["google"]
    assert list(
        SocialAccount.objects.filter(user=via_github).values_list("provider", flat=True)
    ) == ["github"]


@pytest.mark.django_db
def test_signing_in_again_returns_the_same_user() -> None:
    first = sign_in_with(GoogleProvider.id, google("g-1", SHARED_EMAIL))
    again = sign_in_with(GoogleProvider.id, google("g-1", SHARED_EMAIL))
    assert first.pk == again.pk
    assert User.objects.count() == 1


@pytest.mark.django_db
def test_me_shows_the_provider(client: Client) -> None:
    assert client.get("/api/me").status_code == 401
    via_github = sign_in_with(GitHubProvider.id, github(42, SHARED_EMAIL))
    client.force_login(via_github)
    response = client.get("/api/me")
    assert response.status_code == 200
    body = response.json()
    assert body["success"] is True
    assert body["data"]["email"] == SHARED_EMAIL
    assert body["data"]["providers"] == ["github"]
    assert body["data"]["is_staff"] is False


@pytest.mark.django_db
def test_me_tells_the_screens_who_is_staff(client: Client) -> None:
    staff = sign_in_with(GitHubProvider.id, github(43, SHARED_EMAIL))
    staff.is_staff = True
    staff.save(update_fields=["is_staff"])
    client.force_login(staff)
    assert client.get("/api/me").json()["data"]["is_staff"] is True


@pytest.mark.django_db
def test_me_sets_the_csrf_cookie_signed_in_or_not(client: Client) -> None:
    response = client.get("/api/me")
    assert response.status_code == 401
    assert response.cookies["csrftoken"].value
    client.force_login(sign_in_with(GoogleProvider.id, google("g-1", SHARED_EMAIL)))
    response = client.get("/api/me")
    assert response.status_code == 200
    assert response.cookies["csrftoken"].value


@pytest.mark.django_db
@pytest.mark.parametrize(
    ("path", "body"),
    [
        (f"{AUTH}/signup", {"email": SHARED_EMAIL, "password": "Correct-Horse-9"}),
        (f"{AUTH}/login", {"email": SHARED_EMAIL, "password": "Correct-Horse-9"}),
        (f"{AUTH}/password/request", {"email": SHARED_EMAIL}),
        (f"{AUTH}/email/verify", {"key": "anything"}),
    ],
)
def test_email_and_password_endpoints_do_not_exist(
    client: Client, path: str, body: dict[str, str]
) -> None:
    response = client.post(path, body, content_type="application/json")
    assert response.status_code == 404


@pytest.mark.django_db
def test_config_offers_only_google_and_github(client: Client) -> None:
    data = client.get("/_allauth/browser/v1/config").json()["data"]
    # is_open_for_signup stays true: it covers first-time sign-in through a
    # provider. The email/password endpoints themselves are 404 (test above).
    assert data["account"]["login_methods"] == []
    providers = {provider["id"] for provider in data["socialaccount"]["providers"]}
    assert providers == {"google", "github"}


def test_social_only_settings() -> None:
    assert settings.SOCIALACCOUNT_ONLY
    assert not settings.SOCIALACCOUNT_EMAIL_AUTHENTICATION
    assert not settings.ACCOUNT_UNIQUE_EMAIL
    providers: dict[str, Any] = settings.SOCIALACCOUNT_PROVIDERS
    assert providers["google"]["APPS"][0]["client_id"] == "test-google-client-id"
    assert providers["github"]["APPS"][0]["client_id"] == "test-github-client-id"
