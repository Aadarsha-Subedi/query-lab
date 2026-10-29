"""Pagination, ordering and filter helpers, on the User model."""

import pytest
from django.http import HttpRequest
from django.test import override_settings
from ninja import NinjaAPI, Query, Schema
from ninja.pagination import paginate
from ninja.testing import TestClient
from pydantic import ValidationError

from accounts.models import User
from common.filter.domain import TimeStampFilter
from common.order.domain import OrderingSchema
from common.pagination.domain import OffsetPagination


class UserRow(Schema):
    email: str


class UserOrdering(OrderingSchema):
    allowed_fields = ["created_at", "email"]


def make_client() -> TestClient:
    api = NinjaAPI(urls_namespace="test-query-helpers")

    @api.get("/users", response=list[UserRow])
    @paginate(OffsetPagination)
    def users(
        request: HttpRequest,
        filters: Query[TimeStampFilter],
        ordering: Query[UserOrdering],
    ) -> object:
        return ordering.apply(filters.filter(User.objects.all()))

    return TestClient(api)


@pytest.fixture
def users() -> None:
    for name in ["c", "a", "b"]:
        User.objects.create_user(email=f"{name}@example.com", password="x")


@pytest.mark.django_db
@override_settings(PAGINATION_DEFAULT_LIMIT=2, PAGINATION_MAX_LIMIT=2)
def test_offset_pagination_uses_settings(users: None) -> None:
    body = make_client().get("/users?ordering=email&limit=50").json()
    assert body["count"] == 3
    assert body["limit"] == 2
    assert [row["email"] for row in body["items"]] == ["a@example.com", "b@example.com"]
    body = make_client().get("/users?ordering=email&offset=2").json()
    assert [row["email"] for row in body["items"]] == ["c@example.com"]


@pytest.mark.django_db
def test_descending_ordering(users: None) -> None:
    body = make_client().get("/users?ordering=-email").json()
    assert body["items"][0]["email"] == "c@example.com"


def test_unknown_ordering_field_is_refused() -> None:
    with pytest.raises(ValidationError):
        UserOrdering(ordering="password")


@pytest.mark.django_db
def test_timestamp_filter(users: None) -> None:
    body = make_client().get("/users?created_after=2999-01-01T00:00:00Z").json()
    assert body["count"] == 0
