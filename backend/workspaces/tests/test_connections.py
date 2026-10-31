import time

import psycopg
import pytest
from django.conf import settings
from django.test import override_settings

from workspaces import connections
from workspaces.tests.conftest import connect

A, B, C = 990011, 990012, 990013


def test_a_connection_is_the_workspace_role_and_ends_its_transaction(provision) -> None:
    provision(A)
    with connections.workspace_connection(A, "rw", 1) as connection:
        assert connection.execute("SELECT current_user").fetchone() == (f"ws_{A}_rw",)
        connection.execute("CREATE TABLE t (id int)")
    # committed on a clean exit, closed after it
    assert connection.closed
    with connect(A, "rw") as check:
        assert check.execute("SELECT count(*) FROM t").fetchone() == (0,)


def test_an_error_rolls_the_request_back(provision) -> None:
    provision(A)
    with (
        pytest.raises(RuntimeError),
        connections.workspace_connection(A, "rw", 1) as connection,
    ):
        connection.execute("CREATE TABLE t (id int)")
        raise RuntimeError("boom")
    with connect(A, "rw") as check:
        assert check.execute("SELECT to_regclass('t')").fetchone() == (None,)


def test_the_reader_kind_connects_as_the_ro_role(provision) -> None:
    provision(A)
    with connections.workspace_connection(A, "ro", 1) as connection:
        assert connection.execute("SELECT current_user").fetchone() == (f"ws_{A}_ro",)
        assert connection.execute("SHOW default_transaction_read_only").fetchone() == (
            "on",
        )


def test_a_wrong_password_version_cannot_connect(provision) -> None:
    provision(A)
    with pytest.raises(psycopg.OperationalError):
        connections.workspace_connection(A, "rw", 2).__enter__()


def test_connect_per_request_is_fast_enough_locally(provision) -> None:
    """Records the number DECISION.md quotes; the real figure is the pooled Neon
    endpoint's (owner task 5.9.7)."""
    provision(A)
    started = time.perf_counter()
    for _ in range(10):
        with connections.workspace_connection(A, "ro", 1) as connection:
            connection.execute("SELECT 1")
    per_request_ms = (time.perf_counter() - started) * 100
    assert per_request_ms < 250


def test_the_role_connection_limit_caps_one_workspace(provision) -> None:
    provision(A)
    limit = settings.WORKSPACE_RW_CONNECTION_LIMIT
    held = [connect(A, "rw") for _ in range(limit)]
    try:
        with pytest.raises(psycopg.OperationalError, match="too many connections"):
            connect(A, "rw")
    finally:
        for connection in held:
            connection.close()


@override_settings(WORKSPACE_RW_CONNECTION_LIMIT=2, WORKSPACE_RO_CONNECTION_LIMIT=2)
def test_a_burst_from_several_workspaces_stays_under_the_ceiling(
    provision, owner
) -> None:
    for workspace_id in (A, B, C):
        provision(workspace_id)
    held = []
    refused = 0
    try:
        for workspace_id in (A, B, C):
            for kind in ("rw", "ro"):
                for _ in range(5):  # far more than the limit of 2 per role
                    try:
                        held.append(connect(workspace_id, kind))
                    except psycopg.OperationalError:
                        refused += 1
        ceiling = int(owner.execute("SHOW max_connections").fetchone()[0])
        in_use = owner.execute(
            "SELECT count(*) FROM pg_stat_activity WHERE usename LIKE 'ws\\_%' ESCAPE '\\'"
        ).fetchone()[0]
        assert len(held) == 3 * 2 * 2  # the limits held, per role
        assert refused == 3 * 2 * 3
        assert in_use == len(held) < ceiling
    finally:
        for connection in held:
            connection.close()
