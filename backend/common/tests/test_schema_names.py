"""openapi.json keys schemas by class name, so two classes with one name silently become one."""

import ast
from collections import defaultdict
from pathlib import Path

BACKEND = Path(__file__).resolve().parents[2]
SCHEMA_BASES = {"Schema", "BaseModel"}


def _schema_classes() -> dict[str, list[str]]:
    found: dict[str, list[str]] = defaultdict(list)
    for path in BACKEND.glob("*/*schemas.py"):
        for node in ast.parse(path.read_text()).body:
            if isinstance(node, ast.ClassDef) and any(
                isinstance(base, ast.Name) and base.id in SCHEMA_BASES
                for base in node.bases
            ):
                found[node.name].append(str(path.relative_to(BACKEND)))
    return found


def test_no_two_api_schemas_share_a_class_name() -> None:
    clashes = {
        name: files for name, files in _schema_classes().items() if len(files) > 1
    }
    assert not clashes, (
        f"rename one of each pair, or openapi.json merges them: {clashes}"
    )
