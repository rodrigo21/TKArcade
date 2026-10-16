"""Zero-QtWidgets policy.

Nothing may import the widgets package. Three allowlisted names remain,
all application-level plumbing rather than UI: `QApplication` in
`gui/kirigami_app.py` (the Plasma platform theme supplies the tray icon
through a `KStatusNotifierItem`, whose constructor builds a `QMenu`, so a
`QGuiApplication` aborts inside `QSystemTrayIcon.show()`),
`QSystemTrayIcon` in `gui/tray.py` (it is a QObject) and the `QMenu` it
exports as the tray context menu (the Plasma SNI host only shows a menu
the app provides, never delivering `activated(Context)`). Every other
widget class -- `QDialog`, `QFileDialog`, ... -- stays banned.
"""

import ast
from pathlib import Path

ROOT = Path(__file__).parent.parent
#: relative path -> QtWidgets names it may import ("*" = whole module).
#: The conftest/app entries pin the trap: conftest builds the QApplication
#: the shell needs, and the app test constructs a bare widget to prove
#: widgets can be created at all (under a QGuiApplication that aborts the
#: interpreter, which is how the shell died on Plasma). The tray tests
#: build a real icon and inspect its native menu.
ALLOWED = {
    "src/tkarcade/gui/tray.py": {"QSystemTrayIcon", "QMenu"},
    "src/tkarcade/gui/kirigami_app.py": {"QApplication"},
    "src/tkarcade/gui/edit.py": {"QApplication"},
    "tests/conftest.py": {"QApplication"},
    "tests/test_kirigami_app.py": {"QApplication", "QWidget"},
    "tests/test_tray.py": {"QSystemTrayIcon", "QMenu"},
}


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


def test_no_qtwidgets_outside_the_allowlist():
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
