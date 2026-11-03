from typing import cast

from django.conf import settings
from django.http import HttpRequest
from ninja import Router
from ninja.security import django_auth

from accounts.models import User
from common.response.domain import SuccessEnvelope, errors, success
from common.throttling.scoped import WorkspaceThrottle
from core.datadb import DEMO_SCHEMA
from workspaces import quota, service, usage
from workspaces.errors import DemoWorkspaceReadOnly
from workspaces.models import Workspace
from workspaces.schemas import (
    BytesLimit,
    CountLimit,
    LimitsOut,
    WorkspaceIn,
    WorkspaceOut,
    WorkspaceRename,
    demo_dict,
    workspace_dict,
)

router = Router(tags=["workspaces"])


def _user(request: HttpRequest) -> User:
    return cast(User, request.user)


def _one(workspace: Workspace) -> dict:
    stats = usage.schema_usage([workspace.schema_name])[workspace.schema_name]
    return workspace_dict(workspace, stats, settings.WORKSPACE_MAX_BYTES)


@router.get(
    "",
    response={200: SuccessEnvelope[list[WorkspaceOut]], **errors(401, 429)},
    auth=django_auth,
)
def list_workspaces(request: HttpRequest) -> dict:
    """The shared demo workspace first, then your own, with table counts and bytes
    used. `meta.max_workspaces` is the cap."""
    owned = service.list_owned(_user(request))
    stats = usage.schema_usage([DEMO_SCHEMA, *(w.schema_name for w in owned)])
    for w in owned:
        quota.remember(w.pk, stats[w.schema_name].bytes)
    items = [demo_dict(stats[DEMO_SCHEMA])] + [
        workspace_dict(w, stats[w.schema_name], settings.WORKSPACE_MAX_BYTES)
        for w in owned
    ]
    return success(items, meta={"max_workspaces": settings.MAX_WORKSPACES_PER_USER})


@router.post(
    "",
    response={200: SuccessEnvelope[WorkspaceOut], **errors(401, 409, 422, 429, 503)},
    auth=django_auth,
    throttle=[WorkspaceThrottle()],
)
def create_workspace(request: HttpRequest, payload: WorkspaceIn) -> dict:
    """Create a private workspace: an empty schema only you and your agent can
    reach. `workspace_limit_reached` when you already have the maximum."""
    workspace = service.create(_user(request), payload.name)
    return success(_one(workspace), message="Workspace created.")


@router.patch(
    "/demo",
    response={200: SuccessEnvelope[WorkspaceOut], **errors(401, 409, 429)},
    auth=django_auth,
)
def rename_demo_workspace(request: HttpRequest, payload: WorkspaceRename) -> dict:
    """Always refused: the shared demo workspace is read-only for everyone."""
    raise DemoWorkspaceReadOnly()


@router.delete(
    "/demo",
    response={200: SuccessEnvelope[None], **errors(401, 409, 429)},
    auth=django_auth,
)
def delete_demo_workspace(request: HttpRequest) -> dict:
    """Always refused: the shared demo workspace cannot be deleted."""
    raise DemoWorkspaceReadOnly()


@router.get(
    "/limits",
    response={200: SuccessEnvelope[LimitsOut], **errors(401, 429)},
    auth=django_auth,
)
def get_workspace_limits(request: HttpRequest) -> dict:
    """What the caller may still do with workspaces: how many workspaces, how many
    bytes (per workspace and together), and
    the dump size and per-table caps. Read only."""
    user = _user(request)
    return success(
        LimitsOut(
            workspaces=CountLimit(
                used=Workspace.objects.filter(owner=user).count(),
                allowed=settings.MAX_WORKSPACES_PER_USER,
            ),
            bytes=BytesLimit(
                used=quota.user_bytes(user),
                allowed=settings.USER_MAX_BYTES,
                per_workspace=settings.WORKSPACE_MAX_BYTES,
            ),
            max_tables=settings.WORKSPACE_MAX_TABLES,
            max_columns=settings.WORKSPACE_MAX_COLUMNS,
            max_relations=settings.WORKSPACE_MAX_RELATIONS,
            max_dump_bytes=settings.DUMP_MAX_FILE_BYTES,
        ).model_dump(mode="json")
    )


@router.get(
    "/{workspace_id}",
    response={200: SuccessEnvelope[WorkspaceOut], **errors(401, 404, 429)},
    auth=django_auth,
)
def get_workspace(request: HttpRequest, workspace_id: int) -> dict:
    """One of your workspaces. Someone else's workspace is a 404, the same as a
    missing one."""
    return success(_one(service.get_owned(_user(request), workspace_id)))


@router.patch(
    "/{workspace_id}",
    response={200: SuccessEnvelope[WorkspaceOut], **errors(401, 404, 409, 422, 429)},
    auth=django_auth,
)
def rename_workspace(
    request: HttpRequest, workspace_id: int, payload: WorkspaceRename
) -> dict:
    workspace = service.get_owned(_user(request), workspace_id)
    return success(_one(service.rename(workspace, payload.name)), message="Renamed.")


@router.delete(
    "/{workspace_id}",
    response={200: SuccessEnvelope[None], **errors(401, 404, 429)},
    auth=django_auth,
    throttle=[WorkspaceThrottle()],
)
def delete_workspace(request: HttpRequest, workspace_id: int) -> dict:
    """Drop the workspace's schema, tables and login roles for good. Your past
    agent runs stay in your history and can still be replayed."""
    service.delete(service.get_owned(_user(request), workspace_id), _user(request))
    return success(None, message="Workspace deleted.")
