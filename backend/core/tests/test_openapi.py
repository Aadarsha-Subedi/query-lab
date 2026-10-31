"""openapi.json is committed and is what the frontend's types come from: it must
match the code, name every model and declare every error."""

import json
from pathlib import Path
from typing import Any

import pytest
from django.conf import settings

from core.management.commands.export_openapi import render

COMMITTED = Path(settings.BASE_DIR) / "openapi.json"
SUCCESS_ONLY = {"200", "304"}


def operations() -> list[tuple[str, str, dict[str, Any]]]:
    paths = json.loads(COMMITTED.read_text())["paths"]
    return [
        (method.upper(), path, op)
        for path, methods in paths.items()
        for method, op in methods.items()
    ]


def test_committed_file_is_up_to_date() -> None:
    assert COMMITTED.read_text() == render(), "run `make openapi` and commit the result"


def test_operation_ids_are_unique() -> None:
    ids = [op["operationId"] for _, _, op in operations()]
    assert len(ids) == len(set(ids))


@pytest.mark.parametrize(("method", "path", "op"), operations())
def test_responses_use_named_models(method: str, path: str, op: dict[str, Any]) -> None:
    for status, response in op["responses"].items():
        schema = (
            response.get("content", {}).get("application/json", {}).get("schema", None)
        )
        if schema is not None:
            assert "$ref" in schema, f"{method} {path} {status} has an unnamed schema"
        if status not in SUCCESS_ONLY and status != "503" and schema is not None:
            assert schema["$ref"].endswith("/ErrorEnvelope"), (method, path, status)


@pytest.mark.parametrize(("method", "path", "op"), operations())
def test_signed_in_routes_declare_401_and_429(
    method: str, path: str, op: dict[str, Any]
) -> None:
    if path == "/api/health":
        pytest.skip("health is public and unwrapped")
    assert {"401", "429"} <= set(op["responses"]), f"{method} {path}"
