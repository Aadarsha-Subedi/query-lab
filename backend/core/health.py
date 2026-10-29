"""Dependency checks for GET /api/health. Each check runs in its own thread
with HEALTH_CHECK_TIMEOUT_SECONDS, so one hung dependency cannot hang the
endpoint; a check that raises or times out is reported as failing."""

import logging
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor, wait

from django.conf import settings
from django.db import connections

from common.redis import get_redis
from common.tasks import PONG, ping

logger = logging.getLogger(__name__)

OK = "ok"
FAIL = "fail"
DEGRADED = "degraded"


def _select_one(alias: str) -> Callable[[], None]:
    def check() -> None:
        try:
            with connections[alias].cursor() as cursor:
                cursor.execute("SELECT 1")
                cursor.fetchone()
        finally:
            # Connections are per thread; this thread is about to end.
            connections[alias].close()

    return check


def check_redis() -> None:
    if not get_redis().ping():
        raise ConnectionError("Redis did not answer PING")


def check_worker() -> None:
    result = ping()
    try:
        answer = result.get(
            blocking=True, timeout=settings.HEALTH_CHECK_TIMEOUT_SECONDS
        )
    except Exception:
        result.revoke()
        raise
    if answer != PONG:
        raise RuntimeError(f"Unexpected ping answer: {answer!r}")


def checks() -> dict[str, Callable[[], None]]:
    return {
        "app_db": _select_one("default"),
        "data_db": _select_one(settings.DATA_DB_ALIAS),
        "data_reader": _select_one(settings.DATA_READER_DB_ALIAS),
        "redis": check_redis,
        "worker": check_worker,
    }


def run_checks() -> dict[str, str]:
    """{name: "ok" | "fail"} for every dependency."""
    timeout = settings.HEALTH_CHECK_TIMEOUT_SECONDS
    to_run = checks()
    executor = ThreadPoolExecutor(max_workers=len(to_run))
    futures = {name: executor.submit(check) for name, check in to_run.items()}
    # One shared deadline: the checks run in parallel.
    done, _ = wait(futures.values(), timeout=timeout)
    results: dict[str, str] = {}
    for name, future in futures.items():
        if future not in done:
            logger.warning("Health check %s timed out after %ss", name, timeout)
            results[name] = FAIL
        elif (exc := future.exception()) is not None:
            logger.warning("Health check %s failed: %s", name, type(exc).__name__)
            results[name] = FAIL
        else:
            results[name] = OK
    # Do not wait for a hung check; its thread ends when the call returns.
    executor.shutdown(wait=False, cancel_futures=True)
    return results
