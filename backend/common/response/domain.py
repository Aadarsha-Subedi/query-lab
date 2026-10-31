"""The response envelope every endpoint returns, as ninja schemas.

Success: {success: true,  status_code, message, data, meta}
Error:   {success: false, status_code, message, code, errors: [{field, message}]}
"""

from typing import Any, Literal

from ninja import Schema


class ErrorDetail(Schema):
    field: str | None = None
    message: str


class ErrorEnvelope(Schema):
    success: Literal[False] = False
    status_code: int
    message: str
    code: str
    errors: list[ErrorDetail] = []
    # 429 only: seconds until a retry can work (also the Retry-After header).
    # Null when waiting does not help, for example too many unfinished runs.
    retry_after_seconds: int | None = None


class SuccessEnvelope[DataT](Schema):
    success: Literal[True] = True
    status_code: int
    message: str
    data: DataT
    meta: dict[str, Any] = {}


def success(
    data: Any,
    message: str = "",
    status_code: int = 200,
    meta: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Body for a SuccessEnvelope response. Return it directly, or as
    `Status(201, success(...))` for another status."""
    return {
        "success": True,
        "status_code": status_code,
        "message": message,
        "data": data,
        "meta": meta or {},
    }


def error_body(
    message: str,
    code: str,
    status_code: int,
    errors: list[dict[str, Any]] | None = None,
    retry_after_seconds: int | None = None,
) -> dict[str, Any]:
    body: dict[str, Any] = {
        "success": False,
        "status_code": status_code,
        "message": message,
        "code": code,
        "errors": errors or [],
    }
    if status_code == 429:
        body["retry_after_seconds"] = retry_after_seconds
    return body
