"""System tray icon with a native context menu (GUI-only).

Owned by kirigami_app when the prefs enable it; rebuilt in place by
apply() (never deleteLater + recreate from a menu slot).

QtWidgets use stays minimal: QSystemTrayIcon itself (a QObject, not a
QWidget) and the QMenu the host shows on right-click. The menu is native
on purpose -- on Plasma the SNI host only shows a context menu the app
exports through setContextMenu() and never delivers activated(Context)
without one, so the QML menu this replaces could never be opened from the
tray. The icon does need the shell's QApplication though -- on Plasma the
platform theme builds a KStatusNotifierItem, whose constructor creates a
QMenu (see kirigami_app.main and docs/QML-NOTES.md).

The entries dispatch through model.trayAction(): Show / Hide, recent
launches, Preferences..., About..., Quit, plus the close/minimize-to-tray
flags the QML shell reads back through model slots. The Global Defaults
entry appears once a defaults UI registers itself, and both it and the
recents are rebuilt on every open (aboutToShow), the freshness the QML
menu had. Labels go through the Python `TrayMenu` translation context
(fed to lupdate by scripts/refresh-translations.sh).
"""

from __future__ import annotations

import logging

log = logging.getLogger("tkarcade.kirigami")


class TrayController:
    """Owns the QSystemTrayIcon and its native context menu."""

    def __init__(self, model):
        self._model = model
        self.tray = None
        self.menu = None

    def is_available(self) -> bool:
        """Whether a tray host is present (tests override this seam)."""
        try:
            from PySide6.QtWidgets import QSystemTrayIcon

            return bool(QSystemTrayIcon.isSystemTrayAvailable())
        except Exception:
            return False

    def apply(self) -> bool:
        """(Re)build per prefs. Returns True when a tray is shown."""
        from .. import config as cfgmod
        from . import icons as iconsmod

        try:
            prefs = cfgmod.load_preferences()
        except Exception:
            prefs = None
        if prefs is None or not prefs.tray_enable or not self.is_available():
            self.drop()
            return False
        if self.tray is None:
            from PySide6.QtWidgets import QMenu, QSystemTrayIcon

            tray = QSystemTrayIcon(iconsmod.app_icon(prefs.tray_icon), None)
            tray.setToolTip("TKArcade")
            tray.activated.connect(self._on_activated)
            # The host owns showing this menu; Qt only exports it.
            menu = QMenu()
            menu.aboutToShow.connect(self.rebuild_menu)
            tray.setContextMenu(menu)
            tray.show()
            self.tray = tray
            self.menu = menu
            self.rebuild_menu()
        else:
            # Update in place: the menu rebuilds its recents on every
            # open, so only the icon style can change here.
            self.tray.setIcon(iconsmod.app_icon(prefs.tray_icon))
        return True

    def drop(self) -> None:
        """Hide and release the tray icon and its menu, if any."""
        tray, self.tray = self.tray, None
        menu, self.menu = self.menu, None
        if tray is not None:
            try:
                tray.hide()
                tray.deleteLater()
            except RuntimeError:
                pass  # already deleted C++ object
        if menu is not None:
            try:
                menu.deleteLater()
            except RuntimeError:
                pass

    def click(self) -> None:
        """Left click / double click: show or hide the shell."""
        self._dispatch("toggle")

    def rebuild_menu(self) -> None:
        """(Re)fill the context menu; fresh recents on every open.

        A native QMenu skips invisible actions outright (unlike the QQC2
        menu, which reserved a hidden entry's height), so the conditional
        entries are simply left out. Labels are translated through a
        `TrayMenu` context; the refresh script feeds this file to lupdate.
        """
        from PySide6.QtCore import QCoreApplication
        from PySide6.QtGui import QAction

        menu = self.menu
        if menu is None:
            return
        menu.clear()

        def add(name: str, text: str, action: str) -> None:
            item = QAction(text, menu)
            item.setObjectName(name)
            item.triggered.connect(lambda _checked=False, a=action: self._dispatch(a))
            menu.addAction(item)

        add("trayShowHide", QCoreApplication.translate("TrayMenu", "Show / Hide"), "toggle")
        recents = self._recents()
        if recents:
            menu.addSeparator()
            for index, (appid, label) in enumerate(recents):
                add("trayRecent" + str(index), label, "play:" + appid)
            menu.addSeparator()
        if self._defaults_available():
            add(
                "trayDefaults",
                QCoreApplication.translate("TrayMenu", "Global Defaults..."),
                "defaults",
            )
        add("trayPrefs", QCoreApplication.translate("TrayMenu", "Preferences..."), "prefs")
        add("trayAbout", QCoreApplication.translate("TrayMenu", "About..."), "about")
        menu.addSeparator()
        add("trayQuit", QCoreApplication.translate("TrayMenu", "Quit"), "quit")

    def _recents(self) -> list[tuple[str, str]]:
        try:
            rows = self._model.trayRecentGames() or []
        except Exception as e:
            log.warning("tray recents failed: %s", e)
            return []
        out = []
        for row in rows:
            try:
                out.append((str(row[0]), str(row[1])))
            except (IndexError, TypeError):
                continue
        return out

    def _defaults_available(self) -> bool:
        try:
            return bool(self._model.trayDefaultsAvailable())
        except Exception:
            return False

    def _dispatch(self, action: str) -> None:
        try:
            self._model.trayAction(action)
        except Exception as e:
            log.warning("tray action %s failed: %s", action, e)

    def _on_activated(self, reason) -> None:
        from PySide6.QtWidgets import QSystemTrayIcon

        reasons = QSystemTrayIcon.ActivationReason
        log.debug("tray activated: %s", reason)
        if reason in (reasons.Trigger, reasons.DoubleClick):
            self.click()
