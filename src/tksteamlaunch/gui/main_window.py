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

from .. import artwork as artmod
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


class _ArtworkWorker(QThread):
    """Download missing artwork in the background (needs an API key)."""

    fetched = Signal(str, str)  # appid, path

    def __init__(self, appids: list[str], api_key: str, parent=None) -> None:
        super().__init__(parent)
        self._appids = appids
        self._api_key = api_key

    def run(self) -> None:
        for appid in self._appids:
            if self.isInterruptionRequested():
                return
            try:
                path = artmod.fetch_missing(appid, self._api_key)
            except Exception:
                continue
            if path:
                self.fetched.emit(appid, str(path))


def _dep_version(dist: str) -> str:
    try:
        from importlib.metadata import version

        return version(dist)
    except Exception:
        return "unknown"


def _about_text() -> str:
    """About dialog body: versions, licenses, active file locations."""
    import platform

    from .. import __version__

    try:
        from PySide6 import __version__ as pyside_version
        from PySide6.QtCore import qVersion
    except Exception:
        pyside_version, qVersion = "unknown", lambda: "unknown"
    lines = [
        f"TKSteamLaunch {__version__}",
        "Minimal Steam launch wrapper. License: GPL-3.0-or-later.",
        "",
        f"Python {platform.python_version()} on {platform.system()}",
        f"PySide6 {pyside_version} (Qt {qVersion()})",
        f"vdf {_dep_version('vdf')} (MIT) · jeepney {_dep_version('jeepney')} (MIT)",
        "",
        f"Config: {xdg.app_config_dir()}",
        f"Logs: {xdg.app_state_dir()}",
    ]
    return "\n".join(lines)


