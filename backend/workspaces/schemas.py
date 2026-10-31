from datetime import datetime
from typing import Literal

from ninja import Schema

from workspaces import usage
from workspaces.models import Workspace

DEMO_NAME = "Olist demo (read-only)"


class WorkspaceIn(Schema):
    name: str


class WorkspaceRename(Schema):
    name: str


class WorkspaceOut(Schema):
    # Null for the shared demo workspace.
    id: int | None
    kind: Literal["demo", "user"]
    name: str
    status: Literal["creating", "ready", "deleting", "failed"]
    read_only: bool
    tables: int
    bytes_used: int
    # Null for the demo: its size is not the user's to spend.
    bytes_allowed: int | None
    created_at: datetime | None


def workspace_dict(
    workspace: Workspace, stats: usage.Usage, bytes_allowed: int
) -> dict:
    return WorkspaceOut(
        id=workspace.pk,
        kind="user",
        name=workspace.name,
        status=workspace.status,  # type: ignore[arg-type]
        read_only=False,
        tables=stats.tables,
        bytes_used=stats.bytes,
        bytes_allowed=bytes_allowed,
        created_at=workspace.created_at,
    ).model_dump(mode="json")


def demo_dict(stats: usage.Usage) -> dict:
    return WorkspaceOut(
        id=None,
        kind="demo",
        name=DEMO_NAME,
        status="ready",
        read_only=True,
        tables=stats.tables,
        bytes_used=stats.bytes,
        bytes_allowed=None,
        created_at=None,
    ).model_dump(mode="json")
