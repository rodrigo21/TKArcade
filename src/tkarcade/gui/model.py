"""QML game list model: stdlib core underneath, QtCore only on top."""

from __future__ import annotations

import logging
import os
import shutil

from PySide6.QtCore import QAbstractListModel, QModelIndex, Qt, Signal, Slot

from .. import config as cfgmod
from .. import launcher as launchermod
from .. import steam as steammod

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

    refreshed = Signal()

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._rows: list[tuple[str, str, str]] = []
        self.refresh()

    def roleNames(self) -> dict:
        return {
            GameListModel.IdRole: b"gameId",
            GameListModel.NameRole: b"name",
            GameListModel.SourceRole: b"source",
        }

    def rowCount(self, parent: QModelIndex | None = None) -> int:
        return 0 if (parent is not None and parent.isValid()) else len(self._rows)

    def data(self, index: QModelIndex, role: int = Qt.ItemDataRole.DisplayRole):
        if not index.isValid() or not 0 <= index.row() < len(self._rows):
            return None
        appid, name, source = self._rows[index.row()]
        if role == GameListModel.IdRole:
            return appid
        if role == GameListModel.NameRole:
            return name
        if role == GameListModel.SourceRole:
            return source
        return None

    @Slot()
    def refresh(self) -> None:
        """Reload rows from disk (Steam names first, local names merged)."""
        names = {a: n for a, n in steammod.list_games()}
        names.update(steammod.local_names())
        rows = []
        for appid in cfgmod.list_appids():
            source = "Steam" if steammod.is_steam_id(appid) else "Local"
            rows.append((appid, names.get(appid, appid), source))
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
