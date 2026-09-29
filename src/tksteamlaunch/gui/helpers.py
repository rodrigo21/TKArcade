"""Shared GUI helpers (PySide6)."""

from __future__ import annotations

import os
import shutil
import subprocess

from PySide6.QtCore import QUrl
from PySide6.QtGui import QDesktopServices


def open_path(path: str) -> bool:
    """Open a file/folder with the desktop default app, with fallbacks."""
    if QDesktopServices.openUrl(QUrl.fromLocalFile(path)):
        return True
    if shutil.which("xdg-open"):
        try:
            subprocess.Popen(["xdg-open", path])
            return True
        except Exception:
            pass
    editor = os.environ.get("EDITOR", "").strip() or os.environ.get("VISUAL", "").strip()
    if editor:
        try:
            subprocess.Popen([editor, path])
            return True
        except Exception:
            pass
    return False


def apply_default_size(widget, fallback: tuple[int, int] = (820, 520)) -> None:
    """Half the available width, full available height, centered.

    availableGeometry() already excludes panels/taskbars. The window
    manager may still constrain the result.
    """
    from PySide6.QtWidgets import QApplication

    screen = QApplication.primaryScreen()
    if screen is None:
        widget.resize(*fallback)
        return
    area = screen.availableGeometry()
    widget.resize(max(640, area.width() // 2), max(480, area.height()))
    frame = widget.frameGeometry()
    frame.moveCenter(area.center())
    widget.move(frame.topLeft())
