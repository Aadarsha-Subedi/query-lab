"""The query runner: read-only SQL on a user's own workspace, as `ws_<id>_ro`."""

import json
import time
from typing import Any

import pytest
from django.test import Client, override_settings

from accounts.models import User
from workspaces.tests.conftest import connect

pytestmark = [pytest.mark.django_db, pytest.mark.usefixtures("data_connections")]


@pytest.fixture
def ws(client: Client, user: User) -> int:
    client.force_login(user)
    response = client.post(
        "/api/workspaces", json.dumps({"name": "S"}), content_type="application/json"
    )
    workspace = response.json()["data"]["id"]
    with connect(workspace, "rw") as rw:  # test setup only: an import does this
        rw.execute("CREATE TABLE t (id int, n int)")
        rw.execute("INSERT INTO t VALUES (1, 3), (2, 9)")
    return workspace


def run(client: Client, ws: int, script: str) -> Any:
    return client.post(
        f"/api/workspaces/{ws}/sql",
        json.dumps({"sql": script}),
        content_type="application/json",
    )


def rows(response: Any, index: int = 0) -> list:
    return response.json()["data"]["statements"][index]["rows"]


def test_select_with_explain_show_values_work(client: Client, ws: int) -> None:
    response = run(
        client,
        ws,
        "SELECT id FROM t ORDER BY id; "
        "WITH big AS (SELECT * FROM t WHERE n > 5) SELECT id FROM big; "
        "VALUES (1), (2); SHOW search_path; EXPLAIN SELECT * FROM t",
    )
    assert response.status_code == 200, response.content
    assert rows(response, 0) == [[1], [2]]
    assert rows(response, 1) == [[2]]
    assert rows(response, 2) == [[1], [2]]
    assert rows(response, 3) == [[f"ws_{ws}"]]
    assert response.json()["data"]["statements"][0]["command"] == "SELECT 2"


@pytest.mark.parametrize(
    "script",
    [
        "INSERT INTO t VALUES (3, 4)",
        "UPDATE t SET n = 0",
        "DELETE FROM t",
        "TRUNCATE t",
        "CREATE TABLE x (id int)",
        "CREATE VIEW v AS SELECT 1",
        "ALTER TABLE t ADD COLUMN z int",
        "DROP TABLE t",
        "GRANT ALL ON t TO PUBLIC",
        "SET ROLE querylab",
        "SET search_path = demo",
        "DO $$ BEGIN DELETE FROM t; END $$",
        "CALL nothing()",
        "COPY t FROM STDIN",
        "COMMENT ON TABLE t IS 'x'",
        "SELECT 1; DROP TABLE t",
        "BEGIN; SELECT 1; COMMIT",
        "ROLLBACK",
    ],
)
def test_anything_that_could_write_is_refused_before_running(
    client: Client, ws: int, script: str
) -> None:
    response = run(client, ws, script)
    assert (response.status_code, response.json()["code"]) == (400, "sql_invalid")
    assert rows(run(client, ws, "SELECT count(*) FROM t")) == [[2]]


@pytest.mark.parametrize(
    "script",
    [
        "WITH d AS (DELETE FROM t RETURNING *) SELECT * FROM d",
        "WITH i AS (INSERT INTO t VALUES (9, 9) RETURNING *) SELECT * FROM i",
        "SELECT * FROM demo.orders",
        "SELECT * FROM ws_1.customer",
        "SELECT * FROM public.anything",
        "SELECT pg_read_file('/etc/passwd')",
        "SELECT * INTO newtable FROM t",
        "EXPLAIN ANALYZE WITH d AS (DELETE FROM t RETURNING *) SELECT * FROM d",
    ],
)
def test_reads_that_hide_a_write_or_reach_elsewhere_fail_in_the_database(
    client: Client, ws: int, script: str
) -> None:
    response = run(client, ws, script)
    assert response.status_code == 422, response.content
    assert response.json()["code"] == "sql_failed"
    assert rows(run(client, ws, "SELECT count(*) FROM t")) == [[2]]


def test_messages_do_not_name_other_workspaces(client: Client, ws: int) -> None:
    message = run(client, ws, "SELECT * FROM ws_424242.customer").json()["errors"][0][
        "message"
    ]
    assert "ws_424242" not in message
    own = run(client, ws, f"SELECT * FROM ws_{ws}.nope").json()["errors"][0]["message"]
    assert f"ws_{ws}" in own or "nope" in own


@pytest.mark.parametrize(
    ("script", "fragment"),
    [("", "some SQL"), ("   ;  ", "some SQL")],
)
def test_empty_requests_are_refused(
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
    response = run(
        client,
        ws,
        "SELECT set_config('statement_timeout', '0', false); SELECT pg_sleep(8)",
    )
    assert time.monotonic() - started < 5
    assert (response.status_code, response.json()["code"]) == (504, "query_timeout")


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


def test_the_console_cannot_reach_another_workspace(
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
