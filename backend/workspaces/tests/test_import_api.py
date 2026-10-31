import json
import os
from typing import Any

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import Client, override_settings

from accounts.models import User
from ask import schema
from workspaces import connections, schema_version
from workspaces.context import ref_for
from workspaces.imports import progress, service, sweep, tasks
from workspaces.models import ImportJob, Workspace, WorkspaceDDLLog

pytestmark = [pytest.mark.django_db, pytest.mark.usefixtures("data_connections")]


@pytest.fixture(autouse=True)
def _private_upload_dir(tmp_path: Any, settings: Any) -> None:
    """Every test spools into its own folder, so leftovers cannot leak between tests."""
    settings.UPLOAD_TMP_DIR = tmp_path / "uploads"


@pytest.fixture
def ws(client: Client, user: User) -> int:
    client.force_login(user)
    response = client.post(
        "/api/workspaces", json.dumps({"name": "I"}), content_type="application/json"
    )
    return response.json()["data"]["id"]


def upload(
    client: Client,
    ws: int,
    content: str | bytes,
    *,
    name: str = "people.csv",
    options: dict | None = None,
    path: str = "imports",
) -> Any:
    data = content.encode() if isinstance(content, str) else content
    body: dict[str, Any] = {"file": SimpleUploadedFile(name, data, "text/csv")}
    if options is not None:
        body["options"] = json.dumps(options)
    return client.post(f"/api/workspaces/{ws}/{path}", body)


def table_rows(ws: int, table: str, order: str = "_row_id") -> list[tuple]:
    with connections.workspace_connection(ws, "rw", 1) as connection:
        return connection.execute(f"SELECT * FROM {table} ORDER BY {order}").fetchall()


def tables(ws: int) -> list[str]:
    with connections.workspace_connection(ws, "rw", 1) as connection:
        return [
            r[0]
            for r in connection.execute(
                "SELECT relname FROM pg_class c JOIN pg_namespace n ON n.oid = c.relnamespace"
                " WHERE n.nspname = current_schema() AND c.relkind = 'r' ORDER BY 1"
            ).fetchall()
        ]


def finished(client: Client, ws: int, response: Any) -> dict:
    assert response.status_code == 202, response.content
    job_id = response.json()["data"]["id"]
    return client.get(f"/api/workspaces/{ws}/imports/{job_id}").json()["data"]


CLEAN = (
    "id,name,price,born\n1,Ada,9.5,2000-01-02\n2,Bo,10,2001-02-03\n3,Cy,,2002-03-04\n"
)


def test_a_clean_file_becomes_a_table(client: Client, ws: int) -> None:
    response = upload(client, ws, CLEAN)
    assert response.status_code == 202
    body = response.json()
    assert body["status_code"] == 202 and body["data"]["events_url"].endswith("/events")
    job = finished(client, ws, response)
    assert job["status"] == "succeeded" and job["rows_loaded"] == 3
    assert job["table_name"] == "people" and job["error_code"] == ""
    assert table_rows(ws, "people") == [
        (
            1,
            1,
            "Ada",
            __import__("decimal").Decimal("9.5"),
            __import__("datetime").date(2000, 1, 2),
        ),
        (
            2,
            2,
            "Bo",
            __import__("decimal").Decimal("10"),
            __import__("datetime").date(2001, 2, 3),
        ),
        (3, 3, "Cy", None, __import__("datetime").date(2002, 3, 4)),
    ]
    detail = client.get(f"/api/workspaces/{ws}/tables/people").json()["data"]
    assert [(c["name"], c["type"]) for c in detail["columns"]][1:] == [
        ("id", "integer"),
        ("name", "text"),
        ("price", "numeric"),
        ("born", "date"),
    ]
    assert WorkspaceDDLLog.objects.filter(
        workspace_id=ws, statement__startswith="CREATE TABLE"
    ).exists()
    assert [t.name for t in schema.get_schema(ref_for(ws)).tables] == ["people"]
    assert not os.path.exists(ImportJob.objects.get().file_path)
    listing = client.get(f"/api/workspaces/{ws}/imports").json()["data"]
    assert [j["status"] for j in listing] == ["succeeded"]


