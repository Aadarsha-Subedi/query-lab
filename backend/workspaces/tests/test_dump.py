import pytest

from workspaces import dump

PREAMBLE = """\
--
-- PostgreSQL database dump
--
SET statement_timeout = 0;
SET client_encoding = 'UTF8';
SELECT pg_catalog.set_config('search_path', '', false);
"""


def items(text: str) -> list[dump.Item]:
    return list(dump.read(text.splitlines(keepends=True)))


def test_pg_dump_shape_is_read_and_public_is_removed() -> None:
    result = items(
        PREAMBLE
        + """\
CREATE TABLE public.customer (
    id integer NOT NULL,
    note text DEFAULT 'a;b'
);
ALTER TABLE public.customer OWNER TO postgres;
COPY public.customer (id, note) FROM stdin;
1\tone
2\ttwo; three
\\.
ALTER TABLE ONLY public.customer
    ADD CONSTRAINT customer_pkey PRIMARY KEY (id);
SELECT pg_catalog.setval('public.customer_id_seq', 2, true);
INSERT INTO public.customer VALUES (3, 'public.x');
"""
    )
    assert [i.kind for i in result] == ["run", "copy", "run", "run", "run"]
    assert "public." not in result[0].text
    assert result[0].number == 4 and result[0].line == 7
    assert "customer_pkey" in result[2].text
    assert "setval('customer_id_seq', 2, true)" in result[3].text
    assert "'public.x'" in result[4].text  # inside a string, untouched


def test_unread_copy_data_is_drained() -> None:
    result = items("COPY t FROM stdin;\n1\n2\n\\.\nINSERT INTO t VALUES (3);\n")
    assert [i.kind for i in result] == ["copy", "run"]


@pytest.mark.parametrize(
    "sql",
    [
        "CREATE ROLE evil LOGIN;",
        "ALTER ROLE evil SUPERUSER;",
        "CREATE EXTENSION dblink;",
        "COMMENT ON EXTENSION dblink IS 'x';",
        "CREATE PUBLICATION p FOR ALL TABLES;",
        "CREATE POLICY p ON t TO someone USING (true);",
        "ALTER TABLE t ENABLE ROW LEVEL SECURITY;",
        "ALTER TABLE ONLY t DROP CONSTRAINT k;",
        "ALTER TABLE t OWNER TO postgres;",
        "ALTER FUNCTION f() OWNER TO postgres;",
        "ALTER DEFAULT PRIVILEGES GRANT SELECT ON TABLES TO x;",
        "DROP TABLE t;",
        "BEGIN;",
        "COMMIT;",
        "ROLLBACK;",
        "SET search_path = ws_9;",
        "GRANT ALL ON t TO x;",
    ],
)
def test_what_belongs_to_the_source_server_is_set_aside(sql: str) -> None:
    result = items("CREATE TABLE ok (a int);\n" + sql + "\n")
    assert [i.text for i in result] == ["CREATE TABLE ok (a int)"]


@pytest.mark.parametrize(
    "sql",
    [
        "CREATE FUNCTION f() RETURNS int AS $$ select 1 $$ LANGUAGE sql;",
        "CREATE TRIGGER t BEFORE INSERT ON x FOR EACH ROW EXECUTE FUNCTION f();",
        "CREATE TYPE s AS ENUM ('a');",
        "CREATE DOMAIN d AS text;",
        "CREATE MATERIALIZED VIEW m AS SELECT 1;",
        "ALTER TABLE t ATTACH PARTITION p FOR VALUES IN (1);",
        "ALTER TYPE s ADD VALUE 'b';",
        "UPDATE t SET a = 1;",
        "DELETE FROM t;",
        "DO $$ BEGIN PERFORM 1; END $$;",
        "COPY t FROM PROGRAM 'id';",
        "COPY t FROM '/etc/passwd';",
        "VALUES (1);",
    ],
)
def test_everything_else_goes_to_postgres(sql: str) -> None:
    assert [i.kind for i in items(sql + "\n")] == ["run"]


def test_set_search_path_is_skipped_not_run() -> None:
    assert items("SET search_path = ws_9;\nGRANT ALL ON t TO x;\n") == []


