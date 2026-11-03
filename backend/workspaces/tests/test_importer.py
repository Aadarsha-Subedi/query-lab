from collections.abc import Callable, Iterator

import psycopg
import pytest
from django.test import override_settings

from accounts.models import User
from workspaces import connections, importer, service, storage
from workspaces.models import ImportJob, Workspace, WorkspaceDDLLog

pytestmark = [pytest.mark.django_db, pytest.mark.usefixtures("data_connections")]

DUMP = """\
SET statement_timeout = 0;
SELECT pg_catalog.set_config('search_path', '', false);
CREATE TABLE public.customer (
    id integer NOT NULL,
    name text
);
CREATE TABLE public.orders (
    id integer NOT NULL,
    customer_id integer
);
COPY public.customer (id, name) FROM stdin;
1\tAda
2\tGrace; Hopper
\\.
INSERT INTO public.orders VALUES (10, 1), (11, 2);
ALTER TABLE ONLY public.customer ADD CONSTRAINT customer_pkey PRIMARY KEY (id);
ALTER TABLE ONLY public.orders
    ADD CONSTRAINT orders_fk FOREIGN KEY (customer_id) REFERENCES public.customer(id);
"""


@pytest.fixture
def workspace(user: User) -> Iterator[Workspace]:
    workspace = service.create(user, "Dumps")
    yield workspace
    service.delete(workspace, user)


@pytest.fixture
def run_dump(
    monkeypatch: pytest.MonkeyPatch, user: User, workspace: Workspace
) -> Callable[..., ImportJob]:
    deleted: list[str] = []
    monkeypatch.setattr(storage, "delete", deleted.append)

    def run(text: str, *, replace: bool = False) -> ImportJob:
        monkeypatch.setattr(
            storage,
            "read_lines",
            lambda key, max_text_bytes: iter(text.splitlines(keepends=True)),
        )
        job = ImportJob.objects.create(
            workspace=workspace,
            owner=user,
            object_key=f"dumps/{user.pk}/{workspace.pk}/x.sql",
            size_bytes=len(text),
            replace=replace,
            status=ImportJob.QUEUED,
        )
        importer.run(job.pk)
        job.refresh_from_db()
        assert deleted[-1] == job.object_key  # the object is always removed
        return job

    return run


def tables(workspace: Workspace) -> list[str]:
    with connections.workspace_connection(
        workspace.pk, "ro", workspace.credential_version
    ) as connection:
        return [
            r[0]
            for r in connection.execute(
                "SELECT table_name FROM information_schema.tables "
                "WHERE table_schema = %s ORDER BY 1",
                [workspace.schema_name],
            )
        ]


def rows(workspace: Workspace, query: str) -> list[tuple]:
    with connections.workspace_connection(
        workspace.pk, "ro", workspace.credential_version
    ) as connection:
        return connection.execute(query).fetchall()


def test_a_pg_dump_lands_in_the_workspace_schema(
    run_dump: Callable[..., ImportJob], workspace: Workspace
) -> None:
    job = run_dump(DUMP)
    assert job.status == ImportJob.SUCCEEDED, job.error_message
    assert (job.statements_run, job.tables_created) == (6, 2)
    assert tables(workspace) == ["customer", "orders"]
    assert rows(workspace, "SELECT name FROM customer ORDER BY id") == [
        ("Ada",),
        ("Grace; Hopper",),
    ]
    assert WorkspaceDDLLog.objects.filter(
        workspace_id=workspace.pk, statement__startswith="import:"
    ).exists()


def test_a_refused_statement_changes_nothing_and_says_where(
    run_dump: Callable[..., ImportJob], workspace: Workspace
) -> None:
    job = run_dump("CREATE TABLE a (x int);\n\nCREATE ROLE evil LOGIN;\n")
    assert job.status == ImportJob.FAILED
    assert job.error_code == "dump_refused"
    assert (job.error_statement, job.error_line) == (2, 3)
    assert tables(workspace) == []


def test_a_postgres_error_rolls_everything_back(
    run_dump: Callable[..., ImportJob], workspace: Workspace
) -> None:
    job = run_dump(
        "CREATE TABLE a (x int);\nINSERT INTO a VALUES (1);\nINSERT INTO nope VALUES (1);\n"
    )
    assert job.error_code == "dump_failed"
    assert job.error_message.startswith("42P01")
    assert (job.error_statement, job.error_line) == (3, 3)
    assert tables(workspace) == []


def test_bad_copy_data_rolls_back(
    run_dump: Callable[..., ImportJob], workspace: Workspace
) -> None:
    job = run_dump(
        "CREATE TABLE a (x int);\nCOPY a (x) FROM stdin;\nnot a number\n\\.\n"
    )
    assert job.error_code == "dump_failed" and job.error_statement == 2
    assert tables(workspace) == []


def test_other_schemas_are_out_of_reach(
    run_dump: Callable[..., ImportJob], workspace: Workspace
) -> None:
    job = run_dump("CREATE TABLE demo.stolen (x int);\n")
    assert job.error_code == "dump_failed"
    assert job.error_message.startswith("42501")  # permission denied


