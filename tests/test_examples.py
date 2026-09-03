from __future__ import annotations

import ast
import json
import re
from pathlib import Path

ROOT = Path(__file__).parents[1]
EXAMPLES = ROOT / "examples"
EXPECTED_NOTEBOOKS = {
    "account_queries.ipynb",
    "cancel_order.ipynb",
    "order_queries.ipynb",
    "place_order.ipynb",
    "public_rest.ipynb",
    "websocket_stream.ipynb",
}


def _notebooks() -> list[Path]:
    return sorted(EXAMPLES.glob("*.ipynb"))


def test_readme_python_blocks_are_valid_standalone_syntax() -> None:
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    blocks = re.findall(r"```python\s*\n(.*?)```", readme, flags=re.DOTALL)
    assert blocks
    for number, source in enumerate(blocks, start=1):
        compile(source, f"README.md:python-block-{number}", "exec")


def test_examples_are_notebooks() -> None:
    assert {path.name for path in _notebooks()} == EXPECTED_NOTEBOOKS
    assert not list(EXAMPLES.glob("*.py"))


def test_notebook_code_cells_compile() -> None:
    for path in _notebooks():
        notebook = json.loads(path.read_text(encoding="utf-8"))
        for number, cell in enumerate(notebook["cells"], start=1):
            if cell["cell_type"] != "code":
                continue
            source = "".join(cell["source"])
            compile(
                source,
                f"{path.name}:cell-{number}",
                "exec",
                flags=ast.PyCF_ALLOW_TOP_LEVEL_AWAIT,
            )
            assert cell.get("execution_count") is None
            assert cell.get("outputs") == []


def test_notebooks_document_required_environment_variables() -> None:
    for path in _notebooks():
        notebook = json.loads(path.read_text(encoding="utf-8"))
        markdown = "\n".join(
            "".join(cell["source"]) for cell in notebook["cells"] if cell["cell_type"] == "markdown"
        )
        assert "Required environment variables" in markdown
