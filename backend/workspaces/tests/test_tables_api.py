import json
from typing import Any

import pytest
from django.test import Client, override_settings

from accounts.models import User
from ask import schema
from workspaces import connections
from workspaces.context import ref_for
from workspaces.models import Workspace, WorkspaceDDLLog

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
    return call(client, "post", "/api/workspaces", {"name": "T"}).json()["data"]["id"]


def base(ws: int) -> str:
    return f"/api/workspaces/{ws}/tables"


CUSTOMER = {
    "name": "Customer",
    "description": "Who buys things",
    "columns": [
        {
            "name": "Full Name",
            "type": "text",
            "nullable": False,
            "description": "As on the card",
        },
        {"name": "Age", "type": "integer"},
        {"name": "Joined", "type": "date"},
    ],
}


def make(client: Client, ws: int, spec: dict | None = None) -> Any:
    return call(client, "post", base(ws), spec or CUSTOMER)


def rw(ws: int) -> Any:
    return connections.workspace_connection(ws, "rw", 1)


def test_create_a_table_from_a_spec(client: Client, ws: int) -> None:
    response = make(client, ws)
    assert response.status_code == 200, response.content
    table = response.json()["data"]
    assert table["name"] == "customer" and table["description"] == "Who buys things"
    assert [
        (c["name"], c["type"], c["nullable"], c["hidden"]) for c in table["columns"]
    ] == [
        ("_row_id", "bigint", False, True),
        ("full_name", "text", False, False),
        ("age", "integer", True, False),
        ("joined", "date", True, False),
    ]
    assert table["columns"][1]["description"] == "As on the card"
    listing = call(client, "get", base(ws)).json()["data"]
    assert [t["name"] for t in listing] == ["customer"]
    assert call(client, "get", f"{base(ws)}/customer").status_code == 200
    assert call(client, "get", f"{base(ws)}/nope").json()["code"] == "table_not_found"


def test_the_table_is_usable_and_the_reader_cannot_write_to_it(
    client: Client, ws: int
) -> None:
    make(client, ws)
    with rw(ws) as connection:
        connection.execute("INSERT INTO customer (full_name, age) VALUES ('Ada', 36)")
        assert connection.execute("SELECT _row_id FROM customer").fetchall() == [(1,)]
    with connections.workspace_connection(ws, "ro", 1) as ro:
        assert ro.execute("SELECT full_name FROM customer").fetchall() == [("Ada",)]


def test_ddl_is_logged_and_the_schema_cache_moves(client: Client, ws: int) -> None:
    ref = ref_for(ws)
    assert schema.get_schema(ref).tables == ()
    make(client, ws)
    statements = list(
        WorkspaceDDLLog.objects.filter(workspace_id=ws).values_list(
            "statement", flat=True
        )
    )
    assert any(s.startswith("CREATE TABLE") for s in statements)
    assert any("COMMENT ON TABLE" in s for s in statements)
    assert [t.name for t in schema.get_schema(ref).tables] == ["customer"]


def test_descriptions_reach_the_prompt_and_row_id_stays_hidden_from_it(
    client: Client, ws: int
) -> None:
    make(client, ws)
    known = schema.get_schema(ref_for(ws), include_samples=True)
    text = schema.render(known)
    assert "Who buys things" in text and "As on the card" in text
    assert "_row_id" not in text
    assert [c.name for c in known.tables[0].columns] == ["full_name", "age", "joined"]


@pytest.mark.parametrize(
    "name",
    ['"; DROP TABLE x;--', "pg_catalog", "select", "ws_1", "名前", "1st", "a" * 300],
)
def test_hostile_table_names_are_made_safe(client: Client, ws: int, name: str) -> None:
    spec = {**CUSTOMER, "name": name}
    response = make(client, ws, spec)
    assert response.status_code == 200, response.content
    created = response.json()["data"]["name"]
    assert created.isascii() and len(created) <= 63
    assert call(client, "get", base(ws)).json()["data"][0]["name"] == created


