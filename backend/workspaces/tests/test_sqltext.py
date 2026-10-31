import pytest

from workspaces import sqltext


def texts(script: str) -> list[str]:
    return [s.text for s in sqltext.split(script)]


def test_splits_on_semicolons_and_drops_empties() -> None:
    assert texts("select 1; select 2;; ;\n select 3") == [
        "select 1",
        "select 2",
        "select 3",
    ]
    assert texts("") == [] and texts("  ;  ; ") == []


@pytest.mark.parametrize(
    "script",
    [
        "select 'a;b'",
        'select "a;b" from t',
        "select 'it''s; fine'",
        "select $$a;b$$",
        "select $tag$ a ; $$ b $tag$",
        "select 1 -- not; a split\n",
        "select /* a; b /* nested; */ c */ 1",
        "create function f() returns int language plpgsql as $f$ begin return 1; end $f$",
    ],
)
def test_semicolons_inside_quotes_comments_and_dollar_quotes_do_not_split(
    script: str,
) -> None:
    assert len(sqltext.split(script)) == 1


def test_kinds() -> None:
    kinds = {
        s.keyword: s
        for s in sqltext.split(
            "-- c\n CREATE TABLE a (i int); insert into a values (1); select 1; COMMIT; Begin;"
            " drop table a; comment on table a is 'x'; with x as (select 1) select * from x"
        )
    }
    assert kinds["create"].is_ddl and kinds["drop"].is_ddl and kinds["comment"].is_ddl
    assert (
        not kinds["insert"].is_ddl
        and not kinds["select"].is_ddl
        and not kinds["with"].is_ddl
    )
    assert (
        kinds["commit"].is_transaction_control and kinds["begin"].is_transaction_control
    )
    assert not kinds["select"].is_transaction_control


def test_an_unterminated_quote_is_one_statement() -> None:
    assert len(sqltext.split("select 'oops; select 2")) == 1
