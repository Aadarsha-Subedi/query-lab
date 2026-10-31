import pytest
from django.test import override_settings

from workspaces.errors import (
    ImportEmpty,
    ImportEncoding,
    ImportNotText,
    ImportTooManyColumns,
)
from workspaces.imports import sniff


def go(text: str | bytes, **kw: object) -> sniff.Sniffed:
    data = text.encode() if isinstance(text, str) else text
    return sniff.sniff(data, **kw)  # type: ignore[arg-type]


def test_a_plain_csv() -> None:
    s = go(
        "id,name,price,born,seen,ok\n1,Ada,9.5,2000-01-02,2024-01-02 03:04:05,true\n2,Bo,10,2001-02-03,2024-01-03T00:00:00,false\n"
    )
    assert s.delimiter == "," and s.has_header
    assert s.names == ["id", "name", "price", "born", "seen", "ok"]
    assert s.types == ["integer", "text", "numeric", "date", "timestamp", "boolean"]
    assert s.sample_rows[0][:2] == ["1", "Ada"]


@pytest.mark.parametrize("delimiter", [";", "\t", "|"])
def test_other_delimiters(delimiter: str) -> None:
    s = go(
        f"a{delimiter}b{delimiter}c\n1{delimiter}x{delimiter}2\n3{delimiter}y{delimiter}4\n"
    )
    assert s.delimiter == delimiter and s.names == ["a", "b", "c"]


def test_a_comma_inside_quotes_is_not_a_delimiter() -> None:
    s = go('name;note\n"Smith, J";"a, b, c"\n"Doe, A";"x, y"\n')
    assert s.delimiter == ";"


def test_bom_and_crlf() -> None:
    s = go(b"\xef\xbb\xbfid,name\r\n1,Ada\r\n2,Bo\r\n")
    assert s.names == ["id", "name"] and s.types == ["integer", "text"]


def test_no_header_when_the_first_row_is_all_numbers() -> None:
    s = go("1,2.5,2024-01-01\n3,4.5,2024-01-02\n")
    assert not s.has_header
    assert s.names == ["column_1", "column_2", "column_3"]
    assert s.types == ["integer", "numeric", "date"]
    forced = go("1,2.5\n3,4.5\n", has_header=True)
    assert forced.has_header and forced.names == ["c_1", "c_2_5"]


def test_hostile_and_duplicate_and_empty_headers() -> None:
    s = go('"; DROP TABLE x;--",name,Name,,select\n1,a,b,c,d\n')
    assert s.names[0] == "drop_table_x"
    assert s.names[1:3] == ["name", "name_2"]
    assert s.names[3] == "unnamed_column" and s.names[4] == "select_column"
    assert len(set(s.names)) == len(s.names)


def test_ragged_rows_pad_to_the_widest() -> None:
    s = go("a,b,c\n1,2\n3,4,5,6\n")
    assert s.column_count == 4 and s.names[3] == "unnamed_column"
    assert s.sample_rows[0] == ["1", "2", "", ""]


def test_types_widen_to_text_on_one_bad_value() -> None:
    assert go("v\n1\n2\nthree\n").types == ["text"]
    assert go("v\n1\n2.5\n").types == ["numeric"]
    assert go("v\n1\n3000000000\n").types == ["bigint"]
    assert go("v\n1\n\n3\n").types == ["integer"]  # empty cells are NULL, not a type
    assert go("v\n\n\n1\n").types == ["integer"]


def test_identifiers_that_look_numeric_stay_text() -> None:
    assert go("zip,phone\n01234,+15551234\n02345,+15559876\n").types == ["text", "text"]
    assert go("n\n0\n0.5\n10\n").types == ["numeric"]


def test_underscored_numbers_are_text() -> None:
    assert go("n\n1_000\n2_000\n").types == ["text"]


@pytest.mark.parametrize(
    ("data", "error"),
    [
        (b"", ImportEmpty),
        (b"  \n\r\n ", ImportEmpty),
        (b"\x00\x01\x02binary\x00", ImportNotText),
        (bytes(range(1, 32)) * 10, ImportNotText),
        (b"\xff\xfeI\x00D\x00", ImportEncoding),
        (b"id,name\n1,caf\xe9\n", ImportEncoding),
    ],
)
def test_refused_files(data: bytes, error: type[Exception]) -> None:
    with pytest.raises(error):
        sniff.sniff(data)


@override_settings(IMPORT_MAX_COLUMNS=3)
def test_too_many_columns() -> None:
    with pytest.raises(ImportTooManyColumns):
        go("a,b,c,d\n1,2,3,4\n")


def test_a_cut_off_character_at_the_end_of_the_sample_is_fine() -> None:
    data = "id,name\n1,Zoë\n".encode()
    assert go(data[:-1]).names == ["id", "name"]
