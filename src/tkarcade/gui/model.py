"""QML game list model: stdlib core underneath, QtCore only on top."""

from __future__ import annotations

import logging
import os
import shutil
import threading

from PySide6.QtCore import (
    Property,
    QAbstractListModel,
    QModelIndex,
    QSortFilterProxyModel,
    Qt,
    Signal,
    Slot,
)

from .. import config as cfgmod
from .. import history as histmod
from .. import launcher as launchermod
from .. import protondb as pdbmod
from .. import steam as steammod
from .. import xdg
from ..backends.notify import format_duration

log = logging.getLogger("tkarcade.kirigami")


def validate_local_game(name: str, exe: str) -> str:
    """Return an error string, or '' when the pair is acceptable."""
    if not name.strip():
        return "Give the game a name."
    if not exe.strip():
        return "Pick the game executable."
    if not os.path.isfile(exe.strip()) and shutil.which(exe.strip()) is None:
        return f"Executable not found: {exe.strip()}"
    return ""


class GameListModel(QAbstractListModel):
    """Configured games for QML (id, name and source roles)."""

    IdRole = Qt.ItemDataRole.UserRole + 1
    NameRole = Qt.ItemDataRole.UserRole + 2
    SourceRole = Qt.ItemDataRole.UserRole + 3
    PlayedRole = Qt.ItemDataRole.UserRole + 4
    TierRole = Qt.ItemDataRole.UserRole + 5
    TierBgRole = Qt.ItemDataRole.UserRole + 6
    TierFgRole = Qt.ItemDataRole.UserRole + 7

    refreshed = Signal()
    browseFinished = Signal(str)

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._rows: list[tuple[str, ...]] = []
        self._steam_detected = 0
        self.refresh()

    def roleNames(self) -> dict:
        # game-prefixed: bare Qt6 delegate properties must never collide
        # with the delegate item's own properties (name/source do).
        return {
            GameListModel.IdRole: b"gameId",
            GameListModel.NameRole: b"gameName",
            GameListModel.SourceRole: b"gameSource",
            GameListModel.PlayedRole: b"gamePlayed",
            GameListModel.TierRole: b"gameTier",
            GameListModel.TierBgRole: b"gameTierBg",
            GameListModel.TierFgRole: b"gameTierFg",
        }

    def rowCount(self, parent: QModelIndex | None = None) -> int:
        return 0 if (parent is not None and parent.isValid()) else len(self._rows)

    def data(self, index: QModelIndex, role: int = Qt.ItemDataRole.DisplayRole):
        if not index.isValid() or not 0 <= index.row() < len(self._rows):
            return None
        row = self._rows[index.row()]
        cols = {
            GameListModel.IdRole: 0,
            GameListModel.NameRole: 1,
            GameListModel.SourceRole: 2,
            GameListModel.PlayedRole: 3,
            GameListModel.TierRole: 4,
            GameListModel.TierBgRole: 5,
            GameListModel.TierFgRole: 6,
        }
        return row[cols[role]] if role in cols else None

    @Slot()
    def refresh(self) -> None:
        """Reload rows from disk (Steam names first, local names merged)."""
        names = {a: n for a, n in steammod.list_games()}
        names.update(steammod.local_names())
        self._steam_detected = len(names)
        try:
            stats = histmod.summarize(histmod.parse_log(xdg.log_file()))
        except Exception:
            stats = {}
        rows = []
        for appid in cfgmod.list_appids():
            source = "Steam" if steammod.is_steam_id(appid) else "Local"
            st = stats.get(appid)
            played = format_duration(st.total_dur) if st is not None else "—"
            data, _fresh = pdbmod.cached(appid)
            tier = str(((data or {}).get("tier", "")) or "").lower()
            bg, fg = pdbmod.TIER_STYLE.get(tier, ("", ""))
            rows.append((appid, names.get(appid, appid), source, played, tier.title(), bg, fg))
        rows.sort(key=lambda r: r[1].lower())
        self.beginResetModel()
        self._rows = rows
        self.endResetModel()
        self.refreshed.emit()

    @Slot(str, str, result=str)
    def addLocal(self, name: str, exe: str) -> str:
        """Create a native local game. Returns the new id, or '' + logs."""
        err = validate_local_game(name, exe)
        if err:
            log.warning("addLocal rejected: %s", err)
            return ""
        appid = cfgmod.new_local_id(name.strip())
        cfg = cfgmod.load_defaults()
        cfg.general.appid = appid
        cfg.general.name = name.strip()
        cfg.general.custom_executable = exe.strip()
        cfg.general.game_type = "native"
        cfgmod.save(cfg)
        self.refresh()
        return appid

    @Slot()
    def browseExecutable(self) -> None:
        """Native file picker off the GUI thread; result via browseFinished.

        Blocking D-Bus round-trips must never freeze the interface: the
        worker reports back ("" included) through the signal.
        """
        threading.Thread(target=self._browse_worker, daemon=True).start()

    def _browse_worker(self) -> None:
        from ..backends import portal as portalmod

        try:
            path = portalmod.pick_file("Game executable", "Select")
        except Exception as e:  # never kill the thread pool on a picker bug
            log.warning("browse worker failed: %s", e)
            path = ""
        self.browseFinished.emit(path)

    @Slot(str, result=bool)
    def play(self, appid: str) -> bool:
        """Play routing: Steam ids via the client, local ids direct."""
        try:
            if steammod.is_steam_id(appid):
                from PySide6.QtCore import QUrl
                from PySide6.QtGui import QDesktopServices

                launchermod.plant_menu_skip(appid)
                return bool(QDesktopServices.openUrl(QUrl(f"steam://rungameid/{appid}")))
            launchermod.launch_local_detached(appid)
            return True
        except Exception as e:  # never crash the list on a launch failure
            log.warning("play(%s) failed: %s", appid, e)
            return False


