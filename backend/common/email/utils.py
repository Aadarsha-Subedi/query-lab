def normalize_email(email: str) -> str:
    """Canonical form used for lookups and storage: trimmed and lower-cased."""
    return email.strip().lower()


def mask_email(email: str) -> str:
    """j***@example.com: enough for the owner to recognise it, not to reuse it."""
    local, _, domain = email.partition("@")
    return f"{local[:1]}***@{domain}" if domain else "***"