def test_import_needs_an_empty_workspace_unless_replacing(
    run_dump: Callable[..., ImportJob], workspace: Workspace
) -> None:
    assert run_dump("CREATE TABLE old (x int);\n").status == ImportJob.SUCCEEDED
    second = run_dump("CREATE TABLE new (x int);\n")
    assert second.error_code == "workspace_not_empty"
    assert tables(workspace) == ["old"]
    third = run_dump("CREATE TABLE new (x int);\n", replace=True)
    assert third.status == ImportJob.SUCCEEDED
    assert tables(workspace) == ["new"]


def test_a_failed_replace_keeps_the_old_data(
    run_dump: Callable[..., ImportJob], workspace: Workspace
) -> None:
    run_dump("CREATE TABLE old (x int);\nINSERT INTO old VALUES (1);\n")
    failed = run_dump("CREATE TABLE new (x int);\nDROP TABLE x;\n", replace=True)
    assert failed.status == ImportJob.FAILED
    assert tables(workspace) == ["old"]
    assert rows(workspace, "SELECT x FROM old") == [(1,)]


@override_settings(WORKSPACE_MAX_TABLES=1)
def test_table_cap(run_dump: Callable[..., ImportJob], workspace: Workspace) -> None:
    job = run_dump("CREATE TABLE a (x int);\nCREATE TABLE b (x int);\n")
    assert job.error_code == "dump_too_many_tables"
    assert tables(workspace) == []


@override_settings(WORKSPACE_MAX_COLUMNS=2)
def test_column_cap(run_dump: Callable[..., ImportJob], workspace: Workspace) -> None:
    job = run_dump("CREATE TABLE a (x int, y int, z int);\n")
    assert job.error_code == "dump_too_many_columns"


@override_settings(WORKSPACE_MAX_BYTES=30_000)
def test_size_cap_rolls_back(
    run_dump: Callable[..., ImportJob], workspace: Workspace
) -> None:
    big = "CREATE TABLE a (x text);\nINSERT INTO a SELECT repeat('x', 1000) FROM generate_series(1, 200);\n"
    job = run_dump(big)
    assert job.error_code == "workspace_full"
    assert tables(workspace) == []


@override_settings(DUMP_MAX_STATEMENTS=2)
def test_statement_cap(
    run_dump: Callable[..., ImportJob], workspace: Workspace
) -> None:
    job = run_dump(
        "CREATE TABLE a (x int);\nINSERT INTO a VALUES (1);\nINSERT INTO a VALUES (2);\n"
    )
    assert job.error_code == "dump_too_many_statements" and job.error_statement == 3


def test_the_workspace_cannot_be_written_by_its_reader_afterwards(
    run_dump: Callable[..., ImportJob], workspace: Workspace
) -> None:
    run_dump(DUMP)
    with (
        pytest.raises(psycopg.errors.ReadOnlySqlTransaction),
        connections.workspace_connection(
            workspace.pk, "ro", workspace.credential_version
        ) as connection,
    ):
        connection.execute("DELETE FROM customer")


MODERN_DUMP = """\
--
-- PostgreSQL database dump
--

\\restrict Zk3jQ9mXaPq

SET statement_timeout = 0;
SET default_tablespace = '';
SET default_table_access_method = heap;

CREATE TABLE public.users (
    id integer NOT NULL,
    email character varying(255) NOT NULL
);

ALTER TABLE public.users OWNER TO postgres;

CREATE SEQUENCE public.users_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;

ALTER SEQUENCE public.users_id_seq OWNED BY public.users.id;

ALTER TABLE ONLY public.users ALTER COLUMN id SET DEFAULT nextval('public.users_id_seq'::regclass);

COPY public.users (id, email) FROM stdin;
1\ta@example.com
\\.

SELECT pg_catalog.setval('public.users_id_seq', 1, true);

ALTER TABLE ONLY public.users
    ADD CONSTRAINT users_pkey PRIMARY KEY (id);

\\unrestrict Zk3jQ9mXaPq
"""


def test_a_modern_pg_dump_with_restrict_and_sequences_imports(
    run_dump: Callable[..., ImportJob], workspace: Workspace
) -> None:
    job = run_dump(MODERN_DUMP)
    assert job.status == ImportJob.SUCCEEDED, (job.error_message, job.error_line)
    assert rows(workspace, "SELECT email FROM users") == [("a@example.com",)]


def test_a_dump_of_a_non_public_schema_lands_in_the_workspace(
    run_dump: Callable[..., ImportJob], workspace: Workspace
) -> None:
    job = run_dump(
        "CREATE SCHEMA shop;\n"
        "CREATE TABLE shop.orders (id integer NOT NULL, note text);\n"
        "COPY shop.orders (id, note) FROM stdin;\n1\tfirst\n\\.\n"
        "ALTER TABLE ONLY shop.orders ADD CONSTRAINT orders_pkey PRIMARY KEY (id);\n"
        "CREATE VIEW shop.recent AS SELECT * FROM shop.orders;\n"
    )
    assert job.status == ImportJob.SUCCEEDED, (job.error_message, job.error_line)
    assert tables(workspace) == ["orders", "recent"]
    assert rows(workspace, "SELECT note FROM recent") == [("first",)]
