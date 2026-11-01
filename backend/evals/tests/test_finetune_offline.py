"""The web app must not import the training libraries (they never ship)."""

import re
from pathlib import Path

from django.conf import settings

BACKEND = Path(settings.BASE_DIR)
HEAVY = re.compile(
    r"^\s*(?:import|from)\s+(?:torch|transformers|peft|trl|bitsandbytes|wandb)\b",
    re.MULTILINE,
)


def test_no_module_imports_a_training_library() -> None:
    offenders = [
        str(path.relative_to(BACKEND))
        for path in BACKEND.rglob("*.py")
        if ".venv" not in path.parts and HEAVY.search(path.read_text())
    ]
    # Test files mention the names inside strings; only real imports count.
    assert [p for p in offenders if "/tests/" not in p] == []
