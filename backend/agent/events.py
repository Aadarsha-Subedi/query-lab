"""Live events for one run: a Redis stream `agent:events:{id}`.

The stream is a nudge, not the record. Each entry says "step N was written" or
"the status changed"; the SSE view reads the steps themselves from Postgres
(agent/api.py). So a lost or trimmed entry only delays a client by one read
block, and an event id is simply the step index, which is what `Last-Event-ID`
carries back on reconnect."""

import logging
from typing import Any

from django.conf import settings
from redis.exceptions import RedisError

from common.redis import get_redis

logger = logging.getLogger(__name__)

KIND_STEP = "step"
KIND_STATUS = "status"


def _text(value: bytes | str) -> str:
    return value.decode() if isinstance(value, bytes) else value


def stream_key(run_id: int) -> str:
    return f"agent:events:{run_id}"


def _publish(run_id: int, fields: dict[str, str | int]) -> None:
    try:
        client = get_redis()
        key = stream_key(run_id)
        client.xadd(key, fields, maxlen=settings.AGENT_EVENTS_MAXLEN)  # type: ignore[arg-type]
        client.expire(key, settings.AGENT_STATE_TTL_SECONDS)
    except RedisError:  # the trace is already stored; readers fall back to polling
        logger.exception("Could not publish an agent event")


def publish_step(run_id: int, index: int) -> None:
    _publish(run_id, {"kind": KIND_STEP, "index": index})


def publish_status(run_id: int) -> None:
    _publish(run_id, {"kind": KIND_STATUS})


def last_id(run_id: int) -> str:
    """The newest stream id now, or 0-0 for an empty stream: where a new reader starts."""
    entries: list[Any] = get_redis().xrevrange(stream_key(run_id), count=1)  # type: ignore[assignment]
    return _text(entries[0][0]) if entries else "0-0"


def wait(run_id: int, after: str, block_ms: int) -> str:
    """Block until something newer than `after` is published or `block_ms` pass;
    return the newest stream id seen."""
    result: Any = get_redis().xread(
        {stream_key(run_id): after}, count=100, block=block_ms
    )
    if not result:
        return after
    return _text(result[0][1][-1][0])
