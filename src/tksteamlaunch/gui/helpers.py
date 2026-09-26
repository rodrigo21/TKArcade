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
