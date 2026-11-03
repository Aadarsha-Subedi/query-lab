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
    assert [i.kind for i in result] == ["run", "copy", "run", "run"]
    assert "public." not in result[0].text
    assert result[0].number == 4 and result[0].line == 7
    assert "customer_pkey" in result[2].text
    assert "'public.x'" in result[3].text  # inside a string, untouched


def test_unread_copy_data_is_drained() -> None:
    result = items("COPY t FROM stdin;\n1\n2\n\\.\nINSERT INTO t VALUES (3);\n")
    assert [i.kind for i in result] == ["copy", "run"]


@pytest.mark.parametrize(
    ("sql", "fragment"),
    [
        ("CREATE ROLE evil LOGIN;", "ROLE"),
        ("CREATE EXTENSION dblink;", "Extensions"),
        (
            "CREATE FUNCTION f() RETURNS int AS $$ select 1 $$ LANGUAGE sql;",
            "Functions",
        ),
        (
            "CREATE TRIGGER t BEFORE INSERT ON x FOR EACH ROW EXECUTE FUNCTION f();",
            "Triggers",
        ),
        ("CREATE SCHEMA other;", "Schemas"),
        ("CREATE TEMP TABLE t (a int);", "Temporary"),
        ("COPY t FROM PROGRAM 'id';", "COPY"),
        ("COPY t TO '/tmp/x';", "COPY"),
        ("COPY t FROM '/etc/passwd';", "COPY"),
        ("DO $$ BEGIN PERFORM 1; END $$;", "DO"),
        ("DROP TABLE t;", "DROP"),
        ("BEGIN;", "transaction"),
        ("ALTER TABLE t DISABLE TRIGGER ALL;", "ALTER"),
        ("ALTER SYSTEM SET x = 1;", "ALTER"),
        ("SELECT pg_read_file('/etc/passwd');", "SELECT"),
        ("VACUUM;", "VACUUM"),
        ("CREATE MATERIALIZED VIEW m AS SELECT 1;", "Materialized"),
    ],
)
def test_dangerous_statements_are_refused_with_position(
    sql: str, fragment: str
) -> None:
    with pytest.raises(dump.DumpRefused) as error:
        items("CREATE TABLE ok (a int);\n\n" + sql + "\n")
    assert fragment in error.value.message
    assert (error.value.number, error.value.line) == (2, 3)


def test_set_search_path_is_skipped_not_run() -> None:
    assert items("SET search_path = ws_9;\nGRANT ALL ON t TO x;\n") == []


def test_semicolons_in_strings_comments_and_dollar_quotes_do_not_split() -> None:
    result = items(
        "INSERT INTO t VALUES ('a;\nb');\n"
        "-- not; a split\nINSERT INTO t VALUES ($q$x;y$q$);\n"
    )
    assert [i.number for i in result] == [1, 2]


def test_quoted_public_prefix_is_removed() -> None:
    assert dump.strip_public('CREATE TABLE "public"."Odd" (a int);') == (
        'CREATE TABLE "Odd" (a int);'
    )
    assert dump.strip_public("SELECT 1 FROM publicity.t") == "SELECT 1 FROM publicity.t"


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


def test_other_psql_commands_are_refused() -> None:
    with pytest.raises(dump.DumpRefused) as error:
        items("CREATE TABLE t (a int);\n\\connect other\n")
    assert "psql command" in error.value.message
    assert (error.value.number, error.value.line) == (2, 2)


def test_public_prefix_inside_a_regclass_cast_is_removed() -> None:
    text = "ALTER TABLE ONLY public.t ALTER COLUMN id SET DEFAULT nextval('public.t_id_seq'::regclass);"
    assert dump.strip_public(text) == (
        "ALTER TABLE ONLY t ALTER COLUMN id SET DEFAULT nextval('t_id_seq'::regclass);"
    )
    assert dump.strip_public("INSERT INTO t VALUES ('public.x');") == (
        "INSERT INTO t VALUES ('public.x');"
    )
