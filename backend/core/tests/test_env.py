"""The keys the code reads must match `.env.example` (and `.env.test`)
exactly, and a missing key must stop the process."""

import os
import re
import subprocess
import sys
from pathlib import Path

from django.conf import settings

BACKEND = Path(settings.BASE_DIR)
SOURCE_DIRS = ["config", "core", "common", "accounts"]
READS = re.compile(
    r"""env\.(?:str|bool|int|float|list|path|db_url|cache_url)\(\s*["']([A-Z0-9_]+)["']"""
    r"""|os\.environ\[\s*["']([A-Z0-9_]+)["']\s*\]"""
    r"""|["']([A-Z0-9_]+)["'] not in os\.environ"""
)


def keys_in_env_file(path: Path) -> set[str]:
    keys = set()
    for line in path.read_text().splitlines():
        line = line.strip()
        if line and not line.startswith("#"):
            keys.add(line.split("=", 1)[0])
    return keys


def keys_read_by_code() -> set[str]:
    files = [BACKEND / "manage.py"]
    for folder in SOURCE_DIRS:
        files.extend(
            path
            for path in (BACKEND / folder).rglob("*.py")
            if "tests" not in path.parts
        )
    keys = set()
    for path in files:
        for match in READS.finditer(path.read_text()):
            keys.add(next(group for group in match.groups() if group))
    return keys


def test_env_example_lists_exactly_the_keys_the_code_reads() -> None:
    assert keys_in_env_file(BACKEND / ".env.example") == keys_read_by_code()


def test_env_test_has_the_same_keys_as_the_example() -> None:
    assert keys_in_env_file(BACKEND / ".env.test") == keys_in_env_file(
        BACKEND / ".env.example"
    )


def test_missing_key_stops_startup() -> None:
    env = {
        key: value
        for key, value in os.environ.items()
        if key not in keys_in_env_file(BACKEND / ".env.example")
    }
    for line in (BACKEND / ".env.test").read_text().splitlines():
        if line and not line.startswith("#") and not line.startswith("REDIS_URL="):
            key, value = line.split("=", 1)
            env[key] = value
    env["DJANGO_SETTINGS_MODULE"] = "config.settings.local"
    result = subprocess.run(
        [sys.executable, "-c", "import django; django.setup()"],
        cwd=BACKEND,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode != 0
    assert "Set the REDIS_URL environment variable" in result.stderr