def test_bad_specs_are_refused(client: Client, ws: int) -> None:
    empty = make(client, ws, {"name": "t", "columns": []})
    assert (empty.status_code, empty.json()["code"]) == (422, "invalid_spec")
    bad_type = make(
        client, ws, {"name": "t", "columns": [{"name": "a", "type": "json"}]}
    )
    assert bad_type.json()["code"] == "invalid_name"
    twice = make(
        client,
        ws,
        {
            "name": "t",
            "columns": [{"name": "A", "type": "text"}, {"name": "a", "type": "text"}],
        },
    )
    assert twice.json()["code"] == "column_name_taken"
    hidden = make(
        client, ws, {"name": "t", "columns": [{"name": "_row_id", "type": "text"}]}
    )
    assert hidden.status_code == 200  # slugged to row_id, the hidden key is untouched
    assert hidden.json()["data"]["columns"][1]["name"] == "row_id"
    long = make(
        client,
        ws,
        {
            "name": "t2",
            "columns": [{"name": "a", "type": "text", "description": "x" * 501}],
        },
    )
    assert long.json()["code"] == "invalid_name"
    assert make(client, ws).status_code == 200
    assert make(client, ws).json()["code"] == "table_name_taken"


@override_settings(WORKSPACE_MAX_TABLES=2, IMPORT_MAX_COLUMNS=3)
def test_the_table_and_column_caps(client: Client, ws: int) -> None:
    wide = make(
        client,
        ws,
        {"name": "w", "columns": [{"name": f"c{i}", "type": "text"} for i in range(4)]},
    )
    assert (wide.status_code, wide.json()["code"]) == (409, "column_limit_reached")
    one = {"name": "a", "columns": [{"name": "x", "type": "text"}]}
    assert make(client, ws, one).status_code == 200
    assert make(client, ws, {**one, "name": "b"}).status_code == 200
    third = make(client, ws, {**one, "name": "c"})
    assert (third.status_code, third.json()["code"]) == (409, "table_limit_reached")
    # adding columns also stops at the cap
    path = f"{base(ws)}/a/columns"
    assert call(client, "post", path, {"name": "y", "type": "text"}).status_code == 200
    assert call(client, "post", path, {"name": "z", "type": "text"}).status_code == 200
    assert (
        call(client, "post", path, {"name": "q", "type": "text"}).json()["code"]
        == "column_limit_reached"
    )


def test_rename_describe_and_drop_a_table(client: Client, ws: int) -> None:
    make(client, ws)
    patched = call(
        client,
        "patch",
        f"{base(ws)}/customer",
        {"name": "Clients", "description": "Paying people"},
    )
    assert patched.json()["data"]["name"] == "clients"
    assert patched.json()["data"]["description"] == "Paying people"
    make(client, ws, {**CUSTOMER, "name": "orders"})
    clash = call(client, "patch", f"{base(ws)}/orders", {"name": "clients"})
    assert clash.json()["code"] == "table_name_taken"
    assert call(client, "delete", f"{base(ws)}/clients").status_code == 200
    assert call(client, "get", f"{base(ws)}/clients").status_code == 404
    assert [t["name"] for t in call(client, "get", base(ws)).json()["data"]] == [
        "orders"
    ]


