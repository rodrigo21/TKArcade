"""Main window: list configured games + Steam library."""
from __future__ import annotations

import shutil
import subprocess

from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from .. import config as cfgmod
from .. import steam as steammod
from .game_dialog import GameDialog


class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("TKSteamLaunch")
        self.resize(720, 480)

        central = QWidget()
        self.setCentralWidget(central)
        layout = QVBoxLayout(central)

        layout.addWidget(QLabel("Configured games (double-click to edit):"))
        self.list = QListWidget()
        self.list.itemDoubleClicked.connect(self._edit_selected)
        layout.addWidget(self.list, stretch=1)

        self.status = QLabel()
        layout.addWidget(self.status)

        row = QHBoxLayout()
        layout.addLayout(row)
        for label, slot in (
            ("Add...", self._add),
            ("Edit...", self._edit_selected),
            ("Remove", self._remove_selected),
            ("Copy Launch Option", self._copy_launch),
            ("Open Ludusavi...", self._open_ludusavi),
            ("Reload", self.refresh),
        ):
            b = QPushButton(label)
            b.clicked.connect(slot)
            row.addWidget(b)
        self.refresh()

    def refresh(self) -> None:
        self.list.clear()
        names = {a: n for a, n in steammod.list_games()}
        for appid in cfgmod.list_appids():
            label = f"{names.get(appid, appid)}  [{appid}]"
            QListWidgetItem(label, self.list).setData(32, appid)
        # also show unconfigured steam games hint in status
        total_cfg = len(cfgmod.list_appids())
        total_steam = len(names)
        self.status.setText(f"{total_cfg} configured · {total_steam} Steam game(s) detected")

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
                self, "Add game", "Steam game:", labels, 0, True
            )
            if ok and choice:
                import re

                m = re.search(r"\[(\d+)\]\s*$", choice)
                appid = m.group(1) if m else choice.strip()
            else:
                return
        else:
            appid, ok = QInputDialog.getText(self, "Add game", "Steam AppID:")
            if not ok or not appid.strip():
                return
            appid = appid.strip()
        dlg = GameDialog(self, appid)
        if dlg.exec():
            self.refresh()

    def _edit_selected(self) -> None:
        appid = self._selected_appid()
        if not appid:
            QMessageBox.information(self, "TKSteamLaunch", "Select a game.")
            return
        dlg = GameDialog(self, appid)
        if dlg.exec():
            self.refresh()

    def _remove_selected(self) -> None:
        appid = self._selected_appid()
        if not appid:
            return
        r = QMessageBox.question(self, "TKSteamLaunch", f"Remove config for {appid}?")
        if r == QMessageBox.StandardButton.Yes:
            try:
                cfgmod.game_file(appid).unlink(missing_ok=True)
            except Exception as e:  # noqa: BLE001
                QMessageBox.warning(self, "TKSteamLaunch", str(e))
            self.refresh()

    def _copy_launch(self) -> None:
        from PySide6.QtGui import QGuiApplication

        QGuiApplication.clipboard().setText("tksteamlaunch %command%")
        self.status.setText("Launch option copied: tksteamlaunch %command%")

    def _open_ludusavi(self) -> None:
        exe = shutil.which("ludusavi")
        if not exe:
            QMessageBox.warning(self, "TKSteamLaunch", "ludusavi not found in PATH.")
            return
        if "/flatpak/" in exe or "flatpak" in exe:
            QMessageBox.warning(
                self, "TKSteamLaunch",
                "Flatpak ludusavi detected: it may not see Proton prefixes. "
                "Prefer the standalone binary.",
            )
        try:
            subprocess.Popen([exe])
        except Exception as e:  # noqa: BLE001
            QMessageBox.warning(self, "TKSteamLaunch", f"Failed to open ludusavi: {e}")
