"""Main window: list configured games + Steam library."""

from __future__ import annotations

import shutil
import subprocess
from collections.abc import Callable

from PySide6.QtCore import QEvent, QSize, Qt, QThread, Signal
from PySide6.QtGui import (
    QBrush,
    QColor,
    QDesktopServices,
    QIcon,
    QKeySequence,
    QShortcut,
)
from PySide6.QtWidgets import (
    QApplication,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QStyle,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from .. import config as cfgmod
from .. import protondb as pdbmod
from .. import steam as steammod
from .. import xdg
from .game_dialog import GameDialog
from .helpers import open_path


class _ProtonDBWorker(QThread):
    """Refresh stale/missing ProtonDB tiers in the background."""

    fetched = Signal(str, dict)

    def __init__(self, appids: list[str], parent=None) -> None:
        super().__init__(parent)
        self._appids = appids

    def run(self) -> None:
        for appid in self._appids:
            if self.isInterruptionRequested():
                return
            try:
                data = pdbmod.refresh(appid)
            except Exception:
                continue
            if data:
                self.fetched.emit(appid, data)


class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("TKSteamLaunch")
        self.resize(820, 520)
        QShortcut(QKeySequence.StandardKey.Quit, self, self.close)

        central = QWidget()
        self.setCentralWidget(central)
        layout = QVBoxLayout(central)

        layout.addWidget(QLabel("Configured Games (double-click a game to edit its settings)"))
        self.table = QTableWidget(0, 3)
        self.table.setHorizontalHeaderLabels(["Game", "App ID", "ProtonDB"])
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeToContents)
        self.table.verticalHeader().setDefaultSectionSize(40)
        self.table.setIconSize(QSize(32, 32))
        self.table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.table.setSelectionBehavior(QTableWidget.SelectRows)
        self.table.itemDoubleClicked.connect(self._on_double_click)
        layout.addWidget(self.table, stretch=1)
        self._pdb_thread: _ProtonDBWorker | None = None
        self._tray = None
        self._tray_menu = None

        self.status = QLabel()
        layout.addWidget(self.status)

        layout.addLayout(
            self._button_row(
                (
                    ("Add Game...", self._add),
                    ("Edit...", self._edit_selected),
                    ("Remove", self._remove_selected),
                    ("History...", self._show_history),
                    ("Reload", self.refresh),
                )
            )
        )
        layout.addLayout(
            self._button_row(
                (
                    ("Copy Launch Options", self._copy_launch),
                    ("Open Ludusavi...", self._open_ludusavi),
                    ("Global Defaults...", self._edit_defaults),
                    ("Preferences...", self._edit_preferences),
                    ("Open Logs Folder", self._open_logs),
                    ("Export...", self._export_configs),
                    ("Import...", self._import_configs),
                )
            )
        )
        self.refresh()
        self._apply_tray()

    @staticmethod
    def _button_row(buttons: tuple[tuple[str, Callable[[], None]], ...]) -> QHBoxLayout:
        """Build a centered button row; append entries to add future actions."""
        row = QHBoxLayout()
        row.addStretch(1)
        for label, slot in buttons:
            b = QPushButton(label)
            b.clicked.connect(slot)
            row.addWidget(b)
        row.addStretch(1)
        return row

    def refresh(self) -> None:
        self._stop_pdb_worker()
        self.table.setRowCount(0)
        names = {a: n for a, n in steammod.list_games()}
        fallback = self.style().standardIcon(QStyle.StandardPixmap.SP_MediaPlay)
        appids = cfgmod.list_appids()
        self.table.setRowCount(len(appids))
        need_fetch: list[str] = []
        for row, appid in enumerate(appids):
            name_item = QTableWidgetItem(names.get(appid, appid))
            name_item.setData(Qt.ItemDataRole.UserRole, appid)
            icon_path = steammod.find_game_icon(appid)
            name_item.setIcon(QIcon(str(icon_path)) if icon_path else fallback)
            self.table.setItem(row, 0, name_item)
            self.table.setItem(row, 1, QTableWidgetItem(appid))
            data, fresh = pdbmod.cached(appid)
            if data:
                self._set_tier_cell(row, appid, data)
            if not fresh:
                need_fetch.append(appid)
        total_cfg = len(appids)
        total_steam = len(names)
        status = f"{total_cfg} configured · {total_steam} Steam games detected"
        self.status.setText(status)
        if need_fetch:
            self._pdb_thread = _ProtonDBWorker(need_fetch, self)
            self._pdb_thread.fetched.connect(self._on_protondb)
            self._pdb_thread.start()

    def _set_tier_cell(self, row: int, appid: str, data: dict) -> None:
        tier = str(data.get("tier", "")).lower()
        total = data.get("total", "?")
        item = QTableWidgetItem(tier.title() if tier else "?")
        if tier in pdbmod.TIER_STYLE:
            bg, fg = pdbmod.TIER_STYLE[tier]
            item.setBackground(QBrush(QColor(bg)))
            item.setForeground(QBrush(QColor(fg)))
        item.setToolTip(f"{tier.title()} · {total} reports — double-click for protondb.com")
        item.setData(Qt.ItemDataRole.UserRole, appid)
        self.table.setItem(row, 2, item)

    def _on_protondb(self, appid: str, data: dict) -> None:
        for row in range(self.table.rowCount()):
            item = self.table.item(row, 0)
            if item is not None and str(item.data(Qt.ItemDataRole.UserRole) or "") == appid:
                self._set_tier_cell(row, appid, data)
                return

    def _stop_pdb_worker(self) -> None:
        if self._pdb_thread is not None:
            if self._pdb_thread.isRunning():
                self._pdb_thread.requestInterruption()
                self._pdb_thread.wait(5000)
                if self._pdb_thread.isRunning():
                    # last resort: never destroy a running QThread (aborts).
                    self._pdb_thread.terminate()
                    self._pdb_thread.wait(2000)
            self._pdb_thread = None

    def closeEvent(self, event) -> None:
        prefs = cfgmod.load_preferences()
        if prefs.close_to_tray and self._tray is not None:
            event.ignore()
            self.hide()
            return
        self._stop_pdb_worker()
        super().closeEvent(event)

    def changeEvent(self, event) -> None:
        super().changeEvent(event)
        if event.type() == QEvent.Type.WindowStateChange and self.isMinimized():
            prefs = cfgmod.load_preferences()
            if prefs.minimize_to_tray and self._tray is not None:
                self.hide()

    def _toggle_visible(self) -> None:
        self.setVisible(not self.isVisible())
        if self.isVisible():
            self.setWindowState(self.windowState() & ~Qt.WindowState.WindowMinimized)
            self.activateWindow()

    def _apply_tray(self) -> None:
        from PySide6.QtWidgets import QMenu, QSystemTrayIcon

        from . import icons as iconsmod

        prefs = cfgmod.load_preferences()
        if not prefs.tray_enable or not QSystemTrayIcon.isSystemTrayAvailable():
            self._drop_tray()
            return
        if self._tray is None:
            tray = QSystemTrayIcon(iconsmod.app_icon(prefs.tray_icon), self)
            tray.setToolTip("TKSteamLaunch")
            menu = QMenu(self)
            show_action = menu.addAction("Show / Hide")
            show_action.triggered.connect(self._toggle_visible)
            defaults_action = menu.addAction("Global Defaults...")
            defaults_action.triggered.connect(self._edit_defaults)
            prefs_action = menu.addAction("Preferences...")
            prefs_action.triggered.connect(self._edit_preferences)
            menu.addSeparator()
            quit_action = menu.addAction("Quit")
            app = QApplication.instance()
            if app is not None:
                quit_action.triggered.connect(app.quit)
            tray.setContextMenu(menu)
            tray.activated.connect(self._on_tray_activated)
            tray.show()
            self._tray = tray
            self._tray_menu = menu
        else:
            # Update in place: never deleteLater + recreate from a menu slot.
            self._tray.setIcon(iconsmod.app_icon(prefs.tray_icon))

    def _drop_tray(self) -> None:
        tray, self._tray = self._tray, None
        self._tray_menu = None
        if tray is not None:
            try:
                tray.hide()
                tray.deleteLater()
            except RuntimeError:
                pass  # already deleted C++ object

    def _on_tray_activated(self, reason) -> None:
        from PySide6.QtWidgets import QSystemTrayIcon

        if reason in (
            QSystemTrayIcon.ActivationReason.Trigger,
            QSystemTrayIcon.ActivationReason.DoubleClick,
        ):
            self._toggle_visible()

    def _on_double_click(self, item: QTableWidgetItem) -> None:
        if item.column() == 2:
            appid = str(item.data(Qt.ItemDataRole.UserRole) or "")
            if appid:
                from PySide6.QtCore import QUrl

                QDesktopServices.openUrl(QUrl(pdbmod.GAME_URL.format(appid=appid)))
            return
        self._edit_selected()

    def _names(self) -> dict[str, str]:
        return {a: n for a, n in steammod.list_games()}

    def _selected_appid(self) -> str:
        row = self.table.currentRow()
        if row < 0:
            return ""
        item = self.table.item(row, 0)
        if not item:
            return ""
        return str(item.data(Qt.ItemDataRole.UserRole) or "")

    def _add(self) -> None:
        from PySide6.QtWidgets import QInputDialog

        # offer steam games first
        games = steammod.list_games()
        configured = set(cfgmod.list_appids())
        unconfigured = [(a, n) for a, n in games if a not in configured]
        if unconfigured:
            labels = [f"{n} [{a}]" for a, n in unconfigured]
            choice, ok = QInputDialog.getItem(self, "Add Game", "Steam game:", labels, 0, True)
            if ok and choice:
                import re

                m = re.search(r"\[(\d+)\]\s*$", choice)
                appid = m.group(1) if m else choice.strip()
                if not appid:
                    return
            else:
                return
        else:
            appid, ok = QInputDialog.getText(self, "Add Game", "Steam App ID:")
            if not ok or not appid.strip():
                return
            appid = appid.strip()
        dlg = GameDialog(self, appid, self._names().get(appid, ""))
        if dlg.exec():
            self.refresh()

    def _edit_selected(self) -> None:
        appid = self._selected_appid()
        if not appid:
            QMessageBox.information(self, "TKSteamLaunch", "Select a game first.")
            return
        dlg = GameDialog(self, appid, self._names().get(appid, ""))
        if dlg.exec():
            self.refresh()

    def _edit_defaults(self) -> None:
        dlg = GameDialog(self, defaults_mode=True)
        dlg.exec()

    def _edit_preferences(self) -> None:
        from .preferences_dialog import PreferencesDialog

        if PreferencesDialog(self).exec():
            self._apply_tray()

    def _show_history(self) -> None:
        from .history_dialog import HistoryDialog

        HistoryDialog(self).exec()

    def _open_logs(self) -> None:
        d = xdg.games_log_dir()
        try:
            d.mkdir(parents=True, exist_ok=True)
        except Exception:
            pass
        if not open_path(str(d)):
            QMessageBox.warning(self, "TKSteamLaunch", f"Could not open {d}.")

    def _export_configs(self) -> None:
        from PySide6.QtWidgets import QFileDialog

        path, _ = QFileDialog.getSaveFileName(
            self,
            "Export Configurations",
            "tksteamlaunch-configs.tar.gz",
            "Archives (*.tar.gz)",
        )
        if not path:
            return
        try:
            saved = cfgmod.export_configs(path)
        except (OSError, ValueError) as e:
            QMessageBox.warning(self, "TKSteamLaunch", f"Export failed: {e}")
            return
        self.status.setText(f"Exported to {saved}")

    def _import_configs(self) -> None:
        from PySide6.QtWidgets import QFileDialog

        path, _ = QFileDialog.getOpenFileName(
            self,
            "Import Configurations",
            "",
            "Archives (*.tar.gz)",
        )
        if not path:
            return
        try:
            imported = cfgmod.import_configs(path)
        except (OSError, ValueError) as e:
            QMessageBox.warning(self, "TKSteamLaunch", f"Import failed: {e}")
            return
        self.status.setText(f"Imported {len(imported)} game(s)")
        self.refresh()

    def _remove_selected(self) -> None:
        appid = self._selected_appid()
        if not appid:
            return
        r = QMessageBox.question(
            self, "TKSteamLaunch", f"Remove the configuration for App ID {appid}?"
        )
        if r == QMessageBox.StandardButton.Yes:
            try:
                cfgmod.game_file(appid).unlink(missing_ok=True)
            except Exception as e:
                QMessageBox.warning(self, "TKSteamLaunch", str(e))
            self.refresh()

    def _copy_launch(self) -> None:
        from PySide6.QtGui import QGuiApplication

        clipboard = QGuiApplication.clipboard()
        if clipboard is None:  # e.g. offscreen/minimal platform
            self.status.setText("Clipboard unavailable on this platform.")
            return
        clipboard.setText("tksteamlaunch %command%")
        self.status.setText("Launch options copied to clipboard: tksteamlaunch %command%")

    def _open_ludusavi(self) -> None:
        exe = shutil.which("ludusavi")
        if not exe:
            QMessageBox.warning(self, "TKSteamLaunch", "Ludusavi was not found in PATH.")
            return
        if "/flatpak/" in exe or "flatpak" in exe:
            QMessageBox.warning(
                self,
                "TKSteamLaunch",
                "Flatpak Ludusavi detected: it may not see Proton prefixes. "
                "Prefer the standalone binary.",
            )
        try:
            subprocess.Popen([exe])
        except Exception as e:
            QMessageBox.warning(self, "TKSteamLaunch", f"Could not open Ludusavi: {e}")
