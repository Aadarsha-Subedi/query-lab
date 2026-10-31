"""Workspace role names and passwords. Passwords are derived, never stored:
HMAC-SHA256 over the master secret, the workspace id, the role kind and a
rotation counter, so the app can reproduce them on any container and a leaked
database row reveals nothing."""

import base64
import hashlib
import hmac
from typing import Literal

from django.conf import settings

from workspaces.context import RO_SUFFIX, RW_SUFFIX, schema_name_for

Kind = Literal["rw", "ro"]


def role_name(workspace_id: int, kind: Kind) -> str:
    suffix = RW_SUFFIX if kind == "rw" else RO_SUFFIX
    return f"{schema_name_for(workspace_id)}{suffix}"


def role_password(workspace_id: int, kind: Kind, version: int) -> str:
    message = f"workspace:{int(workspace_id)}:{kind}:{int(version)}".encode()
    digest = hmac.new(
        settings.MASTER_WORKSPACE_SECRET.encode(), message, hashlib.sha256
    ).digest()
    return base64.urlsafe_b64encode(digest).decode().rstrip("=")
