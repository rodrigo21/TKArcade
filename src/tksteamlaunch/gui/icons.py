"""Bundled application icons (normal + monochrome tray variant)."""

from __future__ import annotations

from pathlib import Path


def icon_path(style: str = "normal") -> Path | None:
    """Absolute SVG path for a style, or None when missing."""
    name = "tksteamlaunch-mono.svg" if style == "mono" else "tksteamlaunch.svg"
    path = Path(__file__).resolve().parent.parent / "icons" / name
    try:
        return path if path.is_file() else None
    except Exception:
        return None


def app_icon(style: str = "normal"):
    """QIcon for a style, falling back to a standard theme icon."""
    from PySide6.QtGui import QIcon

    path = icon_path(style)
    if path is not None:
        icon = QIcon(str(path))
        if not icon.isNull():
            return icon
    from PySide6.QtWidgets import QApplication, QStyle

    app = QApplication.instance()
    if app is not None:
        return app.style().standardIcon(QStyle.StandardPixmap.SP_ComputerIcon)
    return QIcon()
