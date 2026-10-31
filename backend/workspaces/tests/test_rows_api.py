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
    workspace = call(client, "post", "/api/workspaces", {"name": "W"}).json()["data"][
        "id"
    ]
    spec = {
        "name": "people",
        "columns": [
            {"name": "name", "type": "text", "nullable": False},
            {"name": "age", "type": "integer"},
            {"name": "joined", "type": "date"},
            {"name": "score", "type": "numeric"},
            {"name": "active", "type": "boolean"},
            {"name": "seen", "type": "timestamp"},
        ],
    }
    assert (
        call(client, "post", f"/api/workspaces/{workspace}/tables", spec).status_code
        == 200
    )
    return workspace


def rows_url(ws: int, rest: str = "") -> str:
    return f"/api/workspaces/{ws}/tables/people/rows{rest}"


def insert(client: Client, ws: int, rows: list[dict]) -> Any:
    return call(client, "post", rows_url(ws), {"rows": rows})


def names(client: Client, ws: int, query: str = "") -> list[str]:
    page = call(client, "get", rows_url(ws, query)).json()["data"]
    index = [c["name"] for c in page["columns"]].index("name")
    return [r[index] for r in page["rows"]]


def test_insert_read_update_delete(client: Client, ws: int) -> None:
    created = insert(
        client,
        ws,
        [
            {
                "name": "Ada",
                "age": "36",
                "joined": "2020-05-01",
                "score": "9.5",
                "active": "yes",
                "seen": "2024-01-31T12:00:00Z",
            },
            {"name": "Bo", "age": None, "active": False},
            {"name": "Cy", "age": 5, "joined": ""},
        ],
    )
    assert created.status_code == 200, created.content
    assert created.json()["data"] == {"inserted": 3, "ids": [1, 2, 3]}
    page = call(client, "get", rows_url(ws)).json()
    assert [c["name"] for c in page["data"]["columns"]][:3] == [
        "_row_id",
        "name",
        "age",
    ]
    first = page["data"]["rows"][0]
    assert (
        first[:3] == [1, "Ada", 36]
        and first[3] == "2020-05-01"
        and first[4] == "9.5"
        and first[5] is True
    )
    assert page["data"]["total"] == 3 and page["meta"]["count"] == 3
    patched = call(
        client, "patch", rows_url(ws, "/2"), {"values": {"name": "Bobby", "age": "41"}}
    )
    assert (
        patched.json()["data"]["row"]["name"] == "Bobby"
        and patched.json()["data"]["row"]["age"] == 41
    )
    assert names(client, ws) == ["Ada", "Bobby", "Cy"]
    deleted = call(client, "delete", rows_url(ws, "/1"))
    assert deleted.json()["data"] == {"deleted": 1, "cascaded": 0}
    assert call(client, "delete", rows_url(ws, "/1")).json()["code"] == "row_not_found"
    assert (
        call(client, "patch", rows_url(ws, "/1"), {"values": {"age": 1}}).status_code
        == 404
    )
    bulk = call(client, "delete", rows_url(ws, "?ids=2&ids=3&ids=99"))
    assert bulk.json()["data"]["deleted"] == 2
    assert names(client, ws) == []


def test_ordering_paging_and_filters(client: Client, ws: int) -> None:
    insert(
        client,
        ws,
        [
            {"name": n, "age": a}
            for n, a in [("Ada", 30), ("Bo", 20), ("Cy", 25), ("ad", 40)]
        ],
    )
    assert names(client, ws, "?order_by=age") == ["Bo", "Cy", "Ada", "ad"]
    assert names(client, ws, "?order_by=age&descending=true&limit=2") == ["ad", "Ada"]
    assert names(client, ws, "?order_by=age&limit=2&offset=2") == ["Ada", "ad"]
    assert names(client, ws, "?filter=name:contains:AD") == ["Ada", "ad"]
    assert names(client, ws, "?filter=name:contains:AD&filter=age:eq:40") == ["ad"]
    assert names(client, ws, "?filter=age:eq:25") == ["Cy"]
    assert names(client, ws, "?filter=name:contains:%25") == []  # % is literal
    assert (
        call(client, "get", rows_url(ws, "?order_by=nope")).json()["code"]
        == "invalid_spec"
    )
    assert call(client, "get", rows_url(ws, "?order_by=name;drop")).status_code == 422
    assert (
        call(client, "get", rows_url(ws, "?filter=nope:eq:1")).json()["code"]
        == "invalid_spec"
    )
    assert (
        call(client, "get", rows_url(ws, "?filter=age:gt:1")).json()["code"]
        == "invalid_spec"
    )
    assert (
        call(client, "get", rows_url(ws, "?filter=age:eq:abc")).json()["code"]
        == "row_invalid"
    )
    assert (
        call(client, "get", f"/api/workspaces/{ws}/tables/nope/rows").json()["code"]
        == "table_not_found"
    )


