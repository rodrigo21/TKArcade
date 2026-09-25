"""Main window: list configured games + Steam library."""
from __future__ import annotations

import shutil
import subprocess
from collections.abc import Callable

from PySide6.QtCore import QSize
from PySide6.QtGui import QIcon, QKeySequence, QShortcut
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QStyle,
    QVBoxLayout,
    QWidget,
)

from .. import config as cfgmod
from .. import steam as steammod
from .. import xdg
from .game_dialog import GameDialog
from .helpers import open_path


class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("TKSteamLaunch")
        self.resize(760, 520)
        QShortcut(QKeySequence.StandardKey.Quit, self, self.close)

        central = QWidget()
        self.setCentralWidget(central)
        layout = QVBoxLayout(central)

        layout.addWidget(QLabel("Configured Games (double-click a game to edit its settings)"))
        self.list = QListWidget()
        self.list.setIconSize(QSize(32, 32))
        self.list.itemDoubleClicked.connect(self._edit_selected)
        layout.addWidget(self.list, stretch=1)

        self.status = QLabel()
        layout.addWidget(self.status)

        layout.addLayout(self._button_row((
            ("Add Game...", self._add),
            ("Edit...", self._edit_selected),
            ("Remove", self._remove_selected),
            ("History...", self._show_history),
            ("Reload", self.refresh),
        )))
        layout.addLayout(self._button_row((
            ("Copy Launch Options", self._copy_launch),
            ("Open Ludusavi...", self._open_ludusavi),
            ("Global Defaults...", self._edit_defaults),
            ("Open Logs Folder", self._open_logs),
            ("Export...", self._export_configs),
            ("Import...", self._import_configs),
        )))
        self.refresh()

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
        self.list.clear()
        names = {a: n for a, n in steammod.list_games()}
        fallback = self.style().standardIcon(QStyle.StandardPixmap.SP_MediaPlay)
        for appid in cfgmod.list_appids():
            label = f"{names.get(appid, appid)}  [{appid}]"
            item = QListWidgetItem(label, self.list)
            item.setData(32, appid)
            icon_path = steammod.find_game_icon(appid)
            item.setIcon(QIcon(str(icon_path)) if icon_path else fallback)
            item.setSizeHint(QSize(200, 48))
        total_cfg = len(cfgmod.list_appids())
        total_steam = len(names)
        status = f"{total_cfg} configured · {total_steam} Steam games detected"
        self.status.setText(status)

    def _names(self) -> dict[str, str]:
        return {a: n for a, n in steammod.list_games()}

    def _selected_appid(self) -> str:
        item = self.list.currentItem()
        if not item:
            return ""
        return str(item.data(32) or "")

    def _add(self) -> None:
        from PySide6.QtWidgets import QInputDialog

        # offer steam games first
        games = steammod.list_games()
        configured = set(cfgmod.list_appids())
        unconfigured = [(a, n) for a, n in games if a not in configured]
        if unconfigured:
            labels = [f"{n} [{a}]" for a, n in unconfigured]
            choice, ok = QInputDialog.getItem(
                self, "Add Game", "Steam game:", labels, 0, True
            )
            if ok and choice:
                import re

                m = re.search(r"\[(\d+)\]\s*$", choice)
                appid = m.group(1) if m else choice.strip()
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
            self, "Export Configurations", "tksteamlaunch-configs.tar.gz",
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
            self, "Import Configurations", "",
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

        QGuiApplication.clipboard().setText("tksteamlaunch %command%")
        self.status.setText("Launch options copied to clipboard: tksteamlaunch %command%")

    def _open_ludusavi(self) -> None:
        exe = shutil.which("ludusavi")
        if not exe:
            QMessageBox.warning(self, "TKSteamLaunch", "Ludusavi was not found in PATH.")
            return
        if "/flatpak/" in exe or "flatpak" in exe:
            QMessageBox.warning(
                self, "TKSteamLaunch",
                "Flatpak Ludusavi detected: it may not see Proton prefixes. "
                "Prefer the standalone binary.",
            )
        try:
            subprocess.Popen([exe])
        except Exception as e:
            QMessageBox.warning(self, "TKSteamLaunch", f"Could not open Ludusavi: {e}")
