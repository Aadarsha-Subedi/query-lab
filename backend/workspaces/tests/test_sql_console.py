import json
import time
from typing import Any

import pytest
from django.test import Client, override_settings

from accounts.models import User
from ask import schema
from workspaces import connections
from workspaces.context import ref_for
from workspaces.models import WorkspaceDDLLog
from workspaces.tests.conftest import connect

pytestmark = [pytest.mark.django_db, pytest.mark.usefixtures("data_connections")]


@pytest.fixture
def ws(client: Client, user: User) -> int:
    client.force_login(user)
    response = client.post(
        "/api/workspaces", json.dumps({"name": "S"}), content_type="application/json"
    )
    return response.json()["data"]["id"]


def run(client: Client, ws: int, script: str) -> Any:
    return client.post(
        f"/api/workspaces/{ws}/sql",
        json.dumps({"sql": script}),
        content_type="application/json",
    )


def test_ddl_dml_and_select_in_one_request(client: Client, ws: int) -> None:
    response = run(
        client,
        ws,
        "CREATE TABLE t (id int, name text);"
        "INSERT INTO t VALUES (1, 'a'), (2, 'b');"
        "UPDATE t SET name = upper(name) WHERE id = 2;"
        "SELECT id, name FROM t ORDER BY id;",
    )
    assert response.status_code == 200, response.content
    data = response.json()["data"]
    assert [s["command"] for s in data["statements"]] == [
        "CREATE TABLE",
        "INSERT 0 2",
        "UPDATE 1",
        "SELECT 2",
    ]
    assert [s["kind"] for s in data["statements"]] == ["ddl", "data", "data", "query"]
    last = data["statements"][-1]
    assert (last["columns"], last["rows"]) == (["id", "name"], [[1, "a"], [2, "B"]])
    assert data["counts"] == {"ddl": 1, "data": 2, "query": 1}


def test_ddl_is_logged_data_is_only_counted_and_the_agent_sees_the_change(
    client: Client, ws: int
) -> None:
    ref = ref_for(ws)
    assert schema.get_schema(ref).tables == ()
    run(
        client,
        ws,
        "CREATE TABLE t (id int); INSERT INTO t VALUES (1); COMMENT ON TABLE t IS 'hi'",
    )
    logged = list(
        WorkspaceDDLLog.objects.filter(workspace_id=ws).values_list(
            "statement", flat=True
        )
    )
    assert (
        "CREATE TABLE t (id int)" in logged and "COMMENT ON TABLE t IS 'hi'" in logged
    )
    assert not any("INSERT" in s for s in logged)
    known = schema.get_schema(ref)
    assert [t.name for t in known.tables] == ["t"] and known.tables[0].comment == "hi"


def test_a_failing_statement_rolls_back_the_whole_request(
    client: Client, ws: int
) -> None:
    run(client, ws, "CREATE TABLE t (id int PRIMARY KEY)")
    failed = run(
        client,
        ws,
        "INSERT INTO t VALUES (1); INSERT INTO t VALUES (2); INSERT INTO t VALUES (1)",
    )
    assert (failed.status_code, failed.json()["code"]) == (422, "sql_failed")
    message = failed.json()["errors"][0]["message"]
    assert message.startswith("Statement 3: 23505:") and "duplicate key" in message
    assert run(client, ws, "SELECT count(*) FROM t").json()["data"]["statements"][0][
        "rows"
    ] == [[0]]
    # DDL that was fine before the failure is rolled back too
    run(client, ws, "CREATE TABLE ghost (id int); SELECT nope")
    assert run(client, ws, "SELECT * FROM ghost").status_code == 422
    assert not WorkspaceDDLLog.objects.filter(
        workspace_id=ws, statement__contains="ghost"
    ).exists()


