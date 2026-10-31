"""The one helper every structural change calls (provisioning, table and column
operations, the SQL console's DDL, imports that create a table)."""

from accounts.models import User
from workspaces.models import WorkspaceDDLLog

MAX_STATEMENT_CHARS = 10_000


def record(workspace_id: int, actor: User | None, statement: str) -> None:
    WorkspaceDDLLog.objects.create(
        workspace_id=workspace_id,
        actor=actor,
        statement=statement[:MAX_STATEMENT_CHARS],
    )
