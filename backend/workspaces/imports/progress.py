"""What the Huey job tells everyone else while it runs: progress counters, a
liveness mark and a cancel flag, all in Redis (never Postgres, which only sees
the final numbers)."""

from typing import Any

from django.conf import settings

from common.redis import get_redis


def _progress_key(job_id: int) -> str:
    return f"import:progress:{job_id}"


def _alive_key(job_id: int) -> str:
    return f"import:alive:{job_id}"


def _cancel_key(job_id: int) -> str:
    return f"import:cancel:{job_id}"


SLOT_KEY = "import:slots"


def alive_ttl() -> int:
    """A running job refreshes its mark at least once per batch; this is how long
    silence is tolerated before the sweep calls it interrupted."""
    return 2 * (settings.IMPORT_STATEMENT_TIMEOUT_MS // 1000) + 30


def report(job_id: int, **fields: Any) -> None:
    redis = get_redis()
    redis.hset(_progress_key(job_id), mapping={k: str(v) for k, v in fields.items()})
    redis.expire(_progress_key(job_id), settings.AGENT_STATE_TTL_SECONDS)
    redis.set(_alive_key(job_id), 1, ex=alive_ttl())


def read(job_id: int) -> dict[str, str]:
    raw = get_redis().hgetall(_progress_key(job_id))
    return {k.decode(): v.decode() for k, v in raw.items()}  # type: ignore[union-attr]


def is_alive(job_id: int) -> bool:
    return bool(get_redis().exists(_alive_key(job_id)))


def request_cancel(job_id: int) -> None:
    get_redis().set(_cancel_key(job_id), 1, ex=settings.AGENT_STATE_TTL_SECONDS)


def cancel_requested(job_id: int) -> bool:
    return bool(get_redis().exists(_cancel_key(job_id)))


def clear(job_id: int) -> None:
    get_redis().delete(_alive_key(job_id), _cancel_key(job_id))
