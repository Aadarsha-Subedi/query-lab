import pytest
from django.test import Client, override_settings

from accounts.models import User
from core import health

ALL_OK = dict.fromkeys(
    ["app_db", "data_db", "data_reader", "redis", "worker"], lambda: None
)


@pytest.fixture(autouse=True)
def fast_health(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(health, "checks", lambda: ALL_OK)


@override_settings(THROTTLE_ANON_RATE="2/m")
def test_anonymous_client_is_throttled_past_its_rate(client: Client) -> None:
    assert client.get("/api/health").status_code == 200
    assert client.get("/api/health").status_code == 200
    response = client.get("/api/health")
    assert response.status_code == 429
    assert response.json()["code"] == "throttled"
    assert int(response["Retry-After"]) > 0


@pytest.mark.django_db
@override_settings(THROTTLE_ANON_RATE="2/m", THROTTLE_USER_RATE="3/m")
def test_signed_in_limit_is_separate_from_anonymous_traffic(client: Client) -> None:
    anonymous = Client()
    assert anonymous.get("/api/health").status_code == 200
    assert anonymous.get("/api/health").status_code == 200
    assert anonymous.get("/api/health").status_code == 429

    user = User.objects.create_user(email="ada@example.com", password="Correct-Horse-9")
    client.force_login(user)
    # Same IP as the exhausted anonymous client, but counted per user.
    for _ in range(3):
        assert client.get("/api/me").status_code == 200
    assert client.get("/api/me").status_code == 429
    # Public routes count a signed-in visitor as a user too, not as anonymous.
    assert client.get("/api/health").status_code == 429
