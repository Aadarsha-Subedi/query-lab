from collections.abc import Callable, Iterator

import psycopg
import pytest

from accounts.models import User
from workspaces import connections, provisioning


@pytest.fixture
def user(db: None) -> User:
    return User.objects.create_user("ada@example.com")


@pytest.fixture
def other_user(db: None) -> User:
    return User.objects.create_user("grace@example.com")


@pytest.fixture
def provision(owner: psycopg.Connection) -> Iterator[Callable[[int], int]]:
    """Provision a real schema and roles for a workspace id (no Workspace row)
    and drop them all after the test, whatever it did."""
    made: list[int] = []

    def make(workspace_id: int) -> int:
        made.append(workspace_id)
        with owner.transaction():
            provisioning.create_workspace_schema(owner, workspace_id)
        return workspace_id

    yield make
    for workspace_id in made:
        with owner.transaction():
            provisioning.drop_workspace_schema(owner, workspace_id)


def connect(workspace_id: int, kind: str) -> psycopg.Connection:
    """A connection as the workspace's own role (autocommit, for tests)."""
    return psycopg.connect(
        connections.role_conninfo(workspace_id, kind, 1),  # type: ignore[arg-type]
        autocommit=True,
        prepare_threshold=None,
    )