def test_views_functions_triggers_and_indexes_work_and_stay_inside(
    client: Client, ws: int
) -> None:
    script = """
    CREATE TABLE t (id int, n int);
    CREATE TABLE audit (note text);
    CREATE VIEW big AS SELECT * FROM t WHERE n > 5;
    CREATE INDEX t_n ON t (n);
    CREATE FUNCTION note() RETURNS trigger LANGUAGE plpgsql AS $$
      BEGIN INSERT INTO audit VALUES ('row ' || NEW.id); RETURN NEW; END $$;
    CREATE TRIGGER t_note AFTER INSERT ON t FOR EACH ROW EXECUTE FUNCTION note();
    INSERT INTO t VALUES (1, 3), (2, 9);
    SELECT id FROM big;
    SELECT note FROM audit ORDER BY note;
    SELECT schemaname FROM pg_tables WHERE tablename = 't'
    """
    response = run(client, ws, script)
    assert response.status_code == 200, response.content
    statements = response.json()["data"]["statements"]
    assert statements[-3]["rows"] == [[2]]
    assert statements[-2]["rows"] == [["row 1"], ["row 2"]]
    assert statements[-1]["rows"] == [[f"ws_{ws}"]]
    with connections.workspace_connection(
        ws, "ro", 1
    ) as ro:  # the agent role reads them
        assert ro.execute("SELECT id FROM big").fetchall() == [(2,)]


@pytest.mark.parametrize(
    "script",
    [
        "SELECT * FROM demo.orders",
        "SELECT * FROM ws_1.customer",
        "CREATE TABLE public.x (id int)",
        "SET ROLE querylab",
        "CREATE EXTENSION dblink",
        "CREATE ROLE evil",
        "CREATE SCHEMA evil",
        "SELECT pg_read_file('/etc/passwd')",
        "CREATE TEMP TABLE t (id int)",
        "ALTER SYSTEM SET work_mem = '1GB'",
        "GRANT ALL ON SCHEMA demo TO PUBLIC",
        "DROP SCHEMA demo CASCADE",
    ],
)
def test_attempts_to_escape_are_refused_and_roll_back(
    client: Client, ws: int, script: str, owner: Any
) -> None:
    response = run(client, ws, "CREATE TABLE keep (id int);" + script)
    assert response.status_code == 422, response.content
    assert response.json()["code"] == "sql_failed"
    assert run(client, ws, "SELECT * FROM keep").status_code == 422  # rolled back
    assert owner.execute("SELECT count(*) FROM demo.orders").fetchone()[0] > 0


def test_messages_do_not_name_other_workspaces(client: Client, ws: int) -> None:
    message = run(client, ws, "SELECT * FROM ws_424242.customer").json()["errors"][0][
        "message"
    ]
    assert "ws_424242" not in message
    own = run(client, ws, f"SELECT * FROM ws_{ws}.nope").json()["errors"][0]["message"]
    assert f"ws_{ws}" in own or "nope" in own


@pytest.mark.parametrize(
    ("script", "fragment"),
    [
        ("", "some SQL"),
        ("   ;  ", "some SQL"),
        ("BEGIN; SELECT 1; COMMIT", "one transaction"),
        ("select 1; rollback", "one transaction"),
        ("COPY t FROM STDIN", "COPY"),
    ],
)
def test_requests_refused_before_running(
    client: Client, ws: int, script: str, fragment: str
) -> None:
    response = run(client, ws, script)
    assert (response.status_code, response.json()["code"]) == (400, "sql_invalid")
    assert fragment.lower() in response.json()["message"].lower()


@override_settings(WORKSPACE_SQL_MAX_CHARS=30, WORKSPACE_SQL_MAX_STATEMENTS=2)
def test_script_length_and_statement_caps(client: Client, ws: int) -> None:
    assert run(client, ws, "select '" + "x" * 40 + "'").json()["code"] == "sql_invalid"
    assert (
        run(client, ws, "select 1; select 2; select 3").json()["code"] == "sql_invalid"
    )
    assert run(client, ws, "select 1; select 2").status_code == 200


@override_settings(WORKSPACE_SQL_MAX_ROWS=3)
def test_result_rows_are_capped(client: Client, ws: int) -> None:
    data = run(client, ws, "SELECT g FROM generate_series(1, 10) g").json()["data"]
    assert data["statements"][0]["truncated"] is True
    assert len(data["statements"][0]["rows"]) == 3


def test_odd_values_come_back_as_json(client: Client, ws: int) -> None:
    row = run(
        client,
        ws,
        "SELECT 1.5::numeric, now()::date, '\\xdeadbeef'::bytea, ARRAY[1,2], '{\"a\":1}'::jsonb",
    ).json()["data"]["statements"][0]["rows"][0]
    assert (
        row[0] == "1.5"
        and row[2] == "\\xdeadbeef"
        and row[3] == [1, 2]
        and row[4] == {"a": 1}
    )


