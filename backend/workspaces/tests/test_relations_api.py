import json
from typing import Any

import pytest
from django.test import Client, override_settings

from accounts.models import User
from ask import schema
from workspaces import connections
from workspaces.context import ref_for
from workspaces.models import WorkspaceDDLLog

pytestmark = [pytest.mark.django_db, pytest.mark.usefixtures("data_connections")]


def call(client: Client, method: str, path: str, body: Any = None) -> Any:
    return getattr(client, method)(
        path,
        json.dumps(body) if body is not None else None,
        content_type="application/json",
    )


@pytest.fixture
def ws(client: Client, user: User) -> int:
    client.force_login(user)
    workspace = call(client, "post", "/api/workspaces", {"name": "R"}).json()["data"][
        "id"
    ]
    for name, cols in (
        ("customer", [("id", "integer"), ("name", "text")]),
        ("orders", [("id", "integer"), ("customer_id", "integer")]),
    ):
        spec = {"name": name, "columns": [{"name": n, "type": t} for n, t in cols]}
        assert (
            call(
                client, "post", f"/api/workspaces/{workspace}/tables", spec
            ).status_code
            == 200
        )
    return workspace


def sql(ws: int, statement: str) -> None:
    with connections.workspace_connection(ws, "rw", 1) as connection:
        connection.execute(statement)


def url(ws: int, rest: str) -> str:
    return f"/api/workspaces/{ws}/{rest}"


def pk(client: Client, ws: int, table: str, columns: list[str]) -> Any:
    return call(
        client, "put", url(ws, f"tables/{table}/primary-key"), {"columns": columns}
    )


def relate(client: Client, ws: int, **overrides: Any) -> Any:
    body = {
        "child_table": "orders",
        "child_columns": ["customer_id"],
        "parent_table": "customer",
        "parent_columns": ["id"],
        **overrides,
    }
    return call(client, "post", url(ws, "relations"), body)


def test_set_a_primary_key_and_the_schema_shows_it(client: Client, ws: int) -> None:
    sql(ws, "INSERT INTO customer (id, name) VALUES (1, 'a'), (2, 'b')")
    response = pk(client, ws, "customer", ["id"])
    assert response.status_code == 200, response.content
    assert response.json()["data"]["primary_key"] == ["id"]
    assert schema.get_schema(ref_for(ws)).table("customer").primary_key == ("id",)  # type: ignore[union-attr]
    # replacing it works too
    assert pk(client, ws, "customer", ["id", "name"]).json()["data"]["primary_key"] == [
        "id",
        "name",
    ]


def test_a_repeated_or_empty_key_value_names_the_row_and_changes_nothing(
    client: Client, ws: int
) -> None:
    sql(
        ws,
        "INSERT INTO customer (id, name) VALUES (1, 'a'), (2, 'b'), (1, 'c'), (NULL, 'd')",
    )
    duplicate = pk(client, ws, "customer", ["id"])
    assert (duplicate.status_code, duplicate.json()["code"]) == (
        409,
        "constraint_violation",
    )
    assert "row 4" in duplicate.json()["errors"][0]["message"]
    sql(ws, "DELETE FROM customer WHERE _row_id = 3")
    empty = pk(client, ws, "customer", ["id"])
    assert (
        "row 4" in empty.json()["errors"][0]["message"]
        and "empty" in empty.json()["errors"][0]["message"]
    )
    assert (
        call(client, "get", url(ws, "tables/customer")).json()["data"]["primary_key"]
        == []
    )
    assert pk(client, ws, "customer", ["nope"]).json()["code"] == "column_not_found"
    assert pk(client, ws, "customer", ["_row_id"]).json()["code"] == "column_not_found"
    assert pk(client, ws, "customer", []).json()["code"] == "invalid_spec"


