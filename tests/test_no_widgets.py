"""Zero-QtWidgets policy on the kirigami branch.

`src/tkarcade/widgets/` and `tests/gui_widgets_reference.py` are parked
reference only: nothing else may import QtWidgets or the widgets package.
"""

import ast
from pathlib import Path

ROOT = Path(__file__).parent.parent
PARKED_FILES = {"gui_widgets_reference.py"}


def _import_targets(path: Path) -> list[str]:
    targets: list[str] = []
    tree = ast.parse(path.read_bytes())
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module:
            prefix = "." * node.level
            targets.append(f"{prefix}{node.module}")
        elif isinstance(node, ast.Import):
            targets += [alias.name for alias in node.names]
    return targets


def _live_python_files():
    for base in ("src", "tests", "scripts"):
        for path in sorted((ROOT / base).rglob("*.py")):
            if "widgets" in path.parts or path.name in PARKED_FILES:
                continue
            yield path


def test_no_qtwidgets_outside_reference():
    offenders = [
        str(path.relative_to(ROOT))
        for path in _live_python_files()
        if any("QtWidgets" in t.split(".") for t in _import_targets(path))
    ]
    assert offenders == []


def test_no_widgets_package_imports_outside_reference():
    offenders = [
        str(path.relative_to(ROOT))
        for path in _live_python_files()
        if any("widgets" in t.split(".") for t in _import_targets(path))
    ]
    assert offenders == []
