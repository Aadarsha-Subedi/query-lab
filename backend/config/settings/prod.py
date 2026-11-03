"""Production (Cloudflare Container behind Cloudflare's proxy)."""

from config.settings.base import *  # noqa: F403

SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True
SECURE_CONTENT_TYPE_NOSNIFF = True

# Neon's pooled endpoints run PgBouncer in transaction mode, where a server-side cursor
# opened outside a transaction does not survive: QuerySet.iterator() must not use one.
for database in DATABASES.values():
    database["DISABLE_SERVER_SIDE_CURSORS"] = True
