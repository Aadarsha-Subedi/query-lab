import logging
import time
from collections.abc import Callable

from django.db import connection
from django.http import HttpRequest, HttpResponse

logger = logging.getLogger("request")


class RequestTimingMiddleware:
    """
    Where a request spends its time: total, database (sum, query count, fastest query) and the rest.

    Listed first in MIDDLEWARE so the total covers every other middleware (session, auth). The
    fastest query is the closest thing to the database round trip, so a high value means the
    app and Neon are far apart. The numbers also go out as a Server-Timing header, which
    DevTools shows on the Timing tab; total minus db is Django, Redis and CPU; cpu is this thread's own CPU time, so a high cpu means
    the instance is too small, and a low cpu with a high remainder means waiting on Redis or the network.
    """

    def __init__(self, get_response: Callable[[HttpRequest], HttpResponse]) -> None:
        self.get_response = get_response

    def __call__(self, request: HttpRequest) -> HttpResponse:
        queries: list[float] = []

        def timed(execute, sql, params, many, context):
            started = time.monotonic()
            try:
                return execute(sql, params, many, context)
            finally:
                queries.append((time.monotonic() - started) * 1000)

        started = time.monotonic()
        cpu_started = time.thread_time()
        with connection.execute_wrapper(timed):
            response = self.get_response(request)
        total_ms = (time.monotonic() - started) * 1000
        cpu_ms = (time.thread_time() - cpu_started) * 1000

        db_ms = sum(queries)
        fastest_ms = min(queries) if queries else 0.0
        response["Server-Timing"] = (
            f"total;dur={total_ms:.0f}, "
            f'db;dur={db_ms:.0f};desc="{len(queries)} queries, fastest {fastest_ms:.0f} ms", '
            f"cpu;dur={cpu_ms:.0f}, "
            f"other;dur={total_ms - db_ms:.0f}"
        )
        logger.info(
            "Request timing",
            extra={
                "request_data": {
                    "route": request.path,
                    "total_ms": round(total_ms),
                    "db_ms": round(db_ms),
                    "queries": len(queries),
                    "fastest_query_ms": round(fastest_ms),
                    "cpu_ms": round(cpu_ms),
                },
                "request_id": getattr(request, "request_id", None),
            },
        )
        return response
