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
def data_connections(django_db_blocker: Any) -> Iterator[None]:
    """Lets code under test use the Django `data` / `data_reader` connections."""
    with django_db_blocker.unblock():
        yield
        connections[settings.DATA_DB_ALIAS].close()
        connections[settings.DATA_READER_DB_ALIAS].close()


@pytest.fixture(autouse=True)
def _clear_cache() -> Iterator[None]:
    """Rate-limit counters live in the cache; start every test from zero."""
    cache.clear()
    yield
    cache.clear()
