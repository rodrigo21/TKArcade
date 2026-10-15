"""System tray icon with recent games (QtWidgets, GUI-only).

Owned by kirigami_app when the prefs enable it; rebuilt in place by
apply() (never deleteLater + recreate from a menu slot). Mirrors the
widgets tray: Show/Hide, recent launches, Preferences..., About...,
Quit, plus the close/minimize-to-tray flags the QML shell reads back
through model slots. The Global Defaults entry returns with the
defaults UI (deferred with Clone/Reset/Defaults).
"""

from __future__ import annotations


class TrayController:
    """Owns the QSystemTrayIcon; QtWidgets imports stay inside methods."""

    def __init__(self, model, toggle_visible, open_prefs, open_about, open_defaults=None):
        self._model = model
        self._toggle_visible = toggle_visible
        self._open_prefs = open_prefs
        self._open_about = open_about
        self._open_defaults = open_defaults
        self.tray = None
        self.menu = None

    def apply(self) -> bool:
        """(Re)build per prefs. Returns True when a tray is shown."""
        from PySide6.QtWidgets import QSystemTrayIcon

        from .. import config as cfgmod
        from . import icons as iconsmod

        try:
            prefs = cfgmod.load_preferences()
        except Exception:
            prefs = None
        try:
            available = bool(QSystemTrayIcon.isSystemTrayAvailable())
        except Exception:
            available = False
        if prefs is None or not prefs.tray_enable or not available:
            self.drop()
            return False
        if self.tray is None:
            from PySide6.QtWidgets import QMenu

            tray = QSystemTrayIcon(iconsmod.app_icon(prefs.tray_icon), None)
            tray.setToolTip("TKArcade")
            menu = QMenu(None)
            menu.aboutToShow.connect(self._rebuild_menu)
            self._rebuild_menu(menu)
            tray.setContextMenu(menu)
            tray.activated.connect(self._on_activated)
            tray.show()
            self.tray = tray
            self.menu = menu
        else:
            # Update in place: freshness comes from aboutToShow
            # rebuilding before every open.
            self.tray.setIcon(iconsmod.app_icon(prefs.tray_icon))
        return True

    def drop(self) -> None:
        """Hide and release the tray icon, if any."""
        tray, self.tray = self.tray, None
        self.menu = None
        if tray is not None:
            try:
                tray.hide()
                tray.deleteLater()
            except RuntimeError:
                pass  # already deleted C++ object

    def recent_games(self, limit: int) -> list:
        """Recent launches as (appid, label) rows, newest first."""
        try:
            rows = self._model.historySummary()
        except Exception:
            return []
        out = []
        for row in (rows or [])[: max(0, int(limit or 0))]:
            try:
                out.append((row["appid"], f"{row['name']} ({row['total']})"))
            except (KeyError, TypeError):
                continue
        return out

    def _rebuild_menu(self, menu=None) -> None:
        from PySide6.QtWidgets import QApplication

        from .. import config as cfgmod

        menu = menu if menu is not None else self.menu
        if menu is None:
            return
        menu.clear()
        show_action = menu.addAction("Show / Hide")
        show_action.triggered.connect(lambda _checked=False: self._toggle_visible())
        try:
            prefs = cfgmod.load_preferences()
        except Exception:
            prefs = None
        if prefs is not None and prefs.tray_quick_launch:
            recents = self.recent_games(prefs.tray_quick_count)
            if recents:
                menu.addSeparator()
                for appid, label in recents:
                    act = menu.addAction(label)
                    act.triggered.connect(lambda _checked=False, a=appid: self._model.play(a))
        menu.addSeparator()
        if self._open_defaults is not None:
            defaults_action = menu.addAction("Global Defaults...")
            defaults_action.triggered.connect(lambda _checked=False: self._open_defaults())
        prefs_action = menu.addAction("Preferences...")
        prefs_action.triggered.connect(lambda _checked=False: self._open_prefs())
        about_action = menu.addAction("About...")
        about_action.triggered.connect(lambda _checked=False: self._open_about())
        menu.addSeparator()
        quit_action = menu.addAction("Quit")
        app = QApplication.instance()
        if app is not None:
            quit_action.triggered.connect(app.quit)

    def _on_activated(self, reason) -> None:
        from PySide6.QtWidgets import QSystemTrayIcon

        if reason in (
            QSystemTrayIcon.ActivationReason.Trigger,
            QSystemTrayIcon.ActivationReason.DoubleClick,
        ):
            self._toggle_visible()