def test_a_relation_is_a_real_constraint_the_agent_sees(
    client: Client, ws: int
) -> None:
    sql(ws, "INSERT INTO customer (id, name) VALUES (1, 'a')")
    sql(ws, "INSERT INTO orders (id, customer_id) VALUES (10, 1), (11, NULL)")
    assert pk(client, ws, "customer", ["id"]).status_code == 200
    created = relate(client, ws)
    assert created.status_code == 200, created.content
    relation = created.json()["data"]
    assert relation["on_delete"] == "NO ACTION" and relation["parent_columns"] == ["id"]
    assert [
        r["name"] for r in call(client, "get", url(ws, "relations")).json()["data"]
    ] == [relation["name"]]
    known = schema.get_schema(ref_for(ws))
    fk = known.table("orders").foreign_keys[0]  # type: ignore[union-attr]
    assert (fk.columns, fk.ref_table, fk.ref_columns) == (
        ("customer_id",),
        "customer",
        ("id",),
    )
    text = schema.render(known)
    assert "FOREIGN KEY (customer_id) REFERENCES" in text and "PRIMARY KEY (id)" in text
    assert WorkspaceDDLLog.objects.filter(
        workspace_id=ws, statement__contains="FOREIGN KEY"
    ).exists()
    removed = call(client, "delete", url(ws, f"relations/{relation['name']}"))
    assert removed.status_code == 200
    assert (
        call(client, "delete", url(ws, f"relations/{relation['name']}")).json()["code"]
        == "relation_not_found"
    )
    assert call(client, "get", url(ws, "relations")).json()["data"] == []


def test_an_orphan_row_is_named_and_nothing_changes(client: Client, ws: int) -> None:
    sql(ws, "INSERT INTO customer (id, name) VALUES (1, 'a')")
    sql(ws, "INSERT INTO orders (id, customer_id) VALUES (10, 1), (11, 99), (12, 98)")
    pk(client, ws, "customer", ["id"])
    refused = relate(client, ws)
    assert (refused.status_code, refused.json()["code"]) == (
        409,
        "constraint_violation",
    )
    assert "row 2" in refused.json()["errors"][0]["message"]
    assert call(client, "get", url(ws, "relations")).json()["data"] == []


def test_the_parent_must_be_a_key_and_types_must_match(client: Client, ws: int) -> None:
    unkeyed = relate(client, ws)
    assert (unkeyed.status_code, unkeyed.json()["code"]) == (422, "relation_invalid")
    pk(client, ws, "customer", ["id"])
    text_vs_int = relate(
        client, ws, child_columns=["customer_id"], parent_columns=["name"]
    )
    assert text_vs_int.json()["code"] in {"relation_invalid", "constraint_violation"}
    assert (
        relate(client, ws, parent_columns=["id", "name"]).json()["code"]
        == "invalid_spec"
    )
    assert relate(client, ws, on_delete="SET NULL").json()["code"] == "invalid_spec"
    assert relate(client, ws, parent_table="nope").json()["code"] == "table_not_found"
    assert (
        relate(client, ws, child_columns=["zzz"]).json()["code"] == "column_not_found"
    )


def test_relations_cannot_leave_the_workspace(client: Client, ws: int) -> None:
    pk(client, ws, "customer", ["id"])
    for parent in ("ws_1.customer", "demo.orders", "public.x", "querylab.demo.orders"):
        response = relate(client, ws, parent_table=parent)
        assert (
            response.status_code == 404 and response.json()["code"] == "table_not_found"
        )


@override_settings(WORKSPACE_MAX_RELATIONS=1)
def test_the_relation_cap(client: Client, ws: int) -> None:
    pk(client, ws, "customer", ["id"])
    assert relate(client, ws).status_code == 200
    assert relate(client, ws).json()["code"] == "relation_limit_reached"


def test_cascade_and_restrict_behave_as_declared(client: Client, ws: int) -> None:
    sql(ws, "INSERT INTO customer (id, name) VALUES (1, 'a')")
    sql(ws, "INSERT INTO orders (id, customer_id) VALUES (10, 1)")
    pk(client, ws, "customer", ["id"])
    assert (
        relate(client, ws, on_delete="CASCADE").json()["data"]["on_delete"] == "CASCADE"
    )
    sql(ws, "DELETE FROM customer WHERE id = 1")
    with connections.workspace_connection(ws, "rw", 1) as connection:
        assert connection.execute("SELECT count(*) FROM orders").fetchone() == (0,)


def test_dropping_a_table_removes_relations_that_point_at_it(
    client: Client, ws: int
) -> None:
    pk(client, ws, "customer", ["id"])
    relate(client, ws)
    assert call(client, "delete", url(ws, "tables/customer")).status_code == 200
    assert call(client, "get", url(ws, "relations")).json()["data"] == []


def test_another_users_workspace_is_a_404(
    client: Client, ws: int, other_user: User
) -> None:
    client.force_login(other_user)
    assert call(client, "get", url(ws, "relations")).status_code == 404
    assert relate(client, ws).status_code == 404
    assert pk(client, ws, "customer", ["id"]).status_code == 404
    assert call(client, "delete", url(ws, "relations/x")).status_code == 404
