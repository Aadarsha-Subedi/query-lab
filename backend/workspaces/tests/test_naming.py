import pytest
from django.test import override_settings

from workspaces import naming
from workspaces.errors import InvalidName

HOSTILE = [
    '"; DROP TABLE x;--',
    "Robert'); DROP TABLE students;--",
    "pg_catalog",
    "pg_authid",
    "information_schema",
    "select",
    "TABLE",
    "",
    "   ",
    "💥",
    "名前",
    "1abc",
    "ws_7",
    "_row_id",
    "demo",
    "a" * 500,
    "Ünïcode Çolumn",
    "x\x00y",
]


@pytest.mark.parametrize("text", HOSTILE)
@pytest.mark.parametrize("kind", ["table", "column"])
def test_hostile_names_become_safe_identifiers(text: str, kind: str) -> None:
    name = naming.identifier_slug(text, kind=kind)
    assert name.isascii() and len(name) <= naming.PG_IDENTIFIER_MAX
    assert all(
        (ch.isalnum() and ch.islower()) or ch.isdigit() or ch == "_" for ch in name
    )
    assert not name[0].isdigit()
    assert name not in naming.RESERVED_WORDS
    assert not name.startswith(naming.CATALOG_PREFIXES)
    assert name != naming.ROW_ID


def test_readable_names_stay_readable() -> None:
    assert naming.identifier_slug("Order Total ($)", kind="column") == "order_total"
    assert naming.identifier_slug("Ünïcode", kind="column") == "unicode"
    assert naming.identifier_slug("2024 sales", kind="table") == "t_2024_sales"
    assert naming.identifier_slug("select", kind="column") == "select_column"
    assert naming.identifier_slug("", kind="table") == "unnamed_table"


def test_duplicates_get_a_numeric_suffix() -> None:
    assert naming.column_names(["Name", "name", "NAME", "", ""]) == [
        "name",
        "name_2",
        "name_3",
        "unnamed_column",
        "unnamed_column_2",
    ]
    assert naming.table_name("Sales", ["sales", "sales_2"]) == "sales_3"


def test_suffix_never_pushes_a_name_past_the_limit() -> None:
    long = "a" * naming.PG_IDENTIFIER_MAX
    second = naming.unique(long, [long])
    assert len(second) == naming.PG_IDENTIFIER_MAX and second.endswith("_2")


def test_the_hidden_key_name_is_never_given_to_a_column() -> None:
    assert naming.column_name("_row_id") != naming.ROW_ID
    assert naming.column_name("row_id", [naming.ROW_ID]) == "row_id"


@override_settings(WORKSPACE_NAME_MAX_LENGTH=10)
def test_workspace_names() -> None:
    assert naming.workspace_name("  My \t  data ") == "My data"
    with pytest.raises(InvalidName):
        naming.workspace_name("   ")
    with pytest.raises(InvalidName):
        naming.workspace_name("x" * 11)
    assert naming.workspace_name("a\x00b") == "ab"


def test_column_types() -> None:
    assert naming.column_type("timestamp") == "timestamp without time zone"
    for bad in ["varchar", "text; drop", "serial", "json", ""]:
        with pytest.raises(InvalidName):
            naming.column_type(bad)
