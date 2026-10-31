"""Shared fixtures.

The data database (querylab) is not a Django test database: it is the real,
bootstrapped database (run `bootstrap_data_db` first, as `make test` and CI
do). Tests reach it through the fixtures below and never through
`@pytest.mark.django_db(databases=[...])`. Tests that change it work in a
throwaway schema and drop it afterwards.
"""

from collections.abc import Iterator
from typing import Any

import psycopg
import pytest
from django.conf import settings
from django.core.cache import cache
from django.db import connections


def conninfo(alias: str, **overrides: Any) -> str:
    db = {**settings.DATABASES[alias], **overrides}
    return psycopg.conninfo.make_conninfo(
        host=db["HOST"],
        port=db["PORT"],
        dbname=db["NAME"],
        user=db["USER"],
        password=db["PASSWORD"],
    )


@pytest.fixture
def reader() -> Iterator[psycopg.Connection]:
    """A fresh autocommit connection as the reader role."""
    with psycopg.connect(
        conninfo(settings.DATA_READER_DB_ALIAS), autocommit=True
    ) as connection:
        yield connection


@pytest.fixture
def owner() -> Iterator[psycopg.Connection]:
    """A fresh autocommit connection to querylab as the owner role."""
    with psycopg.connect(
        conninfo(settings.DATA_DB_ALIAS), autocommit=True
    ) as connection:
        yield connection


@pytest.fixture
def data_connections(
    request: pytest.FixtureRequest, django_db_blocker: Any
) -> Iterator[None]:
    """Lets code under test use the Django `data` / `data_reader` connections,
    also in a test that uses the app database (`db`), whose guard would
    otherwise forbid them."""
    if "db" in request.fixturenames:
        request.getfixturevalue("db")  # its guards go in first, ours come off after
    guards: list[tuple[Any, str, Any]] = []
    with django_db_blocker.unblock():
        for alias in (settings.DATA_DB_ALIAS, settings.DATA_READER_DB_ALIAS):
            connection = connections[alias]
            for (
                name,
                _,
            ) in connection.features.disallowed_simple_test_case_connection_methods:
                method = getattr(connection, name)
                if hasattr(method, "wrapped"):
                    guards.append((connection, name, method))
                    setattr(connection, name, method.wrapped)
        yield
        # Put the guards back: Django removes them itself when the test ends.
        for connection, name, method in guards:
            setattr(connection, name, method)
        connections[settings.DATA_DB_ALIAS].close()
        connections[settings.DATA_READER_DB_ALIAS].close()


# Workspace schemas live in the real `querylab` database, whose names (`ws_<id>`)
# come from the id of a Workspace row. The test app database starts its ids at 1,
# which would collide with a developer's own workspaces, so tests start theirs
# here and only ever touch ids from this number up.
TEST_WORKSPACE_ID_START = 900_000


@pytest.fixture(scope="session", autouse=True)
def _high_workspace_ids(django_db_setup: None, django_db_blocker: Any) -> None:
    with django_db_blocker.unblock(), connections["default"].cursor() as cursor:
        cursor.execute(
            "SELECT setval(pg_get_serial_sequence('workspaces_workspace', 'id'), %s, false)",
            [TEST_WORKSPACE_ID_START],
        )


@pytest.fixture(autouse=True)
def _clear_cache() -> Iterator[None]:
    """Rate-limit counters live in the cache; start every test from zero."""
    cache.clear()
    yield
    cache.clear()
