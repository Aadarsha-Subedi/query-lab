from disposable_email_domains import blocklist
from django.conf import settings

from common.exception.domain import ValidationException


def is_disposable(email: str) -> bool:
    """True when the address is on a known throwaway-mail domain. A subdomain
    of a listed domain counts too (x@mx.yopmail.com)."""
    domain = email.rpartition("@")[2].strip().lower().rstrip(".")
    parts = domain.split(".")
    return any(".".join(parts[i:]) in blocklist for i in range(len(parts) - 1))


def ensure_not_disposable(
    email: str, *, field: str, message: str, error_code: str
) -> None:
    """Refuse a throwaway address when BLOCK_DISPOSABLE_EMAILS is on (prod)."""
    if settings.BLOCK_DISPOSABLE_EMAILS and is_disposable(email):
        raise ValidationException(
            errors=[{"field": field, "message": message}], error_code=error_code
        )
