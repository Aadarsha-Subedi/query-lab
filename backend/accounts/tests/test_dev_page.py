"""The dev-only OAuth test page exists in local URLs and nowhere else."""

import pytest
from django.test import Client, override_settings

from accounts.models import User

LOCAL = override_settings(ROOT_URLCONF="config.urls_local")


def test_dev_page_is_not_in_the_normal_urls() -> None:
    assert Client().get("/dev/").status_code == 404
    assert Client().get("/dev/session").status_code == 404


@LOCAL
def test_dev_page_renders_both_providers_with_a_csrf_token() -> None:
    response = Client().get("/dev/")

    body = response.content.decode()
    assert response.status_code == 200
    assert 'value="google"' in body and 'value="github"' in body
    assert "csrfmiddlewaretoken" in body


@LOCAL
@pytest.mark.django_db
def test_dev_session_endpoint() -> None:
    client = Client()
    assert client.get("/dev/session").json() == {"authenticated": False}

    user = User.objects.create_user(email="ada@example.com")
    client.force_login(user)
    data = client.get("/dev/session").json()

    assert data["authenticated"] is True
    assert data["email"] == "ada@example.com"
    assert data["session_key"] == client.cookies["sessionid"].value