@override_settings(WORKSPACE_STATEMENT_TIMEOUT_MS=1000)
def test_the_timeout_holds_even_when_the_user_turns_it_off(
    client: Client, ws: int
) -> None:
    started = time.monotonic()
    response = run(client, ws, "SET statement_timeout = 0; SELECT pg_sleep(8)")
    assert time.monotonic() - started < 5
    assert (response.status_code, response.json()["code"]) == (504, "query_timeout")


@override_settings(WORKSPACE_MAX_BYTES=400_000)
def test_a_workspace_is_full_before_it_can_fill_the_disk(
    client: Client, ws: int
) -> None:
    run(client, ws, "CREATE TABLE t (v text)")
    full = run(
        client,
        ws,
        "INSERT INTO t SELECT repeat('x', 1000) FROM generate_series(1, 5000)",
    )
    assert (full.status_code, full.json()["code"]) == (409, "workspace_full")
    rows = run(client, ws, "SELECT count(*) FROM t").json()["data"]["statements"][0][
        "rows"
    ]
    assert rows == [[0]]  # rolled back
    # the rolled-back rows leave dead space until autovacuum: start the table over
    ok = run(
        client,
        ws,
        "DROP TABLE t; CREATE TABLE t (v text);"
        "INSERT INTO t SELECT repeat('x', 1000) FROM generate_series(1, 100)",
    )
    assert ok.status_code == 200, ok.content


def test_a_full_workspace_can_still_delete_its_way_out(client: Client, ws: int) -> None:
    run(
        client,
        ws,
        "CREATE TABLE t (v text); INSERT INTO t SELECT repeat('x', 1000) FROM generate_series(1, 500)",
    )
    with override_settings(WORKSPACE_MAX_BYTES=10_000):
        assert run(client, ws, "DELETE FROM t").status_code == 200
        assert run(client, ws, "DROP TABLE t").status_code == 200
        blocked = run(
            client,
            ws,
            "CREATE TABLE t (v text); INSERT INTO t SELECT repeat('x', 1000) FROM generate_series(1, 50)",
        )
        assert blocked.json()["code"] == "workspace_full"


@override_settings(USER_MAX_BYTES=300_000)
def test_the_user_total_cap(client: Client, ws: int) -> None:
    run(client, ws, "CREATE TABLE t (v text)")
    response = run(
        client,
        ws,
        "INSERT INTO t SELECT repeat('x', 1000) FROM generate_series(1, 5000)",
    )
    assert response.json()["code"] == "user_storage_full"


def test_one_console_request_at_a_time_per_user(client: Client, ws: int) -> None:
    from common.redis import get_redis
    from workspaces.sql import _running_key

    user = User.objects.get(email="ada@example.com")
    get_redis().set(_running_key(user), 1)
    try:
        busy = run(client, ws, "select 1")
        assert (busy.status_code, busy.json()["code"]) == (429, "sql_busy")
        assert busy.json()["retry_after_seconds"] is None
    finally:
        get_redis().delete(_running_key(user))
    assert run(client, ws, "select 1").status_code == 200
    assert int(get_redis().get(_running_key(user)) or 0) == 0


def test_someone_elses_workspace_is_a_404(
    client: Client, ws: int, other_user: User
) -> None:
    client.force_login(other_user)
    assert run(client, ws, "select 1").status_code == 404


def test_the_console_cannot_be_used_to_reach_the_connection_of_another_workspace(
    client: Client, ws: int, other_user: User
) -> None:
    client.force_login(other_user)
    other = client.post(
        "/api/workspaces", json.dumps({"name": "O"}), content_type="application/json"
    ).json()["data"]["id"]
    with connect(other, "rw") as theirs:
        theirs.execute("CREATE TABLE secret (v text)")
        theirs.execute("INSERT INTO secret VALUES ('hidden')")
    client.force_login(User.objects.get(email="ada@example.com"))
    attempt = run(client, ws, f"SELECT * FROM ws_{other}.secret")
    assert attempt.status_code == 422 and "hidden" not in attempt.content.decode()