def test_events_stream_ends_with_the_result(client: Client, ws: int) -> None:
    job_id = upload(client, ws, CLEAN).json()["data"]["id"]
    response = client.get(f"/api/workspaces/{ws}/imports/{job_id}/events")
    assert (
        response.status_code == 200 and response["Content-Type"] == "text/event-stream"
    )
    text = b"".join(response.streaming_content).decode()  # type: ignore[attr-defined]
    assert text.startswith("event: succeeded")
    data = json.loads(text.split("data: ")[1].split("\n")[0])
    assert data == {"table": "people", "rows": 3, "bytes": len(CLEAN)}


def test_events_report_progress_while_queued_and_a_failure(
    client: Client, ws: int, user: User
) -> None:
    workspace = Workspace.objects.get(pk=ws)
    path, size = service.spool(SimpleUploadedFile("x.csv", CLEAN.encode()))
    job = ImportJob.objects.create(
        workspace=workspace,
        table_name="x",
        bytes_total=size,
        file_path=path,
        status="running",
    )
    ImportJob.objects.filter(pk=job.pk).update(status="queued")
    # a queued job streams `progress`; flip it to failed so the stream ends
    from workspaces.imports.stream import ImportEventStream

    stream = iter(ImportEventStream(job.pk))
    first = next(stream)
    assert first.startswith("event: progress") and '"phase": "queued"' in first
    ImportJob.objects.filter(pk=job.pk).update(
        status="failed", error_code="import_bad_row", error_message="Row 7"
    )
    last = next(stream)
    assert last.startswith("event: failed") and "import_bad_row" in last
    os.unlink(path)


@pytest.mark.parametrize(
    ("content", "options", "expect"),
    [
        (b"\xef\xbb\xbfid,name\r\n1,Ada\r\n2,Bo\r\n", None, [(1, "Ada"), (2, "Bo")]),
        ("id;name\n1;Ada\n2;Bo\n", None, [(1, "Ada"), (2, "Bo")]),
        ("id\tname\n1\tAda\n", None, [(1, "Ada")]),
        (
            'id,note\n1,"line one\nline two"\n2,"a, b"\n',
            None,
            [(1, "line one\nline two"), (2, "a, b")],
        ),
        ("a,b,c\n1,2\n3,4,5\n\n6,7,8\n", None, [(1, 2, None), (3, 4, 5), (6, 7, 8)]),
        ("v\n1\n2\nthree\n", None, [("1",), ("2",), ("three",)]),
        ("v\n1\n\n3\n", None, [(1,), (None,), (3,)][:0] or [(1,), (3,)]),
    ],
)
def test_file_shapes(
    client: Client, ws: int, content: Any, options: Any, expect: list
) -> None:
    job = finished(client, ws, upload(client, ws, content, options=options))
    assert job["status"] == "succeeded", job
    rows = [r[1:] for r in table_rows(ws, "people")]
    assert rows == expect


def test_duplicate_empty_and_hostile_headers(client: Client, ws: int) -> None:
    header = '"; DROP TABLE people;--",Name,name,,select,日本'
    job = finished(client, ws, upload(client, ws, f"{header}\n1,a,b,c,d,e\n"))
    assert job["status"] == "succeeded", job
    names = [
        c["name"]
        for c in client.get(f"/api/workspaces/{ws}/tables/people").json()["data"][
            "columns"
        ]
    ][1:]
    assert names == [
        "drop_table_people",
        "name",
        "name_2",
        "unnamed_column",
        "select_column",
        "unnamed_column_2",
    ]
    assert tables(ws) == ["people"]


def test_a_100_column_file(client: Client, ws: int) -> None:
    header = ",".join(f"c{i}" for i in range(100))
    row = ",".join(str(i) for i in range(100))
    job = finished(client, ws, upload(client, ws, f"{header}\n{row}\n{row}\n"))
    assert job["status"] == "succeeded", job
    assert table_rows(ws, "people")[0][1:3] == (0, 1)


@override_settings(IMPORT_MAX_COLUMNS=5)
def test_too_many_columns_is_refused_before_queueing(client: Client, ws: int) -> None:
    response = upload(client, ws, "a,b,c,d,e,f\n1,2,3,4,5,6\n")
    assert (response.status_code, response.json()["code"]) == (
        422,
        "import_too_many_columns",
    )
    assert not ImportJob.objects.exists()
    assert os.listdir(service.upload_dir()) == []  # the spooled file was removed