class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("TKSteamLaunch")
        self._apply_default_size()
        QShortcut(QKeySequence.StandardKey.Quit, self, self._quit)

        central = QWidget()
        self.setCentralWidget(central)
        layout = QVBoxLayout(central)

        layout.addWidget(QLabel("Configured Games (double-click a game to edit its settings)"))
        self.table = QTableWidget(0, 3)
        self.table.setHorizontalHeaderLabels(["Game", "App ID", "ProtonDB"])
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeToContents)
        self.table.horizontalHeader().setSectionsClickable(True)
        self.table.horizontalHeader().setSortIndicatorShown(True)
        self.table.setSortingEnabled(True)
        self.table.verticalHeader().setDefaultSectionSize(40)
        self.table.setIconSize(QSize(32, 32))
        self.table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.table.setSelectionBehavior(QTableWidget.SelectRows)
        self.table.itemDoubleClicked.connect(self._on_double_click)
        layout.addWidget(self.table, stretch=1)
        self.empty_state = QWidget()
        self.empty_state.setObjectName("empty_state")
        empty_layout = QVBoxLayout(self.empty_state)
        empty_title = QLabel("No games configured yet")
        empty_title.setObjectName("empty_title")
        self.empty_title = empty_title
        empty_title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        empty_title.setStyleSheet("font-weight: bold; font-size: 14pt;")
        empty_layout.addWidget(empty_title)
        empty_steps = QLabel(
            "1. Add a Steam game below · 2. Edit its settings · "
            "3. Set its Steam launch options to tksteamlaunch %command%"
        )
        empty_steps.setObjectName("empty_steps")
        self.empty_steps = empty_steps
        empty_steps.setAlignment(Qt.AlignmentFlag.AlignCenter)
        empty_steps.setWordWrap(True)
        empty_layout.addWidget(empty_steps)
        empty_btns = QHBoxLayout()
        empty_btns.addStretch(1)
        self.empty_add = QPushButton("Add Game...")
        self.empty_add.setObjectName("empty_add")
        self.empty_add.setToolTip("Pick a Steam game to configure.")
        self.empty_add.clicked.connect(self._add)
        empty_btns.addWidget(self.empty_add)
        self.empty_import = QPushButton("Import...")
        self.empty_import.setObjectName("empty_import")
        self.empty_import.setToolTip("Restore from an export tarball or SteamTinkerLaunch.")
        self.empty_import.clicked.connect(self._import_configs)
        empty_btns.addWidget(self.empty_import)
        self.empty_copy = QPushButton("Copy Launch Options")
        self.empty_copy.setObjectName("empty_copy")
        self.empty_copy.setToolTip("Copy tksteamlaunch %command% for Steam.")
        self.empty_copy.clicked.connect(self._copy_launch)
        empty_btns.addWidget(self.empty_copy)
        empty_btns.addStretch(1)
        empty_layout.addLayout(empty_btns)
        layout.addWidget(self.empty_state, stretch=1)
        self._pdb_thread: _ProtonDBWorker | None = None
        self._art_thread: _ArtworkWorker | None = None
        self._tray = None
        self._tray_menu = None
        self._user_sorted = False
        self.table.horizontalHeader().sortIndicatorChanged.connect(self._mark_user_sorted)
        self._tray_menu = None

        self.status = QLabel()
        layout.addWidget(self.status)
        layout.addSpacing(2)

        layout.addWidget(
            self._section_row(
                "Games",
                (
                    ("Add Game...", self._add),
                    ("Edit...", self._edit_selected),
                    ("Remove", self._remove_selected),
                    ("History...", self._show_history),
                ),
            )
        )
        layout.addSpacing(4)
        layout.addWidget(
            self._section_row(
                "Tools",
                (
                    ("Copy Launch Options", self._copy_launch),
                    ("Open Ludusavi...", self._open_ludusavi),
                    ("Open Logs Folder", self._open_logs),
                    ("Reload", self.refresh),
                ),
            )
        )
        layout.addSpacing(4)
        layout.addWidget(
            self._section_row(
                "Application",
                (
                    ("Global Defaults...", self._edit_defaults),
                    ("Preferences...", self._edit_preferences),
                    ("About...", self._show_about),
                    ("Export...", self._export_configs),
                    ("Import...", self._import_configs),
                ),
            )
        )
        self.refresh()
        self._apply_tray()

    def _apply_default_size(self) -> None:
        from .helpers import apply_default_size

        apply_default_size(self)

    @staticmethod
    def _section_row(title: str, buttons: tuple[tuple[str, Callable[[], None]], ...]) -> QWidget:
        """Labeled row with its buttons centered in the full row width.

        A trailing spacer mirrors the label so the group centers on the
        window, not on the space after the label. Untitled group box for
        a full frame without a top title.
        """
        from PySide6.QtWidgets import QGroupBox

        frame = QGroupBox()
        layout = QHBoxLayout(frame)
        layout.setSpacing(8)
        label = QLabel(title)
        label.setMinimumWidth(90)
        layout.addWidget(label)
        layout.addStretch(1)
        for text, slot in buttons:
            b = QPushButton(text)
            b.clicked.connect(slot)
            layout.addWidget(b)
        layout.addStretch(1)
        spacer = QWidget()
        spacer.setFixedWidth(90)
        layout.addWidget(spacer)
        return frame

    def _mark_user_sorted(self, *_args) -> None:
        self._user_sorted = True

    def refresh(self) -> None:
        self._stop_pdb_worker()
        self._stop_art_worker()
        steammod.clear_games_cache()
        self.table.setSortingEnabled(False)
        self.table.setRowCount(0)
        names = {a: n for a, n in steammod.list_games()}
        fallback = self.style().standardIcon(QStyle.StandardPixmap.SP_MediaPlay)
        appids = cfgmod.list_appids()
        self.table.setRowCount(len(appids))
        api_key = cfgmod.load_preferences().sgdb_api_key.strip()
        need_fetch: list[str] = []
        need_art: list[str] = []
        for row, appid in enumerate(appids):
            name_item = QTableWidgetItem(names.get(appid, appid))
            name_item.setData(Qt.ItemDataRole.UserRole, appid)
            icon_path = artmod.resolve_icon(appid)
            if icon_path:
                name_item.setIcon(QIcon(str(icon_path)))
            else:
                name_item.setIcon(fallback)
                if api_key:
                    need_art.append(appid)
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
        empty = not appids
        self.empty_state.setVisible(empty)
        self.table.setVisible(not empty)
        if need_fetch:
            self._pdb_thread = _ProtonDBWorker(need_fetch, self)
            self._pdb_thread.fetched.connect(self._on_protondb)
            self._pdb_thread.start()
        if need_art:
            self._art_thread = _ArtworkWorker(need_art, api_key, self)
            self._art_thread.fetched.connect(self._on_artwork)
            self._art_thread.start()
        self.table.setSortingEnabled(True)
        if not self._user_sorted:
            self.table.sortByColumn(0, Qt.SortOrder.AscendingOrder)

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

    def _on_artwork(self, appid: str, path: str) -> None:
        for row in range(self.table.rowCount()):
            item = self.table.item(row, 0)
            if item is not None and str(item.data(Qt.ItemDataRole.UserRole) or "") == appid:
                item.setIcon(QIcon(path))
                return

    def _stop_art_worker(self) -> None:
        if self._art_thread is not None:
            if self._art_thread.isRunning():
                self._art_thread.requestInterruption()
                self._art_thread.wait(5000)
                if self._art_thread.isRunning():
                    self._art_thread.terminate()
                    self._art_thread.wait(2000)
            self._art_thread = None

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

    def _quit(self) -> None:
        app = QApplication.instance()
        if app is not None:
            app.quit()

    def closeEvent(self, event) -> None:
        prefs = cfgmod.load_preferences()
        if prefs.close_to_tray and self._tray is not None:
            event.ignore()
            self.hide()
            return
        self._drop_tray()
        self._stop_pdb_worker()
        self._stop_art_worker()
        super().closeEvent(event)

    def _show_about(self) -> None:
        from PySide6.QtWidgets import QMessageBox

        QMessageBox.about(self, "About TKSteamLaunch", _about_text())

    def changeEvent(self, event) -> None:
        super().changeEvent(event)
        if event.type() == QEvent.Type.WindowStateChange and self.isMinimized():
            prefs = cfgmod.load_preferences()
            if prefs.minimize_to_tray and self._tray is not None:
                from PySide6.QtCore import QTimer

                QTimer.singleShot(0, self.hide)

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
            about_action = menu.addAction("About...")
            about_action.triggered.connect(self._show_about)
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
        from .. import stl_import as sti
        from .import_dialog import ImportChooserDialog, StlImportDialog

        choice = ImportChooserDialog(self)
        picked = choice.exec()
        if not picked:
            return
        if picked == 2:
            names = {a: n for a, n in steammod.list_games()}
            configured = set(cfgmod.list_appids())
            stl = set(sti.list_stl_appids())
            games = [(a, names.get(a, a)) for a in sorted(configured & stl)]
            if StlImportDialog(self, games).exec():
                self.refresh()
            return
        self._import_tarball()

    def _import_tarball(self) -> None:
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
