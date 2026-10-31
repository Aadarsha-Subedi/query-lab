"""Housekeeping for imports: jobs a restart cut off, queued jobs whose file is
gone, and temp files nobody will use."""

import contextlib
import os
import time
from pathlib import Path

from django.conf import settings
from django.utils import timezone

from workspaces.imports import progress
from workspaces.models import ImportJob

INTERRUPTED_CODE = "import_interrupted"
UPLOAD_LOST_CODE = "import_upload_lost"


def mark_interrupted(*, all_running: bool = False) -> int:
    """Running jobs are failed `import_interrupted`: all of them at worker start,
    otherwise only those that stopped reporting progress."""
    count = 0
    for job in ImportJob.objects.filter(status=ImportJob.STATUS_RUNNING):
        if all_running or not progress.is_alive(job.pk):
            updated = ImportJob.objects.filter(
                pk=job.pk, status=ImportJob.STATUS_RUNNING
            ).update(
                status=ImportJob.STATUS_FAILED,
                finished_at=timezone.now(),
                error_code=INTERRUPTED_CODE,
                error_message="The import was interrupted. Nothing was kept; upload again.",
            )
            if updated:
                _unlink(job.file_path)
                progress.clear(job.pk)
                count += 1
    return count


def fail_lost_uploads() -> int:
    count = 0
    for job in ImportJob.objects.filter(status=ImportJob.STATUS_QUEUED):
        if job.file_path and not os.path.exists(job.file_path):
            count += bool(
                ImportJob.objects.filter(
                    pk=job.pk, status=ImportJob.STATUS_QUEUED
                ).update(
                    status=ImportJob.STATUS_FAILED,
                    finished_at=timezone.now(),
                    error_code=UPLOAD_LOST_CODE,
                    error_message="The uploaded file is gone. Upload it again.",
                )
            )
    return count


def remove_stale_files() -> int:
    """Files in the upload folder that no active job owns and that are older than
    IMPORT_FILE_TTL_SECONDS (a crash between spooling and creating the job)."""
    folder = Path(settings.UPLOAD_TMP_DIR)
    if not folder.exists():
        return 0
    owned = set(
        ImportJob.objects.filter(status__in=ImportJob.ACTIVE).values_list(
            "file_path", flat=True
        )
    )
    removed = 0
    for path in folder.glob("*.csv"):
        old = time.time() - path.stat().st_mtime > settings.IMPORT_FILE_TTL_SECONDS
        if old and str(path) not in owned:
            _unlink(str(path))
            removed += 1
    return removed


def _unlink(path: str) -> None:
    if path:
        with contextlib.suppress(OSError):
            os.unlink(path)


def sweep() -> None:
    mark_interrupted()
    fail_lost_uploads()
    remove_stale_files()