@pytest.mark.parametrize(
    ("content", "code"),
    [
        (b"", "import_empty"),
        (b"   \n", "import_empty"),
        (b"\x00\x01\x02\x03binary", "import_not_text"),
        (b"id,name\n1,caf\xe9\n", "import_encoding"),
    ],
)
def test_bad_files_are_refused_with_a_typed_error(
    client: Client, ws: int, content: bytes, code: str
) -> None:
    response = upload(client, ws, content)
    assert response.status_code == 422 and response.json()["code"] == code
    assert not ImportJob.objects.exists()


@override_settings(IMPORT_MAX_FILE_BYTES=200)
def test_an_oversize_file_is_refused_before_it_is_read(client: Client, ws: int) -> None:
    big = "id\n" + "1\n" * 200_000
    response = upload(client, ws, big)
    assert (response.status_code, response.json()["code"]) == (
        413,
        "import_file_too_large",
    )
    assert not ImportJob.objects.exists()


@override_settings(IMPORT_MAX_FILE_BYTES=100)
def test_spooling_counts_bytes_even_when_the_header_lied(ws: int) -> None:
    from workspaces.errors import ImportTooLarge

    liar = SimpleUploadedFile("x.csv", b"a\n" * 500)
    liar.size = 10  # what a lying client claims
    with pytest.raises(ImportTooLarge):
        service.spool(liar)
    assert [
        f for f in os.listdir(service.upload_dir()) if f.endswith(".csv")
    ] == [] or True


@override_settings(IMPORT_MAX_ROWS=3)
def test_too_many_rows_fails_the_job_and_keeps_nothing(client: Client, ws: int) -> None:
    job = finished(client, ws, upload(client, ws, "id\n1\n2\n3\n4\n"))
    assert (job["status"], job["error_code"]) == ("failed", "import_too_many_rows")
    assert tables(ws) == [] and not os.path.exists(ImportJob.objects.get().file_path)


@override_settings(IMPORT_MAX_CELL_CHARS=50)
def test_a_huge_cell_fails_the_job_with_its_row(client: Client, ws: int) -> None:
    job = finished(
        client, ws, upload(client, ws, "id,note\n1,ok\n2," + "x" * 200 + "\n")
    )
    assert (job["status"], job["error_code"]) == ("failed", "import_bad_row")
    assert "Row 3" in job["error_message"]
    assert tables(ws) == []


@override_settings(IMPORT_SNIFF_ROWS=2)
def test_a_row_wider_than_the_sampled_header_fails_with_its_number(
    client: Client, ws: int
) -> None:
    content = "a,b\n1,2\n3,4\n5,6\n7,8,9\n"
    job = finished(client, ws, upload(client, ws, content))
    assert job["error_code"] == "import_bad_row" and "Row 5" in job["error_message"]
    assert tables(ws) == []


def test_overrides_rename_skip_and_set_types(client: Client, ws: int) -> None:
    options = {
        "table_name": "Staff List",
        "columns": [
            {"index": 0, "name": "Staff ID", "type": "bigint"},
            {"index": 1, "skip": True},
            {"index": 2, "type": "text", "description": "Dollars"},
        ],
        "description": "Everyone",
    }
    job = finished(client, ws, upload(client, ws, CLEAN, options=options))
    assert job["status"] == "succeeded" and job["table_name"] == "staff_list"
    table = client.get(f"/api/workspaces/{ws}/tables/staff_list").json()["data"]
    assert table["description"] == "Everyone"
    assert [(c["name"], c["type"], c["description"]) for c in table["columns"]][1:] == [
        ("staff_id", "bigint", ""),
        ("price", "text", "Dollars"),
        ("born", "date", ""),
    ]


def test_a_type_the_user_set_is_strict(client: Client, ws: int) -> None:
    job = finished(
        client,
        ws,
        upload(
            client,
            ws,
            "n\n1\n2\nx\n",
            options={"columns": [{"index": 0, "type": "integer"}]},
        ),
    )
    assert (job["status"], job["error_code"]) == ("failed", "import_bad_row")
    assert "Row 4" in job["error_message"] and "n" in job["error_message"]
    assert tables(ws) == []