def test_columns_add_rename_describe_nullability_and_drop(
    client: Client, ws: int
) -> None:
    make(client, ws)
    with rw(ws) as connection:
        connection.execute(
            "INSERT INTO customer (full_name, age) VALUES ('Ada', 36), ('Bo', NULL)"
        )
    cols = f"{base(ws)}/customer/columns"
    needs_default = call(
        client, "post", cols, {"name": "Score", "type": "integer", "nullable": False}
    )
    assert (needs_default.status_code, needs_default.json()["code"]) == (
        409,
        "constraint_violation",
    )
    ok = call(
        client,
        "post",
        cols,
        {
            "name": "Score",
            "type": "integer",
            "nullable": False,
            "default": "0",
            "description": "Points",
        },
    )
    assert ok.status_code == 200, ok.content
    assert ok.json()["data"]["columns"][-1]["name"] == "score"
    with rw(ws) as connection:
        assert connection.execute("SELECT score FROM customer").fetchall() == [
            (0,),
            (0,),
        ]
    assert (
        call(client, "post", cols, {"name": "SCORE", "type": "text"}).json()["code"]
        == "column_name_taken"
    )
    renamed = call(
        client, "patch", f"{cols}/score", {"name": "Points", "description": "How many"}
    )
    names = [c["name"] for c in renamed.json()["data"]["columns"]]
    assert "points" in names and "score" not in names
    # NOT NULL on a column that has empty values names the row
    refused = call(client, "patch", f"{cols}/age", {"nullable": False})
    assert refused.status_code == 409
    assert "row 2" in refused.json()["errors"][0]["message"]
    assert (
        call(client, "patch", f"{cols}/full_name", {"nullable": True}).status_code
        == 200
    )
    assert call(client, "patch", f"{cols}/_row_id", {"name": "x"}).status_code == 404
    assert call(client, "delete", f"{cols}/_row_id").status_code == 404
    assert call(client, "delete", f"{cols}/points").status_code == 200
    only = make(
        client, ws, {"name": "solo", "columns": [{"name": "a", "type": "text"}]}
    )
    assert (
        call(client, "delete", f"{base(ws)}/solo/columns/a").json()["code"]
        == "invalid_spec"
    )
    assert only.status_code == 200


def test_retype_converts_inside_a_transaction(client: Client, ws: int) -> None:
    make(client, ws, {"name": "t", "columns": [{"name": "v", "type": "text"}]})
    with rw(ws) as connection:
        connection.execute("INSERT INTO t (v) VALUES ('1'), ('22'), (NULL)")
    ok = call(client, "patch", f"{base(ws)}/t/columns/v", {"type": "integer"})
    assert ok.status_code == 200, ok.content
    assert ok.json()["data"]["columns"][1]["type"] == "integer"
    with rw(ws) as connection:
        assert connection.execute("SELECT v FROM t ORDER BY _row_id").fetchall() == [
            (1,),
            (22,),
            (None,),
        ]
        connection.execute("ALTER TABLE t ALTER COLUMN v TYPE text")
        connection.execute("INSERT INTO t (v) VALUES ('oops')")
    bad = call(client, "patch", f"{base(ws)}/t/columns/v", {"type": "integer"})
    assert (bad.status_code, bad.json()["code"]) == (422, "cast_failed")
    assert "row 4" in bad.json()["errors"][0]["message"]
    # nothing changed
    assert (
        call(client, "get", f"{base(ws)}/t").json()["data"]["columns"][1]["type"]
        == "text"
    )
    with rw(ws) as connection:
        assert connection.execute("SELECT v FROM t WHERE _row_id = 4").fetchone() == (
            "oops",
        )


def test_another_users_workspace_is_a_404_for_every_table_route(
    client: Client, ws: int, other_user: User
) -> None:
    make(client, ws)
    client.force_login(other_user)
    for method, path, body in [
        ("get", base(ws), None),
        ("post", base(ws), CUSTOMER),
        ("get", f"{base(ws)}/customer", None),
        ("patch", f"{base(ws)}/customer", {"name": "x"}),
        ("delete", f"{base(ws)}/customer", None),
        ("post", f"{base(ws)}/customer/columns", {"name": "a", "type": "text"}),
        ("patch", f"{base(ws)}/customer/columns/age", {"name": "x"}),
        ("delete", f"{base(ws)}/customer/columns/age", None),
    ]:
        response = call(client, method, path, body)
        assert response.status_code == 404, (method, path)
        assert response.json()["code"] == "workspace_not_found"


def test_the_database_rows_of_the_workspace_survive_a_failed_change(
    client: Client, ws: int
) -> None:
    make(client, ws)
    before = WorkspaceDDLLog.objects.filter(workspace_id=ws).count()
    assert (
        call(
            client, "patch", f"{base(ws)}/customer/columns/age", {"name": "full_name"}
        ).status_code
        == 409
    )
    assert WorkspaceDDLLog.objects.filter(workspace_id=ws).count() == before
    assert Workspace.objects.filter(pk=ws).exists()
