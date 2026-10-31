import psycopg
import pytest

from workspaces import credentials, provisioning
from workspaces.tests.conftest import connect

A, B = 990001, 990002


def role_row(owner: psycopg.Connection, name: str) -> tuple:
    row = owner.execute(
        "SELECT rolsuper, rolcreatedb, rolcreaterole, rolinherit, rolreplication,"
        " rolbypassrls, rolcanlogin, rolconnlimit FROM pg_roles WHERE rolname = %s",
        [name],
    ).fetchone()
    assert row is not None
    return row


def test_create_makes_a_schema_and_two_locked_down_roles(owner, provision) -> None:
    provision(A)
    for kind in ("rw", "ro"):
        row = role_row(owner, credentials.role_name(A, kind))
        # super, createdb, createrole, inherit, replication, bypassrls: all off
        assert row[:6] == (False,) * 6
        assert row[6] is True
        assert row[7] > 0
    schema_owner = owner.execute(
        "SELECT nspowner::regrole::text FROM pg_namespace WHERE nspname = %s",
        [f"ws_{A}"],
    ).fetchone()
    assert schema_owner == (f"ws_{A}_rw",)


def test_roles_are_members_of_nothing(owner, provision) -> None:
    provision(A)
    members = owner.execute(
        "SELECT r.rolname, g.rolname FROM pg_auth_members m"
        " JOIN pg_roles r ON r.oid = m.roleid JOIN pg_roles g ON g.oid = m.member"
        " WHERE g.rolname LIKE 'ws\\_%' ESCAPE '\\'"
    ).fetchall()
    assert members == []


def test_rw_owns_its_schema_and_ro_reads_it_only(owner, provision) -> None:
    provision(A)
    with connect(A, "rw") as rw:
        rw.execute("CREATE TABLE customer (id int, name text)")
        rw.execute("INSERT INTO customer VALUES (1, 'a')")
        # defaults: the unqualified name is this workspace's table
        assert rw.execute("SELECT current_schema()").fetchone() == (f"ws_{A}",)
    with connect(A, "ro") as ro:
        assert ro.execute("SELECT name FROM customer").fetchall() == [("a",)]
        with pytest.raises(psycopg.errors.ReadOnlySqlTransaction):
            ro.execute("INSERT INTO customer VALUES (2, 'b')")
        with pytest.raises(
            (
                psycopg.errors.InsufficientPrivilege,
                psycopg.errors.ReadOnlySqlTransaction,
            )
        ):
            ro.execute("CREATE TABLE x (id int)")


def test_passwords_are_derived_and_not_shared() -> None:
    assert credentials.role_password(A, "rw", 1) == credentials.role_password(
        A, "rw", 1
    )
    assert credentials.role_password(A, "rw", 1) != credentials.role_password(
        A, "ro", 1
    )
    assert credentials.role_password(A, "rw", 1) != credentials.role_password(
        B, "rw", 1
    )
    assert credentials.role_password(A, "rw", 1) != credentials.role_password(
        A, "rw", 2
    )


def test_create_is_idempotent(owner, provision) -> None:
    provision(A)
    with owner.transaction():
        provisioning.create_workspace_schema(owner, A)
    with connect(A, "rw") as rw:
        rw.execute("SELECT 1")


def test_drop_removes_the_schema_and_both_roles(owner, provision) -> None:
    provision(A)
    with connect(A, "rw") as rw:
        rw.execute("CREATE TABLE t (id int)")
    kept = connect(A, "ro")  # an open session must not block the drop
    with owner.transaction():
        provisioning.drop_workspace_schema(owner, A)
    kept.close()
    assert owner.execute(
        "SELECT count(*) FROM pg_namespace WHERE nspname = %s", [f"ws_{A}"]
    ).fetchone() == (0,)
    assert owner.execute(
        "SELECT count(*) FROM pg_roles WHERE rolname LIKE %s", [f"ws\\_{A}\\_%"]
    ).fetchone() == (0,)
    with pytest.raises(psycopg.OperationalError):
        connect(A, "rw")
    with owner.transaction():  # dropping again is fine
        provisioning.drop_workspace_schema(owner, A)
