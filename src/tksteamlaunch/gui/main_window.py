"""Main window: list configured games + Steam library."""
from __future__ import annotations

import logging
import shutil
import subprocess

from PySide6.QtCore import QSize
from PySide6.QtGui import QIcon
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

log = logging.getLogger("tksteamlaunch.gui")


class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("TKSteamLaunch")
        self.resize(760, 520)
        try:
            migrated = cfgmod.migrate_sparse_to_snapshots()
            if migrated:
                log.info("migrated %d game(s) to snapshots", len(migrated))
                self._pending_migration_note = (
                    f"Migrated {len(migrated)} game(s) to standalone configs."
                )
            else:
                self._pending_migration_note = ""
        except Exception as e:  # noqa: BLE001
            log.error("config migration failed: %s", e)
            self._pending_migration_note = ""

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

        row = QHBoxLayout()
        layout.addLayout(row)
        for label, slot in (
            ("Add Game...", self._add),
            ("Edit...", self._edit_selected),
            ("Remove", self._remove_selected),
            ("Copy Launch Options", self._copy_launch),
            ("Open Ludusavi...", self._open_ludusavi),
            ("Global Defaults...", self._edit_defaults),
            ("Open Logs Folder", self._open_logs),
            ("Reload", self.refresh),
        ):
            b = QPushButton(label)
            b.clicked.connect(slot)
            row.addWidget(b)
        self.refresh()

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
        if getattr(self, "_pending_migration_note", ""):
            status += f" · {self._pending_migration_note}"
            self._pending_migration_note = ""
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

    def _open_logs(self) -> None:
        d = xdg.games_log_dir()
        try:
            d.mkdir(parents=True, exist_ok=True)
        except Exception:  # noqa: BLE001
            pass
        if not open_path(str(d)):
            QMessageBox.warning(self, "TKSteamLaunch", f"Could not open {d}.")

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
            except Exception as e:  # noqa: BLE001
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
        except Exception as e:  # noqa: BLE001
            QMessageBox.warning(self, "TKSteamLaunch", f"Could not open Ludusavi: {e}")