def test_a_bad_value_names_row_and_column_and_writes_nothing(
    client: Client, ws: int
) -> None:
    bad = insert(
        client, ws, [{"name": "ok"}, {"name": "x", "age": "old"}, {"name": "y"}]
    )
    assert (bad.status_code, bad.json()["code"]) == (422, "row_invalid")
    assert bad.json()["errors"][0]["field"] == "rows[1].age"
    assert "whole number" in bad.json()["errors"][0]["message"]
    unknown = insert(client, ws, [{"nope": 1}])
    assert unknown.json()["errors"][0]["field"] == "rows[0].nope"
    hidden = insert(client, ws, [{"_row_id": 5, "name": "x"}])
    assert hidden.json()["errors"][0]["field"] == "rows[0]._row_id"
    assert names(client, ws) == []


def test_injection_strings_are_plain_data(client: Client, ws: int) -> None:
    evil = "x'); DROP TABLE people;--"
    assert insert(client, ws, [{"name": evil}]).status_code == 200
    assert names(client, ws) == [evil]
    assert names(
        client, ws, "?filter=name:eq:" + "x%27%29%3B%20DROP%20TABLE%20people%3B--"
    ) == [evil]
    patched = call(
        client,
        "patch",
        rows_url(ws, "/1"),
        {"values": {"name": "'; DELETE FROM people;--"}},
    )
    assert patched.status_code == 200
    assert names(client, ws) == ["'; DELETE FROM people;--"]


@override_settings(WORKSPACE_MAX_ROWS_PER_EDIT=3)
def test_the_per_request_cap(client: Client, ws: int) -> None:
    assert (
        insert(client, ws, [{"name": str(i)} for i in range(4)]).json()["code"]
        == "too_many_rows"
    )
    assert insert(client, ws, []).json()["code"] == "invalid_spec"
    assert insert(client, ws, [{"name": str(i)} for i in range(3)]).status_code == 200
    assert (
        call(client, "delete", rows_url(ws, "?ids=1&ids=2&ids=3&ids=4")).json()["code"]
        == "too_many_rows"
    )
    assert call(client, "delete", rows_url(ws)).status_code == 422  # ids is required


def test_constraints_are_respected_and_named(client: Client, ws: int) -> None:
    base = f"/api/workspaces/{ws}"
    assert (
        insert(client, ws, [{}]).json()["code"] == "constraint_violation"
    )  # name NOT NULL
    ids = insert(client, ws, [{"name": "a", "age": 1}, {"name": "b", "age": 2}]).json()[
        "data"
    ]["ids"]
    call(client, "put", f"{base}/tables/people/primary-key", {"columns": ["age"]})
    duplicate = insert(client, ws, [{"name": "c", "age": 1}])
    assert duplicate.status_code == 409
    assert "people_pkey" in duplicate.json()["errors"][0]["message"]
    assert (
        call(
            client, "patch", rows_url(ws, f"/{ids[1]}"), {"values": {"age": 1}}
        ).json()["code"]
        == "constraint_violation"
    )
    assert (
        call(
            client, "patch", rows_url(ws, f"/{ids[1]}"), {"values": {"name": None}}
        ).json()["code"]
        == "constraint_violation"
    )
    call(
        client,
        "post",
        f"{base}/tables",
        {"name": "pets", "columns": [{"name": "owner_age", "type": "integer"}]},
    )
    call(
        client,
        "post",
        f"{base}/tables/pets/rows",
        {"rows": [{"owner_age": 1}, {"owner_age": 1}, {"owner_age": 2}]},
    )
    relation = {
        "child_table": "pets",
        "child_columns": ["owner_age"],
        "parent_table": "people",
        "parent_columns": ["age"],
    }
    assert call(client, "post", f"{base}/relations", relation).status_code == 200
    refused = call(
        client, "post", f"{base}/tables/pets/rows", {"rows": [{"owner_age": 77}]}
    )
    assert refused.json()["code"] == "constraint_violation"
    blocked = call(client, "delete", rows_url(ws, f"/{ids[0]}"))
    assert (blocked.status_code, blocked.json()["code"]) == (
        409,
        "constraint_violation",
    )


