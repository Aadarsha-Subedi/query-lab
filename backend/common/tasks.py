"""Shared background tasks (Huey)."""

from huey.contrib.djhuey import task

PONG = "pong"


@task()
def ping() -> str:
    """Proves a worker is consuming the queue (used by the health check)."""
    return PONG