def _counts_property(kind: str):
    """Count accessor factory (kept tiny: steam/local/total/steam-detected)."""

    def get(self) -> int:
        if kind == "steam-detected":
            return self._steam_detected
        if kind == "total":
            return len(self._rows)
        want_steam = kind == "steam"
        return sum(1 for row in self._rows if steammod.is_steam_id(row[0]) == want_steam)

    return Property(int, get, notify=GameListModel.refreshed)


GameListModel.totalCount = _counts_property("total")
GameListModel.steamCount = _counts_property("steam")
GameListModel.localCount = _counts_property("local")
GameListModel.steamDetectedCount = _counts_property("steam-detected")


class GameFilterModel(QSortFilterProxyModel):
    """Source + text filter over a GameListModel (drawer + search drive it)."""

    sourceChanged = Signal()
    textChanged = Signal()

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._source = "all"
        self._text = ""

    def _get_source(self) -> str:
        return self._source

    def _set_source(self, key: str) -> None:
        key = key if key in ("all", "steam", "local") else "all"
        if key != self._source:
            self._source = key
            self.invalidate()
            self.sourceChanged.emit()

    sourceKey = Property(str, _get_source, _set_source, notify=sourceChanged)

    def _get_text(self) -> str:
        return self._text

    def _set_text(self, query: str) -> None:
        query = query or ""
        if query != self._text:
            self._text = query
            self.invalidate()
            self.textChanged.emit()

    textQuery = Property(str, _get_text, _set_text, notify=textChanged)

    def filterAcceptsRow(self, source_row: int, source_parent: QModelIndex) -> bool:
        model = self.sourceModel()
        if model is None:
            return False
        index = model.index(source_row, 0, source_parent)
        appid = model.data(index, GameListModel.IdRole) or ""
        if self._source != "all":
            want_steam = self._source == "steam"
            if steammod.is_steam_id(str(appid)) != want_steam:
                return False
        if self._text:
            query = self._text.lower()
            name = str(model.data(index, GameListModel.NameRole) or "").lower()
            if query not in name and query not in str(appid).lower():
                return False
        return True
