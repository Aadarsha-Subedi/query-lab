from typing import Any

from common.logger.constants import REDACTED, SENSITIVE_KEYS


def redact_sensitive_data(data: Any, keys: set[str] = SENSITIVE_KEYS) -> Any:
    """Recursively redact sensitive keys from a dict/list, case-insensitive
    key matching. Returns a new structure — never mutates the original."""

    if isinstance(data, dict):
        return {
            key: (
                REDACTED if key.lower() in keys else redact_sensitive_data(value, keys)
            )
            for key, value in data.items()
        }

    if isinstance(data, list):
        return [redact_sensitive_data(item, keys) for item in data]

    return data
