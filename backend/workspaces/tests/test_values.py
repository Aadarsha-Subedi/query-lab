import datetime
from decimal import Decimal
from typing import Any

import pytest

from workspaces import values


@pytest.mark.parametrize(
    ("api_type", "raw", "expected"),
    [
        ("integer", 5, 5),
        ("integer", "42", 42),
        ("integer", " 7 ", 7),
        ("integer", 3.0, 3),
        ("integer", "", None),
        ("integer", None, None),
        ("bigint", 2**40, 2**40),
        ("numeric", "1.50", Decimal("1.50")),
        ("numeric", 2, Decimal("2")),
        ("numeric", 0.5, Decimal("0.5")),
        ("numeric", "  ", None),
        ("boolean", True, True),
        ("boolean", "yes", True),
        ("boolean", "F", False),
        ("boolean", 0, False),
        ("boolean", "", None),
        ("date", "2024-01-31", datetime.date(2024, 1, 31)),
        ("date", "", None),
        ("timestamp", "2024-01-31T12:30:00", datetime.datetime(2024, 1, 31, 12, 30)),
        ("timestamp", "2024-01-31 12:30:00", datetime.datetime(2024, 1, 31, 12, 30)),
        ("timestamp", "2024-01-31T12:30:00Z", datetime.datetime(2024, 1, 31, 12, 30)),
        (
            "timestamp",
            "2024-01-31T14:30:00+02:00",
            datetime.datetime(2024, 1, 31, 12, 30),
        ),
        ("text", "", ""),
        ("text", "  keep  ", "  keep  "),
        ("text", 12, "12"),
        ("text", True, "true"),
        ("text", "'; DROP TABLE x;--", "'; DROP TABLE x;--"),
    ],
)
def test_good_values(api_type: str, raw: Any, expected: Any) -> None:
    assert values.coerce(raw, api_type) == expected


@pytest.mark.parametrize(
    ("api_type", "raw"),
    [
        ("integer", "abc"),
        ("integer", 1.5),
        ("integer", True),
        ("integer", "1_000"),
        ("integer", 2**31),
        ("integer", [1]),
        ("bigint", 2**63),
        ("numeric", "NaN"),
        ("numeric", "Infinity"),
        ("numeric", float("inf")),
        ("numeric", "1,5"),
        ("numeric", True),
        ("boolean", "maybe"),
        ("boolean", 2),
        ("date", "31/01/2024"),
        ("date", 20240131),
        ("timestamp", "yesterday"),
        ("text", ["a"]),
        ("text", {"a": 1}),
        ("text", "nul\x00byte"),
        ("json", "{}"),
    ],
)
def test_bad_values_say_what_was_expected_and_nothing_else(
    api_type: str, raw: Any
) -> None:
    with pytest.raises(values.BadValue) as caught:
        values.coerce(raw, api_type)
    if isinstance(raw, str):  # the message never echoes what was sent
        assert raw not in str(caught.value)
