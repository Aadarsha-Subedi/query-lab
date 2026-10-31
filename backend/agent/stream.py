"""Server-sent events for one run.

On connect the stream sends the stored steps after `Last-Event-ID` (the event id
is the step index), then waits on the run's Redis stream for news, with a
heartbeat comment while idle. It ends when the run pauses for approval or reaches
a terminal status, so a paused run holds no gunicorn thread; the client reopens
the stream after it decides, with the last id it saw.

Each open stream holds one thread of the small container, so they are capped
(AGENT_MAX_OPEN_STREAMS, counted in Redis) and each lives at most
AGENT_SSE_MAX_SECONDS."""

import json
import time
from collections.abc import Iterator

from django.conf import settings

from agent import events
from agent.errors import StreamLimitReached
from agent.models import AgentRun
from agent.schemas import pending_dict, step_dict
from common.redis import get_redis

STREAMS_KEY = "agent:streams"


def format_event(event: str, data: object, event_id: int | None = None) -> str:
    head = f"id: {event_id}\n" if event_id is not None else ""
    return f"{head}event: {event}\ndata: {json.dumps(data, default=str)}\n\n"


def acquire_slot() -> None:
    client = get_redis()
    count = client.incr(STREAMS_KEY)
    # The counter heals itself if a process dies without releasing its slot.
    client.expire(STREAMS_KEY, settings.AGENT_SSE_MAX_SECONDS + 60)
    if count > settings.AGENT_MAX_OPEN_STREAMS:
        client.decr(STREAMS_KEY)
        raise StreamLimitReached()


def release_slot() -> None:
    client = get_redis()
    if client.decr(STREAMS_KEY) < 0:
        client.set(STREAMS_KEY, 0)


class EventStream:
    """An iterator of SSE text. `close()` frees the stream slot exactly once, also
    when the client disconnects before the first chunk."""

    def __init__(self, run_id: int, last_index: int):
        self.run_id = run_id
        self.last_index = last_index
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
        cursor = events.last_id(self.run_id)
        last_beat = time.monotonic()
        while True:
            # Status first, then steps: a terminal status read here means every
            # step it implies is already stored and gets sent below.
            run = AgentRun.objects.get(pk=self.run_id)
            status = run.status
            for step in run.steps.filter(index__gt=self.last_index).order_by("index"):
                self.last_index = step.index
                yield format_event("step", step_dict(step), step.index)
                last_beat = time.monotonic()
            if status != AgentRun.STATUS_RUNNING:
                yield format_event(
                    "status",
                    {
                        "status": status,
                        "error_code": run.error_code,
                        # the same block as GET /runs/{id}; null unless paused
                        "pending": pending_dict(run),
                    },
                )
                return
            now = time.monotonic()
            if now >= deadline:
                yield format_event("timeout", {"status": status})
                return
            if now - last_beat >= settings.AGENT_SSE_HEARTBEAT_SECONDS:
                yield ": heartbeat\n\n"
                last_beat = now
            cursor = events.wait(self.run_id, cursor, settings.AGENT_SSE_READ_BLOCK_MS)
