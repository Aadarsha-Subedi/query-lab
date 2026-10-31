"""Typed application exceptions. Each carries its HTTP status and a stable
error code; the ninja exception handler turns them into the error envelope."""


class AppException(Exception):
    status_code = 500
    message = "An unexpected error occurred."
    error_code = "internal_error"
    # 429 only: seconds until a retry can work, when waiting helps at all.
    retry_after: int | None = None

    def __init__(
        self,
        message: str | None = None,
        errors: list[dict] | None = None,
        error_code: str | None = None,
        headers: dict[str, str] | None = None,
    ):
        self.message = message or self.message
        self.errors = errors or []
        self.error_code = error_code or self.error_code
        self.headers = headers or {}
        super().__init__(self.message)


# ── 4xx: Request / Input problems ──────────────────────────────


class BadRequestException(AppException):
    status_code = 400
    message = "The request was malformed or invalid."
    error_code = "bad_request"


class ValidationException(AppException):
    status_code = 400
    message = "Validation failed."
    error_code = "validation_error"


class UnprocessableEntityException(AppException):
    status_code = 422
    message = "The request was well-formed but semantically invalid."
    error_code = "unprocessable_entity"


# ── 4xx: Auth / Access ─────────────────────────────────────────


class AuthenticationDeniedException(AppException):
    status_code = 401
    message = "You are not authenticated to perform this action."
    error_code = "authentication_denied"


class InvalidTokenException(AppException):
    status_code = 401
    message = "The provided token is invalid."
    error_code = "invalid_token"


class TokenExpiredException(AppException):
    status_code = 401
    message = "The provided token has expired."
    error_code = "token_expired"


class PermissionDeniedException(AppException):
    status_code = 403
    message = "You do not have permission to perform this action."
    error_code = "permission_denied"


# ── 4xx: Resource state ────────────────────────────────────────


class NotFoundException(AppException):
    status_code = 404
    message = "Resource not found."
    error_code = "not_found"


class ConflictException(AppException):
    status_code = 409
    message = "Resource conflict."
    error_code = "conflict"


class DuplicateResourceException(AppException):
    status_code = 409
    message = "A resource with these details already exists."
    error_code = "duplicate_resource"


class ResourceLockedException(AppException):
    status_code = 423
    message = "This resource is currently locked and cannot be modified."
    error_code = "resource_locked"


class StaleDataException(AppException):
    status_code = 409
    message = "This resource has been modified since you last fetched it."
    error_code = "stale_data"


# ── 4xx: Rate limiting / payload ───────────────────────────────


class ThrottledException(AppException):
    status_code = 429
    message = "Too many requests. Please try again later."
    error_code = "throttled"


class PayloadTooLargeException(AppException):
    status_code = 413
    message = "The request payload is too large."
    error_code = "payload_too_large"


# ── 5xx: Server / infrastructure ───────────────────────────────


class ServiceUnavailableException(AppException):
    status_code = 503
    message = "Service is temporarily unavailable. Please try again later."
    error_code = "service_unavailable"


class ExternalServiceException(AppException):
    status_code = 502
    message = "An upstream service failed to respond correctly."
    error_code = "external_service_error"


class DatabaseException(AppException):
    status_code = 500
    message = "A database error occurred."
    error_code = "database_error"


class ConfigurationException(AppException):
    status_code = 500
    message = "A server configuration error occurred."
    error_code = "configuration_error"


class NotImplementedException(AppException):
    status_code = 501
    message = "This feature is not yet implemented."
    error_code = "not_implemented"
