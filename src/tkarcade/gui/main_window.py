"""Main window: list configured games + Steam library."""

from __future__ import annotations

import shutil
import subprocess
import sys

from PySide6.QtCore import QEvent, QSize, Qt, QThread, QTimer, Signal
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
    QCheckBox,
    QDialog,
    QDialogButtonBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMainWindow,
    QMenu,
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
from .. import history as histmod
from .. import protondb as pdbmod
from .. import steam as steammod
from .. import xdg
from ..backends.notify import format_duration
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

    from PySide6.QtCore import QCoreApplication

    from .. import __version__

    try:
        from PySide6 import __version__ as pyside_version
        from PySide6.QtCore import qVersion
    except Exception:
        pyside_version, qVersion = "unknown", lambda: "unknown"
    lines = [
        f"TKArcade {__version__}",
        QCoreApplication.translate(
            "MainWindow", "Minimal Steam launch wrapper. License: GPL-3.0-or-later."
        ),
        "",
        f"Python {platform.python_version()} on {platform.system()}",
        f"PySide6 {pyside_version} (Qt {qVersion()})",
        f"vdf {_dep_version('vdf')} (MIT) · jeepney {_dep_version('jeepney')} (MIT)",
        "",
        f"Config: {xdg.app_config_dir()}",
        f"Logs: {xdg.app_state_dir()}",
    ]
    return "\n".join(lines)


def _appid_sort_key(text: str) -> tuple[int, int, str]:
    """Numeric AppIDs first (by value), then anything else by text."""
    try:
        return (0, int(text), "")
    except ValueError:
        return (1, 0, text)


class _AppIdItem(QTableWidgetItem):
    """App ID cell sorting numerically (Qt compares item text as strings).

    Never call super().__lt__ here: PySide re-dispatches the virtual
    back into this override (infinite recursion).
    """

    def __lt__(self, other: object) -> bool:
        theirs = other.text() if isinstance(other, QTableWidgetItem) else ""
        return _appid_sort_key(self.text()) < _appid_sort_key(theirs)


class _ScanDialog(QDialog):
    """Checkbox table of unconfigured Steam games for batch add."""

    def __init__(self, parent, entries: list[tuple[str, str]]) -> None:
        super().__init__(parent)
        self.setWindowTitle(self.tr("Add Games"))
        self._entries = entries
        layout = QVBoxLayout(self)
        layout.addWidget(QLabel(self.tr("Steam games without a saved configuration:")))
        table = QTableWidget(len(entries), 3)
        table.setHorizontalHeaderLabels(["", self.tr("Game"), self.tr("App ID")])
        table.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)
        table.setEditTriggers(QTableWidget.NoEditTriggers)
        for row, (appid, name) in enumerate(entries):
            check = QTableWidgetItem()
            check.setFlags(check.flags() | Qt.ItemFlag.ItemIsUserCheckable)
            check.setCheckState(Qt.CheckState.Checked)
            table.setItem(row, 0, check)
            table.setItem(row, 1, QTableWidgetItem(name))
            table.setItem(row, 2, QTableWidgetItem(appid))
        self._table = table
        layout.addWidget(table)
        btns = QDialogButtonBox()
        btns.addButton(self.tr("Add Selected"), QDialogButtonBox.ButtonRole.AcceptRole)
        btns.addButton(QDialogButtonBox.Cancel)
        btns.accepted.connect(self.accept)
        btns.rejected.connect(self.reject)
        layout.addWidget(btns)

    def selected(self) -> list[str]:
        """Checked AppIDs, in table order."""
        out = []
        for row, (appid, _name) in enumerate(self._entries):
            item = self._table.item(row, 0)
            if item is not None and item.checkState() == Qt.CheckState.Checked:
                out.append(appid)
        return out


class _ProfileCleanupDialog(QDialog):
    """Offer leftover profile cleanup after game removal."""

    def __init__(self, parent, entries: list[tuple[str, str, int]]) -> None:
        super().__init__(parent)
        self.setWindowTitle(self.tr("Clean Up Profiles"))
        self._entries = entries
        layout = QVBoxLayout(self)
        layout.addWidget(QLabel(self.tr("These games were removed but still have saved profiles:")))
        table = QTableWidget(len(entries), 3)
        table.setHorizontalHeaderLabels(["", self.tr("Game"), self.tr("Profiles")])
        table.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)
        for row, (appid, name, count) in enumerate(entries):
            check = QTableWidgetItem()
            check.setFlags(check.flags() | Qt.ItemFlag.ItemIsUserCheckable)
            check.setCheckState(Qt.CheckState.Checked)
            table.setItem(row, 0, check)
            table.setItem(row, 1, QTableWidgetItem(f"{name} ({appid})"))
            table.setItem(row, 2, QTableWidgetItem(str(count)))
        self._table = table
        layout.addWidget(table)
        btns = QDialogButtonBox()
        btns.addButton(self.tr("Clean Selected"), QDialogButtonBox.ButtonRole.AcceptRole)
        btns.addButton(self.tr("Keep All"), QDialogButtonBox.ButtonRole.RejectRole)
        btns.accepted.connect(self.accept)
        btns.rejected.connect(self.reject)
        layout.addWidget(btns)

    def selected(self) -> list[str]:
        """AppIDs still checked for cleanup."""
        out = []
        for row, (appid, _name, _count) in enumerate(self._entries):
            item = self._table.item(row, 0)
            if item is not None and item.checkState() == Qt.CheckState.Checked:
                out.append(appid)
        return out


class _PlayedItem(QTableWidgetItem):
    """Played cell sorting by seconds (text is a human duration).

    Never call super().__lt__ here: PySide re-dispatches the virtual
    back into this override (infinite recursion).
    """

    def __init__(self, seconds: int, text: str) -> None:
        super().__init__(text)
        self._seconds = seconds

    def __lt__(self, other: object) -> bool:
        if isinstance(other, _PlayedItem):
            return self._seconds < other._seconds
        theirs = other.text() if isinstance(other, QTableWidgetItem) else ""
        return self.text() < theirs