def test_cascade_deletes_are_counted(client: Client, ws: int) -> None:
    base = f"/api/workspaces/{ws}"
    insert(client, ws, [{"name": "a", "age": 1}, {"name": "b", "age": 2}])
    call(client, "put", f"{base}/tables/people/primary-key", {"columns": ["age"]})
    call(
        client,
        "post",
        f"{base}/tables",
        {"name": "pets", "columns": [{"name": "owner_age", "type": "integer"}]},
    )
    call(
        client,
        "post",
        f"{base}/tables/pets/rows",
        {"rows": [{"owner_age": 1}, {"owner_age": 1}, {"owner_age": 2}]},
    )
    relation = {
        "child_table": "pets",
        "child_columns": ["owner_age"],
        "parent_table": "people",
        "parent_columns": ["age"],
        "on_delete": "CASCADE",
    }
    call(client, "post", f"{base}/relations", relation)
    deleted = call(client, "delete", rows_url(ws, "/1"))
    assert deleted.json()["data"] == {"deleted": 1, "cascaded": 2}
    remaining = call(client, "get", f"{base}/tables/pets/rows").json()["data"]
    assert remaining["total"] == 1


def test_edits_do_not_move_the_schema_version_unless_the_size_class_changes(
    client: Client, ws: int
) -> None:
    ref = ref_for(ws)
    from workspaces import schema_version

    insert(client, ws, [{"name": "a"}])
    start = schema_version.current(ref)
    call(client, "patch", rows_url(ws, "/1"), {"values": {"name": "b"}})
    insert(
        client, ws, [{"name": str(i)} for i in range(2, 5)]
    )  # 1 -> 4 rows, same size class
    assert schema_version.current(ref) == start
    insert(client, ws, [{"name": str(i)} for i in range(5, 15)])  # 4 -> 14 rows
    assert schema_version.current(ref) == start + 1
    assert not WorkspaceDDLLog.objects.filter(
        workspace_id=ws, statement__contains="INSERT"
    ).exists()


@override_settings(WORKSPACE_MAX_BYTES=200_000)
def test_writes_refuse_when_the_workspace_is_full(client: Client, ws: int) -> None:
    with connections.workspace_connection(ws, "rw", 1) as rw:
        rw.execute(
            "INSERT INTO people (name) SELECT repeat('x', 1000) FROM generate_series(1, 400)"
        )
    full = insert(client, ws, [{"name": "one more"}])
    assert (full.status_code, full.json()["code"]) == (409, "workspace_full")
    assert (
        call(client, "patch", rows_url(ws, "/1"), {"values": {"name": "x"}}).json()[
            "code"
        ]
        == "workspace_full"
    )
    assert (
        call(client, "delete", rows_url(ws, "/1")).status_code == 200
    )  # deleting is allowed


def test_the_agent_sees_edited_data_on_its_next_read(client: Client, ws: int) -> None:
    from ask import runner

    insert(client, ws, [{"name": "Ada"}])
    ref = ref_for(ws)
    assert runner.run("SELECT name FROM people", ref).rows == [["Ada"]]
    call(client, "patch", rows_url(ws, "/1"), {"values": {"name": "Grace"}})
    assert runner.run("SELECT name FROM people", ref).rows == [["Grace"]]
    assert "_row_id" not in schema.render(schema.get_schema(ref))


@pytest.mark.django_db(transaction=True)
def test_concurrent_edits_to_the_same_row_both_apply_in_order(
    client: Client, ws: int
) -> None:
    import threading

    from django.db import connection as django_connection

    insert(client, ws, [{"name": "a", "age": 0}])
    results: list[int] = []

    def edit(age: int) -> None:
        try:
            other = Client()
            other.force_login(User.objects.get(email="ada@example.com"))
            results.append(
                call(
                    other, "patch", rows_url(ws, "/1"), {"values": {"age": age}}
                ).status_code
            )
        finally:
            django_connection.close()

    threads = [threading.Thread(target=edit, args=(i,)) for i in (1, 2)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    assert sorted(results) == [200, 200]
    page = call(client, "get", rows_url(ws)).json()["data"]
    assert page["rows"][0][2] in (1, 2)


def test_another_users_rows_are_a_404(
    client: Client, ws: int, other_user: User
) -> None:
    insert(client, ws, [{"name": "secret"}])
    client.force_login(other_user)
    for method, rest, body in [
        ("get", "", None),
        ("post", "", {"rows": [{"name": "x"}]}),
        ("patch", "/1", {"values": {"name": "x"}}),
        ("delete", "/1", None),
        ("delete", "?ids=1", None),
    ]:
        response = call(client, method, rows_url(ws, rest), body)
        assert (
            response.status_code == 404
            and response.json()["code"] == "workspace_not_found"
        )