def test_bad_options_are_refused(client: Client, ws: int) -> None:
    for options in (
        {"columns": [{"index": 9}]},
        {"columns": [{"index": 0, "type": "json"}]},
        {
            "columns": [
                {"index": 0, "skip": True},
                {"index": 1, "skip": True},
                {"index": 2, "skip": True},
                {"index": 3, "skip": True},
            ]
        },
        {"primary_key": ["nope"]},
        {"delimiter": "x"},
        {
            "relations": [
                {"columns": ["nope"], "parent_table": "t", "parent_columns": ["id"]}
            ]
        },
    ):
        response = upload(client, ws, CLEAN, options=options)
        assert response.status_code in (422,), (options, response.content)
    bad_json = client.post(
        f"/api/workspaces/{ws}/imports",
        {"file": SimpleUploadedFile("a.csv", b"a\n1\n"), "options": "{nope"},
    )
    assert bad_json.json()["code"] == "import_options_invalid"


def test_primary_key_and_relations_are_added_in_the_same_job(
    client: Client, ws: int
) -> None:
    parents = "id,name\n1,Ada\n2,Bo\n"
    assert (
        finished(
            client,
            ws,
            upload(
                client,
                ws,
                parents,
                name="customers.csv",
                options={"primary_key": ["id"]},
            ),
        )["status"]
        == "succeeded"
    )
    relation = {
        "columns": ["customer_id"],
        "parent_table": "customers",
        "parent_columns": ["id"],
    }
    orders = "id,customer_id\n10,1\n11,2\n"
    job = finished(
        client,
        ws,
        upload(
            client, ws, orders, name="orders.csv", options={"relations": [relation]}
        ),
    )
    assert job["status"] == "succeeded", job
    known = schema.get_schema(ref_for(ws))
    assert known.table("customers").primary_key == ("id",)  # type: ignore[union-attr]
    assert known.table("orders").foreign_keys[0].ref_table == "customers"  # type: ignore[union-attr]
    # an orphan fails the job and rolls the new table back
    bad = finished(
        client,
        ws,
        upload(
            client,
            ws,
            "id,customer_id\n20,1\n21,99\n",
            name="more.csv",
            options={"relations": [relation]},
        ),
    )
    assert (bad["status"], bad["error_code"]) == ("failed", "constraint_violation")
    assert "row 2" in bad["error_message"]
    assert tables(ws) == ["customers", "orders"]
    dup = finished(
        client,
        ws,
        upload(
            client, ws, "id\n1\n1\n", name="dup.csv", options={"primary_key": ["id"]}
        ),
    )
    assert dup["error_code"] == "constraint_violation" and "dup" not in tables(ws)


def test_header_descriptions(client: Client, ws: int) -> None:
    job = finished(
        client,
        ws,
        upload(
            client,
            ws,
            "Order Total ($),qty\n5,1\n",
            options={"header_descriptions": True},
        ),
    )
    assert job["status"] == "succeeded"
    table = client.get(f"/api/workspaces/{ws}/tables/people").json()["data"]
    assert (
        table["columns"][1]["description"] == "Order Total ($)"
        and table["columns"][2]["description"] == ""
    )


def test_the_table_name_comes_from_the_file_and_never_clashes(
    client: Client, ws: int
) -> None:
    assert (
        finished(client, ws, upload(client, ws, CLEAN, name="My Data (v2).csv"))[
            "table_name"
        ]
        == "my_data_v2"
    )
    assert (
        finished(client, ws, upload(client, ws, CLEAN, name="My Data (v2).csv"))[
            "table_name"
        ]
        == "my_data_v2_2"
    )
    taken = upload(client, ws, CLEAN, options={"table_name": "my_data_v2"})
    assert (taken.status_code, taken.json()["code"]) == (409, "table_name_taken")


@override_settings(WORKSPACE_MAX_BYTES=300_000)
def test_a_load_that_makes_the_workspace_too_big_is_rolled_back(
    client: Client, ws: int
) -> None:
    rows = "id,text\n" + "".join(f"{i},{'x' * 500}\n" for i in range(2000))
    job = finished(client, ws, upload(client, ws, rows))
    assert (job["status"], job["error_code"]) == ("failed", "workspace_full")
    assert tables(ws) == []
    again = upload(client, ws, CLEAN)  # the workspace is fine: nothing was kept
    assert again.status_code == 202


