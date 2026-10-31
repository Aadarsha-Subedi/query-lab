"""Credentialed cross-origin calls work for the listed origins and for nobody else."""

import pytest
from django.test import Client, override_settings

ALLOWED = "http://localhost:3000"
OTHER = "https://evil.example"
URL = "/api/me"


@override_settings(CORS_ALLOWED_ORIGINS=[ALLOWED])
def test_listed_origin_gets_credentialed_cors_headers(client: Client) -> None:
    response = client.get(URL, headers={"Origin": ALLOWED})
    assert response["Access-Control-Allow-Origin"] == ALLOWED
    assert response["Access-Control-Allow-Credentials"] == "true"


@override_settings(CORS_ALLOWED_ORIGINS=[ALLOWED])
@pytest.mark.parametrize("origin", [OTHER, "http://localhost:3001", "null"])
def test_other_origins_get_no_cors_headers(client: Client, origin: str) -> None:
    response = client.get(URL, headers={"Origin": origin})
    assert "Access-Control-Allow-Origin" not in response
    assert "Access-Control-Allow-Credentials" not in response


@override_settings(CORS_ALLOWED_ORIGINS=[ALLOWED])
def test_preflight_for_a_csrf_protected_post_is_allowed_for_the_listed_origin(
    client: Client,
) -> None:
    response = client.options(
        "/api/agent/runs",
        headers={
            "Origin": ALLOWED,
            "Access-Control-Request-Method": "POST",
            "Access-Control-Request-Headers": "content-type,x-csrftoken",
        },
    )
    assert response.status_code == 200
    assert response["Access-Control-Allow-Origin"] == ALLOWED
    assert response["Access-Control-Allow-Credentials"] == "true"
    assert "x-csrftoken" in response["Access-Control-Allow-Headers"].lower()
    assert "POST" in response["Access-Control-Allow-Methods"]


@override_settings(CORS_ALLOWED_ORIGINS=[ALLOWED])
def test_preflight_from_an_unlisted_origin_is_not_allowed(client: Client) -> None:
    response = client.options(
        "/api/agent/runs",
        headers={"Origin": OTHER, "Access-Control-Request-Method": "POST"},
    )
    assert "Access-Control-Allow-Origin" not in response
    assert "Access-Control-Allow-Credentials" not in response
