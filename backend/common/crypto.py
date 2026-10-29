"""Symmetric encryption for secrets stored in the database (for example a
user's own LLM API key). Keys come from settings, never from code."""

from cryptography.fernet import Fernet, InvalidToken, MultiFernet
from django.conf import settings

from common.exception.domain import ServiceUnavailableException

NOT_CONFIGURED_MESSAGE = "Encryption is not configured."
NOT_CONFIGURED_CODE = "encryption_not_configured"
INVALID_KEY_MESSAGE = "An encryption key is invalid."
INVALID_KEY_CODE = "encryption_key_invalid"


def _fernet() -> MultiFernet:
    """The first configured key encrypts; every key can decrypt, so a new key
    is rotated in by putting it first."""
    keys = settings.ENCRYPTION_KEYS
    if not keys:
        raise ServiceUnavailableException(
            NOT_CONFIGURED_MESSAGE, error_code=NOT_CONFIGURED_CODE
        )
    try:
        return MultiFernet([Fernet(key.encode()) for key in keys])
    except ValueError:
        # Say what is wrong without echoing the key.
        raise ServiceUnavailableException(
            INVALID_KEY_MESSAGE, error_code=INVALID_KEY_CODE
        ) from None


def encrypt(plain: str) -> str:
    return _fernet().encrypt(plain.encode()).decode()


def decrypt(token: str) -> str:
    return _fernet().decrypt(token.encode()).decode()


def rotate(token: str) -> str:
    """Re-encrypt `token` with the first key."""
    return _fernet().rotate(token.encode()).decode()


__all__ = ["InvalidToken", "decrypt", "encrypt", "rotate"]
