from django.core.exceptions import PermissionDenied
from django.http import Http404, HttpRequest
from django.test import Client
from ninja import NinjaAPI, Schema
from ninja.testing import TestClient

from common.exception.domain import ConflictException, ThrottledException
from common.exception.handler import (
    flatten_validation_errors,
    install_exception_handlers,
)


class Payload(Schema):
    email: str
    age: int


def make_client() -> TestClient:
    api = NinjaAPI(urls_namespace="test-exceptions")
    install_exception_handlers(api)

    @api.get("/conflict")
    def conflict(request: HttpRequest) -> None:
        raise ConflictException(error_code="duplicate_workspace")

    @api.get("/throttled")
    def throttled(request: HttpRequest) -> None:
        raise ThrottledException(headers={"Retry-After": "30"})

    @api.post("/validate")
    def validate(request: HttpRequest, payload: Payload) -> None:
        return None

    @api.get("/missing")
    def missing(request: HttpRequest) -> None:
        raise Http404

    @api.get("/forbidden")
    def forbidden(request: HttpRequest) -> None:
        raise PermissionDenied

    return TestClient(api)


def test_app_exception_uses_the_error_envelope() -> None:
    response = make_client().get("/conflict")
    assert response.status_code == 409
    assert response.json() == {
        "success": False,
        "status_code": 409,
        "message": "Resource conflict.",
        "code": "duplicate_workspace",
        "errors": [],
    }


def test_app_exception_headers_are_sent() -> None:
    response = make_client().get("/throttled")
    assert response.status_code == 429
    assert response["Retry-After"] == "30"


def test_validation_errors_are_flattened() -> None:
    response = make_client().post("/validate", json={"email": "a@b.co", "age": "x"})
    assert response.status_code == 422
    body = response.json()
    assert body["code"] == "validation_error"
    assert [error["field"] for error in body["errors"]] == ["age"]


def test_django_404_and_403_use_the_envelope() -> None:
    client = make_client()
    assert client.get("/missing").json()["code"] == "not_found"
    assert client.get("/forbidden").json()["code"] == "permission_denied"


def test_flatten_drops_the_request_part() -> None:
    errors = [{"loc": ("body", "payload", "email"), "msg": "bad"}]
    assert flatten_validation_errors(errors) == [{"field": "email", "message": "bad"}]


def test_unauthenticated_api_call_is_401_in_the_envelope(client: Client) -> None:
    response = client.get("/api/me")
    assert response.status_code == 401
    assert response.json()["code"] == "authentication_denied"
