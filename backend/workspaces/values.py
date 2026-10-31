"""Turning what a client sends into a value of the column's type. Values are only
ever bound as query parameters, never put into SQL text."""

import datetime
import math
from decimal import Decimal, InvalidOperation
from typing import Any

INT_RANGES = {
    "integer": (-(2**31), 2**31 - 1),
    "bigint": (-(2**63), 2**63 - 1),
}
TRUE = {"true", "t", "yes", "y", "1"}
FALSE = {"false", "f", "no", "n", "0"}


class BadValue(ValueError):
    """The message says what was expected, never what was sent."""


def coerce(value: Any, api_type: str) -> Any:
    """`None` stays NULL; an empty string is NULL for every type but text."""
    if value is None:
        return None
    if isinstance(value, str) and api_type != "text" and not value.strip():
        return None
    match api_type:
        case "text":
            return _text(value)
        case "integer" | "bigint":
            return _integer(value, api_type)
        case "numeric":
            return _numeric(value)
        case "boolean":
            return _boolean(value)
        case "date":
            return _date(value)
        case "timestamp":
            return _timestamp(value)
    raise BadValue("This column type cannot be edited.")


def _text(value: Any) -> str:
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, int | float | Decimal):
        return str(value)
    if not isinstance(value, str):
        raise BadValue("Expected text.")
    if "\x00" in value:
        raise BadValue("Text cannot contain the NUL character.")
    return value


def _integer(value: Any, api_type: str) -> int:
    low, high = INT_RANGES[api_type]
    if isinstance(value, bool):
        raise BadValue("Expected a whole number.")
    if isinstance(value, float):
        if not value.is_integer():
            raise BadValue("Expected a whole number.")
        number = int(value)
    elif isinstance(value, int):
        number = value
    elif isinstance(value, str):
        text = value.strip()
        try:
            if "_" in text:  # int() would accept 1_000
                raise ValueError(text)
            number = int(text)
        except ValueError:
            raise BadValue("Expected a whole number.") from None
    else:
        raise BadValue("Expected a whole number.")
    if not low <= number <= high:
        raise BadValue(f"Expected a whole number between {low} and {high}.")
    return number


def _numeric(value: Any) -> Decimal:
    if isinstance(value, bool) or not isinstance(value, int | float | str | Decimal):
        raise BadValue("Expected a number.")
    if isinstance(value, str) and "_" in value:  # Decimal() would accept 1_000
        raise BadValue("Expected a number.")
    try:
        number = Decimal(str(value).strip())
    except InvalidOperation:
        raise BadValue("Expected a number.") from None
    if not number.is_finite() or (
        isinstance(value, float) and not math.isfinite(value)
    ):
        raise BadValue("Expected a finite number.")
    return number


def _boolean(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, int) and value in (0, 1):
        return bool(value)
    if isinstance(value, str):
        text = value.strip().lower()
        if text in TRUE:
            return True
        if text in FALSE:
            return False
    raise BadValue("Expected true or false.")


def _date(value: Any) -> datetime.date:
    if not isinstance(value, str):
        raise BadValue("Expected a date like 2024-01-31.")
    try:
        return datetime.date.fromisoformat(value.strip())
    except ValueError:
        raise BadValue("Expected a date like 2024-01-31.") from None


def _timestamp(value: Any) -> datetime.datetime:
    if not isinstance(value, str):
        raise BadValue("Expected a timestamp like 2024-01-31T12:00:00.")
    try:
        parsed = datetime.datetime.fromisoformat(value.strip().replace("Z", "+00:00"))
    except ValueError:
        raise BadValue("Expected a timestamp like 2024-01-31T12:00:00.") from None
    if parsed.tzinfo is not None:  # stored without a zone, as UTC
        parsed = parsed.astimezone(datetime.UTC).replace(tzinfo=None)
    return parsed
