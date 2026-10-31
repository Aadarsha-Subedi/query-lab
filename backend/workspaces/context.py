"""Which workspace a request, an ask or an agent run is about.

The shared Olist demo is not a database row: it is the constant `DEMO`, handled
here and nowhere else. A user workspace is a `Workspace` row whose schema and
role names are generated from its id, never taken from a request or a model.
"""

from dataclasses import dataclass

from core.datadb import DEMO_SCHEMA


@dataclass(frozen=True)
class WorkspaceRef:
    """What the data paths need to know: an id (None for the demo) and the schema
    that holds the tables."""

    id: int | None
    schema_name: str
    # Which derived password the workspace's roles currently have.
    credential_version: int = 1

    @property
    def is_demo(self) -> bool:
        return self.id is None


DEMO = WorkspaceRef(id=None, schema_name=DEMO_SCHEMA)

SCHEMA_PREFIX = "ws_"
RO_SUFFIX = "_ro"
RW_SUFFIX = "_rw"


def schema_name_for(workspace_id: int) -> str:
    return f"{SCHEMA_PREFIX}{int(workspace_id)}"


def ref_for(workspace_id: int | None) -> WorkspaceRef:
    """The reference for an id stored on a run (None means the demo)."""
    if workspace_id is None:
        return DEMO
    return WorkspaceRef(id=workspace_id, schema_name=schema_name_for(workspace_id))
