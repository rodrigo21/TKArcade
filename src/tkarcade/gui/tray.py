"""System tray icon with recent games (GUI-only).

Owned by kirigami_app when the prefs enable it; rebuilt in place by
apply() (never deleteLater + recreate from a menu slot).

Its only QtWidgets use is QSystemTrayIcon itself (a QObject, not a
QWidget): the context menu is a QML Menu, because QtWidgets' QMenu would
drag the entire menu through the widget toolkit. The icon does need the
shell's QApplication though -- on Plasma the platform theme builds a
KStatusNotifierItem, whose constructor creates a QMenu (see
kirigami_app.main and TODO.md).
The entries live in main.qml and come back through model.trayAction(),
which kirigami_app wires to the shell: Show / Hide, recent launches,
Preferences..., About..., Quit, plus the close/minimize-to-tray flags the
QML shell reads back through model slots. The Global Defaults entry
appears once a defaults UI registers itself.
"""

from __future__ import annotations

import logging

log = logging.getLogger("tkarcade.kirigami")


class TrayController:
    """Owns the QSystemTrayIcon; QtWidgets imports stay inside methods."""

    def __init__(self, model):
        self._model = model
        self.tray = None

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
            from PySide6.QtWidgets import QSystemTrayIcon

            tray = QSystemTrayIcon(iconsmod.app_icon(prefs.tray_icon), None)
            tray.setToolTip("TKArcade")
            tray.activated.connect(self._on_activated)
            tray.show()
            self.tray = tray
        else:
            # Update in place: the menu (QML) rebuilds its recents on
            # every open, so only the icon style can change here.
            self.tray.setIcon(iconsmod.app_icon(prefs.tray_icon))
        return True

    def drop(self) -> None:
        """Hide and release the tray icon, if any."""
        tray, self.tray = self.tray, None
        if tray is not None:
            try:
                tray.hide()
                tray.deleteLater()
            except RuntimeError:
                pass  # already deleted C++ object

    def click(self) -> None:
        """Left click / double click: show or hide the shell."""
        self._model.trayAction("toggle")

    def open_menu(self) -> None:
        """Right click: ask QML to open the menu at the icon."""
        x = y = None
        try:
            # The host reports the icon rectangle; the menu hangs from
            # its bottom edge. Empty when there is no host (offscreen,
            # tests): fall back to the cursor, which is where the user
            # just clicked.
            rect = self.tray.geometry() if self.tray is not None else None
            if rect is not None and rect.width() > 0 and rect.height() > 0:
                x, y = rect.x(), rect.y() + rect.height()
        except Exception:
            x = y = None
        if x is None:
            from PySide6.QtGui import QCursor

            point = QCursor.pos()
            x, y = point.x(), point.y()
        try:
            self._model.requestTrayMenu(int(x), int(y))
        except Exception as e:
            log.warning("tray menu failed: %s", e)

    def _on_activated(self, reason) -> None:
        from PySide6.QtWidgets import QSystemTrayIcon

        reasons = QSystemTrayIcon.ActivationReason
        if reason == reasons.Context:
            self.open_menu()
        elif reason in (reasons.Trigger, reasons.DoubleClick):
            self.click()
