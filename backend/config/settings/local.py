"""Local development in Docker Compose. Values still come from `backend/.env`."""

from config.settings.base import *  # noqa: F403

# Adds the dev-only OAuth test page at /dev/ (see accounts/dev.py).
ROOT_URLCONF = "config.urls_local"
