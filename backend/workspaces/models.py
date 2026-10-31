from django.conf import settings
from django.db import models

from common.models import TimeStampModel
from workspaces.context import WorkspaceRef, schema_name_for


class Workspace(TimeStampModel):
    """A user's private schema in `querylab`. The schema and its two login roles
    are named from the id (`ws_<id>`, `ws_<id>_rw`, `ws_<id>_ro`), so no name ever
    comes from user input."""

    STATUS_CREATING = "creating"
    STATUS_READY = "ready"
    STATUS_DELETING = "deleting"
    STATUS_FAILED = "failed"

    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="workspaces"
    )
    name = models.CharField(max_length=100)
    status = models.CharField(max_length=10, default=STATUS_CREATING)

    class Meta:
        ordering = ["created_at", "id"]
        constraints = [
            models.UniqueConstraint(
                fields=["owner", "name"], name="workspace_owner_name_unique"
            )
        ]
        indexes = [models.Index(fields=["owner"])]

    def __str__(self) -> str:
        return f"workspace {self.pk} ({self.name})"

    @property
    def schema_name(self) -> str:
        return schema_name_for(self.pk)

    @property
    def role_name(self) -> str:
        """The schema owner role (read and write); the agent's is `<name>_ro`."""
        return f"{self.schema_name}_rw"

    @property
    def ref(self) -> WorkspaceRef:
        return WorkspaceRef(id=self.pk, schema_name=self.schema_name)
