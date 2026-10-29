"""Request correlation: one id per request, visible in every log line and in
the `X-Request-ID` response header."""

import logging
import re
import uuid
from collections.abc import Callable
from contextvars import ContextVar

from django.http import HttpRequest, HttpResponse

REQUEST_ID_HEADER = "X-Request-ID"
_VALID_ID = re.compile(r"^[A-Za-z0-9._-]{8,64}$")

request_id_var: ContextVar[str | None] = ContextVar("request_id", default=None)
user_id_var: ContextVar[str | None] = ContextVar("user_id", default=None)


def current_request_id() -> str | None:
    return request_id_var.get()


def new_request_id() -> str:
    return uuid.uuid4().hex


def accept_request_id(candidate: str | None) -> str:
    """Use the caller's id only when it looks like one, otherwise make our own
    (so a client cannot inject odd characters into logs)."""
    if candidate and _VALID_ID.match(candidate):
        return candidate
    return new_request_id()


class RequestIdFilter(logging.Filter):
    """Stamps every log record with the current request and user ids."""

    def filter(self, record: logging.LogRecord) -> bool:
        if getattr(record, "request_id", None) is None:
            record.request_id = request_id_var.get()
        if getattr(record, "user_id", None) is None:
            record.user_id = user_id_var.get()
        return True


class RequestIdMiddleware:
    """First middleware: assigns the id, echoes it on the response and clears
    the context afterwards."""

    def __init__(self, get_response: Callable[[HttpRequest], HttpResponse]) -> None:
        self.get_response = get_response

    def __call__(self, request: HttpRequest) -> HttpResponse:
        request_id = accept_request_id(request.headers.get(REQUEST_ID_HEADER))
        request.request_id = request_id  # type: ignore[attr-defined]
        id_token = request_id_var.set(request_id)
        user_token = user_id_var.set(None)
        try:
            response = self.get_response(request)
        finally:
            request_id_var.reset(id_token)
            user_id_var.reset(user_token)
        response[REQUEST_ID_HEADER] = request_id
        return response


class UserContextMiddleware:
    """After authentication: remembers who the request is for in the logs
    (user id only, never email or IP)."""

    def __init__(self, get_response: Callable[[HttpRequest], HttpResponse]) -> None:
        self.get_response = get_response

    def __call__(self, request: HttpRequest) -> HttpResponse:
        user = getattr(request, "user", None)
        if user is not None and user.is_authenticated:
            user_id_var.set(str(user.pk))
        return self.get_response(request)
