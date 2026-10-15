"""Bundled application icons for the GUI (QtGui only, never QtWidgets).

Same two styles the packaged icons ship (normal + monochrome tray
variant). Kept here rather than in the parked widgets reference so the
tray stops importing that package.
"""

from __future__ import annotations

from pathlib import Path

#: Theme names tried, in order, when the bundled files are missing (an
#: unpackaged source tree is the only realistic case).
_THEME_FALLBACKS = ("tkarcade", "computer")


def icon_path(style: str = "normal") -> Path | None:
    """Absolute SVG path for a style, or None when missing."""
    name = "tkarcade-mono.svg" if style == "mono" else "tkarcade.svg"
    path = Path(__file__).resolve().parent.parent / "icons" / name
    try:
        return path if path.is_file() else None
    except Exception:
        return None


def app_icon(style: str = "normal"):
    """QIcon for a style, falling back to the theme entry.

    The widgets reference fell back to the QtWidgets style's computer
    icon; the package installs the same name into hicolor, so the theme
    lookup covers it without pulling QtWidgets in.
    """
    from PySide6.QtGui import QIcon

    path = icon_path(style)
    if path is not None:
        icon = QIcon(str(path))
        if not icon.isNull():
            return icon
    for name in _THEME_FALLBACKS:
        icon = QIcon.fromTheme(name)
        if not icon.isNull():
            return icon
    return QIcon()
