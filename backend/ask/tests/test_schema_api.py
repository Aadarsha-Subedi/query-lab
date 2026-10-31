"""GET /api/schema and /api/schema/tables/{name}."""

import pytest
from django.test import Client, override_settings

from accounts.models import User
from ask import schema as ask_schema
from ask.schema import Column, ForeignKey, Schema, Table

pytestmark = pytest.mark.django_db

PATHS = ["/api/schema", "/api/schema/tables/orders"]


@pytest.fixture
def fake_schema(monkeypatch: pytest.MonkeyPatch) -> list[bool]:
    """A two-table schema; records the include_samples flag each read used."""
    flags: list[bool] = []
    schema = Schema(
        name="demo",
        tables=(
            Table(
                name="orders",
                comment="Customer\n orders.",
                columns=(
                    Column("order_id", "text", False, "Order id."),
                    Column("customer_id", "text", True),
                    Column(
                        "order_status", "text", True, None, samples=("shipped", "new")
                    ),
                ),
                primary_key=("order_id",),
                foreign_keys=(
                    ForeignKey(("customer_id",), "customers", ("customer_id",)),
                ),
                row_estimate=99441,
            ),
            Table(
                name="customers",
                comment=None,
                columns=(Column("customer_id", "text", False),),
                primary_key=("customer_id",),
            ),
        ),
    )

    def fake_get(schema_name: str = "demo", *, include_samples: bool = False) -> Schema:
        flags.append(include_samples)
        return schema

    monkeypatch.setattr(ask_schema, "get_schema", fake_get)
    return flags


@pytest.fixture
def signed_in(client: Client, user: User) -> Client:
    client.force_login(user)
    return client


@pytest.mark.parametrize("path", PATHS)
def test_needs_sign_in(client: Client, path: str) -> None:
    assert client.get(path).status_code == 401


def test_schema_shape(signed_in: Client, fake_schema: list[bool]) -> None:
    body = signed_in.get("/api/schema").json()
    assert body["success"] is True
    data = body["data"]
    assert data["name"] == "demo"
    orders, customers = data["tables"]
    assert orders == {
        "name": "orders",
        "comment": "Customer orders.",
        "row_estimate": 99441,
        "primary_key": ["order_id"],
        "foreign_keys": [
            {
                "columns": ["customer_id"],
                "ref_table": "customers",
                "ref_columns": ["customer_id"],
            }
        ],
        "columns": [
            {
                "name": "order_id",
                "type": "text",
                "nullable": False,
                "comment": "Order id.",
                "samples": [],
            },
            {
                "name": "customer_id",
                "type": "text",
                "nullable": True,
                "comment": "",
                "samples": [],
            },
            {
                "name": "order_status",
                "type": "text",
                "nullable": True,
                "comment": "",
                "samples": [],
            },
        ],
    }
    assert customers["row_estimate"] is None and customers["foreign_keys"] == []


def test_one_table_has_the_same_shape(
    signed_in: Client, fake_schema: list[bool]
) -> None:
    full = signed_in.get("/api/schema").json()["data"]["tables"][0]
    one = signed_in.get("/api/schema/tables/orders").json()["data"]
    assert one == full


def test_unknown_table_is_a_typed_404_that_lists_nothing(
    signed_in: Client, fake_schema: list[bool]
) -> None:
    response = signed_in.get("/api/schema/tables/secrets")
    assert response.status_code == 404
    body = response.json()
    assert body["code"] == "table_not_found"
    assert "orders" not in response.content.decode()


def test_samples_are_off_by_default(signed_in: Client, fake_schema: list[bool]) -> None:
    data = signed_in.get("/api/schema").json()["data"]
    assert fake_schema == [False]
    assert all(c["samples"] == [] for t in data["tables"] for c in t["columns"])


@override_settings(SCHEMA_API_INCLUDE_SAMPLES=True)
def test_samples_show_when_the_setting_is_on(
    signed_in: Client, fake_schema: list[bool]
) -> None:
    data = signed_in.get("/api/schema/tables/orders").json()["data"]
    assert fake_schema == [True]
    status = next(c for c in data["columns"] if c["name"] == "order_status")
    assert status["samples"] == ["shipped", "new"]


def test_etag_gives_a_304_until_the_schema_changes(
    signed_in: Client, fake_schema: list[bool]
) -> None:
    first = signed_in.get("/api/schema")
    etag = first["ETag"]
    assert first["Cache-Control"] == "private, no-cache"
    again = signed_in.get("/api/schema", headers={"If-None-Match": etag})
    assert again.status_code == 304 and again.content == b""
    assert (
        signed_in.get("/api/schema", headers={"If-None-Match": '"old"'}).status_code
        == 200
    )
    # a different table has a different tag
    assert signed_in.get("/api/schema/tables/customers")["ETag"] != etag


@pytest.mark.parametrize("path", PATHS)
@pytest.mark.parametrize("method", ["post", "put", "patch", "delete"])
def test_nothing_can_be_written_through_it(
    signed_in: Client, fake_schema: list[bool], path: str, method: str
) -> None:
    assert getattr(signed_in, method)(path).status_code == 405


@pytest.mark.usefixtures("data_connections")
def test_reads_the_real_demo_schema(signed_in: Client) -> None:
    data = signed_in.get("/api/schema").json()["data"]
    assert "orders" in {t["name"] for t in data["tables"]}
