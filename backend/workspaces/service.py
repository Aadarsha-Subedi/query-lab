"""The workspace lifecycle: create, list, rename, delete. A workspace is looked up
only through `get_owned`, so someone else's workspace and a missing one are the
same 404."""

import logging

from django.conf import settings
from django.db import IntegrityError, transaction

from accounts.models import User
from workspaces import connections, ddl_log, naming, provisioning, schema_version
from workspaces.errors import (
    WorkspaceLimitReached,
    WorkspaceNameTaken,
    WorkspaceNotFound,
    WorkspaceProvisioningFailed,
)
from workspaces.models import Workspace

logger = logging.getLogger(__name__)


def get_owned(user: User, workspace_id: int) -> Workspace:
    """The caller's own workspace, or WorkspaceNotFound. Used by every endpoint."""
    workspace = Workspace.objects.filter(pk=workspace_id, owner=user).first()
    if workspace is None:
        raise WorkspaceNotFound()
    return workspace


def list_owned(user: User) -> list[Workspace]:
    return list(Workspace.objects.filter(owner=user))


def create(user: User, name: str) -> Workspace:
    """Check the name and the cap, store the row, then provision the schema and
    roles. A provisioning failure removes everything it made."""
    name = naming.workspace_name(name)
    with transaction.atomic():
        # Serialise a user's creates, so two at once cannot both slip under the cap.
        User.objects.select_for_update().get(pk=user.pk)
        owned = Workspace.objects.filter(owner=user)
        if owned.count() >= settings.MAX_WORKSPACES_PER_USER:
            raise WorkspaceLimitReached()
        if owned.filter(name=name).exists():
            raise WorkspaceNameTaken()
        workspace = Workspace.objects.create(owner=user, name=name)
    try:
        with connections.owner_connection() as connection:
            provisioning.create_workspace_schema(
                connection, workspace.pk, workspace.credential_version
            )
    except Exception:
        logger.exception("Provisioning workspace %s failed", workspace.pk)
        workspace.status = Workspace.STATUS_FAILED
        workspace.save(update_fields=["status", "updated_at"])
        try:
            _drop(workspace)
        except Exception:
            # Left as `failed`: the user can delete it, which retries the cleanup.
            logger.exception("Cleaning up workspace %s failed", workspace.pk)
        else:
            workspace.delete()
        raise WorkspaceProvisioningFailed() from None
    workspace.status = Workspace.STATUS_READY
    workspace.save(update_fields=["status", "updated_at"])
    ddl_log.record(workspace.pk, user, "provision: create schema and login roles")
    return workspace


def rename(workspace: Workspace, name: str) -> Workspace:
    name = naming.workspace_name(name)
    if (
        Workspace.objects.filter(owner=workspace.owner, name=name)
        .exclude(pk=workspace.pk)
        .exists()
    ):
        raise WorkspaceNameTaken()
    workspace.name = name
    try:
        workspace.save(update_fields=["name", "updated_at"])
    except IntegrityError:  # lost a race with another rename
        raise WorkspaceNameTaken() from None
    return workspace


def _drop(workspace: Workspace) -> None:
    with connections.owner_connection() as connection:
        provisioning.drop_workspace_schema(connection, workspace.pk)


def delete(workspace: Workspace, actor: User) -> None:
    """Mark the workspace `deleting`, drop its schema and both roles, then remove
    the row. Run traces (AgentRun) are not touched: they keep the workspace id,
    which now names nothing. Safe to call again on a half-deleted workspace."""
    workspace.status = Workspace.STATUS_DELETING
    workspace.save(update_fields=["status", "updated_at"])
    from workspaces.imports import service as import_service

    import_service.cancel_all(workspace)  # nothing may keep loading into it
    _drop(workspace)
    ddl_log.record(workspace.pk, actor, "drop: schema and login roles")
    schema_version.forget(workspace.pk)
    workspace.delete()