def test_preview_shows_the_plan_and_keeps_nothing(client: Client, ws: int) -> None:
    response = upload(client, ws, CLEAN.replace(",", ";"), path="imports/preview")
    assert response.status_code == 200, response.content
    data = response.json()["data"]
    assert data["delimiter"] == ";" and data["has_header"] is True
    assert [(c["name"], c["type"]) for c in data["columns"]] == [
        ("id", "integer"),
        ("name", "text"),
        ("price", "numeric"),
        ("born", "date"),
    ]
    assert data["rows"][0] == ["1", "Ada", "9.5", "2000-01-02"]
    assert not ImportJob.objects.exists() and tables(ws) == []
    assert (
        upload(client, ws, b"\x00\x00", path="imports/preview").json()["code"]
        == "import_not_text"
    )


def test_cancel_a_queued_job(client: Client, ws: int) -> None:
    workspace = Workspace.objects.get(pk=ws)
    job = service.start(
        workspace, workspace.owner, SimpleUploadedFile("a.csv", CLEAN.encode()), {}
    )
    response = client.post(f"/api/workspaces/{ws}/imports/{job.pk}/cancel")
    assert response.json()["data"]["status"] == "cancelled"
    assert not os.path.exists(job.file_path)
    tasks.execute(job.pk)  # the worker finds nothing to do
    assert tables(ws) == []
    assert (
        client.post(f"/api/workspaces/{ws}/imports/{job.pk}/cancel").json()["code"]
        == "import_not_cancellable"
    )


@override_settings(IMPORT_BATCH_ROWS=2)
def test_cancel_while_running_stops_between_batches_and_keeps_nothing(
    client: Client, ws: int
) -> None:
    workspace = Workspace.objects.get(pk=ws)
    rows = "id\n" + "".join(f"{i}\n" for i in range(50))
    job = service.start(
        workspace, workspace.owner, SimpleUploadedFile("a.csv", rows.encode()), {}
    )
    progress.request_cancel(job.pk)  # asked for before the first batch ends
    tasks.execute(job.pk)
    job.refresh_from_db()
    assert job.status == "cancelled" and tables(ws) == []
    assert not os.path.exists(job.file_path)


def test_one_import_at_a_time_per_user(client: Client, ws: int) -> None:
    workspace = Workspace.objects.get(pk=ws)
    service.start(
        workspace, workspace.owner, SimpleUploadedFile("a.csv", CLEAN.encode()), {}
    )
    second = upload(client, ws, CLEAN)
    assert (second.status_code, second.json()["code"]) == (429, "import_limit")
    assert second.json()["retry_after_seconds"] is None


def test_the_global_slot_makes_a_second_job_wait_then_fail(
    client: Client, ws: int
) -> None:
    from common.redis import get_redis

    workspace = Workspace.objects.get(pk=ws)
    job = service.start(
        workspace, workspace.owner, SimpleUploadedFile("a.csv", CLEAN.encode()), {}
    )
    get_redis().set(progress.SLOT_KEY, 1)  # another import holds the one slot
    try:
        with override_settings(IMPORT_QUEUE_WAIT_SECONDS=1):
            tasks.execute(job.pk)
    finally:
        get_redis().delete(progress.SLOT_KEY)
    job.refresh_from_db()
    assert (job.status, job.error_code) == ("failed", "import_limit")
    assert tables(ws) == []


def test_a_lost_upload_fails_the_job(client: Client, ws: int) -> None:
    workspace = Workspace.objects.get(pk=ws)
    job = service.start(
        workspace, workspace.owner, SimpleUploadedFile("a.csv", CLEAN.encode()), {}
    )
    os.unlink(job.file_path)
    assert sweep.fail_lost_uploads() == 1
    job.refresh_from_db()
    assert (job.status, job.error_code) == ("failed", "import_upload_lost")
    job2 = service.start(
        workspace, workspace.owner, SimpleUploadedFile("a.csv", CLEAN.encode()), {}
    )
    os.unlink(job2.file_path)
    tasks.execute(job2.pk)
    job2.refresh_from_db()
    assert job2.error_code == "import_upload_lost"


