"""Test settings: load `backend/.env.test` over whatever the process has, so a
test run never picks up the developer's real email or OAuth credentials."""

from pathlib import Path

import environ

environ.Env.read_env(
    Path(__file__).resolve().parent.parent.parent / ".env.test", overwrite=True
)

from config.settings.base import *  # noqa: E402, F403

# Hashing cost is irrelevant in tests and makes every login slow.
PASSWORD_HASHERS = ["django.contrib.auth.hashers.MD5PasswordHasher"]
