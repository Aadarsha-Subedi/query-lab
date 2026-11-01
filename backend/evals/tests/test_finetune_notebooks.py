"""The Colab notebooks are committed clean: valid, no outputs, no secrets, and the
code cells compile (shell lines aside)."""

import ast
import json
from pathlib import Path

import pytest
from django.conf import settings

FOLDER = Path(settings.BASE_DIR) / "finetune" / "colab"
NOTEBOOKS = sorted(FOLDER.glob("*.ipynb"))


def test_both_notebooks_exist() -> None:
    assert [p.name for p in NOTEBOOKS] == ["predict.ipynb", "train.ipynb"]


@pytest.mark.parametrize("path", NOTEBOOKS, ids=lambda p: p.name)
def test_notebook_is_clean_and_compiles(path: Path) -> None:
    notebook = json.loads(path.read_text())
    code = [c for c in notebook["cells"] if c["cell_type"] == "code"]
    assert code
    for cell in code:
        assert cell["outputs"] == []
        assert cell["execution_count"] is None
        source = "".join(
            line for line in cell["source"] if not line.lstrip().startswith("!")
        )
        ast.parse(source)
    assert "hf_" not in path.read_text()