def test_semicolons_in_strings_comments_and_dollar_quotes_do_not_split() -> None:
    result = items(
        "INSERT INTO t VALUES ('a;\nb');\n"
        "-- not; a split\nINSERT INTO t VALUES ($q$x;y$q$);\n"
    )
    assert [i.number for i in result] == [1, 2]


def test_quoted_public_prefix_is_removed() -> None:
    assert dump.strip_schemas('CREATE TABLE "public"."Odd" (a int);') == (
        'CREATE TABLE "Odd" (a int);'
    )
    assert (
        dump.strip_schemas("SELECT 1 FROM publicity.t") == "SELECT 1 FROM publicity.t"
    )


def test_truncated_dump_is_refused() -> None:
    with pytest.raises(dump.DumpRefused) as error:
        items("CREATE TABLE t (a int);\nINSERT INTO t VALUES (1")
    assert "middle" in error.value.message


def test_copy_data_lines_are_streamed_to_the_caller() -> None:
    stream = dump.read(
        iter(
            "COPY t (a) FROM stdin;\n1\n2; x\n\\.\nINSERT INTO t VALUES (3);\n".splitlines(
                keepends=True
            )
        )
    )
    first = next(stream)
    assert first.kind == "copy"
    assert list(first.data) == ["1\n", "2; x\n"]
    assert next(stream).kind == "run"


def test_pg_dump_restrict_lines_are_skipped() -> None:
    result = items("\\restrict aB3xYz\nCREATE TABLE t (a int);\n\\unrestrict aB3xYz\n")
    assert [(i.kind, i.number, i.line) for i in result] == [("run", 1, 2)]


def test_other_psql_commands_are_skipped() -> None:
    assert len(items("\\connect other\nCREATE TABLE t (a int);\n")) == 1


def test_a_routine_body_and_its_search_path_are_folded_too() -> None:
    result = items(
        "CREATE SCHEMA app;\n"
        "CREATE FUNCTION app.c() RETURNS bigint\n"
        "    LANGUAGE sql\n"
        "    SET search_path TO 'app'\n"
        "    AS $$ SELECT count(*) FROM app.orders $$;\n"
        "SELECT pg_catalog.setval('app.s', 2, true);\n"
    )
    assert "search_path" not in result[0].text
    assert "FUNCTION c()" in result[0].text and "FROM orders" in result[0].text
    assert "setval('s', 2, true)" in result[1].text


def test_public_prefix_inside_a_regclass_cast_is_removed() -> None:
    text = "ALTER TABLE ONLY public.t ALTER COLUMN id SET DEFAULT nextval('public.t_id_seq'::regclass);"
    assert dump.strip_schemas(text) == (
        "ALTER TABLE ONLY t ALTER COLUMN id SET DEFAULT nextval('t_id_seq'::regclass);"
    )
    assert dump.strip_schemas("INSERT INTO t VALUES ('public.x');") == (
        "INSERT INTO t VALUES ('public.x');"
    )


def test_a_schema_the_dump_creates_is_folded_into_the_workspace() -> None:
    result = items(
        "CREATE SCHEMA shop;\n"
        "ALTER SCHEMA shop OWNER TO postgres;\n"
        "COMMENT ON SCHEMA shop IS 'x';\n"
        "CREATE TABLE shop.orders (id integer NOT NULL);\n"
        "ALTER TABLE ONLY shop.orders ALTER COLUMN id SET DEFAULT nextval('shop.orders_id_seq'::regclass);\n"
        "INSERT INTO shop.orders VALUES (1);\n"
        "INSERT INTO shop.orders VALUES ('shop.keep');\n"
        'CREATE VIEW "shop".v AS SELECT * FROM "shop"."orders";\n'
    )
    assert [i.number for i in result] == [4, 5, 6, 7, 8]
    assert result[0].text == "CREATE TABLE orders (id integer NOT NULL)"
    assert "nextval('orders_id_seq'::regclass)" in result[1].text
    assert result[3].text == "INSERT INTO orders VALUES ('shop.keep')"
    assert result[4].text == 'CREATE VIEW v AS SELECT * FROM "orders"'


def test_a_schema_that_was_not_created_by_the_dump_is_left_for_postgres_to_refuse() -> (
    None
):
    result = items("CREATE TABLE other.t (a int);\n")
    assert result[0].text == "CREATE TABLE other.t (a int)"
