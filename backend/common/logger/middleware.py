import json
import logging
import time
from collections.abc import Callable

from django.http import HttpRequest, HttpResponse

from common.logger.constants import SENSITIVE_QUERY_KEYS
from common.logger.redaction import redact_sensitive_data

logger = logging.getLogger("request")


class RequestLoggingMiddleware:
    """One log line per request: route, redacted headers/query/body, status and
    duration. Errors (4xx/5xx) log at ERROR so they stand out."""

    def __init__(self, get_response: Callable[[HttpRequest], HttpResponse]) -> None:
        self.get_response = get_response

    def get_view_name(self, request: HttpRequest) -> str | None:
        return (
            getattr(request.resolver_match, "view_name", None)
            if request.resolver_match
            else None
        )

    def get_request_body(self, request: HttpRequest) -> dict | None:
        if (request.content_type or "").startswith("multipart/"):
            return {"raw": "<multipart body>"}

        if not request.body:
            return None

        try:
            return json.loads(request.body)
        except (json.JSONDecodeError, UnicodeDecodeError):
            return {"raw": "<non-JSON body>"}

    def __call__(self, request: HttpRequest) -> HttpResponse:
        start = time.monotonic()

        request_body = self.get_request_body(request)

        response = self.get_response(request)

        duration_ms = round((time.monotonic() - start) * 1000, 2)

        log_data = {
            "method": request.method,
            "route": request.path,
            "view_name": self.get_view_name(request),
            "query_params": redact_sensitive_data(
                dict(request.GET), SENSITIVE_QUERY_KEYS
            ),
            "headers": redact_sensitive_data(dict(request.headers)),
            "body": redact_sensitive_data(request_body),
            "status_code": response.status_code,
            "duration_ms": duration_ms,
        }

        level = logging.ERROR if response.status_code >= 400 else logging.INFO

        logger.log(
            level,
            "Request handled",
            extra={
                "request_data": log_data,
                "request_id": getattr(request, "request_id", None),
            },
        )

        return response
