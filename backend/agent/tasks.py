"""Huey tasks. They only call the loop; a paused run holds no task."""

from huey import crontab
from huey.contrib.djhuey import db_periodic_task, db_task

from agent import loop, service


@db_task()
def start_run(run_id: int) -> None:
    loop.advance(run_id)


@db_task()
def resume_run(run_id: int) -> None:
    """After approve or edit: the run is `running` again with its decision stored."""
    loop.advance(run_id)


@db_periodic_task(crontab(minute="*"))
def expire_stale_runs() -> None:
    service.expire_stale()
