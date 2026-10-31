"""The Huey side of an import: claim the job, wait for the one import slot, load,
and always leave the job in a final state with its temp file gone."""

import logging
import os
import time

from django.conf import settings
from django.utils import timezone
from huey import crontab
from huey.contrib.djhuey import db_periodic_task, db_task, on_startup

from common.exception.domain import AppException
from common.redis import get_redis
from workspaces.imports import loader, progress, service, sweep
from workspaces.imports import plan as planning
from workspaces.models import ImportJob

logger = logging.getLogger(__name__)

INTERNAL_ERROR_CODE = "import_failed"
BUSY_ERROR_CODE = "import_limit"
SLOT_POLL_SECONDS = 1


def _acquire_slot() -> bool:
    """At most IMPORT_MAX_CONCURRENT imports run at once in this container: the
    small instance cannot parse and load two files and still serve the API."""
    redis = get_redis()
    deadline = time.monotonic() + settings.IMPORT_QUEUE_WAIT_SECONDS
    while True:
        if redis.incr(progress.SLOT_KEY) <= settings.IMPORT_MAX_CONCURRENT:
            redis.expire(progress.SLOT_KEY, progress.alive_ttl())
            return True
        redis.decr(progress.SLOT_KEY)
        if time.monotonic() >= deadline:
            return False
        time.sleep(SLOT_POLL_SECONDS)


def _release_slot() -> None:
    redis = get_redis()
    if redis.decr(progress.SLOT_KEY) < 0:
        redis.set(progress.SLOT_KEY, 0)


def _finish(job_id: int, status: str, **fields: object) -> None:
    ImportJob.objects.filter(pk=job_id).update(
        status=status, finished_at=timezone.now(), **fields
    )


def execute(job_id: int) -> None:
    """Run one import job. Also called directly by tests."""
    claimed = ImportJob.objects.filter(
        pk=job_id, status=ImportJob.STATUS_QUEUED
    ).update(status=ImportJob.STATUS_RUNNING, started_at=timezone.now())
    if not claimed:
        return
    job = ImportJob.objects.select_related("workspace__owner").get(pk=job_id)
    try:
        if not _acquire_slot():
            _finish(
                job_id,
                ImportJob.STATUS_FAILED,
                error_code=BUSY_ERROR_CODE,
                error_message="The server is busy with other imports. Try again.",
            )
            return
        try:
            _run(job)
        finally:
            _release_slot()
    finally:
        service.discard_file(job)
        progress.clear(job_id)


def _run(job: ImportJob) -> None:
    try:
        if not job.file_path or not os.path.exists(job.file_path):
            _finish(
                job.pk,
                ImportJob.STATUS_FAILED,
                error_code=sweep.UPLOAD_LOST_CODE,
                error_message="The uploaded file is gone. Upload it again.",
            )
            return
        progress.report(job.pk, phase="starting", rows=0, bytes_read=0)
        sniffed = service.sniff_file(job.file_path, job.options)
        plan = planning.build(sniffed, job.options, job.table_name)
        loaded = loader.load(job, sniffed, plan)
    except loader.ImportCancelled:
        _finish(job.pk, ImportJob.STATUS_CANCELLED)
    except AppException as error:
        detail = error.errors[0]["message"] if error.errors else error.message
        _finish(
            job.pk,
            ImportJob.STATUS_FAILED,
            error_code=error.error_code,
            error_message=detail[:500],
        )
    except Exception:
        logger.exception("Import %s crashed", job.pk)
        _finish(
            job.pk,
            ImportJob.STATUS_FAILED,
            error_code=INTERNAL_ERROR_CODE,
            error_message="The import hit an unexpected error. Nothing was kept.",
        )
    else:
        _finish(
            job.pk,
            ImportJob.STATUS_SUCCEEDED,
            rows_loaded=loaded,
            bytes_read=job.bytes_total,
        )


@db_task()
def run_import(job_id: int) -> None:
    execute(job_id)


@db_periodic_task(crontab(minute="*/5"))
def sweep_imports() -> None:
    sweep.sweep()


@on_startup()
def sweep_on_start() -> None:
    """A worker that starts has no import running: whatever the database still
    calls running was cut off by a restart."""
    sweep.mark_interrupted(all_running=True)
