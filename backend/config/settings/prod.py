"""Production (Cloudflare Container behind Cloudflare's proxy)."""

from config.settings.base import *  # noqa: F403

SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True
SECURE_CONTENT_TYPE_NOSNIFF = True
