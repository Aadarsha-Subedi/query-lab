"""Neon's project owner is not a superuser: it has CREATEROLE and owns the
database. This rehearses provisioning with such a role on a scratch database, so
the parts that need membership of the workspace roles are exercised locally.
The real check on Neon stays an owner task (DECISION.md)."""

from collections.abc import Iterator

import psycopg
import pytest
from django.conf import settings
from psycopg import sql
from psycopg.conninfo import make_conninfo

from workspaces import credentials, provisioning

SIM_OWNER = "neonsim_owner"
SIM_DB = "neonsim_data"
WS = 990021


@pytest.fixture
def sim_owner(owner: psycopg.Connection) -> Iterator[psycopg.Connection]:
    owner.execute(
        sql.SQL("DROP DATABASE IF EXISTS {db}").format(db=sql.Identifier(SIM_DB))
    )
    for role in (SIM_OWNER,):
        owner.execute(sql.SQL("DROP ROLE IF EXISTS {r}").format(r=sql.Identifier(role)))
    owner.execute(
        sql.SQL("CREATE ROLE {r} LOGIN CREATEROLE NOSUPERUSER PASSWORD 'sim'").format(
            r=sql.Identifier(SIM_OWNER)
        )
    )
    owner.execute(
        sql.SQL("CREATE DATABASE {db} OWNER {r}").format(
            db=sql.Identifier(SIM_DB), r=sql.Identifier(SIM_OWNER)
        )
    )
    db = settings.DATABASES[settings.DATA_DB_ALIAS]
    connection = psycopg.connect(
        make_conninfo(
            host=db["HOST"],
            port=db["PORT"],
            dbname=SIM_DB,
            user=SIM_OWNER,
            password="sim",
        ),
        autocommit=True,
    )
    yield connection
    connection.close()
    for name in (credentials.role_name(WS, "rw"), credentials.role_name(WS, "ro")):
        owner.execute(
            "SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE usename = %s",
            [name],
        )
    owner.execute(
        sql.SQL("DROP DATABASE IF EXISTS {db} WITH (FORCE)").format(
            db=sql.Identifier(SIM_DB)
        )
    )
    for name in (credentials.role_name(WS, "rw"), credentials.role_name(WS, "ro")):
        owner.execute(sql.SQL("DROP ROLE IF EXISTS {r}").format(r=sql.Identifier(name)))
    owner.execute(
        sql.SQL("DROP ROLE IF EXISTS {r}").format(r=sql.Identifier(SIM_OWNER))
    )


def test_a_createrole_owner_can_create_use_and_drop_a_workspace(
    sim_owner: psycopg.Connection,
) -> None:
    assert sim_owner.execute(
        "SELECT rolsuper FROM pg_roles WHERE rolname = current_user"
    ).fetchone() == (False,)
    with sim_owner.transaction():
        provisioning.create_workspace_schema(sim_owner, WS)
    db = settings.DATABASES[settings.DATA_DB_ALIAS]

    def login(kind: str) -> psycopg.Connection:
        return psycopg.connect(
            make_conninfo(
                host=db["HOST"],
                port=db["PORT"],
                dbname=SIM_DB,
                user=credentials.role_name(WS, kind),  # type: ignore[arg-type]
                password=credentials.role_password(WS, kind, 1),  # type: ignore[arg-type]
            ),
            autocommit=True,
        )

    with login("rw") as rw:
        rw.execute("CREATE TABLE t (id int)")
        rw.execute("INSERT INTO t VALUES (1)")
    open_session = login("ro")
    # the default privileges set by the owner reach tables the rw role creates
    assert open_session.execute("SELECT id FROM t").fetchall() == [(1,)]
    with sim_owner.transaction():
        provisioning.drop_workspace_schema(sim_owner, WS)
    open_session.close()
    assert sim_owner.execute(
        "SELECT count(*) FROM pg_roles WHERE rolname LIKE 'ws\\_%' ESCAPE '\\'"
    ).fetchone() == (0,)