class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("TKArcade")
        self._apply_default_size()
        QShortcut(QKeySequence.StandardKey.Quit, self, self._quit)

        central = QWidget()
        self.setCentralWidget(central)
        outer = QHBoxLayout(central)
        self.source_list = QListWidget()
        self.source_list.setObjectName("source_list")
        self.source_list.setMaximumWidth(170)
        self.source_list.setToolTip(self.tr("Filter games by source."))
        self.source_list.currentRowChanged.connect(self._on_source_changed)
        outer.addWidget(self.source_list)
        right = QWidget()
        outer.addWidget(right, stretch=1)
        layout = QVBoxLayout(right)
        self._source_filter = "all"

        layout.addWidget(
            QLabel(self.tr("Configured Games (double-click a game to edit its settings)"))
        )
        filter_row = QHBoxLayout()
        self.filter_input = QLineEdit()
        self.filter_input.setObjectName("filter_input")
        self.filter_input.setPlaceholderText(self.tr("Filter by name or ID..."))
        self.filter_input.setToolTip(self.tr("Show only games whose name or ID matches."))
        self.filter_input.setClearButtonEnabled(True)
        self.filter_input.textChanged.connect(self._apply_filter)
        filter_row.addWidget(self.filter_input, stretch=1)
        self.issues_only = QCheckBox(self.tr("With issues only"))
        self.issues_only.setObjectName("issues_only")
        self.issues_only.setToolTip(
            self.tr("Show only games failing validation (same checks as --validate).")
        )
        self.issues_only.toggled.connect(self._apply_filter)
        filter_row.addWidget(self.issues_only)
        layout.addLayout(filter_row)
        self.table = QTableWidget(0, 5)
        self.table.setHorizontalHeaderLabels(
            [
                self.tr("Game"),
                self.tr("App ID"),
                self.tr("Played"),
                self.tr("ProtonDB"),
                self.tr("Source"),
            ]
        )
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(4, QHeaderView.ResizeToContents)
        self.table.horizontalHeader().setSectionsClickable(True)
        self.table.horizontalHeader().setSortIndicatorShown(True)
        self.table.setSortingEnabled(True)
        self.table.verticalHeader().setDefaultSectionSize(40)
        self.table.setIconSize(QSize(32, 32))
        self.table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.table.setSelectionBehavior(QTableWidget.SelectRows)
        self.table.setSelectionMode(QTableWidget.SelectionMode.ExtendedSelection)
        self.table.itemDoubleClicked.connect(self._on_double_click)
        header = self.table.horizontalHeader()
        header.setSectionsMovable(True)
        header.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        header.customContextMenuRequested.connect(self._header_context_menu)
        header.sectionMoved.connect(lambda *a: self._save_column_layout())
        self._apply_column_layout()
        self.table.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.table.customContextMenuRequested.connect(self._game_context_menu)
        layout.addWidget(self.table, stretch=1)
        self.empty_state = QWidget()
        self.empty_state.setObjectName("empty_state")
        empty_layout = QVBoxLayout(self.empty_state)
        empty_title = QLabel(self.tr("No games configured yet"))
        empty_title.setObjectName("empty_title")
        self.empty_title = empty_title
        empty_title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        empty_title.setStyleSheet("font-weight: bold; font-size: 14pt;")
        empty_layout.addWidget(empty_title)
        empty_steps = QLabel(
            self.tr(
                "1. Add a Steam game below · 2. Edit its settings · "
                "3. Set its Steam launch options to tkarcade %command%"
            )
        )
        empty_steps.setObjectName("empty_steps")
        self.empty_steps = empty_steps
        empty_steps.setAlignment(Qt.AlignmentFlag.AlignCenter)
        empty_steps.setWordWrap(True)
        empty_layout.addWidget(empty_steps)
        empty_btns = QHBoxLayout()
        empty_btns.addStretch(1)
        self.empty_add = QPushButton(self.tr("Add Game..."))
        self.empty_add.setObjectName("empty_add")
        self.empty_add.setToolTip(self.tr("Add a Steam or local game."))
        self.empty_add.clicked.connect(self._add)
        empty_btns.addWidget(self.empty_add)
        self.empty_import = QPushButton(self.tr("Import..."))
        self.empty_import.setObjectName("empty_import")
        self.empty_import.setToolTip(
            self.tr("Restore from an export tarball or SteamTinkerLaunch.")
        )
        self.empty_import.clicked.connect(self._import_configs)
        empty_btns.addWidget(self.empty_import)
        self.empty_copy = QPushButton(self.tr("Copy Launch Options"))
        self.empty_copy.setObjectName("empty_copy")
        self.empty_copy.setToolTip(self.tr("Copy tkarcade %command% for Steam."))
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

        self._build_tool_bar()
        self._build_menu_bar()
        self.refresh()
        self._apply_tray()

    def _menu_action(self, menu, text: str, slot) -> None:
        """Add a menu entry (split out so tests skip modal exec)."""
        menu.addAction(text, slot)

    def _build_menu_bar(self) -> None:
        """Top-level menus (KDE-style): global actions live here, per-game
        actions live in the row context menu."""
        bar = self.menuBar()
        file_menu = bar.addMenu(self.tr("File"))
        self._menu_action(file_menu, self.tr("Export..."), self._export_configs)
        self._menu_action(file_menu, self.tr("Import..."), self._import_configs)
        file_menu.addSeparator()
        self._menu_action(file_menu, self.tr("Quit"), self._quit)

        game_menu = bar.addMenu(self.tr("Game"))
        self._menu_action(game_menu, self.tr("Play"), self._play_selected)
        self._menu_action(game_menu, self.tr("Add Game..."), self._add)
        self._menu_action(game_menu, self.tr("Scan Steam Library..."), self._scan_library)
        game_menu.addSeparator()
        self._menu_action(game_menu, self.tr("Edit..."), self._edit_selected)
        self._menu_action(
            game_menu,
            self.tr("Clone Settings To..."),
            lambda: self._clone_game_to(self._selected_appid()),
        )
        self._menu_action(game_menu, self.tr("Remove"), self._remove_selected)
        self._menu_action(game_menu, self.tr("Reset..."), self._reset_selected)
        game_menu.addSeparator()
        self._menu_action(game_menu, self.tr("History..."), self._show_history)

        view_menu = bar.addMenu(self.tr("View"))
        view_menu.addAction(self._tool_bar.toggleViewAction())

        tools_menu = bar.addMenu(self.tr("Tools"))
        self._menu_action(
            tools_menu,
            self.tr("Validate Game"),
            lambda: self._validate_selected(self._selected_appid()),
        )
        self._menu_action(tools_menu, self.tr("Open Ludusavi..."), self._open_ludusavi)
        self._menu_action(tools_menu, self.tr("Open Logs Folder"), self._open_logs)
        self._menu_action(tools_menu, self.tr("Clean Profiles..."), self._clean_profiles)
        tools_menu.addSeparator()
        self._menu_action(tools_menu, self.tr("Reload"), self.refresh)

        settings_menu = bar.addMenu(self.tr("Settings"))
        self._menu_action(settings_menu, self.tr("Global Defaults..."), self._edit_defaults)
        self._menu_action(settings_menu, self.tr("Preferences..."), self._edit_preferences)

        help_menu = bar.addMenu(self.tr("Help"))
        self._menu_action(help_menu, self.tr("About..."), self._show_about)

    def _build_tool_bar(self) -> None:
        """Slim toolbar with the primary actions only, centered."""
        from PySide6.QtWidgets import QSizePolicy, QToolBar, QWidget

        bar = QToolBar(self.tr("Main Toolbar"), self)
        bar.setObjectName("main_toolbar")
        bar.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextBesideIcon)
        self._tool_bar = bar

        def _spacer(name: str) -> QWidget:
            w = QWidget()
            w.setObjectName(name)
            w.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
            return w

        def _icon(theme: str, fallback: QStyle.StandardPixmap) -> QIcon:
            icon = QIcon.fromTheme(theme)
            return icon if not icon.isNull() else self.style().standardIcon(fallback)

        bar.addWidget(_spacer("toolbar_lead"))
        play = bar.addAction(
            self.style().standardIcon(QStyle.StandardPixmap.SP_MediaPlay),
            self.tr("Play"),
            self._play_selected,
        )
        play.setObjectName("toolbar_play")
        add = bar.addAction(
            _icon("list-add", QStyle.StandardPixmap.SP_FileDialogNewFolder),
            self.tr("Add Game..."),
            self._add,
        )
        add.setObjectName("toolbar_add")
        edit = bar.addAction(
            _icon("document-edit", QStyle.StandardPixmap.SP_DialogOpenButton),
            self.tr("Edit..."),
            self._edit_selected,
        )
        edit.setObjectName("toolbar_edit")
        remove = bar.addAction(
            _icon("edit-delete", QStyle.StandardPixmap.SP_TrashIcon),
            self.tr("Remove"),
            self._remove_selected,
        )
        remove.setObjectName("toolbar_remove")
        bar.addWidget(_spacer("toolbar_tail"))
        self.addToolBar(bar)

    def _apply_default_size(self) -> None:
        """1280x720 (or the saved size), centered on the available geometry."""
        from PySide6.QtWidgets import QApplication

        size = cfgmod.load_preferences().main_window_size or "1280x720"
        w, h = (int(x) for x in size.split("x"))
        self.resize(w, h)
        screen = QApplication.primaryScreen()
        if screen is not None:
            area = screen.availableGeometry()
            frame = self.frameGeometry()
            frame.moveCenter(area.center())
            self.move(frame.topLeft())
        self._size_timer = QTimer(self)
        self._size_timer.setSingleShot(True)
        self._size_timer.setInterval(500)
        self._size_timer.timeout.connect(self._save_main_size)

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        if self.isVisible():  # ignore pre-show layout resizes
            self._size_timer.start()  # debounced: one write per resize gesture

    def _save_main_size(self) -> None:
        """Persist the current window size (best effort, never raises)."""
        try:
            prefs = cfgmod.load_preferences()
        except Exception:
            return
        size = self.size()
        prefs.main_window_size = f"{max(640, size.width())}x{max(480, size.height())}"
        try:
            cfgmod.save_preferences(prefs)
        except OSError:
            pass

    def _mark_user_sorted(self, *_args) -> None:
        self._user_sorted = True

    def refresh(self) -> None:
        self._stop_pdb_worker()
        self._stop_art_worker()
        steammod.clear_games_cache()
        self.table.setSortingEnabled(False)
        self.table.setRowCount(0)
        names = {a: n for a, n in steammod.list_games()}
        names.update(steammod.local_names())
        fallback = self.style().standardIcon(QStyle.StandardPixmap.SP_MediaPlay)
        appids = cfgmod.list_appids()
        self.table.setRowCount(len(appids))
        api_key = cfgmod.load_preferences().sgdb_api_key.strip()
        need_fetch: list[str] = []
        need_art: list[str] = []
        try:
            stats = histmod.summarize(histmod.parse_log(xdg.log_file()))
        except Exception:
            stats = {}
        for row, appid in enumerate(appids):
            name_item = QTableWidgetItem(names.get(appid, appid))
            name_item.setData(Qt.ItemDataRole.UserRole, appid)
            icon_path = artmod.resolve_icon(appid)
            if icon_path:
                name_item.setIcon(QIcon(str(icon_path)))
            else:
                name_item.setIcon(fallback)
                if api_key and steammod.is_steam_id(appid):
                    need_art.append(appid)
            self.table.setItem(row, 0, name_item)
            self.table.setItem(row, 1, _AppIdItem(appid))
            source = "Steam" if steammod.is_steam_id(appid) else "Local"
            self.table.setItem(row, 4, QTableWidgetItem(self.tr(source)))
            data, fresh = pdbmod.cached(appid)
            if data:
                self._set_tier_cell(row, appid, data)
            st = stats.get(appid)
            if st is None:
                played = _PlayedItem(-1, "—")
                played.setToolTip(self.tr("No recorded sessions"))
            else:
                played = _PlayedItem(st.total_dur, format_duration(st.total_dur))
                last = st.last.replace("T", " ")
                played.setToolTip(
                    self.tr(f"{st.runs} sessions · last {last} · {st.fails} failures")
                )
            self.table.setItem(row, 2, played)
            if not fresh and steammod.is_steam_id(appid):
                need_fetch.append(appid)
        total_cfg = len(appids)
        total_steam = len(names)
        self._base_status = self.tr(f"{total_cfg} configured · {total_steam} Steam games detected")
        self._issues_cache: dict[str, list[str]] = {}
        self._refresh_sources(appids)
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
        self._apply_filter()

    def _refresh_sources(self, appids: list[str]) -> None:
        """Rebuild the source sidebar, keeping the current selection."""
        steam = sum(1 for a in appids if steammod.is_steam_id(a))
        local = len(appids) - steam
        current = self._source_filter
        self.source_list.blockSignals(True)
        try:
            self.source_list.clear()
            for key, title, count in (
                ("all", self.tr("All Games"), len(appids)),
                ("steam", self.tr("Steam"), steam),
                ("local", self.tr("Local"), local),
            ):
                item = QListWidgetItem(f"{title} ({count})")
                item.setData(Qt.ItemDataRole.UserRole, key)
                self.source_list.addItem(item)
            if current not in ("all", "steam", "local"):
                current = "all"
            self._source_filter = current
            self.source_list.setCurrentRow(("all", "steam", "local").index(current))
        finally:
            self.source_list.blockSignals(False)

    def _on_source_changed(self, _row: int = 0) -> None:
        item = self.source_list.currentItem()
        self._source_filter = str(item.data(Qt.ItemDataRole.UserRole) or "all") if item else "all"
        self._apply_filter()

    def _game_issues(self, appid: str) -> list[str]:
        """Cached per-game validation issues (same checks as --validate)."""
        if appid not in self._issues_cache:
            from ..launcher import validate_game

            try:
                self._issues_cache[appid] = validate_game(appid)
            except Exception:
                self._issues_cache[appid] = []
        return self._issues_cache[appid]

    def _apply_filter(self) -> None:
        query = self.filter_input.text().strip().lower()
        only_issues = self.issues_only.isChecked()
        shown = 0
        for row in range(self.table.rowCount()):
            name_item = self.table.item(row, 0)
            if name_item is None:
                self.table.setRowHidden(row, True)
                continue
            appid = str(name_item.data(Qt.ItemDataRole.UserRole) or "")
            name = (name_item.text() or "").lower()
            match = not query or query in name or query in appid.lower()
            if match and self._source_filter != "all":
                want_steam = self._source_filter == "steam"
                if steammod.is_steam_id(appid) != want_steam:
                    match = False
            if match and only_issues and not self._game_issues(appid):
                match = False
            self.table.setRowHidden(row, not match)
            if match:
                shown += 1
        base = getattr(self, "_base_status", "")
        if query or only_issues:
            self.status.setText(self.tr(f"{base} · {shown} shown"))
        else:
            self.status.setText(base)

    def _set_tier_cell(self, row: int, appid: str, data: dict) -> None:
        tier = str(data.get("tier", "")).lower()
        total = data.get("total", "?")
        item = QTableWidgetItem(tier.title() if tier else "?")
        if tier in pdbmod.TIER_STYLE:
            bg, fg = pdbmod.TIER_STYLE[tier]
            item.setBackground(QBrush(QColor(bg)))
            item.setForeground(QBrush(QColor(fg)))
        item.setToolTip(
            self.tr(f"{tier.title()} · {total} reports — double-click for protondb.com")
        )
        item.setData(Qt.ItemDataRole.UserRole, appid)
        self.table.setItem(row, 3, item)

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

        QMessageBox.about(self, self.tr("About TKArcade"), _about_text())

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
            tray.setToolTip("TKArcade")
            menu = QMenu(self)
            menu.aboutToShow.connect(self._refresh_tray_menu)
            self._refresh_tray_menu(menu)
            tray.setContextMenu(menu)
            tray.activated.connect(self._on_tray_activated)
            tray.show()
            self._tray = tray
            self._tray_menu = menu
        else:
            # Update in place: never deleteLater + recreate from a menu slot
            # (_edit_preferences calls back here). Freshness comes from
            # aboutToShow rebuilding before every open.
            self._tray.setIcon(iconsmod.app_icon(prefs.tray_icon))

    def _recent_games(self, limit: int) -> list[tuple[str, str, int]]:
        """Recent launches as (appid, name, total seconds), newest first."""
        names = self._names()
        try:
            stats = histmod.summarize(histmod.parse_log(xdg.log_file()))
        except Exception:
            return []
        rows = sorted(stats.values(), key=lambda s: s.last, reverse=True)
        return [(s.appid, names.get(s.appid, s.appid), s.total_dur) for s in rows[:limit]]

    def _launch_steam(self, appid: str) -> None:
        """Launch through the Steam client (with its time tracking).

        Plants a one-shot menu skip so the pre-launch menu does not pop
        on a launch requested from here, even with show_menu enabled.
        """
        from PySide6.QtCore import QUrl

        from ..launcher import consume_menu_skip, plant_menu_skip

        if not appid.isdigit():
            QMessageBox.warning(self, "TKArcade", self.tr(f"Not a Steam App ID: {appid}"))
            return
        plant_menu_skip(appid)
        if not QDesktopServices.openUrl(QUrl(f"steam://rungameid/{appid}")):
            consume_menu_skip(appid)  # failed handoff: never skip a later real menu
            QMessageBox.warning(
                self, "TKArcade", self.tr("Could not ask Steam to launch the game.")
            )

    def _refresh_tray_menu(self, menu=None) -> None:
        """Rebuild the tray menu, including the recent-games section."""
        from ..backends.notify import format_duration

        menu = menu if menu is not None else self._tray_menu
        if menu is None:
            return
        menu.clear()
        show_action = menu.addAction(self.tr("Show / Hide"))
        show_action.triggered.connect(self._toggle_visible)
        prefs = cfgmod.load_preferences()
        if prefs.tray_quick_launch:
            recents = self._recent_games(prefs.tray_quick_count)
            if recents:
                menu.addSeparator()
                for appid, name, total in recents:
                    act = menu.addAction(self.tr(f"{name} ({format_duration(total)})"))
                    act.triggered.connect(lambda _=False, a=appid: self._play_game(a))
        menu.addSeparator()
        defaults_action = menu.addAction(self.tr("Global Defaults..."))
        defaults_action.triggered.connect(self._edit_defaults)
        prefs_action = menu.addAction(self.tr("Preferences..."))
        prefs_action.triggered.connect(self._edit_preferences)
        about_action = menu.addAction(self.tr("About..."))
        about_action.triggered.connect(self._show_about)
        menu.addSeparator()
        quit_action = menu.addAction(self.tr("Quit"))
        app = QApplication.instance()
        if app is not None:
            quit_action.triggered.connect(app.quit)

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

    def _column_layout(self) -> tuple[list[int], set[int]]:
        """Persisted (order, hidden) with defaults for missing/garbage."""
        prefs = cfgmod.load_preferences()
        order = [int(x) for x in prefs.column_order.split(",") if x.strip().isdigit()]
        if sorted(order) != [0, 1, 2, 3, 4]:
            order = [0, 1, 2, 3, 4]
        hidden = {int(x) for x in prefs.hidden_columns.split(",") if x.strip().isdigit()}
        return order, (hidden & {1, 2, 3, 4})

    def _apply_column_layout(self) -> None:
        order, hidden = self._column_layout()
        header = self.table.horizontalHeader()
        header.blockSignals(True)
        try:
            for visual, logical in enumerate(order):
                header.moveSection(header.visualIndex(logical), visual)
            for logical in range(header.count()):
                header.setSectionHidden(logical, logical in hidden)
        finally:
            header.blockSignals(False)

    def _save_column_layout(self) -> None:
        header = self.table.horizontalHeader()
        order = [header.logicalIndex(v) for v in range(header.count())]
        hidden = sorted(i for i in range(header.count()) if header.isSectionHidden(i))
        prefs = cfgmod.load_preferences()
        prefs.column_order = ",".join(map(str, order))
        prefs.hidden_columns = ",".join(map(str, hidden))
        cfgmod.save_preferences(prefs)

    def _set_column_visible(self, logical: int, visible: bool) -> None:
        if logical == 0:  # Game column always stays on
            return
        self.table.horizontalHeader().setSectionHidden(logical, not visible)
        self._save_column_layout()

    def _reset_columns(self) -> None:
        prefs = cfgmod.load_preferences()
        prefs.column_order = ""
        prefs.hidden_columns = ""
        cfgmod.save_preferences(prefs)
        self._apply_column_layout()

    def _build_header_menu(self) -> QMenu:
        """Column chooser (split out so tests skip modal exec)."""
        header = self.table.horizontalHeader()
        menu = QMenu(self)
        for logical, title in enumerate(
            (
                self.tr("Game"),
                self.tr("App ID"),
                self.tr("Played"),
                self.tr("ProtonDB"),
                self.tr("Source"),
            )
        ):
            act = menu.addAction(title)
            act.setCheckable(True)
            act.setChecked(not header.isSectionHidden(logical))
            if logical == 0:
                act.setEnabled(False)
            else:
                act.toggled.connect(
                    lambda checked, log=logical: self._set_column_visible(log, checked)
                )
        menu.addSeparator()
        menu.addAction(self.tr("Reset Columns"), lambda: self._reset_columns())
        return menu

    def _header_context_menu(self, pos) -> None:
        menu = self._build_header_menu()
        menu.exec(self.table.horizontalHeader().mapToGlobal(pos))

    def _on_double_click(self, item: QTableWidgetItem) -> None:
        if item.column() == 3:
            appid = str(item.data(Qt.ItemDataRole.UserRole) or "")
            if appid:
                self._open_protondb_page(appid)
            return
        self._edit_selected()

    def _open_protondb_page(self, appid: str) -> None:
        from PySide6.QtCore import QUrl

        QDesktopServices.openUrl(QUrl(pdbmod.GAME_URL.format(appid=appid)))

    def _game_context_menu(self, pos) -> None:
        item = self.table.itemAt(pos)
        if item is None:
            return
        row = item.row()
        name_item = self.table.item(row, 0)
        appid = str((name_item.data(Qt.ItemDataRole.UserRole) if name_item else "") or "")
        if not appid:
            return
        self._ensure_row_selected(row)
        menu = self._build_game_menu(appid)
        menu.exec(self.table.viewport().mapToGlobal(pos))

    def _build_game_menu(self, appid: str) -> QMenu:
        """Context menu for a game row (split out so tests skip modal exec).

        Multiple selection shows only multi-game actions; single-row
        actions stay on single selection. Order mirrors the button rows
        below the list (Games, then copies, then tools).
        """
        menu = QMenu(self)
        sel = self._selected_appids() or [appid]
        multi = len(sel) > 1
        if multi:
            menu.addAction(self.tr("Copy Launch Options"), lambda: self._copy_launch())
        else:
            name = self._names().get(appid, appid)
            menu.addAction(self.tr("Play"), lambda: self._play_game(appid))
            menu.addAction(self.tr("Edit Settings"), lambda: self._edit_selected(appid))
            menu.addSeparator()
            if steammod.is_steam_id(appid):
                menu.addAction(self.tr("Copy Launch Options"), lambda: self._copy_launch())
            else:
                menu.addAction(
                    self.tr("Copy Launch Command"),
                    lambda: self._copy_text(f"tkarcade --appid {appid}", self.tr("Launch command")),
                )
            menu.addAction(
                self.tr("Copy App ID"), lambda: self._copy_text(appid, self.tr("App ID"))
            )
            menu.addAction(
                self.tr("Copy Game Name"),
                lambda: self._copy_text(name, self.tr("Game name")),
            )
            menu.addSeparator()
            install = steammod.install_dir(appid)
            act_install = menu.addAction(self.tr("Open Install Folder"))
            act_install.setEnabled(install is not None)
            if install is not None:
                act_install.triggered.connect(
                    lambda: self._open_folder(install, self.tr("install folder"))
                )
            prefix = steammod.prefix_dir(appid)
            act_prefix = menu.addAction(self.tr("Open Proton Prefix"))
            act_prefix.setEnabled(prefix is not None)
            if prefix is not None:
                act_prefix.triggered.connect(
                    lambda: self._open_folder(prefix, self.tr("Proton prefix"))
                )
            shaders = steammod.shader_dir(appid)
            act_shaders = menu.addAction(self.tr("Clear Shader Cache"))
            act_shaders.setEnabled(shaders is not None)
            if shaders is not None:
                act_shaders.triggered.connect(lambda: self._clear_shader_cache(appid))
            if steammod.is_steam_id(appid):
                menu.addAction(
                    self.tr("Open ProtonDB Page"), lambda: self._open_protondb_page(appid)
                )
            menu.addAction(self.tr("Validate Game"), lambda: self._validate_selected(appid))
            menu.addAction(self.tr("Clear History"), lambda: self._clear_game_history(appid))
            menu.addAction(self.tr("Clone Settings To..."), lambda: self._clone_game_to(appid))
            menu.addSeparator()
        n = len(sel)
        menu.addAction(
            self.tr(f"Remove {n} Game") if n == 1 else self.tr(f"Remove {n} Games"),
            lambda: self._remove_selected(),
        )
        menu.addAction(self.tr("Reset to Global Defaults"), lambda: self._reset_selected())
        return menu

    def _open_folder(self, path, what: str) -> None:
        if not open_path(str(path)):
            QMessageBox.warning(self, "TKArcade", self.tr(f"Could not open {what}."))

    def _clear_shader_cache(self, appid: str) -> None:
        """Delete a game's precompiled shaders (Steam rebuilds them)."""
        target = steammod.shader_dir(appid)
        if target is None:
            return
        size = steammod.format_size(steammod.dir_size(target))
        r = QMessageBox.question(
            self,
            "TKArcade",
            self.tr(f"Delete {size} of shader cache for {appid}?\nSteam rebuilds it on demand."),
        )
        if r != QMessageBox.StandardButton.Yes:
            return
        try:
            shutil.rmtree(target)
        except Exception as e:
            QMessageBox.warning(self, "TKArcade", f"{appid}: {e}")
            return
        self.status.setText(self.tr(f"Cleared {size} of shader cache."))

    def _validate_selected(self, appid: str = "") -> None:
        from ..launcher import validate_game

        if not appid:
            QMessageBox.information(self, "TKArcade", self.tr("Select a game first."))
            return
        issues = validate_game(appid)
        if issues:
            QMessageBox.warning(self, "TKArcade", "\n".join(issues))
        else:
            QMessageBox.information(self, "TKArcade", self.tr("No issues found."))

    def _clear_game_history(self, appid: str) -> None:
        from .. import history as histmod

        r = QMessageBox.question(
            self,
            "TKArcade",
            self.tr(f"Clear session history for {appid}? This cannot be undone."),
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if r != QMessageBox.StandardButton.Yes:
            return
        try:
            removed = histmod.clear_appid(xdg.log_file(), appid)
        except Exception as e:
            QMessageBox.warning(self, "TKArcade", f"{appid}: {e}")
            return
        self.refresh()
        self.status.setText(self.tr(f"Cleared {removed} session(s)."))

    def _clone_game_to(self, appid: str = "") -> None:
        if not appid:
            QMessageBox.information(self, "TKArcade", self.tr("Select a game first."))
            return
        dest = self._pick_game_id(
            self.tr("Clone Settings"), self.tr("Clone into game:"), exclude={appid}
        )
        if not dest:
            return
        if dest == appid:
            QMessageBox.information(self, "TKArcade", self.tr("Source and target are the same."))
            return
        if cfgmod.game_file(dest).exists():
            go = QMessageBox.question(
                self,
                "TKArcade",
                self.tr(f"Overwrite the saved settings for {dest}?"),
            )
            if go != QMessageBox.StandardButton.Yes:
                return
        try:
            cfgmod.clone_game(appid, dest)
        except (OSError, ValueError) as e:
            QMessageBox.warning(self, "TKArcade", str(e))
            return
        self.refresh()
        self.status.setText(self.tr(f"Cloned {appid} to {dest}."))

    def _names(self) -> dict[str, str]:
        names = {a: n for a, n in steammod.list_games()}
        names.update(steammod.local_names())
        return names

    def _selected_appid(self) -> str:
        row = self.table.currentRow()
        if row < 0:
            return ""
        item = self.table.item(row, 0)
        if not item:
            return ""
        return str(item.data(Qt.ItemDataRole.UserRole) or "")

    def _pick_steam_game(self, title: str, label: str, exclude=frozenset()) -> str:
        """Pick a Steam game from a list, else a manual AppID. "" when cancelled."""
        from PySide6.QtWidgets import QInputDialog

        games = steammod.list_games()
        configured = set(cfgmod.list_appids())
        cands = [(a, n) for a, n in games if a not in configured and a not in exclude]
        if cands:
            labels = [f"{n} [{a}]" for a, n in cands]
            choice, ok = QInputDialog.getItem(self, title, label, labels, 0, True)
            if ok and choice:
                import re

                m = re.search(r"\[(\d+)\]\s*$", choice)
                appid = m.group(1) if m else choice.strip()
                if not appid:
                    return ""
                if not appid.isdigit():
                    QMessageBox.information(
                        self, "TKArcade", self.tr(f"Not a Steam App ID: {choice}")
                    )
                    return ""
                return appid
            return ""
        appid, ok = QInputDialog.getText(self, title, self.tr("Steam App ID:"))
        if not ok or not appid.strip():
            return ""
        if not appid.strip().isdigit():
            QMessageBox.information(
                self, "TKArcade", self.tr(f"Not a Steam App ID: {appid.strip()}")
            )
            return ""
        return appid.strip()

    def _pick_game_id(self, title: str, label: str, exclude=frozenset()) -> str:
        """Pick any configured game, else a manual ID. "" when cancelled."""
        from PySide6.QtWidgets import QInputDialog

        names = self._names()
        configured = sorted(set(cfgmod.list_appids()) - set(exclude))
        labels = [f"{names.get(a, a)} [{a}]" for a in configured]
        choice, ok = QInputDialog.getItem(self, title, label, labels, 0, True)
        if not ok or not choice:
            return ""
        import re

        m = re.search(r"\[(.+)\]\s*$", choice)
        cand = (m.group(1) if m else choice).strip()
        if not cand or xdg.safe_stem(cand) != cand:
            QMessageBox.information(self, "TKArcade", self.tr(f"Invalid game ID: {choice}"))
            return ""
        return cand

    def _add(self) -> None:
        """Single entry point: pick the source, then run its flow."""
        from .game_dialog import AddSourceDialog

        dlg = AddSourceDialog(self)
        if dlg.exec() != QDialog.DialogCode.Accepted:
            return
        if dlg.choice() == AddSourceDialog.LOCAL:
            self._add_local()
        else:
            self._add_steam()

    def _add_steam(self) -> None:
        appid = self._pick_steam_game(self.tr("Add Game"), self.tr("Steam game:"))
        if not appid:
            return
        dlg = GameDialog(self, appid, self._names().get(appid, ""))
        if dlg.exec():
            self.refresh()

    def _add_local(self) -> None:
        """Add a manually installed native Linux game (name + executable)."""
        from .game_dialog import AddLocalDialog

        dlg = AddLocalDialog(self)
        if dlg.exec() != QDialog.DialogCode.Accepted:
            return
        name, exe = dlg.values()
        appid = cfgmod.new_local_id(name)
        cfg = cfgmod.load_defaults()
        cfg.general.appid = appid
        cfg.general.name = name
        cfg.general.custom_executable = exe
        cfg.general.game_type = "native"
        cfgmod.save(cfg)
        settings = GameDialog(self, appid, name)
        settings.exec()
        self.refresh()
        self.status.setText(self.tr(f"Added {name}."))

    def _scan_library(self) -> None:
        """Batch-add Steam games without a saved config (defaults template)."""
        cands = steammod.unconfigured_games(set(cfgmod.list_appids()))
        if not cands:
            QMessageBox.information(
                self,
                "TKArcade",
                self.tr("Every Steam game is already configured."),
            )
            return
        dlg = _ScanDialog(self, cands)
        if dlg.exec() != QDialog.DialogCode.Accepted:
            return
        added = 0
        for appid in dlg.selected():
            if cfgmod.game_file(appid).exists():
                continue
            cfg = cfgmod.load_defaults()
            cfg.general.appid = appid
            cfgmod.save(cfg)
            added += 1
        self.refresh()
        self.status.setText(self.tr(f"Added {added} game(s)."))

    def _play_selected(self) -> None:
        """Play the current game (Steam client or direct local launch)."""
        sel = self._selected_appids()
        if not sel:
            self.status.setText(self.tr("Select a game first."))
            return
        self._play_game(sel[0])

    def _play_game(self, appid: str) -> None:
        """Play routing: Steam IDs go through the client, local IDs run direct."""
        if steammod.is_steam_id(appid):
            self._launch_steam(appid)
        else:
            self._launch_local(appid)

    def _launch_local(self, appid: str) -> None:
        """Run a local game detached through this same launcher.

        Logs, history and the one-shot menu skip apply exactly like a
        Steam launch; only the client handoff is missing.
        """
        from ..launcher import plant_menu_skip

        runner = shutil.which("tkarcade") or sys.argv[0]
        plant_menu_skip(appid)
        try:
            subprocess.Popen(
                [runner, "--appid", appid],
                start_new_session=True,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
        except OSError as e:
            QMessageBox.warning(self, "TKArcade", self.tr(f"Could not launch game: {e}"))
            return
        name = self._names().get(appid, appid)
        self.status.setText(self.tr(f"Launched {name}."))

    def _edit_selected(self, appid: str = "") -> None:
        appid = appid or self._selected_appid()
        if not appid:
            QMessageBox.information(self, "TKArcade", self.tr("Select a game first."))
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
        self.refresh()

    def _open_logs(self) -> None:
        d = xdg.games_log_dir()
        try:
            d.mkdir(parents=True, exist_ok=True)
        except Exception:
            pass
        if not open_path(str(d)):
            QMessageBox.warning(self, "TKArcade", self.tr(f"Could not open {d}."))

    def _export_configs(self) -> None:
        from PySide6.QtWidgets import QFileDialog

        path, _ = QFileDialog.getSaveFileName(
            self,
            self.tr("Export Configurations"),
            "tkarcade-configs.tar.gz",
            self.tr("Archives (*.tar.gz)"),
        )
        if not path:
            return
        try:
            saved = cfgmod.export_configs(path)
        except (OSError, ValueError) as e:
            QMessageBox.warning(self, "TKArcade", self.tr(f"Export failed: {e}"))
            return
        self.status.setText(self.tr(f"Exported to {saved}"))

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
        if picked == 3:
            self._import_tksteamlaunch()
            return
        self._import_tarball()

    def _import_tksteamlaunch(self) -> None:
        """Copy predecessor configs (missing files only, never overwrite)."""
        try:
            imported, skipped = cfgmod.import_tksteamlaunch()
        except (OSError, ValueError) as e:
            QMessageBox.warning(self, "TKArcade", self.tr(f"Import failed: {e}"))
            return
        lines = [self.tr(f"Imported {len(imported)} file(s).")]
        if skipped:
            lines.append(self.tr(f"Skipped {len(skipped)} existing file(s)."))
        QMessageBox.information(self, "TKArcade", "\n".join(lines))
        self.refresh()
        self.status.setText(self.tr(f"Imported {len(imported)} file(s)."))

    def _import_tarball(self) -> None:
        from PySide6.QtWidgets import QFileDialog

        path, _ = QFileDialog.getOpenFileName(
            self,
            self.tr("Import Configurations"),
            "",
            self.tr("Archives (*.tar.gz)"),
        )
        if not path:
            return
        try:
            imported = cfgmod.import_configs(path)
        except (OSError, ValueError) as e:
            QMessageBox.warning(self, "TKArcade", self.tr(f"Import failed: {e}"))
            return
        self.status.setText(self.tr(f"Imported {len(imported)} game(s)"))
        self.refresh()

    def _selected_appids(self) -> list[str]:
        """AppIDs of all selected rows, in row order."""
        rows = sorted({i.row() for i in self.table.selectedItems()})
        out = []
        for row in rows:
            item = self.table.item(row, 0)
            appid = str((item.data(Qt.ItemDataRole.UserRole) if item else "") or "")
            if appid and appid not in out:
                out.append(appid)
        return out

    def _ensure_row_selected(self, row: int) -> None:
        """Select the row unless already selected (preserves multi-select)."""
        item = self.table.item(row, 0)
        if item is not None and not item.isSelected():
            self.table.selectRow(row)

    def _remove_selected(self) -> None:
        appids = self._selected_appids()
        if not appids:
            self.status.setText(self.tr("Select games first."))
            return
        names = self._names()
        label = ", ".join(f"{names.get(a, a)} ({a})" for a in appids)
        what = self.tr("these configurations") if len(appids) > 1 else self.tr("the configuration")
        r = QMessageBox.question(self, "TKArcade", self.tr(f"Remove {what} for {label}?"))
        if r != QMessageBox.StandardButton.Yes:
            return
        errors = []
        for appid in appids:
            try:
                cfgmod.game_file(appid).unlink(missing_ok=True)
            except Exception as e:
                errors.append(f"{appid}: {e}")
        if errors:
            QMessageBox.warning(self, "TKArcade", "\n".join(errors))
        self._offer_profile_cleanup(appids)
        self.refresh()

    def _clean_profiles(self) -> None:
        """Clean profiles orphaned by past removals (checkbox pre-selection)."""
        names = self._names()
        entries = [
            (appid, names.get(appid, appid), count) for appid, count in cfgmod.orphaned_profiles()
        ]
        if not entries:
            QMessageBox.information(self, "TKArcade", self.tr("No orphaned profiles."))
            return
        dlg = _ProfileCleanupDialog(self, entries)
        if dlg.exec() != QDialog.DialogCode.Accepted:
            return
        cleaned = 0
        for appid in dlg.selected():
            try:
                shutil.rmtree(cfgmod.profiles_dir(appid))
                cleaned += 1
            except Exception as e:
                QMessageBox.warning(self, "TKArcade", f"{appid}: {e}")
        self.status.setText(self.tr(f"Cleaned profiles for {cleaned} game(s)."))

    def _offer_profile_cleanup(self, appids: list[str]) -> None:
        """Offer to delete leftover profiles of just-removed games."""
        names = self._names()
        entries = []
        for appid in appids:
            try:
                left = [p for p in cfgmod.profiles_dir(appid).glob("*.toml") if p.is_file()]
            except Exception:
                left = []
            if left:
                entries.append((appid, names.get(appid, appid), len(left)))
        if not entries:
            return
        dlg = _ProfileCleanupDialog(self, entries)
        if dlg.exec() != QDialog.DialogCode.Accepted:
            return
        for appid in dlg.selected():
            try:
                shutil.rmtree(cfgmod.profiles_dir(appid))
            except Exception as e:
                QMessageBox.warning(self, "TKArcade", f"{appid}: {e}")

    def _reset_selected(self) -> None:
        """Reset every selected game to the Global Defaults template."""
        appids = self._selected_appids()
        if not appids:
            self.status.setText(self.tr("Select games first."))
            return
        names = self._names()
        label = ", ".join(f"{names.get(a, a)} ({a})" for a in appids)
        r = QMessageBox.question(
            self,
            "TKArcade",
            self.tr(
                f"Reset {len(appids)} game(s) to the Global Defaults template now?\n"
                f"{label}\nThis overwrites their saved configs (profiles are kept)."
            ),
        )
        if r != QMessageBox.StandardButton.Yes:
            return
        for appid in appids:
            cfg = cfgmod.load_defaults()
            cfg.general.appid = appid
            cfgmod.save(cfg)
        self.refresh()

    def _copy_text(self, text: str, what: str) -> None:
        from PySide6.QtGui import QGuiApplication

        clipboard = QGuiApplication.clipboard()
        if clipboard is None:  # e.g. offscreen/minimal platform
            self.status.setText(self.tr("Clipboard unavailable on this platform."))
            return
        clipboard.setText(text)
        self.status.setText(self.tr(f"{what} copied to clipboard: {text}"))

    def _copy_launch(self) -> None:
        self._copy_text("tkarcade %command%", self.tr("Launch options"))

    def _open_ludusavi(self) -> None:
        exe = shutil.which("ludusavi")
        if not exe:
            QMessageBox.warning(
                self,
                "TKArcade",
                self.tr("Ludusavi was not found in PATH."),
            )
            return
        if "/flatpak/" in exe or "flatpak" in exe:
            QMessageBox.warning(
                self,
                "TKArcade",
                self.tr(
                    "Flatpak Ludusavi detected: it may not see Proton prefixes. "
                    "Prefer the standalone binary."
                ),
            )
        try:
            subprocess.Popen([exe])
        except Exception as e:
            QMessageBox.warning(self, "TKArcade", self.tr(f"Could not open Ludusavi: {e}"))
