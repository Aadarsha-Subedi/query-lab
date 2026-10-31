from collections.abc import Callable

import pytest
from django.test import override_settings

from accounts.models import User
from workspaces import connections, quota
from workspaces.errors import UserStorageFull, WorkspaceFull
from workspaces.models import Workspace

pytestmark = pytest.mark.django_db


@pytest.fixture
def two(user: User, provision: Callable[[int], int]) -> tuple[Workspace, Workspace]:
    made = []
    for name in ("a", "b"):
        workspace = Workspace.objects.create(owner=user, name=name, status="ready")
        provision(workspace.pk)
        with connections.workspace_connection(workspace.pk, "rw", 1) as rw:
            rw.execute("CREATE TABLE t (v text)")
            rw.execute(
                "INSERT INTO t SELECT repeat('x', 1000) FROM generate_series(1, 200)"
            )
        made.append(workspace)
    return made[0], made[1]


def test_size_is_the_catalogs_total_relation_size(
    two: tuple[Workspace, Workspace],
) -> None:
    first, _ = two
    size = quota.cached_bytes(first)
    assert 100_000 < size < 1_000_000


@override_settings(WORKSPACE_MAX_BYTES=50_000)
def test_a_full_workspace_refuses_before_a_write(
    two: tuple[Workspace, Workspace],
) -> None:
    with pytest.raises(WorkspaceFull) as caught:
        quota.ensure_room(two[0])
    assert caught.value.error_code == "workspace_full"


@override_settings(USER_MAX_BYTES=300_000)
def test_the_user_total_counts_every_workspace(
    two: tuple[Workspace, Workspace],
) -> None:
    first, second = two
    assert quota.user_bytes(first.owner) == quota.cached_bytes(
        first
    ) + quota.cached_bytes(second)
    with pytest.raises(UserStorageFull):
        quota.ensure_room(first)


def test_ensure_within_measures_inside_the_writers_transaction(
    two: tuple[Workspace, Workspace],
) -> None:
    first, _ = two
    with (
        override_settings(WORKSPACE_MAX_BYTES=2_000_000),
        connections.workspace_connection(first.pk, "rw", 1) as rw,
    ):
        before = quota.ensure_within(rw, first)
        rw.execute(
            "INSERT INTO t SELECT repeat('y', 1000) FROM generate_series(1, 400)"
        )
        assert quota.ensure_within(rw, first) > before
    with (
        override_settings(WORKSPACE_MAX_BYTES=500_000),
        connections.workspace_connection(first.pk, "rw", 1) as rw,
    ):
        rw.execute(
            "INSERT INTO t SELECT repeat('z', 1000) FROM generate_series(1, 2000)"
        )
        with pytest.raises(WorkspaceFull):
            quota.ensure_within(rw, first)


def test_an_empty_workspace_has_room(
    user: User, provision: Callable[[int], int]
) -> None:
    workspace = Workspace.objects.create(owner=user, name="e", status="ready")
    provision(workspace.pk)
    quota.ensure_room(workspace)
