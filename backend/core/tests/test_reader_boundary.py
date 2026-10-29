"""The reader role (what the agent uses) can SELECT from demo and nothing else.
Runs against the bootstrapped data database; see conftest.py."""

import os
import time

import environ
import psycopg
import pytest
from django.conf import settings
from psycopg import errors

from conftest import conninfo

DEMO_TABLE = "demo.customers"


def test_reader_can_select_from_demo(reader: psycopg.Connection) -> None:
    row = reader.execute(f"SELECT count(*) FROM {DEMO_TABLE}").fetchone()
    assert row is not None


@pytest.mark.parametrize(
    "statement",
    [
        f"INSERT INTO {DEMO_TABLE} VALUES ('x', 'x', 'x', 'x', 'x')",
        f"UPDATE {DEMO_TABLE} SET customer_city = 'x'",
        f"DELETE FROM {DEMO_TABLE}",
        "CREATE TABLE demo.sneaky (id int)",
        "CREATE TABLE public.sneaky (id int)",
        "CREATE TEMP TABLE sneaky (id int)",
        f"DROP TABLE {DEMO_TABLE}",
        f"TRUNCATE {DEMO_TABLE}",
        "CREATE SCHEMA sneaky",
    ],
)
def test_reader_cannot_write_or_create(
    reader: psycopg.Connection, statement: str
) -> None:
    with pytest.raises((errors.ReadOnlySqlTransaction, errors.InsufficientPrivilege)):
        reader.execute(statement)


@pytest.mark.parametrize(
    "statement",
    [
        f"INSERT INTO {DEMO_TABLE} VALUES ('x', 'x', 'x', 'x', 'x')",
        "CREATE TABLE demo.sneaky (id int)",
        "CREATE TEMP TABLE sneaky (id int)",
    ],
)
def test_privileges_hold_even_when_read_only_is_switched_off(
    reader: psycopg.Connection, statement: str
) -> None:
    """default_transaction_read_only is only a default; privileges are the wall."""
    reader.execute("SET default_transaction_read_only = off")
    with pytest.raises(errors.InsufficientPrivilege):
        reader.execute(statement)


def test_role_has_the_configured_statement_timeout(reader: psycopg.Connection) -> None:
    row = reader.execute(
        "SELECT setting::int FROM pg_settings WHERE name = 'statement_timeout'"
    ).fetchone()
    assert row is not None
    assert row[0] == settings.READER_STATEMENT_TIMEOUT_MS, (
        "Re-run bootstrap_data_db with the current settings."
    )


def test_long_query_is_cancelled(reader: psycopg.Connection) -> None:
    timeout_s = settings.READER_STATEMENT_TIMEOUT_MS / 1000
    started = time.monotonic()
    with pytest.raises(errors.QueryCanceled):
        reader.execute("SELECT pg_sleep(%s)", [timeout_s * 3])
    assert time.monotonic() - started < timeout_s * 2


def test_reader_cannot_connect_to_the_app_database() -> None:
    # The real app database, not the test copy Django renamed it to.
    app_db = environ.Env.db_url_config(os.environ["APP_DATABASE_URL"])["NAME"]
    with pytest.raises(psycopg.OperationalError, match="permission denied"):
        psycopg.connect(conninfo(settings.DATA_READER_DB_ALIAS, NAME=app_db))
