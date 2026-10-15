"""Zero-QtWidgets policy.

Nothing may import the widgets package, and only `gui/tray.py` may touch
QtWidgets: QSystemTrayIcon is a QObject (not a QWidget), constructs fine
on a QGuiApplication and is the only prepackaged status-icon host that
does not mean reimplementing StatusNotifierItem by hand.
"""

import ast
from pathlib import Path

ROOT = Path(__file__).parent.parent
#: relative path -> QtWidgets names it may import ("*" = whole module).
ALLOWED = {"src/tkarcade/gui/tray.py": {"QSystemTrayIcon"}}


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


def _qtwidgets_names(path: Path) -> list[str]:
    """Names taken from PySide6.QtWidgets ("*" for the whole module)."""
    names: list[str] = []
    tree = ast.parse(path.read_bytes())
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom):
            if node.module == "PySide6.QtWidgets":
                names += [alias.name for alias in node.names]
            elif node.module == "PySide6":
                names += ["*" for alias in node.names if alias.name == "QtWidgets"]
        elif isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name == "PySide6.QtWidgets" or alias.name.startswith("PySide6.QtWidgets."):
                    names.append("*")
    return names


def _live_python_files():
    for base in ("src", "tests", "scripts"):
        yield from sorted((ROOT / base).rglob("*.py"))


def test_no_qtwidgets_outside_the_tray_controller():
    offenders = []
    for path in _live_python_files():
        rel = str(path.relative_to(ROOT))
        allowed = ALLOWED.get(rel, set())
        offenders += [f"{rel}: {name}" for name in _qtwidgets_names(path) if name not in allowed]
    assert offenders == []


def test_no_widgets_package_imports():
    offenders = [
        str(path.relative_to(ROOT))
        for path in _live_python_files()
        if any("widgets" in t.split(".") for t in _import_targets(path))
    ]
    assert offenders == []
