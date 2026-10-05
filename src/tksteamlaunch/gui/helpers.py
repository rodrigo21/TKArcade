"""Shared GUI helpers (PySide6)."""

from __future__ import annotations

import os
import shutil
import subprocess

from PySide6.QtCore import QLocale, QTranslator, QUrl
from PySide6.QtGui import QDesktopServices

_translators: list = []  # kept alive: Qt unloads GC'd translators

#: Autonyms for shipped locales (never translated by definition).
LANGUAGE_NAMES = {"pt_BR": "Português (Brasil)"}


def preferred_language() -> str:
    """GUI language from preferences ("" on any error: system default)."""
    try:
        from .. import config as cfgmod

        return cfgmod.load_preferences().language
    except Exception:
        return ""


def available_languages() -> list[tuple[str, str]]:
    """Shipped [(code, label)] for the language picker (English included)."""
    codes: set[str] = set()
    try:
        from importlib import resources

        pkg = resources.files("tksteamlaunch.translations")
        for entry in pkg.iterdir():
            name = entry.name
            if name.startswith("tksteamlaunch_") and name.endswith(".qm"):
                codes.add(name[len("tksteamlaunch_") : -len(".qm")])
    except Exception:
        pass
    out = [("en", "English")]
    out.extend((code, LANGUAGE_NAMES.get(code, code)) for code in sorted(codes))
    return out


def install_translations(app, language: str = "") -> str:
    """Install the matching bundled translator, if any.

    language: "" or "system" follows the OS locale, "en" forces
    English, anything else is tried as a locale code first.
    Returns the loaded locale name or "". English (and unknown
    locales) run untranslated. Safe to call repeatedly.
    """
    from importlib import resources

    choice = (language or "").strip()
    if choice.lower() in ("en", "c"):
        return ""
    if choice and choice != "system":
        candidates = [choice]
    else:
        locale = QLocale.system().name()
        candidates = [locale]
        if "_" in locale:
            candidates.append(locale.split("_")[0])
    try:
        pkg_files = resources.files("tksteamlaunch.translations")
    except Exception:
        return ""
    for lang in candidates:
        name = f"tksteamlaunch_{lang}.qm"
        try:
            ref = pkg_files.joinpath(name)
            if not ref.is_file():
                continue
            with resources.as_file(ref) as path:
                translator = QTranslator()
                if not translator.load(str(path)):
                    continue
        except Exception:
            continue
        if not any(t.language() == translator.language() for t in _translators):
            app.installTranslator(translator)
            _translators.append(translator)
            return lang
    return ""


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