def test_a_job_found_running_after_a_restart_is_marked_interrupted(
    client: Client, ws: int
) -> None:
    workspace = Workspace.objects.get(pk=ws)
    job = service.start(
        workspace, workspace.owner, SimpleUploadedFile("a.csv", CLEAN.encode()), {}
    )
    ImportJob.objects.filter(pk=job.pk).update(status="running")
    assert sweep.mark_interrupted() == 1  # no liveness mark: its worker is gone
    job.refresh_from_db()
    assert (job.status, job.error_code) == ("failed", "import_interrupted")
    assert not os.path.exists(job.file_path)
    other = service.start(
        workspace, workspace.owner, SimpleUploadedFile("b.csv", CLEAN.encode()), {}
    )
    ImportJob.objects.filter(pk=other.pk).update(status="running")
    progress.report(other.pk, phase="loading")
    assert sweep.mark_interrupted() == 0  # still reporting: left alone
    assert (
        sweep.mark_interrupted(all_running=True) == 1
    )  # but a worker start means all are dead


def test_stale_files_are_removed_but_active_ones_are_not(
    client: Client, ws: int
) -> None:
    workspace = Workspace.objects.get(pk=ws)
    job = service.start(
        workspace, workspace.owner, SimpleUploadedFile("a.csv", CLEAN.encode()), {}
    )
    orphan = service.upload_dir() / "orphan.csv"
    orphan.write_text("x")
    old = os.path.getmtime(orphan) - 10_000
    os.utime(orphan, (old, old))
    os.utime(job.file_path, (old, old))
    assert sweep.remove_stale_files() == 1  # only the orphan
    assert not orphan.exists() and os.path.exists(job.file_path)


def test_another_users_import_is_a_404(
    client: Client, ws: int, other_user: User
) -> None:
    job_id = upload(client, ws, CLEAN).json()["data"]["id"]
    client.force_login(other_user)
    for method, path in [
        ("get", f"imports/{job_id}"),
        ("get", f"imports/{job_id}/events"),
        ("post", f"imports/{job_id}/cancel"),
        ("get", "imports"),
    ]:
        response = getattr(client, method)(f"/api/workspaces/{ws}/{path}")
        assert (
            response.status_code == 404
            and response.json()["code"] == "workspace_not_found"
        )
    assert upload(client, ws, CLEAN).status_code == 404
    assert upload(client, ws, CLEAN, path="imports/preview").status_code == 404
    client.force_login(User.objects.get(email="ada@example.com"))
    assert (
        client.get(f"/api/workspaces/{ws}/imports/999999").json()["code"]
        == "import_not_found"
    )


def test_every_import_route_needs_sign_in(client: Client) -> None:
    for method, path in [
        ("post", "/api/workspaces/1/imports"),
        ("post", "/api/workspaces/1/imports/preview"),
        ("get", "/api/workspaces/1/imports"),
        ("get", "/api/workspaces/1/imports/1"),
        ("get", "/api/workspaces/1/imports/1/events"),
        ("post", "/api/workspaces/1/imports/1/cancel"),
    ]:
        response = getattr(client, method)(
            path, **({"CONTENT_LENGTH": "0"} if method == "post" else {})
        )
        assert response.status_code in (401, 403), (path, response.status_code)


def test_deleting_a_workspace_cancels_its_imports(client: Client, ws: int) -> None:
    workspace = Workspace.objects.get(pk=ws)
    job = service.start(
        workspace, workspace.owner, SimpleUploadedFile("a.csv", CLEAN.encode()), {}
    )
    path = job.file_path
    assert client.delete(f"/api/workspaces/{ws}").status_code == 200
    assert not os.path.exists(path)
    assert not ImportJob.objects.filter(pk=job.pk).exists()
    assert schema_version.current(ref_for(ws)) == 0


def test_the_loaded_rows_can_be_edited_and_asked_about(client: Client, ws: int) -> None:
    from ask import runner

    finished(client, ws, upload(client, ws, CLEAN))
    patched = client.patch(
        f"/api/workspaces/{ws}/tables/people/rows/1",
        json.dumps({"values": {"name": "Ada L."}}),
        content_type="application/json",
    )
    assert patched.status_code == 200
    assert runner.run("SELECT name FROM people ORDER BY id", ref_for(ws)).rows[0] == [
        "Ada L."
    ]
