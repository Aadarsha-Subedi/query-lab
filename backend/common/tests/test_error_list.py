"""API_ERRORS.md and the code must agree on which error codes exist."""

import re
from pathlib import Path

from django.conf import settings

import agent.errors
import agent.service  # noqa: F401
import ask.errors
import ask.schema_api  # noqa: F401
import common.permissions  # noqa: F401
import workspaces.errors  # noqa: F401
from common.exception import domain, handler

BACKEND = Path(settings.BASE_DIR)
ROW = re.compile(r"^\| `([a-z_]+)` \|")
CODE_ASSIGNMENT = re.compile(
    r'(?:\bcode|\berror_code|\b[A-Z_]*CODE[A-Z_]*)\s*=\s*"([a-z][a-z_]*)"'
)
SOURCE_DIRS = [
    "config",
    "core",
    "common",
    "accounts",
    "ask",
    "agent",
    "workspaces",
    "evals",
]


def documented() -> tuple[set[str], set[str]]:
    """The codes in the API table and in the run table."""
    api: set[str] = set()
    runs: set[str] = set()
    target = api
    for line in (BACKEND / "API_ERRORS.md").read_text().splitlines():
        if line.startswith("## Run error codes"):
            target = runs
        match = ROW.match(line)
        if match:
            target.add(match.group(1))
    return api, runs


def exception_classes() -> set[type[domain.AppException]]:
    found: set[type[domain.AppException]] = set()
    pending = [domain.AppException]
    while pending:
        for sub in pending.pop().__subclasses__():
            found.add(sub)
            pending.append(sub)
    return found


def codes_in_source() -> set[str]:
    codes = set(handler._CODES.values())
    for folder in SOURCE_DIRS:
        for path in (BACKEND / folder).rglob("*.py"):
            if "tests" in path.parts or "migrations" in path.parts:
                continue
            codes.update(CODE_ASSIGNMENT.findall(path.read_text()))
    return codes


def test_every_exception_class_is_in_the_list() -> None:
    api, _ = documented()
    own = {
        cls.error_code for cls in exception_classes() if "tests" not in cls.__module__
    }
    assert own - api == set(), f"add to API_ERRORS.md: {sorted(own - api)}"


def test_the_list_names_only_codes_that_exist() -> None:
    api, runs = documented()
    stale = (api | runs) - codes_in_source()
    assert stale == set(), f"in API_ERRORS.md but not in the code: {sorted(stale)}"


def test_the_failed_run_codes_are_documented() -> None:
    from agent import errors

    _, runs = documented()
    run_codes = {
        value
        for name, value in vars(errors).items()
        if name.startswith("CODE_") and isinstance(value, str)
    }
    assert run_codes - runs == set(), (
        f"add to the run table: {sorted(run_codes - runs)}"
    )
