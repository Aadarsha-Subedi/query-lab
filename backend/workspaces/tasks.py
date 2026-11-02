"""Huey tasks for workspaces: the dump import runs here, not in a request."""

from huey.contrib.djhuey import db_task

from workspaces import importer


@db_task()
def run_import(job_id: int) -> None:
    importer.run(job_id)
