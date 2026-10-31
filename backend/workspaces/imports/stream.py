"""Server-sent events for one import: `progress` while it waits or loads, then one
of `succeeded`, `failed` or `cancelled`. State-based, not a log: a client that
reconnects simply gets the current state again. Each open stream holds a server
thread, so it shares the open-stream cap of the agent streams
(AGENT_MAX_OPEN_STREAMS) and ends after AGENT_SSE_MAX_SECONDS."""

import time
from collections.abc import Iterator

from django.conf import settings

from agent.stream import acquire_slot, format_event, release_slot
from workspaces.imports import service
from workspaces.models import ImportJob


def _progress(job: ImportJob) -> dict:
    data = service.job_dict(job)
    return {
        "status": data["status"],
        "phase": data["phase"]
        or ("queued" if job.status == ImportJob.STATUS_QUEUED else ""),
        "bytes_read": data["bytes_read"],
        "bytes_total": data["bytes_total"],
        "rows_loaded": data["rows_loaded"],
    }


def _final(job: ImportJob) -> tuple[str, dict]:
    if job.status == ImportJob.STATUS_SUCCEEDED:
        return "succeeded", {
            "table": job.table_name,
            "rows": job.rows_loaded,
            "bytes": job.bytes_total,
        }
    if job.status == ImportJob.STATUS_FAILED:
        return "failed", {"error_code": job.error_code, "message": job.error_message}
    return "cancelled", {}


class ImportEventStream:
    def __init__(self, job_id: int):
        self.job_id = job_id
        self._released = False
        acquire_slot()

    def close(self) -> None:
        if not self._released:
            self._released = True
            release_slot()

    def __iter__(self) -> Iterator[str]:
        try:
            yield from self._events()
        finally:
            self.close()

    def _events(self) -> Iterator[str]:
        deadline = time.monotonic() + settings.AGENT_SSE_MAX_SECONDS
        last_beat = time.monotonic()
        last_sent: dict | None = None
        while True:
            job = ImportJob.objects.filter(pk=self.job_id).first()
            if job is None:  # the workspace was deleted under it
                yield format_event("cancelled", {})
                return
            if job.is_terminal:
                event, data = _final(job)
                yield format_event(event, data)
                return
            snapshot = _progress(job)
            if snapshot != last_sent:
                last_sent = snapshot
                last_beat = time.monotonic()
                yield format_event("progress", snapshot)
            now = time.monotonic()
            if now >= deadline:
                yield format_event("timeout", {"status": job.status})
                return
            if now - last_beat >= settings.AGENT_SSE_HEARTBEAT_SECONDS:
                yield ": heartbeat\n\n"
                last_beat = now
            time.sleep(settings.AGENT_SSE_READ_BLOCK_MS / 1000)
