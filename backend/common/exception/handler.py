"""Ninja exception handlers: every error leaves the API in the same envelope
(see common.response.domain). Unknown exceptions are not caught, so Django
returns its normal 500 and the traceback reaches the logs."""

import logging
from typing import Any

from django.core.exceptions import PermissionDenied as DjangoPermissionDenied
from django.http import Http404, HttpRequest, HttpResponse
from ninja import NinjaAPI
from ninja.errors import AuthenticationError, HttpError, Throttled
from ninja.errors import ValidationError as NinjaValidationError

from common.exception.domain import AppException
from common.response.domain import error_body

logger = logging.getLogger(__name__)

_CODES = {
    400: "bad_request",
    401: "authentication_denied",
    403: "permission_denied",
    404: "not_found",
    405: "method_not_allowed",
    409: "conflict",
    415: "unsupported_media_type",
    422: "validation_error",
    429: "throttled",
}


def flatten_validation_errors(errors: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Pydantic's [{loc: ("body", "payload", "email"), msg}] as [{field, message}].
    The request part ("body", "query", ...) is dropped from the field path."""
    flat = []
    for error in errors:
        loc = [str(part) for part in error.get("loc", ())]
        field = ".".join(loc[2:] if len(loc) > 2 else loc[1:]) or None
        flat.append({"field": field, "message": str(error.get("msg", ""))})
    return flat


def _respond(
    api: NinjaAPI,
    request: HttpRequest,
    status: int,
    message: str,
    code: str | None = None,
    errors: list[dict[str, Any]] | None = None,
) -> HttpResponse:
    return api.create_response(
        request,
        error_body(message, code or _CODES.get(status, "error"), status, errors),
        status=status,
    )


def install_exception_handlers(api: NinjaAPI) -> None:
    @api.exception_handler(AppException)
    def app_exception(request: HttpRequest, exc: AppException) -> HttpResponse:
        response = _respond(
            api, request, exc.status_code, exc.message, exc.error_code, exc.errors
        )
        for name, value in exc.headers.items():
            response[name] = value
        return response

    @api.exception_handler(NinjaValidationError)
    def validation_error(
        request: HttpRequest, exc: NinjaValidationError
    ) -> HttpResponse:
        return _respond(
            api,
            request,
            422,
            "Validation failed.",
            errors=flatten_validation_errors(list(exc.errors)),
        )

    @api.exception_handler(AuthenticationError)
    def authentication_error(
        request: HttpRequest, exc: AuthenticationError
    ) -> HttpResponse:
        return _respond(
            api, request, 401, "You are not authenticated to perform this action."
        )

    @api.exception_handler(Throttled)
    def throttled(request: HttpRequest, exc: Throttled) -> HttpResponse:
        # ninja adds the Retry-After header to this response itself.
        return _respond(api, request, 429, "Too many requests. Please try again later.")

    @api.exception_handler(HttpError)
    def http_error(request: HttpRequest, exc: HttpError) -> HttpResponse:
        return _respond(api, request, exc.status_code, str(exc))

    @api.exception_handler(Http404)
    def not_found(request: HttpRequest, exc: Http404) -> HttpResponse:
        return _respond(api, request, 404, "Resource not found.")

    @api.exception_handler(DjangoPermissionDenied)
    def permission_denied(
        request: HttpRequest, exc: DjangoPermissionDenied
    ) -> HttpResponse:
        return _respond(
            api, request, 403, "You do not have permission to perform this action."
        )
