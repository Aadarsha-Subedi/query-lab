import pytest

from accounts.models import User
from workspaces import ddl_log
from workspaces.models import WorkspaceDDLLog

pytestmark = pytest.mark.django_db


def test_a_record_keeps_who_what_and_when(user: User) -> None:
    ddl_log.record(7, user, "CREATE TABLE t (id int)")
    row = WorkspaceDDLLog.objects.get()
    assert (row.workspace_id, row.actor, row.statement) == (
        7,
        user,
        "CREATE TABLE t (id int)",
    )
    assert row.created_at is not None


def test_the_trail_outlives_the_user_and_is_capped(user: User) -> None:
    ddl_log.record(7, user, "x" * (ddl_log.MAX_STATEMENT_CHARS + 50))
    user.delete()
    row = WorkspaceDDLLog.objects.get()
    assert row.actor is None
    assert len(row.statement) == ddl_log.MAX_STATEMENT_CHARS
