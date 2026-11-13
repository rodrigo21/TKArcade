"""QML game list model: stdlib core underneath, QtCore only on top."""

from __future__ import annotations

import io
import logging
import os
import re
import shlex
import shutil
import subprocess
import threading
from pathlib import Path

from PySide6.QtCore import (
    Property,
    QAbstractTableModel,
    QEvent,
    QMetaObject,
    QModelIndex,
    QObject,
    QSortFilterProxyModel,
    Qt,
    QTimer,
    Signal,
    Slot,
)
from PySide6.QtQuick import QQuickItem

from .. import artwork as artmod
from .. import config as cfgmod
from .. import graphics as graphicsmod
from .. import history as histmod
from .. import igdb as igdbmod
from .. import launcher as launchermod
from .. import metadata as metamod
from .. import protondb as pdbmod
from .. import releasedate as rdmod
from .. import running as runningmod
from .. import runtime_archives as archivesmod
from .. import runtimes, xdg
from .. import steam as steammod
from .. import winetricks as wtmod
from ..backends import network as net_backend
from ..backends.notify import format_duration

log = logging.getLogger("tkarcade.kirigami")


def _apply_metadata(cfg, data: dict) -> None:
    """Write the Details metadata fields into a config (helper keeps lint sane)."""
    md = cfg.metadata
    md.version = str(data.get("version", "")).strip()
    md.date = str(data.get("date", "")).strip()
    md.tag = str(data.get("tag", "")).strip()
    md.description = str(data.get("description", "")).strip()
    md.developer = str(data.get("developer", "")).strip()
    md.publisher = str(data.get("publisher", "")).strip()
    md.genre = str(data.get("genre", "")).strip()
    md.series = str(data.get("series", "")).strip()
    raw_ratings = data.get("age_ratings", [])
    if isinstance(raw_ratings, str):
        raw_ratings = [part.strip() for part in raw_ratings.split(",")]
    elif not isinstance(raw_ratings, (list, tuple)):
        raw_ratings = []
    ratings = []
    for value in raw_ratings:
        rating = str(value).strip()
        if rating in cfgmod.AGE_RATINGS and rating not in ratings:
            ratings.append(rating)
    md.age_ratings = ratings
    region = str(data.get("region", "")).strip().lower()
    md.region = region if region in cfgmod.REGIONS else ""
    status = str(data.get("status", "")).strip().lower()
    md.status = status if status in cfgmod.GAME_STATUSES else ""
    md.locked = cfgmod.normalize_locked_fields(data.get("locked", ""))
    md.steam_appid = cfgmod.normalize_steam_appid(data.get("steam_appid", ""))
    md.vndb_id = cfgmod.normalize_vndb_id(data.get("vndb_id", ""))
    md.igdb_id = cfgmod.normalize_igdb_id(data.get("igdb_id", ""))
    # Only a caller that carries the field writes it: an older form map
    # without tags must not clear the list on save.
    if "tags" in data:
        raw_tags = data.get("tags", [])
        if isinstance(raw_tags, str):
            raw_tags = raw_tags.split(",")
        md.tags = cfgmod.normalize_categories(raw_tags)


def _fill_steam_metadata(cfg, data: dict) -> bool:
    """Fill a config's empty metadata fields from a Steam store payload.

    Fill-empty only, and a locked field stays out even when it is empty: a
    lock is a decision, not a default. Returns whether anything changed.
    """
    md = cfg.metadata
    locked = set(cfgmod.normalize_locked_fields(md.locked).split(","))
    changed = False
    for name in ("description", "developer", "publisher", "genre", "series"):
        value = str(data.get(name, "") or "").strip()
        if value and name not in locked and not getattr(md, name):
            setattr(md, name, value)
            changed = True
    date = str(data.get("date", "") or "").strip()
    if date and "date" not in locked and not md.date and cfgmod.metadata_date_valid(date):
        md.date = date
        changed = True
    ratings = data.get("age_ratings")
    known = [
        str(value).strip()
        for value in (ratings if isinstance(ratings, list) else [])
        if str(value).strip() in cfgmod.AGE_RATINGS
    ]
    if known and "age_ratings" not in locked and not md.age_ratings:
        md.age_ratings = list(dict.fromkeys(known))
        changed = True
    raw_tags = data.get("tags")
    tags = cfgmod.normalize_categories(raw_tags if isinstance(raw_tags, list) else [])
    if tags and "tags" not in locked and not md.tags:
        md.tags = tags
        changed = True
    return changed


#: Solid status badge colors (background, text). The text is always black:
#: every background is light enough for WCAG AA at badge size.
STATUS_STYLE: dict[str, tuple[str, str]] = {
    "abandoned": ("#F44336", "#000000"),
    "beaten": ("#9CCC65", "#000000"),
    "completed": ("#66BB6A", "#000000"),
    "not_played": ("#BDBDBD", "#000000"),
    "on_hold": ("#FFC107", "#000000"),
    "plan_to_play": ("#4FC3F7", "#000000"),
    "played": ("#4DD0E1", "#000000"),
    "playing": ("#81C784", "#000000"),
}

#: Preferred symbol fonts for the Unicode status glyphs, in fallback order.
SYMBOL_FONTS = (
    "Noto Sans Symbols 2",
    "Noto Sans Symbols",
    "DejaVu Sans",
    "Segoe UI Symbol",
    "Apple Symbols",
    "Symbola",
)
_SYMBOL_FONT_FAMILY: str | None = None

#: `wine --version` per (binary, mtime): the manager probes on open, never
#: on the launch path.
_WINE_VERSION_CACHE: dict[tuple[str, float], str] = {}

# `tkarcade --version` of the binary Steam resolves from PATH, cached by
# path plus mtime: the launch-options row compares it with this build.
_PATH_VERSION_CACHE: dict[str, tuple[int, str]] = {}


def _path_tkarcade_version() -> tuple[str, str]:
    """(path, version) of the `tkarcade` on PATH, along with which Steam runs."""
    import subprocess

    exe = shutil.which("tkarcade")
    if not exe:
        return "", ""
    try:
        mtime = Path(exe).stat().st_mtime_ns
    except OSError:
        mtime = 0
    hit = _PATH_VERSION_CACHE.get(exe)
    if hit is not None and hit[0] == mtime:
        return exe, hit[1]
    version = ""
    try:
        proc = subprocess.run([exe, "--version"], capture_output=True, text=True, timeout=5)
        if proc.returncode == 0:
            version = (proc.stdout or "").strip().splitlines()[0]
    except Exception:
        version = ""
    _PATH_VERSION_CACHE[exe] = (mtime, version)
    return exe, version


def validate_local_game(name: str, exe: str) -> str:
    """Return an error string, or '' when the pair is acceptable."""
    if not name.strip():
        return "Give the Game a Name."
    if not exe.strip():
        return "Pick the Game Executable."
    if not os.path.isfile(exe.strip()) and shutil.which(exe.strip()) is None:
        return f"Executable Not Found: {exe.strip()}"
    return ""


def _split_args(text: str) -> list[str]:
    """Shell-like split for the args fields (falls back to whitespace)."""
    try:
        return shlex.split(text)
    except ValueError:
        return text.split()


def _dep_binary(name: str, enabled: bool, note: str = "") -> dict:
    """Widgets _binary_status: a missing binary only warns when enabled.

    `note` is "fail" for the custom-prefix probe, where a missing
    binary kills the launch instead of being skipped. The text stays in
    QML (`GameSettings.statusText`): the model only names the message.
    """
    path = shutil.which(name)
    if path:
        msg = "binary-ok" if enabled else "binary-off"
        return {"kind": "ok", "msg": msg, "args": [name, path]}
    if enabled:
        msg = "binary-missing-fatal" if note == "fail" else "binary-missing"
        return {"kind": "warn", "msg": msg, "args": [name]}
    return {"kind": "note", "msg": "binary-absent", "args": [name]}


def _played_cells(st) -> tuple[str, int, str, str, int]:
    """(duration, seconds, tooltip, last played, last epoch) for one game."""
    if st is None:
        return "—", -1, "No Recorded Sessions", "—", -1
    last = st.last.replace("T", " ")
    try:
        from datetime import datetime

        last_secs = int(datetime.fromisoformat(st.last).timestamp())
    except (ValueError, TypeError):
        last_secs = -1
    tip = f"{st.runs} sessions · last {last} · {st.fails} failures"
    return format_duration(st.total_dur), st.total_dur, tip, last[:16], last_secs


class _QuitFilter(QObject):
    """Ctrl+Q to quit for watched windows (never raises).

    Installed per top-level window (never application-wide: wrapping
    arbitrary QML watched objects aborts shiboken at startup).
    """

    def __init__(self, quit_fn=None, parent=None):
        super().__init__(parent)
        self._quit_fn = quit_fn

    def eventFilter(self, watched, event):
        try:
            if (
                event.type() == QEvent.Type.KeyPress
                and event.key() == Qt.Key.Key_Q
                and event.modifiers() & Qt.KeyboardModifier.ControlModifier
                and not event.isAutoRepeat()
            ):
                if self._quit_fn is not None:
                    self._quit_fn()
                else:
                    from PySide6.QtCore import QCoreApplication

                    QCoreApplication.quit()
                return True
        except Exception:
            pass
        return False


class _DialogKeyFilter(QObject):
    """Escape closes a watched dialog; Enter stays with the dialog body.

    A QML `Window` is not a `QDialog`: nothing maps Escape to reject() for
    it, and with no field focused its focus item is the window root, so the
    key never reaches a QML `Keys` handler on the body. An open popup (a
    combo list, a menu) handles Escape itself, so the filter only closes
    the window when none is open. Enter is left to the body's
    `Keys.onReturnPressed` (it knows the window's default buttons).
    """

    def eventFilter(self, watched, event):
        try:
            if (
                event.type() == QEvent.Type.KeyPress
                and not event.isAutoRepeat()
                and event.key() == Qt.Key.Key_Escape
            ):
                if _popup_open(watched):
                    # Let the popup take it; Qt closes the list itself.
                    return False
                watched.close()
                return True
        except Exception:
            pass
        return False


def _popup_open(window) -> bool:
    """Whether a popup (menu, combo list) is open in `window`.

    Walks the popup's visual items, never the `Controls.Menu` object: a
    Python wrapper of a Menu damages PySide's wrapper cache for the rest
    of the process (docs/QML-NOTES.md). `QQuickPopupItem` exists for every
    declared popup and is visible only while it is open.
    """
    try:
        for item in window.findChildren(QQuickItem):
            if item.metaObject().className() == "QQuickPopupItem" and item.property("visible"):
                return True
    except Exception:
        pass
    return False


class GameListModel(QAbstractTableModel):
    """Configured games for QML (id, name and source roles)."""

    IdRole = Qt.ItemDataRole.UserRole + 1
    NameRole = Qt.ItemDataRole.UserRole + 2
    OriginRole = Qt.ItemDataRole.UserRole + 3
    PlayedRole = Qt.ItemDataRole.UserRole + 4
    TierRole = Qt.ItemDataRole.UserRole + 5
    TierBgRole = Qt.ItemDataRole.UserRole + 6
    TierFgRole = Qt.ItemDataRole.UserRole + 7
    IconRole = Qt.ItemDataRole.UserRole + 8
    PlayedSecsRole = Qt.ItemDataRole.UserRole + 9
    PlayedTipRole = Qt.ItemDataRole.UserRole + 10
    LastPlayedRole = Qt.ItemDataRole.UserRole + 11
    LastSecsRole = Qt.ItemDataRole.UserRole + 12
    PlatformRole = Qt.ItemDataRole.UserRole + 13
    RuntimeRole = Qt.ItemDataRole.UserRole + 14
    WineRole = Qt.ItemDataRole.UserRole + 15
    InstallDirRole = Qt.ItemDataRole.UserRole + 16
    CategoryRole = Qt.ItemDataRole.UserRole + 17
    RunningRole = Qt.ItemDataRole.UserRole + 18
    CoverRole = Qt.ItemDataRole.UserRole + 19
    IssueLevelRole = Qt.ItemDataRole.UserRole + 20
    IssuesTipRole = Qt.ItemDataRole.UserRole + 21
    ReleaseDateRole = Qt.ItemDataRole.UserRole + 22
    InstalledAtRole = Qt.ItemDataRole.UserRole + 23
    StatusRole = Qt.ItemDataRole.UserRole + 24
    StatusBgRole = Qt.ItemDataRole.UserRole + 25
    StatusFgRole = Qt.ItemDataRole.UserRole + 26

    ROLE_NAMES = (
        "gameId",
        "gameName",
        "gameOrigin",
        "gamePlayed",
        "gameTier",
        "gameTierBg",
        "gameTierFg",
        "gameIcon",
        "gamePlayedSecs",
        "gamePlayedTip",
        "gameLastPlayed",
        "gameLastSecs",
        "gamePlatform",
        "gameRuntime",
        "gameWine",
        "gameInstallDir",
        "gameCategory",
        "gameRunning",
        "gameCover",
        "gameReleaseDate",
        "gameInstalledAt",
        "gameStatus",
        "gameStatusBg",
        "gameStatusFg",
    )

    refreshed = Signal()
    browseFinished = Signal(str)
    displayModesFinished = Signal("QVariantList")
    coverageFinished = Signal(str, str)
    # Parsed `winetricks list-all` rows for the verb picker (verb,
    # description, category); [] when winetricks is missing.
    verbCatalogReady = Signal("QVariantList")
    # The interactive protontricks/winetricks window exited: the dialog
    # re-reads the prefix log, which the tool may have just written to.
    # status is "" for a clean exit, "failed" otherwise; detail is the
    # tool's log file when it failed.
    verbToolClosed = Signal(str, str)
    # Widgets parity: every launch path reported itself (the status line
    # said "Launched X.", the handoff failures warned — the tray recents
    # ran the same code). The model only says what happened; the QML side
    # owns the wording. kind is "steam" or "local".
    launchReported = Signal(bool, str, str, str)
    # The GUI asked a running game's launcher to stop (ok, name, error).
    terminateReported = Signal(bool, str, str)
    # The set of running AppIDs changed (indicator repaint).
    runningChanged = Signal()
    # Runtime archive work: download/extraction progress (kind, message),
    # the end of one download (kind, "" = installed) and the managed
    # versions changed. GUI-only; the launcher never imports that helper.
    archiveProgress = Signal(str, str)
    archiveFinished = Signal(str, str)
    archivesChanged = Signal()
    # Releases the manager can install (kind, rows, "" or an error message).
    runtimeReleases = Signal(str, "QVariantList", str)
    # A background shader-cache walk finished (appid, human size).
    shaderSizeReady = Signal(str, str)
    # A background Steam launch-options probe finished (appid).
    steamStatusReady = Signal(str)

    # How often the running records are re-read, and how long a
    # terminating launcher gets before its process group is SIGKILLed.
    RUNNING_POLL_MS = 2000
    TERMINATE_GRACE_MS = 10_000

    @Slot(str, result=int)
    def roleId(self, roleName: str) -> int:
        """Numeric role id for a game* role name (-1 when unknown)."""
        ids = {bytes(v).decode(): k for k, v in self.roleNames().items()}
        return int(ids.get(roleName, -1))

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._rows: list[tuple[str, ...]] = []
        self._steam_detected = 0
        self._tray_active = False
        self._tray_refresher = None
        self._tray_actions: dict = {}
        self._quit_filter = _QuitFilter()
        self._dialog_key_filter = _DialogKeyFilter()
        # Last Steam launch-options probe: (appid, status, detail). The
        # scan reads every profile's localconfig.vdf, so the dependency
        # status reuses it between the dialog's explicit refreshes.
        self._steam_status: dict[str, tuple[str, str]] = {}
        self._steam_status_busy: set[str] = set()
        # Shader-cache sizes are walked off the GUI thread (a large cache
        # can take seconds); the context menu fills in when the walk ends.
        self._shader_sizes: dict[str, str] = {}
        self._shader_size_busy: set[str] = set()
        # Live running records by AppID (the launcher owns the files).
        self._running: dict[str, dict] = {}
        # Global log signature at the last refresh, so the poll notices a
        # session line written after the game (and its post-hook) ends.
        self._log_sig: tuple[int, int] | None = None
        # Runtime archive downloads/extraction (one of each at a time).
        self._archive_lock = threading.Lock()
        self._archive_work_lock = threading.Lock()
        self._archive_busy: set[str] = set()
        self._archive_sync_running = False
        self.backgroundDone.connect(self.refresh)
        self._running_timer = QTimer(self)
        self._running_timer.setInterval(self.RUNNING_POLL_MS)
        self._running_timer.timeout.connect(self._refresh_running)
        self._running_timer.timeout.connect(self._poll_history)
        self._running_timer.start()
        # Escalation for a launcher that ignored the SIGTERM (model-owned
        # so a destroyed model cannot fire into nothing).
        self._kill_record: dict | None = None
        self._kill_timer = QTimer(self)
        self._kill_timer.setSingleShot(True)
        self._kill_timer.timeout.connect(self._force_kill)
        # Timers outlive a Python-side test teardown if left running: the
        # event loop may deliver a queued timeout after the C++ object is
        # gone. Stop them with the object they belong to, and let the
        # callbacks check the flag in case a timeout is already in flight.
        self._closing = False
        # Prefix paths captured before a removal deletes the config: the
        # cleanup offer needs them to show/delete the prefix.
        self._removed_prefixes: dict[str, str] = {}
        self._removed_names: dict[str, str] = {}
        self.destroyed.connect(self._stop_timers)
        self._migrate_ids()
        self.refresh()

    @staticmethod
    def _migrate_ids() -> None:
        """Rename legacy IDs to the canonical origin-prefixed form (GUI startup only)."""
        try:
            for old, new in cfgmod.migrate_ids():
                log.info("migrated AppID %s -> %s", old, new)
        except Exception as e:
            log.warning("AppID migration failed: %s", e)
        try:
            for old, new in artmod.migrate_cache_keys():
                log.info("migrated cache key %s -> %s", old, new)
        except Exception as e:
            log.warning("cache key migration failed: %s", e)

    def _count_total(self) -> int:
        return len(self._rows)

    def _count_steam(self) -> int:
        return sum(1 for row in self._rows if steammod.is_steam_id(row[0]))

    def _count_local(self) -> int:
        return sum(1 for row in self._rows if not steammod.is_steam_id(row[0]))

    def _count_steam_detected(self) -> int:
        return self._steam_detected

    totalCount = Property(int, _count_total, notify=refreshed)
    steamCount = Property(int, _count_steam, notify=refreshed)
    localCount = Property(int, _count_local, notify=refreshed)
    steamDetectedCount = Property(int, _count_steam_detected, notify=refreshed)

    def roleNames(self) -> dict:
        # game-prefixed: bare Qt6 delegate properties must never collide
        # with the delegate item's own properties (name/source do).
        return {
            GameListModel.IdRole: b"gameId",
            GameListModel.NameRole: b"gameName",
            GameListModel.OriginRole: b"gameOrigin",
            GameListModel.PlayedRole: b"gamePlayed",
            GameListModel.TierRole: b"gameTier",
            GameListModel.TierBgRole: b"gameTierBg",
            GameListModel.TierFgRole: b"gameTierFg",
            GameListModel.IconRole: b"gameIcon",
            GameListModel.PlayedSecsRole: b"gamePlayedSecs",
            GameListModel.PlayedTipRole: b"gamePlayedTip",
            GameListModel.LastPlayedRole: b"gameLastPlayed",
            GameListModel.LastSecsRole: b"gameLastSecs",
            GameListModel.PlatformRole: b"gamePlatform",
            GameListModel.RuntimeRole: b"gameRuntime",
            GameListModel.WineRole: b"gameWine",
            GameListModel.InstallDirRole: b"gameInstallDir",
            GameListModel.CategoryRole: b"gameCategory",
            GameListModel.RunningRole: b"gameRunning",
            GameListModel.CoverRole: b"gameCover",
            GameListModel.IssueLevelRole: b"gameIssueLevel",
            GameListModel.IssuesTipRole: b"gameIssuesTip",
            GameListModel.ReleaseDateRole: b"gameReleaseDate",
            GameListModel.InstalledAtRole: b"gameInstalledAt",
            GameListModel.StatusRole: b"gameStatus",
            GameListModel.StatusBgRole: b"gameStatusBg",
            GameListModel.StatusFgRole: b"gameStatusFg",
        }

    def rowCount(self, parent: QModelIndex | None = None) -> int:
        return 0 if (parent is not None and parent.isValid()) else len(self._rows)

    def columnCount(self, parent: QModelIndex | None = None) -> int:
        # Fixed logical columns (proxy permutes/hides them for the view).
        return 0 if (parent is not None and parent.isValid()) else 13

    def index(self, row: int, column: int, parent: QModelIndex | None = None):
        # Table models own their indexes (unlike proxy mapping, this is safe).
        if parent is not None and parent.isValid():
            return QModelIndex()
        if 0 <= row < len(self._rows) and 0 <= column < 13:
            return self.createIndex(row, column)
        return QModelIndex()

    def data(self, index: QModelIndex, role: int = Qt.ItemDataRole.DisplayRole):
        if not index.isValid() or not 0 <= index.row() < len(self._rows):
            return None
        row = self._rows[index.row()]
        if role == GameListModel.RunningRole:
            return self.isRunning(str(row[0]))
        if role == GameListModel.IssueLevelRole:
            return self._issue_level(str(row[0]))
        if role == GameListModel.IssuesTipRole:
            return self._issue_tip(str(row[0]))
        cols = {
            GameListModel.IdRole: 0,
            GameListModel.NameRole: 1,
            GameListModel.OriginRole: 2,
            GameListModel.PlayedRole: 3,
            GameListModel.TierRole: 4,
            GameListModel.TierBgRole: 5,
            GameListModel.TierFgRole: 6,
            GameListModel.IconRole: 7,
            GameListModel.PlayedSecsRole: 8,
            GameListModel.PlayedTipRole: 9,
            GameListModel.LastPlayedRole: 10,
            GameListModel.LastSecsRole: 11,
            GameListModel.PlatformRole: 12,
            GameListModel.RuntimeRole: 13,
            GameListModel.WineRole: 14,
            GameListModel.InstallDirRole: 15,
            GameListModel.CategoryRole: 16,
            GameListModel.CoverRole: 17,
            GameListModel.ReleaseDateRole: 18,
            GameListModel.InstalledAtRole: 19,
            GameListModel.StatusRole: 20,
            GameListModel.StatusBgRole: 21,
            GameListModel.StatusFgRole: 22,
        }
        return row[cols[role]] if role in cols else None

    @Slot(int, result="QVariantMap")
    def rowData(self, row: int) -> dict:
        """Display roles for one source row (feeds the proxy rowData)."""
        keys = (
            "gameId",
            "gameName",
            "gameOrigin",
            "gamePlayed",
            "gameTier",
            "gameTierBg",
            "gameTierFg",
            "gameIcon",
            "gamePlayedSecs",
            "gamePlayedTip",
            "gameLastPlayed",
            "gameLastSecs",
            "gamePlatform",
            "gameRuntime",
            "gameWine",
            "gameInstallDir",
            "gameCategory",
            "gameCover",
            "gameReleaseDate",
            "gameInstalledAt",
            "gameStatus",
            "gameStatusBg",
            "gameStatusFg",
        )
        if not 0 <= row < len(self._rows):
            return {}
        data = dict(zip(keys, self._rows[row], strict=True))
        data["gameRunning"] = self.isRunning(str(self._rows[row][0]))
        return data

    @staticmethod
    def _all_names() -> dict[str, str]:
        """Display names of every game: Steam library first, locals merged."""
        names = {a: n for a, n in steammod.list_games()}
        names.update(steammod.local_names())
        return names

    @Slot()
    def refresh(self) -> None:
        """Reload rows from disk (Steam names first, local names merged)."""
        if self._closing:
            return
        # Captured before parsing: a line appended mid-read changes the
        # signature again and the next poll refreshes.
        self._log_sig = self._log_signature()
        self._steam_detected = len(steammod.list_games())
        names = self._all_names()
        # Drop stale validation results: configs may have changed on disk.
        self._issues_cache = {}
        try:
            stats = histmod.summarize(histmod.parse_log(xdg.log_file()))
        except Exception:
            stats = {}
        rows = [self._row(appid, names, stats) for appid in cfgmod.list_appids()]
        rows.sort(key=lambda r: r[1].lower())
        running = self._load_running()
        running_changed = running.keys() != self._running.keys()
        self._running = running
        try:
            self._sync_category_store()
        except Exception as e:
            log.warning("category store not synced: %s", e)
        self.beginResetModel()
        self._rows = rows
        self.endResetModel()
        if running_changed:
            self.runningChanged.emit()
        self.refreshed.emit()

    @Slot()
    def reload(self) -> None:
        """Reload rows and drop the Steam games cache first (the Reload action)."""
        steammod.clear_games_cache()
        self.refresh()

    def _load_running(self) -> dict[str, dict]:
        """Live running records by AppID (never raises: a poll, not a load)."""
        try:
            return runningmod.list_running()
        except Exception as e:
            log.warning("running records unreadable: %s", e)
            return {}

    def _stop_timers(self) -> None:
        self._closing = True
        for timer in (self._running_timer, self._kill_timer):
            try:
                timer.stop()
            except RuntimeError:
                pass  # already deleted with the C++ parent

    def _refresh_running(self) -> None:
        """Re-read the launcher's records; repaint only on a change."""
        if self._closing:
            return
        running = self._load_running()
        changed = running.keys() != self._running.keys()
        self._running = running
        pending = self._kill_record
        if pending is not None:
            live = running.get(str(pending.get("appid")))
            # The game exited (or a new launch replaced it): the escalating
            # SIGKILL would hit the launcher's post-hook instead.
            if live is None or live.get("pid") != pending.get("pid"):
                self._kill_timer.stop()
                self._kill_record = None
        if not changed:
            return
        if self._rows:
            self.dataChanged.emit(
                self.index(0, 0),
                self.index(len(self._rows) - 1, self.columnCount() - 1),
                [GameListModel.RunningRole],
            )
        self.runningChanged.emit()

    @staticmethod
    def _log_signature() -> tuple[int, int] | None:
        """(mtime_ns, size) of the global log; None when it is absent."""
        try:
            st = xdg.log_file().stat()
        except OSError:
            return None
        return st.st_mtime_ns, st.st_size

    def _poll_history(self) -> None:
        """Reload rows when the launcher appended a session line."""
        if self._closing:
            return
        if self._log_signature() != self._log_sig:
            self.refresh()

    def _running_ids(self) -> list[str]:
        return list(self._running)

    # QML bindings cannot depend on isRunning(); this list is their
    # notifying dependency (menu entries, badges).
    runningIds = Property("QVariantList", _running_ids, notify=runningChanged)

    @Slot(str, result=bool)
    def isRunning(self, appid: str) -> bool:
        """True while a launcher we started still has the game open."""
        return str(appid) in self._running

    @Slot(str, result=bool)
    def terminate(self, appid: str) -> bool:
        """Ask the game's launcher to stop it (SIGTERM, then SIGKILL)."""
        record = runningmod.terminate(appid)
        name = self._display_name(appid)
        if record is None:
            self._refresh_running()
            self.terminateReported.emit(False, name, "")
            return False
        self._kill_record = record
        self._kill_timer.start(self.TERMINATE_GRACE_MS)
        self.terminateReported.emit(True, name, "")
        return True

    def _force_kill(self) -> None:
        """A launcher that ignored SIGTERM takes the group down with it."""
        if self._closing:
            return
        record, self._kill_record = self._kill_record, None
        # Only while that very launcher still holds the record: after the
        # game exits the launcher runs its post-hook with the record gone,
        # and SIGKILL there would skip the display/audio restore.
        live = runningmod.read(str(record.get("appid"))) if record else None
        if live is not None and live.get("pid") == record.get("pid") and runningmod.kill(record):
            log.warning("terminate: SIGKILL to the process group of pid %s", record.get("pid"))
        self._refresh_running()

    def _row(self, appid: str, names: dict, stats: dict) -> tuple:
        """One table row for an AppID (column order mirrors `rowData`)."""
        played, played_secs, played_tip, last_played, last_secs = _played_cells(stats.get(appid))
        try:
            gcfg = cfgmod.load(appid)
        except Exception:
            gcfg = None
        origin = steammod.origin(appid)
        is_steam = origin == "steam"
        # ProtonDB needs a Steam AppID: the game's own or its store link.
        target = self._steam_target(appid, gcfg)
        data, _fresh = pdbmod.cached(appid, target) if target else (None, False)
        tier = str(((data or {}).get("tier", "")) or "").lower()
        bg, fg = pdbmod.TIER_STYLE.get(tier, ("", ""))
        icon = self._row_icon(appid, gcfg)
        cover = self._row_cover(appid, gcfg)
        label = cfgmod.game_display_name(names.get(appid, appid), gcfg)
        status = gcfg.metadata.status if gcfg is not None else ""
        status_bg, status_fg = STATUS_STYLE.get(status, ("", ""))
        return (
            appid,
            label,
            origin.title(),
            played,
            tier.title(),
            bg,
            fg,
            str(icon) if icon else "",
            played_secs,
            played_tip,
            last_played,
            last_secs,
            cfgmod.platform_for(gcfg.runtime.type) if gcfg is not None else "",
            (
                cfgmod.runtime_short_label(gcfg.runtime.type, is_steam, gcfg.runtime.steam_runtime)
                or "Not Set"
            )
            if gcfg is not None
            else "",
            self._row_wine(appid, gcfg, is_steam),
            self._row_install_dir(appid, gcfg),
            ", ".join(gcfg.general.categories) if gcfg is not None else "",
            str(cover) if cover else "",
            self._row_release_date(appid, gcfg, is_steam),
            self._row_installed(appid, gcfg),
            status,
            status_bg,
            status_fg,
        )

    @staticmethod
    def _steam_target(appid: str, gcfg=None, draft: str = "") -> str:
        """Numeric Steam AppID for store lookups ("" when the game has none).

        A Steam ID derives its AppID. A local game uses the Steam store
        link typed in the dialog (``draft``), else ``[metadata]
        steam_appid``; ProtonDB, the store metadata and the release date
        share this target. The Artwork Source AppID is art-only and never
        used here.
        """
        numeric = steammod.steam_appid(appid)
        if numeric:
            return numeric
        value = str(draft or "").strip()
        if value:
            return value if value.isdigit() else ""
        if gcfg is None:
            try:
                gcfg = cfgmod.load(str(appid))
            except Exception:
                return ""
        return cfgmod.normalize_steam_appid(gcfg.metadata.steam_appid) if gcfg is not None else ""

    @staticmethod
    def _art_source(appid: str, draft: str = "") -> str:
        """Artwork Source AppID: the dialog draft when given, else the config."""
        value = str(draft or "").strip()
        if value:
            return value
        try:
            return cfgmod.load(str(appid)).artwork.artwork_appid.strip()
        except Exception:
            return ""

    @staticmethod
    def _row_cover(appid: str, gcfg) -> Path | None:
        """Card cover: the Artwork Source AppID's art first, then the game's."""
        source = ""
        if gcfg is not None:
            source = gcfg.artwork.artwork_appid.strip()
        try:
            return artmod.resolve(appid, "cover", source)[0]
        except Exception as e:
            log.warning("artwork resolve(%s, cover) failed: %s", appid, e)
            return None

    @staticmethod
    def _row_icon(appid: str, gcfg) -> Path | None:
        """Row icon: the Artwork Source AppID's art first, then the game's."""
        source = ""
        if gcfg is not None:
            source = gcfg.artwork.artwork_appid.strip()
        try:
            return artmod.resolve(appid, "icon", source, GameListModel._local_exe(appid, gcfg))[0]
        except Exception as e:
            log.warning("artwork resolve(%s) failed: %s", appid, e)
            return None

    @staticmethod
    def _local_exe(appid: str, gcfg=None) -> str:
        """Executable whose embedded icon fills a local game's icon slot."""
        if not str(appid).startswith("local-"):
            return ""
        try:
            cfg = gcfg if gcfg is not None else cfgmod.load(str(appid))
        except Exception:
            return ""
        return (cfg.general.custom_executable or "").strip() if cfg is not None else ""

    @staticmethod
    def _row_wine(appid: str, gcfg, is_steam: bool, with_version: bool = False) -> str:
        """Wine/Proton label; a dash when the game runs natively."""
        if is_steam:
            from .. import proton as protonmod

            try:
                if gcfg is not None and gcfg.runtime.type == cfgmod.RuntimeType.NATIVE:
                    return "—"
                tool = protonmod.compat_tool_name(appid)
                if tool and protonmod.is_steam_runtime_tool(tool):
                    return "—"
                return protonmod.tool_display(appid, with_version=with_version)
            except Exception:
                return "—"
        tool = (gcfg.runtime.tool or "").strip() if gcfg is not None else ""
        if not tool or gcfg.runtime.type == cfgmod.RuntimeType.NATIVE:
            return "—"
        if gcfg.runtime.type == cfgmod.RuntimeType.UMU:
            return Path(tool.rstrip("/")).name or tool
        return tool

    @staticmethod
    def _row_release_date(appid: str, gcfg, is_steam: bool) -> str:
        """Manual metadata date first, else the cached Steam store date."""
        if gcfg is not None and gcfg.metadata.date.strip():
            return gcfg.metadata.date.strip()
        if not is_steam:
            return "—"
        try:
            date, _fresh = rdmod.cached(appid)
        except Exception:
            date = ""
        return date or "—"

    @staticmethod
    def _row_installed(appid: str, gcfg) -> str:
        """First-save timestamp, falling back to the config file's birth time."""
        stamp = gcfg.general.installed_at if gcfg is not None else ""
        if not stamp:
            try:
                stamp = cfgmod.installed_stamp(cfgmod.game_file(appid))
            except Exception:
                stamp = ""
        return stamp.replace("T", " ")[:16] if stamp else "—"

    @staticmethod
    def _row_install_dir(appid: str, gcfg) -> str:
        """Steam install dir, falling back to the custom executable's folder."""
        try:
            install = steammod.install_dir(appid)
            install_dir = os.fspath(install) if install else ""
        except Exception:
            install_dir = ""
        if not install_dir and gcfg is not None and gcfg.general.custom_executable:
            exe = Path(gcfg.general.custom_executable).expanduser()
            install_dir = str(exe.parent) if exe.name else ""
        return install_dir

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
        cfg.runtime.type = "native"
        cfgmod.save(cfg)
        self.refresh()
        # The new game's art comes from a name lookup now, not at next start.
        self._fetch_async([appid])
        return appid

    @Slot()
    def browseExecutable(self) -> None:
        """Native file picker off the GUI thread; result via browseFinished.

        Blocking D-Bus round-trips must never freeze the interface: the
        worker reports back ("" included) through the signal.
        """
        threading.Thread(
            target=self._pick_worker,
            args=("Game Executable", "Select", False, ""),
            daemon=True,
        ).start()

    @Slot(str, str)
    def pickDir(self, title: str, accept_label: str) -> None:
        """Generic folder picker off the GUI thread; result via browseFinished."""
        threading.Thread(
            target=self._pick_dir_worker,
            args=(title or "Pick a Folder", accept_label or "Select"),
            daemon=True,
        ).start()

    def _pick_dir_worker(self, title: str, accept_label: str) -> None:
        from ..backends import portal as portalmod

        try:
            path = portalmod.pick_dir(title, accept_label)
        except Exception as e:
            log.warning("pick dir worker failed: %s", e)
            path = ""
        self.browseFinished.emit(path)

    @Slot(str, str)
    def pickPath(self, title: str, accept_label: str) -> None:
        """Generic open picker off the GUI thread; result via browseFinished."""
        threading.Thread(
            target=self._pick_worker,
            args=(title or "Pick a File", accept_label or "Open", False, ""),
            daemon=True,
        ).start()

    @Slot(str, str, str)
    def pickSavePath(self, title: str, accept_label: str, filename: str) -> None:
        """Generic save picker off the GUI thread; result via browseFinished."""
        threading.Thread(
            target=self._pick_worker,
            args=(title or "Save File", accept_label or "Save", True, filename or ""),
            daemon=True,
        ).start()

    def _pick_worker(self, title: str, accept_label: str, save: bool, filename: str) -> None:
        from ..backends import portal as portalmod

        try:
            if save:
                path = portalmod.pick_save_file(title, accept_label, filename)
            else:
                path = portalmod.pick_file(title, accept_label)
        except Exception as e:  # never kill the thread pool on a picker bug
            log.warning("pick worker failed: %s", e)
            path = ""
        self.browseFinished.emit(path)

    @staticmethod
    def _game_to_map(cfg, appid: str, warning: str = "") -> dict:
        """Settings form fields for a config (games, factory, defaults)."""
        try:
            profiles = cfgmod.list_profiles(appid)
        except Exception:
            profiles = []
        g = cfg.general
        return {
            "appid": g.appid,
            "load_warning": warning or "",
            "name": g.name,
            "version": cfg.metadata.version,
            "date": cfg.metadata.date,
            "tag": cfg.metadata.tag,
            "description": cfg.metadata.description,
            "developer": cfg.metadata.developer,
            "publisher": cfg.metadata.publisher,
            "genre": cfg.metadata.genre,
            "series": cfg.metadata.series,
            "age_ratings": list(cfg.metadata.age_ratings),
            "region": cfg.metadata.region,
            "status": cfg.metadata.status,
            "locked": cfg.metadata.locked,
            "steam_appid": cfg.metadata.steam_appid,
            "vndb_id": cfg.metadata.vndb_id,
            "igdb_id": cfg.metadata.igdb_id,
            "tags": list(cfg.metadata.tags),
            "custom_executable": g.custom_executable,
            "runtime_type": cfgmod.normalize_runtime(cfg.runtime.type),
            "show_menu": bool(g.show_menu),
            "menu_timeout": max(0, min(600, int(g.menu_timeout or 0))),
            "custom_prefix": g.custom_prefix,
            "active_profile": g.active_profile,
            "categories": list(g.categories),
            "launch_args": g.launch_args,
            "launch_cwd": g.launch_cwd,
            "art_icon": cfg.artwork.icon,
            "art_cover": cfg.artwork.cover,
            "art_banner": cfg.artwork.banner,
            "art_background": cfg.artwork.background,
            "art_source": cfg.artwork.artwork_appid,
            "art_provider": cfg.artwork.provider,
            "notes": cfg.notes.text,
            "profiles": profiles,
            "is_steam": bool(steammod.is_steam_id(appid)),
            "env_vars": [{"key": k, "value": v} for k, v in cfg.env.vars.items()],
            "pre_command": cfg.pre_post.pre_command,
            "pre_args": shlex.join(cfg.pre_post.pre_args),
            "post_command": cfg.pre_post.post_command,
            "post_args": shlex.join(cfg.pre_post.post_args),
            "pp_timeout": max(1, min(3600, int(cfg.pre_post.timeout or 60))),
            "run_in_shell": bool(cfg.pre_post.run_in_shell),
            "gamemode_feral": bool(cfg.gamemode.feral_gamemode),
            "gamemode_cachy": bool(cfg.gamemode.cachyos_game_performance),
            "display_provider": cfg.display.provider
            if cfg.display.provider in ("auto", "plasma", "gnome", "wlroots", "x11", "off")
            else "auto",
            "display_output": cfg.display.output,
            "display_mode": cfg.display.mode,
            "dip_seconds": max(3, min(15, int(cfg.display.dip_seconds or 8))),
            "gamescope_enable": bool(cfg.gamescope.enable),
            "gamescope_args": cfg.gamescope.args,
            "mangohud_enable": bool(cfg.mangohud.enable),
            "mangohud_args": cfg.mangohud.args,
            "mangohud_config": cfg.mangohud.config_file,
            "mangohud_fps": max(0, int(cfg.mangohud.fps_limit or 0)),
            "rt_enable": bool(cfg.rtupscale.enable),
            "rt_args": cfg.rtupscale.args,
            "ludusavi_enable": bool(cfg.ludusavi.enable),
            "ludusavi_restore": bool(cfg.ludusavi.restore),
            "ludusavi_backup": bool(cfg.ludusavi.backup),
            "ludusavi_name": cfg.ludusavi.name_override,
            "ludusavi_gui": bool(cfg.ludusavi.use_gui),
            "notify_on_launch": bool(cfg.notifications.notify_on_launch),
            "inhibit_idle": bool(cfg.session.inhibit_idle),
            "block_internet": bool(cfg.network.block_internet),
            "nl_disable": bool(cfg.nightlight.disable_during_game),
            "nl_provider": cfg.nightlight.provider
            if cfg.nightlight.provider in ("auto", "plasma", "gnome", "off")
            else "auto",
            "fresh_prefix": bool(cfg.runtime.fresh_prefix),
            "audio_sink": cfg.audio.sink,
            "winetricks_verbs": " ".join(cfg.runtime.winetricks_verbs),
            "proton_log": bool(cfg.debug.proton_log),
            "winedebug": cfg.debug.winedebug,
            "runtime_prefix": cfg.runtime.prefix,
            "runtime_prefix_name": cfg.runtime.prefix_name,
            "runtime_tool": cfg.runtime.tool,
            "runtime_steam_runtime": cfg.runtime.steam_runtime,
            "graphics_dxvk": bool(cfg.graphics.dxvk),
            "graphics_dxvk_version": cfg.graphics.dxvk_version,
            "graphics_vkd3d": cfgmod.normalize_graphics_vkd3d(cfg.graphics.vkd3d),
            "graphics_vkd3d_version": cfg.graphics.vkd3d_version,
        }

    @Slot(str, result="QVariantMap")
    def loadGame(self, appid: str) -> dict:
        """Settings form fields plus profile names for one game."""
        try:
            cfg, warning = cfgmod.load_with_warning(appid)
        except Exception as e:  # unknown id: empty form, never a traceback
            log.warning("loadGame(%s) failed: %s", appid, e)
            return {}
        return self._game_to_map(cfg, appid, warning or "")

    @Slot(result="QVariantMap")
    def loadDefaults(self) -> dict:
        """Global defaults template for the settings UI."""
        try:
            return self._game_to_map(cfgmod.load_defaults(), "")
        except Exception as e:
            log.warning("loadDefaults failed: %s", e)
            return {}

    @Slot(str, result="QVariantMap")
    def factoryGame(self, appid: str) -> dict:
        """Built-in factory fields (defaults editor Reset, unsaved until Save)."""
        cfg = cfgmod.GameConfig()
        cfg.general.appid = appid
        return self._game_to_map(cfg, appid)

    @staticmethod
    def _keep_local_identity(cfg, live) -> None:
        """Keep what identifies and launches a local game across a Reset."""
        cfg.general.name = live.general.name
        cfg.general.custom_executable = live.general.custom_executable
        cfg.runtime.type = live.runtime.type
        cfg.runtime.tool = live.runtime.tool
        cfg.runtime.prefix = live.runtime.prefix
        cfg.runtime.prefix_name = live.runtime.prefix_name

    @Slot(str, result="QVariantMap")
    def templateGame(self, appid: str) -> dict:
        """The user's Global Defaults template as fields for one game.

        Widgets parity (_on_reset): Reset applies defaults.toml, never the
        built-in factory values, and the AppID is kept. A local game keeps
        its identity (name, executable, runtime); profiles are not touched
        (the caller clears the active profile).
        """
        try:
            cfg = cfgmod.load_defaults()
            cfg.general.appid = appid
            if appid and steammod.origin(appid) == "local":
                self._keep_local_identity(cfg, cfgmod.load(appid))
        except Exception as e:
            log.warning("templateGame(%s) failed: %s", appid, e)
            return {}
        return self._game_to_map(cfg, appid)

    @Slot(str, str, result=bool)
    def needsNewerApp(self, appid: str, profile: str) -> bool:
        """True when the source behind the dialog stamps a newer version.

        Widgets _refresh_newer_flag parity: `profile` empty means the live
        file, `appid` empty means the Global Defaults template. Gates Save
        and Reset so a downgrade is explicit.
        """
        if appid:
            path = (
                cfgmod.profile_file(appid, profile)
                if str(profile or "")
                else cfgmod.game_file(appid)
            )
        else:
            path = xdg.defaults_file()
        try:
            return cfgmod.needs_newer_app(path)
        except Exception as e:
            log.warning("needsNewerApp(%s, %s) failed: %s", appid, profile, e)
            return False

    @Slot(str, result=bool)
    def metadataDateValid(self, value: str) -> bool:
        """Release-date shape accepted by the metadata field."""
        return cfgmod.metadata_date_valid(str(value or ""))

    @Slot(str, "QVariantMap", result=str)
    def saveGame(self, appid: str, values) -> str:
        """Persist the General-section fields. Returns the id, or ''."""
        data = dict(values or {})
        # A trailing [version] typed into the name moves into its own
        # field; Steam names are Steam's and never rewritten.
        if not appid or not steammod.is_steam_id(appid):
            name, version = cfgmod.split_name_version(str(data.get("name", "")))
            data["name"] = name
            if version and not str(data.get("version", "")).strip():
                data["version"] = version
        if not appid:
            cfg = self._new_local_game(data)
            if cfg is None:
                return ""
            appid = cfg.general.appid
        else:
            cfg = self._load_or_new(appid)
            if cfg is None:
                return ""
            if not steammod.is_steam_id(appid):
                cfg.general.name = str(data.get("name", "")).strip()
        active = str(data.get("active_profile", "")).strip()
        if appid and active:
            return self._save_profile(appid, active, data)
        is_new = not cfgmod.game_file(appid).is_file()
        old_link = cfgmod.normalize_steam_appid(cfg.metadata.steam_appid)
        self._apply_map(cfg, data)
        try:
            cfgmod.save(cfg)
        except Exception as e:
            log.warning("saveGame(%s) failed: %s", appid, e)
            return ""
        self.refresh()
        self._fetch_on_save(appid, is_new or cfg.metadata.steam_appid != old_link)
        return appid

    def _fetch_on_save(self, appid: str, needed: bool) -> None:
        """Fill missing art after every save; new games also get metadata.

        The pass is cache-aware, so a game with all its art costs no
        request; a new game or a changed Steam store link also gets the
        store metadata (only a Steam id has one).
        """
        # A Steam game also gets its store metadata for a new game or a
        # changed link: the source is official and there is nothing to lose.
        self._fetch_async([appid], enrich=needed)

    @staticmethod
    def _new_local_game(data: dict):
        """Defaults config for a brand-new local game, or None when invalid."""
        err = validate_local_game(str(data.get("name", "")), str(data.get("custom_executable", "")))
        if err:
            log.warning("saveGame create rejected: %s", err)
            return None
        name = str(data.get("name", "")).strip()
        cfg = cfgmod.load_defaults()
        cfg.general.appid = cfgmod.new_local_id(name)
        cfg.general.name = name
        return cfg

    @staticmethod
    def _load_or_new(appid: str):
        """The saved config, defaults for an unsaved Steam id, else None.

        Uses load_with_warning, so a config written by a newer TKArcade (or
        an unreadable one) can still be overwritten once the GUI gate has
        asked -- the widgets saved the same fallback config.
        """
        if cfgmod.game_file(appid).is_file():
            try:
                cfg, _warning = cfgmod.load_with_warning(appid)
                return cfg
            except Exception as e:
                log.warning("saveGame(%s) failed: %s", appid, e)
                return None
        if not steammod.is_steam_id(appid):
            log.warning("saveGame(%s) rejected: unknown game", appid)
            return None
        cfg = cfgmod.load_defaults()
        cfg.general.appid = appid
        return cfg

    def _save_profile(self, appid: str, active: str, data: dict) -> str:
        """Write the form into the active profile and mark it active."""
        try:
            known = cfgmod.list_profiles(appid)
        except Exception:
            known = []
        if active not in known:
            log.warning("saveGame(%s) rejected: unknown profile", appid)
            return ""
        try:
            prof = cfgmod.load_profile(appid, active)
        except Exception as e:
            log.warning("saveGame(%s) failed: %s", appid, e)
            return ""
        prof.general.appid = appid
        if not steammod.is_steam_id(appid):
            prof.general.name = str(data.get("name", "")).strip()
        self._apply_map(prof, data)
        try:
            cfgmod.save_profile(appid, active, prof)
            live, _warning = cfgmod.load_with_warning(appid)
            live.general.active_profile = active
            cfgmod.save(live)
        except Exception as e:
            log.warning("saveGame(%s) failed: %s", appid, e)
            return ""
        self.refresh()
        return appid

    @staticmethod
    def _pin_prefix_name(cfg) -> None:
        """Pin the folder name derived from the game name.

        A rename must never move the prefix, so the derived name is kept
        in ``[runtime] prefix_name`` (the dialog shows it from then on).
        """
        if cfg.runtime.prefix_name or steammod.is_steam_id(cfg.general.appid):
            return
        stem = xdg.folder_stem(cfg.general.name)
        if stem:
            cfg.runtime.prefix_name = stem

    @staticmethod
    def _apply_map(cfg, data: dict) -> None:
        """Write settings form fields into a config (no save, no refresh)."""
        cfg.general.custom_executable = str(data.get("custom_executable", "")).strip()
        cfg.runtime.type = cfgmod.normalize_runtime(data.get("runtime_type", ""))
        cfg.general.show_menu = bool(data.get("show_menu", False))
        try:
            cfg.general.menu_timeout = max(0, min(600, int(data.get("menu_timeout", 0) or 0)))
        except (TypeError, ValueError):
            cfg.general.menu_timeout = 0
        cfg.general.custom_prefix = str(data.get("custom_prefix", "")).strip()
        cfg.runtime.prefix = str(data.get("runtime_prefix", "")).strip()
        cfg.runtime.prefix_name = str(data.get("runtime_prefix_name", "")).strip()
        GameListModel._pin_prefix_name(cfg)
        cfg.runtime.tool = str(data.get("runtime_tool", "")).strip()
        cfg.runtime.steam_runtime = cfgmod.normalize_steam_runtime(
            data.get("runtime_steam_runtime", "")
        )
        cfg.graphics.dxvk = bool(data.get("graphics_dxvk", False))
        cfg.graphics.dxvk_version = str(data.get("graphics_dxvk_version", "")).strip()
        cfg.graphics.vkd3d = cfgmod.normalize_graphics_vkd3d(data.get("graphics_vkd3d", ""))
        cfg.graphics.vkd3d_version = str(data.get("graphics_vkd3d_version", "")).strip()
        cats = data.get("categories", [])
        if isinstance(cats, str):
            cats = [c.strip() for c in cats.split(",")]
        cfg.general.categories = cfgmod.normalize_categories(cats)
        cfg.general.launch_args = str(data.get("launch_args", "")).strip()
        cfg.general.launch_cwd = str(data.get("launch_cwd", "")).strip()
        _apply_metadata(cfg, data)
        cfg.artwork.icon = str(data.get("art_icon", "")).strip()
        cfg.artwork.cover = str(data.get("art_cover", "")).strip()
        cfg.artwork.banner = str(data.get("art_banner", "")).strip()
        cfg.artwork.background = str(data.get("art_background", "")).strip()
        cfg.artwork.artwork_appid = str(data.get("art_source", "")).strip()
        cfg.artwork.provider = cfgmod.normalize_artwork_provider(data.get("art_provider", ""))
        cfg.notes.text = str(data.get("notes", ""))
        env_vars = {}
        for row in data.get("env_vars", []) or []:
            if isinstance(row, dict):
                key = str(row.get("key", "")).strip()
                if key:
                    env_vars[key] = str(row.get("value", ""))
        cfg.env.vars = env_vars
        cfg.pre_post.pre_command = str(data.get("pre_command", "")).strip()
        cfg.pre_post.pre_args = _split_args(str(data.get("pre_args", "")))
        cfg.pre_post.post_command = str(data.get("post_command", "")).strip()
        cfg.pre_post.post_args = _split_args(str(data.get("post_args", "")))
        try:
            cfg.pre_post.timeout = max(1, min(3600, int(data.get("pp_timeout", 60) or 60)))
        except (TypeError, ValueError):
            cfg.pre_post.timeout = 60
        cfg.pre_post.run_in_shell = bool(data.get("run_in_shell", False))
        cfg.gamemode.feral_gamemode = bool(data.get("gamemode_feral", False))
        cfg.gamemode.cachyos_game_performance = bool(data.get("gamemode_cachy", False))
        provider = str(data.get("display_provider", "auto"))
        cfg.display.provider = (
            provider if provider in ("auto", "plasma", "gnome", "wlroots", "x11", "off") else "auto"
        )
        cfg.display.output = str(data.get("display_output", "")).strip()
        cfg.display.mode = str(data.get("display_mode", "")).strip()
        try:
            cfg.display.dip_seconds = max(3, min(15, int(data.get("dip_seconds", 8) or 8)))
        except (TypeError, ValueError):
            cfg.display.dip_seconds = 8
        cfg.gamescope.enable = bool(data.get("gamescope_enable", False))
        cfg.gamescope.args = str(data.get("gamescope_args", "")).strip()
        cfg.mangohud.enable = bool(data.get("mangohud_enable", False))
        cfg.mangohud.args = str(data.get("mangohud_args", "")).strip()
        cfg.mangohud.config_file = str(data.get("mangohud_config", "")).strip()
        try:
            cfg.mangohud.fps_limit = max(0, int(data.get("mangohud_fps", 0) or 0))
        except (TypeError, ValueError):
            cfg.mangohud.fps_limit = 0
        cfg.rtupscale.enable = bool(data.get("rt_enable", False))
        cfg.rtupscale.args = str(data.get("rt_args", "")).strip()
        cfg.ludusavi.enable = bool(data.get("ludusavi_enable", False))
        cfg.ludusavi.restore = bool(data.get("ludusavi_restore", True))
        cfg.ludusavi.backup = bool(data.get("ludusavi_backup", True))
        cfg.ludusavi.name_override = str(data.get("ludusavi_name", "")).strip()
        cfg.ludusavi.use_gui = bool(data.get("ludusavi_gui", True))
        cfg.notifications.notify_on_launch = bool(data.get("notify_on_launch", True))
        cfg.session.inhibit_idle = bool(data.get("inhibit_idle", False))
        cfg.network.block_internet = bool(data.get("block_internet", False))
        cfg.nightlight.disable_during_game = bool(data.get("nl_disable", False))
        nl_provider = str(data.get("nl_provider", "auto"))
        cfg.nightlight.provider = (
            nl_provider if nl_provider in ("auto", "plasma", "gnome", "off") else "auto"
        )
        cfg.runtime.fresh_prefix = bool(data.get("fresh_prefix", False))
        cfg.runtime.winetricks_verbs = _split_args(str(data.get("winetricks_verbs", "")))
        cfg.audio.sink = str(data.get("audio_sink", "")).strip()
        cfg.debug.proton_log = bool(data.get("proton_log", False))
        cfg.debug.winedebug = str(data.get("winedebug", ""))

    @Slot(result=bool)
    def networkIsolationAvailable(self) -> bool:
        """True when the launcher can build an unprivileged network namespace."""
        return net_backend.available()

    @Slot("QVariantMap", result=bool)
    def saveDefaults(self, values) -> bool:
        """Persist the global defaults template."""
        try:
            cfg = cfgmod.load_defaults()
            self._apply_map(cfg, dict(values or {}))
            cfgmod.save_defaults(cfg)
        except Exception as e:
            log.warning("saveDefaults failed: %s", e)
            return False
        return True

    @Slot(str, result=list)
    def cloneTargets(self, exclude: str) -> list:
        """Configured games except one: [[appid, name]], by name."""
        try:
            names = self._all_names()
            rows = [[a, names.get(a, a)] for a in sorted(set(cfgmod.list_appids()) - {exclude})]
        except Exception:
            return []
        return sorted(rows, key=lambda r: r[1].lower())

    @Slot(result=list)
    def pickableGames(self) -> list:
        """Every game the standalone editor can pick: [[appid, name]].

        Configured games first (config order), then Steam/local ones not
        configured yet, sorted by name -- the order the widgets picker
        used. QML rebuilds a fresh JS array from it (never a list handed
        in from Python: Repeater models must stay JS).
        """
        try:
            names = self._all_names()
            configured = list(cfgmod.list_appids())
            rows = [[a, names.get(a, a)] for a in configured]
            known = set(configured)
            extra = sorted(
                ([a, n] for a, n in names.items() if a not in known),
                key=lambda r: str(r[1]).lower(),
            )
        except Exception:
            return []
        return rows + extra

    @Slot(str, result="QVariantMap")
    def playStats(self, appid: str) -> dict:
        """Sessions + total playtime for one game ({} when never played).

        The pre-launch menu shows this; both pieces are formatted here so
        the QML side only lays out translatable text.
        """
        try:
            stats = histmod.summarize(histmod.parse_log(xdg.log_file())).get(appid or "")
        except Exception:
            return {}
        if stats is None or not stats.runs:
            return {}
        return {"runs": stats.runs, "total": format_duration(stats.total_dur)}

    @Slot(str, result=str)
    def activeWrappers(self, appid: str) -> str:
        """Enabled wrappers for one game ("GameMode · MangoHud"; "" none)."""
        try:
            if not appid:
                return ""
            wrappers = launchermod.active_wrappers(cfgmod.load_effective(appid))
        except Exception:
            return ""
        return " · ".join(wrappers)

    @Slot(str, result=str)
    def detectedRuntime(self, appid: str) -> str:
        """Proton tool/version for a Steam game (widgets parity).

        The Native case is translated in QML ("Native (no Proton)").
        """
        try:
            if not appid or not steammod.is_steam_id(appid):
                return ""
            return self._row_wine(appid, None, True, with_version=True)
        except Exception:
            return ""

    @Slot(str, result=str)
    def detectedRuntimeKind(self, appid: str) -> str:
        """Runtime Steam will use for a game: "proton", "native" or "".

        Reads Steam's compat mapping: the game's own entry, else the
        default one. A Steam Linux Runtime tool means a native game.
        """
        try:
            if not appid or not steammod.is_steam_id(appid):
                return ""
            from .. import proton as protonmod

            tool = protonmod.compat_tool_name(appid) or protonmod.default_compat_tool()
            if not tool:
                return ""
            return "native" if protonmod.is_steam_runtime_tool(tool) else "proton"
        except Exception:
            return ""

    @Slot(str, result=str)
    def landscapeArt(self, appid: str) -> str:
        """Landscape artwork path for the pre-launch menu ('' when none)."""
        try:
            if not appid:
                return ""
            path = artmod.resolve(appid, "banner", self._art_source(appid))[0]
            return str(path) if path else ""
        except Exception:
            return ""

    @Slot(str, result=str)
    def launchRuntimeLabel(self, appid: str) -> str:
        """Runtime line for the pre-launch menu (widgets parity)."""
        appid = str(appid or "")
        if not appid:
            return "—"
        try:
            cfg = cfgmod.load(appid)
        except Exception:
            return "Runtime Not Set"
        is_steam = steammod.is_steam_id(appid)
        kind = cfg.runtime.type
        if kind == "proton" and is_steam:
            from .. import proton as protonmod

            try:
                tool = protonmod.tool_display(appid)
            except Exception:
                tool = "Proton"
            return f"Proton: {tool}" if tool != "Proton" else "Proton"
        if kind == "umu" and not is_steam:
            try:
                install = self._wine_env(cfg)[2]
            except Exception:
                install = None
            return f"UMU: {install.name}" if install is not None else "UMU"
        if kind == "wine" and not is_steam:
            try:
                wine = self._wine_env(cfg)[1]
            except Exception:
                wine = ""
            return f"Wine: {Path(wine).name}" if wine else "Wine"
        return cfgmod.runtime_label(kind, is_steam, cfg.runtime.steam_runtime) or "Runtime Not Set"

    @Slot(result=list)
    def allCategories(self) -> list:
        """Every category on record (store plus game tags), sorted."""
        found = [cat.name for cat in cfgmod.load_categories()]
        try:
            for appid in cfgmod.list_appids():
                try:
                    found.extend(cfgmod.load(appid).general.categories)
                except Exception:
                    continue
        except Exception:
            pass
        return sorted(cfgmod.normalize_categories(found), key=str.lower)

    @Slot(result="QVariantMap")
    def categoryIcons(self) -> dict:
        """Sidebar icon for each category on record (theme icon names)."""
        icons = {cat.name.lower(): cat.icon for cat in cfgmod.load_categories()}
        return {name: icons.get(name.lower(), "folder") for name in self.allCategories()}

    def _register_categories(self, names) -> None:
        """Keep the given names in the store so they outlive their tags."""
        wanted = cfgmod.normalize_categories(names)
        if not wanted:
            return
        entries = cfgmod.load_categories()
        known = {cat.name.lower() for cat in entries}
        added = [cfgmod.Category(name) for name in wanted if name.lower() not in known]
        if added:
            cfgmod.save_categories(entries + added)

    def _sync_category_store(self) -> None:
        """Persist every tag seen on disk, so zero-game categories stay."""
        found: list[str] = []
        for appid in cfgmod.list_appids():
            try:
                found.extend(cfgmod.load(appid).general.categories)
            except Exception:
                continue
        self._register_categories(found)

    @Slot(list, str, result=str)
    def setCategories(self, appids, text: str) -> str:
        """Bulk-set category tags from comma text. Returns a status message."""
        ids = [str(a) for a in appids or []]
        if not ids:
            return "Select Games First."
        cats = cfgmod.normalize_categories(str(text or "").split(","))
        count = 0
        for appid in ids:
            try:
                cfg = cfgmod.load(appid)
                cfg.general.categories = cats
                cfgmod.save(cfg)
                count += 1
            except Exception as e:
                log.warning("setCategories(%s) failed: %s", appid, e)
        self._register_categories(cats)
        self.refresh()
        return f"Set {len(cats)} Categor(ies) on {count} Game(s)."

    @Slot(list, result="QVariantMap")
    def categoryPresence(self, appids) -> dict:
        """How many of `appids` carry each category in use, by label."""
        ids = [str(a) for a in appids or []]
        canonical = {name.lower(): name for name in self.allCategories()}
        counts: dict[str, int] = {name: 0 for name in canonical.values()}
        for appid in ids:
            try:
                cats = cfgmod.load(appid).general.categories
            except Exception:
                continue
            seen: set[str] = set()
            for cat in cats:
                key = cat.lower()
                label = canonical.get(key)
                if label and key not in seen:
                    seen.add(key)
                    counts[label] += 1
        return counts

    @Slot(result="QVariantMap")
    def categoryCounts(self) -> dict:
        """How many games carry each category in use, by label."""
        return self.categoryPresence(cfgmod.list_appids())

    @Slot(str, result="QVariantList")
    def categoryGameRows(self, name: str) -> list:
        """Every game and whether it carries `name` (category editor rows)."""
        key = str(name or "").strip().lower()
        ids = cfgmod.list_appids()
        labels = self.gameNames(ids)
        rows: list[dict] = []
        for appid, label in zip(ids, labels, strict=False):
            try:
                cats = cfgmod.load(appid).general.categories
            except Exception:
                cats = []
            has = key in [str(cat).strip().lower() for cat in cats]
            rows.append({"appid": appid, "name": label, "state": 2 if has else 0})
        rows.sort(key=lambda row: str(row["name"]).lower())
        return rows

    @Slot(str, list, result=str)
    def setCategoryGames(self, name: str, appids) -> str:
        """Apply `name` to the checked games and strip it from the rest."""
        names = cfgmod.normalize_categories([name])
        if not names:
            return "Pick a Category First."
        label, key = names[0], names[0].lower()
        checked = {str(appid) for appid in appids or []}
        changed = 0
        for appid in cfgmod.list_appids():
            try:
                cfg = cfgmod.load(appid)
                cats = list(cfg.general.categories)
                has = key in [str(cat).strip().lower() for cat in cats]
                want = appid in checked
                if want == has:
                    continue
                if want:
                    cats.append(label)
                else:
                    cats = [cat for cat in cats if str(cat).strip().lower() != key]
                cfg.general.categories = cfgmod.normalize_categories(cats)
                cfgmod.save(cfg)
                changed += 1
            except Exception as e:
                log.warning("setCategoryGames(%s) failed: %s", appid, e)
        self._register_categories([label])
        self.refresh()
        return f"Updated {changed} Game(s)."

    @Slot(str, str)
    def setCategoryIcon(self, name: str, icon: str) -> None:
        """Set the sidebar icon of a category (creates it when missing)."""
        names = cfgmod.normalize_categories([name])
        if not names:
            return
        label, key = names[0], names[0].lower()
        value = str(icon or "").strip() or "folder"
        entries = cfgmod.load_categories()
        for entry in entries:
            if entry.name.lower() == key:
                entry.icon = value
                break
        else:
            entries.append(cfgmod.Category(label, value))
        cfgmod.save_categories(entries)
        self.refresh()

    @Slot(str, result=str)
    def deleteCategory(self, name: str) -> str:
        """Delete a category: drop it from the store and every game."""
        names = cfgmod.normalize_categories([name])
        if not names:
            return "Pick a Category First."
        label, key = names[0], names[0].lower()
        entries = cfgmod.load_categories()
        stored = next((cat.name for cat in entries if cat.name.lower() == key), label)
        cfgmod.save_categories([cat for cat in entries if cat.name.lower() != key])
        for appid in cfgmod.list_appids():
            try:
                cfg = cfgmod.load(appid)
                cats = list(cfg.general.categories)
                kept = [cat for cat in cats if str(cat).strip().lower() != key]
                if len(kept) != len(cats):
                    cfg.general.categories = cfgmod.normalize_categories(kept)
                    cfgmod.save(cfg)
            except Exception as e:
                log.warning("deleteCategory(%s) failed: %s", appid, e)
        self.refresh()
        return f"Deleted {stored}."

    @Slot(str, str, str, result=str)
    def storeArtwork(self, appid: str, kind: str, src: str) -> str:
        """Copy an image into the manual slot and point the config at it."""
        dest = artmod.store_manual(appid, kind, src)
        if dest is None:
            return "Pick a PNG, JPG or WebP Image File."
        try:
            cfg = cfgmod.load(appid)
            setattr(cfg.artwork, kind, os.fspath(dest))
            cfgmod.save(cfg)
        except Exception as e:
            log.warning("storeArtwork(%s) failed: %s", appid, e)
            return "Could Not Save the Artwork Path."
        artmod.unmark_cleared(appid)
        self.refresh()
        return ""

    @Slot(str, str, str, result=str)
    def storeArtworkUrl(self, appid: str, kind: str, url: str) -> str:
        """Download an image from a pasted URL into a manual slot.

        Validation is synchronous (the token comes back at once); the
        download runs in a worker and reports through `artworkStored`.
        """
        if not appid:
            return "no-game"
        if kind not in artmod.MANUAL_KINDS:
            return "no-kind"
        link = str(url or "").strip()
        if not link.startswith(("http://", "https://")):
            return "bad-url"

        def worker() -> None:
            token = ""
            try:
                data, error = artmod.fetch_image(link)
                if data is None:
                    token = error or "network"
                else:
                    dest = artmod.store_manual_bytes(appid, kind, data)
                    if dest is None:
                        token = "not-image"
                    else:
                        cfg = cfgmod.load(appid)
                        setattr(cfg.artwork, kind, os.fspath(dest))
                        cfgmod.save(cfg)
                        artmod.unmark_cleared(appid)
            except Exception as e:
                log.warning("storeArtworkUrl(%s) failed: %s", appid, e)
                token = "network"
            self.artworkStored.emit(str(appid), kind, token)
            try:
                self.refresh()
            except Exception:
                pass

        threading.Thread(target=worker, daemon=True).start()
        return ""

    @Slot(str, str, result=bool)
    def clearArtwork(self, appid: str, kind: str) -> bool:
        """Empty one slot: manual file, downloaded copy and config path.

        The kind stays hidden — Steam's own art and the exec icon too —
        until Fetch Artwork is pressed.
        """
        try:
            cfg = cfgmod.load(appid)
            if kind in artmod.MANUAL_KINDS:
                setattr(cfg.artwork, kind, "")
            cfgmod.save(cfg)
        except Exception as e:
            log.warning("clearArtwork(%s) failed: %s", appid, e)
            return False
        artmod.clear_manual(appid, kind)
        artmod.clear_kind(appid, kind)
        self.refresh()
        return True

    @Slot(result=list)
    def wineTools(self) -> list:
        """[[tool, version]] installed Proton builds."""
        from .. import proton as protonmod

        try:
            return [[t, protonmod.tool_version(t) or ""] for t in protonmod.list_compat_tools()]
        except Exception:
            return []

    @Slot(result=bool)
    def steamRunning(self) -> bool:
        """Whether a Steam process is alive (mapping writes need it idle)."""
        import subprocess

        for argv in (
            ["pgrep", "-x", "steam"],
            ["pgrep", "-f", "[c]om.valvesoftware.Steam"],
        ):
            try:
                proc = subprocess.run(argv, capture_output=True, timeout=10, check=False)
            except Exception:
                return True
            if proc.returncode == 0:
                return True
            if proc.returncode != 1:  # pgrep error: cannot tell, assume alive
                return True
        return False

    @Slot(str, str, result=str)
    def applyWineVersion(self, appid: str, tool: str) -> str:
        """Point Steam's compat mapping at a tool. '' on success, else why."""
        numeric = steammod.steam_appid(appid)
        if not numeric:
            return "Version Selection Needs a Steam Game."
        tool = str(tool or "").strip()
        if not tool:
            return "Pick a Compat Tool First."
        if self.steamRunning():
            return "Quit Steam First: It Rewrites config.vdf on Exit."
        try:
            import vdf
        except ImportError:
            return "The vdf Module Is Missing."
        for root in steammod.steam_roots():
            path = root / "config" / "config.vdf"
            if not path.is_file():
                continue
            try:
                with open(path, encoding="utf-8") as handle:
                    data = vdf.load(handle)
                node = data["InstallConfigStore"]["Software"]["Valve"]["Steam"]
                mapping = node.setdefault("CompatToolMapping", {})
                mapping[numeric] = {"name": tool}
                backup = path.with_suffix(".vdf.tkarcade-bak")
                backup.write_bytes(path.read_bytes())
                buffer = io.StringIO()
                vdf.dump(data, buffer, pretty=True)
                # Dump to memory first: a failing dump must never truncate
                # Steam's config.vdf.
                cfgmod.write_atomic(path, buffer.getvalue())
            except Exception as e:
                log.warning("applyWineVersion(%s) failed: %s", appid, e)
                return f"Could Not Update {path}: {e}"
            try:
                cfg = cfgmod.load(appid)
                cfg.runtime.tool = tool
                cfgmod.save(cfg)
            except Exception as e:
                log.warning("applyWineVersion record failed: %s", e)
            from .. import proton as protonmod

            protonmod.clear_tool_cache()
            self.refresh()
            return ""
        return "No Steam config.vdf Found."

    @Slot(str, str, result=str)
    def ensurePrefix(self, appid: str, target: str = "") -> str:
        """Create a prefix dir: the dialog's target, else the saved one."""
        if target.strip():
            chosen = Path(target.strip()).expanduser()
            try:
                chosen.mkdir(parents=True, exist_ok=True)
            except Exception as e:
                return f"Could Not Create {chosen}: {e}"
            return ""
        try:
            cfg = cfgmod.load(appid)
        except Exception as e:
            return f"Could Not Read the Config: {e}"
        target = cfgmod.prefix_target(appid, cfg)
        if target is None or (steammod.is_steam_id(appid) and not target.managed):
            return "Set a Custom Prefix Dir First (Steam Creates Its Own)."
        try:
            target.container.mkdir(parents=True, exist_ok=True)
        except Exception as e:
            return f"Could Not Create {target.container}: {e}"
        return ""

    @Slot(str, result=str)
    def clearCustomPrefix(self, appid: str) -> str:
        """Delete the game's prefix dir (guarded). '' on success, else why."""
        import shutil as _shutil

        try:
            cfg = cfgmod.load(appid)
        except Exception as e:
            return f"Could Not Read the Config: {e}"
        target, error = self._prefix_to_clear(appid, cfg)
        if error:
            return error
        try:
            resolved = target.resolve()
            home = Path.home().resolve()
            if resolved == home or resolved == home.parent or len(resolved.parts) <= 2:
                return f"Refusing to Delete {resolved}."
            if not target.is_dir():
                return f"Not a Directory: {target}."
        except Exception as e:
            return f"Could Not Inspect {target}: {e}"
        try:
            _shutil.rmtree(target)
        except Exception as e:
            return f"Could Not Delete {target}: {e}"
        return f"Cleared {target}."

    def _prefix_to_clear(self, appid: str, cfg) -> tuple[Path | None, str]:
        """The dir Clear deletes: Steam's custom one, or the local prefix.

        A local prefix is a subfolder of the base: only it is deleted,
        and never one another game still points at. A directory that is
        not a Wine prefix is refused: a misconfigured path must never
        turn Clear into a recursive delete of an unrelated folder.
        """
        target = cfgmod.prefix_target(appid, cfg)
        if target is None or not target.managed:
            return None, "No Custom Prefix Set."
        try:
            users = self._prefix_users(cfgmod.load_preferences()).get(
                os.fspath(target.container), []
            )
        except Exception:
            users = []
        others = [a for a in users if a != appid]
        if others:
            return None, f"Shared Prefix: Still Used by {', '.join(others)}."
        if not self._deletable_prefix(target.container):
            return None, f"Refusing to Delete {target.container}: Not a Wine Prefix."
        return target.container, ""

    @staticmethod
    def _deletable_prefix(target: Path) -> bool:
        """True when deleting `target` cannot destroy an unrelated folder.

        An empty directory is harmless; a real prefix has ``drive_c``
        directly (local WINEPREFIX) or under ``pfx`` (Steam container).
        Anything else is refused, so a wrong prefix path cannot wipe a
        games or documents folder.
        """
        try:
            if not target.is_dir():
                return False
            if not any(target.iterdir()):
                return True
            return (target / "drive_c").is_dir() or (target / "pfx" / "drive_c").is_dir()
        except OSError:
            return False

    @staticmethod
    def _steam_proton(cfg) -> object:
        """The Proton install a Steam game launches with (None = unresolved).

        An explicit ``[runtime] tool`` wins; otherwise Steam's own compat
        mapping for the AppID decides, so the answer matches the launch.
        """
        from .. import proton as protonmod

        tool = cfg.runtime.tool.strip() or protonmod.compat_tool_name(cfg.general.appid) or ""
        if not tool:
            return None
        return runtimes.find_proton(tool)

    def _wine_env(self, cfg) -> tuple[Path, str, object]:
        """(prefix dir, wine binary, Proton install) for a local game."""
        prefs = cfgmod.load_preferences()
        prefix = cfgmod.prefix_target(cfg.general.appid, cfg, prefs).wineprefix
        wine = runtimes.wine_binary(cfg.runtime.tool or prefs.wine_default, prefs.wine_versions)
        proton = runtimes.find_proton(cfg.runtime.tool)
        return prefix, wine, proton

    @Slot(str, result="QVariantMap")
    def steamRuntimeState(self, name: str) -> dict:
        """A Steam Linux Runtime's label, dir and whether umu already has it.

        A missing runtime is only a hint: umu downloads it on the first launch
        that asks for it, so this never blocks Save or Play.
        """
        code = cfgmod.normalize_steam_runtime(name)
        if not code:
            return {"installed": False, "label": "", "path": ""}
        path = runtimes.steam_runtime_dir(code)
        return {
            "installed": runtimes.steam_runtime_installed(code),
            "label": cfgmod.steam_runtime_label(code),
            "path": os.fspath(path) if path is not None else "",
        }

    @Slot(str, str, result="QVariantMap")
    def installedVerbs(self, appid: str, verbs: str = "") -> dict:
        """Verbs in the prefix's winetricks.log, plus the draft's pending ones.

        ``verbs`` is the dialog's field text: what it names and the log
        does not is installed at the next launch, so the dialog shows the
        two lists apart. A Steam game reads its compatdata container (the
        ``pfx`` inside it); a local game reads its WINEPREFIX.
        """
        prefix: Path | None = None
        try:
            cfg = cfgmod.load(appid)
            target = cfgmod.prefix_target(appid, cfg)
            if target is not None:
                prefix = target.container
        except Exception:
            prefix = None
        installed = wtmod.installed_verbs(prefix) if prefix is not None else []
        try:
            wanted = _split_args(str(verbs or ""))
        except Exception:
            wanted = str(verbs or "").split()
        return {"installed": installed, "pending": [v for v in wanted if v not in installed]}

    @Slot(str, result=str)
    def openWinetricksGui(self, appid: str) -> str:
        """Open protontricks/winetricks interactively. '' = started, else why."""

        try:
            cfg = cfgmod.load(appid)
        except Exception as e:
            return f"Could Not Read the Config: {e}"
        env: dict[str, str] = {}
        target = cfgmod.prefix_target(appid, cfg)
        if steammod.is_steam_id(appid) and target is not None and target.managed:
            # protontricks only ever targets Steam's own compatdata dir, so a
            # custom [runtime] prefix takes winetricks instead: the game's
            # Proton supplies wine, the container's pfx is the WINEPREFIX.
            proton = self._steam_proton(cfg)
            if proton is None:
                return "Could Not Resolve the Game's Proton: Pick One in the Runtime Tab."
            argv, env, message = wtmod.local_gui(target.wineprefix, "proton", "", proton)
        elif steammod.is_steam_id(appid):
            # protontricks needs the game installed and launched once: it
            # targets the compatdata prefix and refuses with a message on
            # stdout that the GUI would never show.
            if target is None:
                return (
                    "Protontricks Needs the Game Installed and Launched Once: "
                    "No Proton Prefix Found for This AppID."
                )
            from .. import proton as protonmod

            argv, message = protonmod.gui_command(appid)
        else:
            environment = cfgmod.normalize_runtime(cfg.runtime.type)
            if environment not in ("wine", "umu"):
                return "Winetricks Verbs Need a Wine or Proton Runtime."
            prefix, wine, proton = self._wine_env(cfg)
            argv, env, message = wtmod.local_gui(prefix, environment, wine, proton)
        if message:
            return message
        return self._spawn_verb_tool(appid, argv, env)

    def _spawn_verb_tool(self, appid: str, argv: list[str], env: dict[str, str]) -> str:
        """Start the tool with its output in a per-game log ('' = started)."""
        import subprocess

        # protontricks reports "app could not be found" on stdout and
        # winetricks prints its own failures there: keep them somewhere
        # the dialog can point at instead of discarding them.
        log_path: Path | None = xdg.games_log_dir() / f"{xdg.safe_stem(appid)}-winetricks.log"
        try:
            log_path.parent.mkdir(parents=True, exist_ok=True)
            with log_path.open("w", encoding="utf-8") as handle:
                proc = subprocess.Popen(
                    argv,
                    env={**os.environ, **env},
                    start_new_session=True,
                    stdout=handle,
                    stderr=subprocess.STDOUT,
                )
        except OSError:
            # No writable log (read-only state dir): still open the tool.
            try:
                proc = subprocess.Popen(argv, env={**os.environ, **env}, start_new_session=True)
            except OSError as e:
                return f"Could Not Open the Tool: {e}"
            log_path = None
        threading.Thread(
            target=self._wait_verb_tool,
            args=(proc, os.fspath(log_path) if log_path is not None else ""),
            daemon=True,
        ).start()
        return ""

    def _wait_verb_tool(self, proc, log_path: str = "") -> None:
        """Report the tool's exit so the dialog re-reads the log and errors."""
        try:
            code = proc.wait()
        except Exception:
            code = 0
        try:
            self.verbToolClosed.emit("" if code == 0 else "failed", log_path if code else "")
        except Exception:
            pass

    @Slot()
    def requestVerbCatalog(self) -> None:
        """Publish `winetricks list-all`; the first call pays its ~2s."""
        if wtmod.catalog_ready():
            self.verbCatalogReady.emit(wtmod.list_all())
            return
        threading.Thread(target=self._catalog_worker, daemon=True).start()

    def _catalog_worker(self) -> None:
        try:
            rows = wtmod.list_all()
        except Exception as e:  # never break the dialog on a probe
            log.warning("winetricks list-all failed: %s", e)
            rows = []
        try:
            self.verbCatalogReady.emit(rows)
        except Exception:
            pass

    @Slot(str, str, result=str)
    def artworkPath(self, appid: str, kind: str) -> str:
        """Stored config path for a manual artwork slot ('' when none)."""
        try:
            art = cfgmod.load(appid).artwork
            value = getattr(art, kind, "") if kind in artmod.MANUAL_KINDS else ""
            return str(value or "")
        except Exception:
            return ""

    @Slot(str, str, str, result=str)
    def effectiveArtwork(self, appid: str, kind: str, source: str = "") -> str:
        """Path the views actually use for one kind ('' when none).

        Follows `artwork.resolve`: the game's manual slot, the Artwork
        Source AppID (draft or saved), then the game's cache and Steam,
        then the local executable's embedded icon.
        """
        try:
            path, _source = artmod.resolve(
                appid, kind, self._art_source(appid, source), self._local_exe(appid)
            )
            return str(path) if path else ""
        except Exception:
            return ""

    @Slot(str, str, str, result=str)
    def artworkPreview(self, appid: str, kind: str, source: str = "") -> str:
        """`file://` URL of the art the views use, versioned by its mtime.

        QML caches an image by URL, so a file Fetch or Clear replaced
        would keep showing the previous picture without the `?v=` stamp.
        Empty when the slot has nothing to show.
        """
        try:
            path, _source = artmod.resolve(
                appid, kind, self._art_source(appid, source), self._local_exe(appid)
            )
            if path is None:
                return ""
            return f"file://{path}?v={path.stat().st_mtime_ns}"
        except Exception:
            return ""

    @Slot(str, str, str, result=str)
    def artworkOrigin(self, appid: str, kind: str, source: str = "") -> str:
        """Token naming where one kind's art comes from ("" when empty).

        `manual`, `steam`, `exe`, `cache:<provider>` (`cache:steam`,
        `cache:sgdb`) or plain `cache` when the sidecar does not say.
        """
        try:
            path, origin = artmod.resolve(
                appid, kind, self._art_source(appid, source), self._local_exe(appid)
            )
        except Exception:
            return ""
        if path is None:
            return ""
        if origin in ("manual", "steam", "exe"):
            return origin
        gid = str(appid)
        provider = artmod.provider_for(gid, kind)
        if not provider and origin.startswith("appid-") and source:
            gid = self._art_source(appid, source)
            provider = artmod.provider_for(gid, kind)
        if not provider:
            # The icon falls back to the cached cover, whose provider is
            # recorded under its own kind; the background falls back to
            # the banner the same way.
            if kind == "icon":
                provider = artmod.provider_for(gid, "cover")
            elif kind == "background":
                provider = artmod.provider_for(gid, "banner")
        return f"cache:{provider}" if provider in artmod.PROVIDERS else "cache"

    @Slot(str, str, result=str)
    def artworkProvider(self, appid: str, source: str = "") -> str:
        """Provider of the downloaded art: "steam", "sgdb" or "".

        Read from the cache sidecar, preferring the Artwork Source AppID.
        """
        source_appid = self._art_source(appid, source)
        chain = [source_appid, str(appid)] if source_appid else [str(appid)]
        for gid in chain:
            for kind in ("cover", "icon", "banner"):
                value = artmod.provider_for(gid, kind)
                if value:
                    return value
        return ""

    @Slot(str, str, result=str)
    def artworkStatus(self, appid: str, source: str = "") -> str:
        """Where a game's three images come from: a token for the dialog.

        "own" (all three present), "partial" (some missing), "none", or
        "cleared" (the downloaded art was removed on purpose).
        """
        source_appid = self._art_source(appid, source)
        if artmod.is_cleared(source_appid or str(appid)):
            return "cleared"
        own = missing = 0
        exe = self._local_exe(appid)
        for kind in artmod.ART_KINDS:
            try:
                path = artmod.resolve(appid, kind, source_appid, exe)[0]
            except Exception:
                path = None
            if path is None:
                missing += 1
            else:
                own += 1
        if own and not missing:
            return "own"
        return "partial" if own else "none"

    @staticmethod
    def _game_provider(appid: str, default: str) -> str:
        """Provider this game fetches with: its own key, else the global."""
        try:
            value = cfgmod.load(str(appid)).artwork.provider
        except Exception:
            value = ""
        return value or default

    @staticmethod
    def _name_queries(appid: str) -> list[str]:
        """Names to try on SteamGridDB for a game without a Steam AppID."""
        try:
            name = str(cfgmod.load(str(appid)).general.name or "").strip()
        except Exception:
            return []
        if not name:
            return []
        short = cfgmod.split_name_version(name)[0].strip()
        return [short, name] if short and short != name else [name]

    @Slot(str, str, result=str)
    def clearFetchedArtwork(self, appid: str, source: str = "") -> str:
        """Delete the downloaded art this game points at ("no-game" if empty).

        With an Artwork Source AppID the cache belongs to that AppID, so
        every game pointing there loses it; the confirmation says so. The
        game shows no art — no Steam fallback, no exe icon — until Fetch
        Artwork is pressed.
        """
        if not appid:
            return "no-game"
        target = self._art_source(appid, source)
        if not target.isdigit():
            target = steammod.steam_appid(str(appid)) or str(appid)
        try:
            artmod.clear_fetched(target)
        except Exception as e:
            log.warning("clearFetchedArtwork(%s) failed: %s", appid, e)
            return "no-appid"
        self.refresh()
        return "done"

    def _art_target(self, appid: str, source: str = "") -> tuple[str, tuple]:
        """(fetch target, name queries) for a game, or ("", ()) when none.

        The typed Artwork Source AppID wins; otherwise a Steam game uses
        its own AppID and a local game its name. A typed value that is
        not numeric is a user error, not a name to search.
        """
        source_appid = self._art_source(appid, source)
        if source_appid and not source_appid.isdigit():
            return "", ()
        target = source_appid or steammod.steam_appid(str(appid)) or str(appid)
        names = () if target.isdigit() else tuple(self._name_queries(appid))
        if not target.isdigit() and not names:
            return "", ()
        return target, names

    @staticmethod
    def _store_igdb_metadata(appid: str, igdb_id: str) -> str:
        """Write a resolved IGDB identity into ``[metadata] igdb_id``.

        Returns the normalized id ("" when invalid) even if the save
        failed, so the dialog draft can still carry it.
        """
        ident = cfgmod.normalize_igdb_id(igdb_id)
        if not ident:
            return ""
        try:
            cfg = cfgmod.load(str(appid))
            if cfg.metadata.igdb_id != ident:
                cfg.metadata.igdb_id = ident
                cfgmod.save(cfg)
        except Exception as e:
            log.warning("store igdb id(%s) failed: %s", appid, e)
        return ident

    @staticmethod
    def _owns_art_target(appid: str, source: str = "") -> bool:
        """True when the art target is the game itself, not a source AppID."""
        if str(source or "").strip():
            return False
        try:
            return not cfgmod.load(str(appid)).artwork.artwork_appid.strip()
        except Exception:
            return False

    @Slot(str, str, str, str, result=str)
    def fetchArtwork(
        self, appid: str, provider: str = "", source: str = "", igdb_id: str = ""
    ) -> str:
        """Re-download this game's art with the chosen provider. '' = ok.

        Target: the Artwork Source AppID typed in the dialog, then the
        game's own Steam AppID, then the SteamGridDB name lookup for a
        local game (IGDB, when chosen, uses the stored igdb_id or the
        dialog draft, which wins when set).
        `provider` is the dialog draft, so a just-changed combo applies
        before Save; empty falls back to the game's key and then to the
        global preference. Explicit, so it forces a refresh of the three
        kinds. The outcome arrives as `artworkFetched(appid, status,
        provider)` and, when the name matched several entries,
        `artworkChoices(appid, rows)`; the dialog stays responsive.
        """
        if not appid:
            return "no-game"
        try:
            prefs = cfgmod.load_preferences()
            api_key = prefs.sgdb_api_key.strip()
            default = prefs.artwork_source
        except Exception:
            api_key, default = "", "steam"
        provider = provider if provider in artmod.PROVIDERS else ""
        provider = provider or self._game_provider(appid, default)
        target, names = self._art_target(appid, source)
        if not target:
            return "no-appid"
        draft_id = str(igdb_id or "").strip()
        # A source AppID's IGDB entry belongs to that AppID, not this game.
        owns_target = self._owns_art_target(appid, source)

        threading.Thread(
            target=self._artwork_fetch_worker,
            args=(appid, target, provider, api_key, names, draft_id, owns_target),
            daemon=True,
        ).start()
        return ""

    def _artwork_fetch_worker(
        self,
        appid: str,
        target: str,
        provider: str,
        api_key: str,
        names,
        draft_id: str,
        owns_target: bool,
    ) -> None:
        """Download and report one explicit Fetch Artwork request."""
        status, provider_used, choices = "network", "", []
        try:
            # A per-tile Clear marks the game, while the fetch target can be
            # its Artwork Source AppID: drop both marks or the tile stays
            # hidden after the target downloads.
            artmod.unmark_cleared(str(appid))
            if target != str(appid):
                artmod.unmark_cleared(target)
            extra = {"igdb_id": draft_id} if draft_id else {}
            result = artmod.fetch_best(target, provider, api_key, force=True, names=names, **extra)
            resolved_id = str(result.get("igdb_id") or "")
            if owns_target and resolved_id:
                ident = self._store_igdb_metadata(appid, resolved_id)
                if ident:
                    self.igdbResolved.emit(str(appid), ident)
            choices = result.get("candidates") or []
            if choices and not result["art"]:
                # A title search needs a human pick before its art.
                status = "choose"
            else:
                status = "ok" if result["art"] else (result["error"] or "no-art")
            provider_used = result["provider"]
        except Exception as e:  # pragma: no cover - defensive
            log.warning("fetchArtwork(%s) failed: %s", appid, e)
        if choices:
            try:
                self.artworkChoices.emit(appid, choices)
            except Exception:
                pass
        self.artworkFetched.emit(appid, status, provider_used)
        try:
            self.backgroundDone.emit()
        except Exception:
            pass

    @Slot(str, str, str, str, result=str)
    def fetchArtworkGame(
        self, appid: str, game_id: str, provider: str = "sgdb", source: str = ""
    ) -> str:
        """Download the SteamGridDB or IGDB entry the user picked."""
        if not appid or not str(game_id).strip():
            return "no-game"
        provider = provider if provider in ("sgdb", "igdb") else "sgdb"
        try:
            api_key = cfgmod.load_preferences().sgdb_api_key.strip()
        except Exception:
            api_key = ""
        if provider == "igdb":
            client_id, secret = igdbmod.credentials()
            if not (client_id and secret):
                return "no-igdb-key"
        elif not api_key:
            return "no-key"
        source = str(source or "").strip()
        if not source:
            try:
                source = cfgmod.load(str(appid)).artwork.artwork_appid.strip()
            except Exception:
                source = ""
        owns_target = not source
        target = source if source.isdigit() else (steammod.steam_appid(str(appid)) or str(appid))

        threading.Thread(
            target=self._artwork_game_worker,
            args=(appid, game_id, provider, api_key, target, owns_target),
            daemon=True,
        ).start()
        return ""

    def _artwork_game_worker(
        self,
        appid: str,
        game_id: str,
        provider: str,
        api_key: str,
        target: str,
        owns_target: bool,
    ) -> None:
        """Download one picked provider entry and report the outcome."""
        status = "network"
        provider_used = provider
        try:
            # A picked entry is an explicit restore: the game's own Clear
            # mark and the target's must both go.
            artmod.unmark_cleared(str(appid))
            artmod.unmark_cleared(target)
            if provider == "igdb":
                if owns_target:
                    ident = self._store_igdb_metadata(appid, str(game_id).strip())
                    if ident:
                        self.igdbResolved.emit(str(appid), ident)
                result = artmod.fetch_best(
                    target,
                    "igdb",
                    api_key,
                    force=True,
                    names=tuple(self._name_queries(appid)),
                    igdb_id=str(game_id).strip(),
                )
                status = "ok" if result["art"] else (result["error"] or "no-art")
                provider_used = result["provider"] or "igdb"
            else:
                art = artmod.fetch_sgdb_game(target, str(game_id).strip(), api_key, force=True)
                if art:
                    artmod.store_sgdb_id(target, str(game_id).strip(), "")
                    status = "ok"
                else:
                    status = "no-art"
        except Exception as e:  # pragma: no cover - defensive
            log.warning("fetchArtworkGame(%s) failed: %s", appid, e)
        self.artworkFetched.emit(appid, status, provider_used)
        try:
            self.backgroundDone.emit()
        except Exception:
            pass

    @Slot(str, str, bool, result=str)
    def cloneGameTo(self, src: str, dest: str, force: bool) -> str:
        """Clone live config plus profiles; '' on success, else a message."""
        import re

        m = re.search(r"\[(.+)\]\s*$", dest or "")
        cand = (m.group(1) if m else (dest or "")).strip()
        if not cand or xdg.safe_stem(cand) != cand:
            return f"Invalid game ID: {dest}"
        cand = steammod.canonical_new_id(cand)
        if cand == src:
            return "Source and Target Are the Same."
        if cfgmod.game_file(cand).is_file() and not force:
            return "OVERWRITE"
        try:
            cfgmod.clone_game(src, cand)
        except (OSError, ValueError) as e:
            return str(e)
        self.refresh()
        msg = f"Cloned {src} to {cand}."
        if steammod.origin(src) != steammod.origin(cand):
            msg += " Review the Runtime for the New Origin."
        return msg

    @Slot(list, result=str)
    def resetGames(self, appids) -> str:
        """Reset live configs to the Global Defaults template (keeps profiles)."""
        ids = [str(a) for a in appids or []]
        if not ids:
            return "Select Games First."
        count = 0
        for appid in ids:
            try:
                cfg = cfgmod.load_defaults()
                cfg.general.appid = appid
                if steammod.origin(appid) == "local":
                    self._keep_local_identity(cfg, cfgmod.load(appid))
                cfgmod.save(cfg)
                count += 1
            except Exception as e:
                log.warning("resetGames(%s) failed: %s", appid, e)
        self.refresh()
        return f"Reset {count} Game(s) to the Global Defaults Template."

    @Slot(str, str, result="QVariantMap")
    def profileContent(self, appid: str, name: str) -> dict:
        """A saved profile as settings fields (live file untouched)."""
        name = str(name or "").strip()
        try:
            known = cfgmod.list_profiles(appid)
        except Exception:
            known = []
        if not appid or not name or name not in known:
            return {}
        try:
            cfg = cfgmod.load_profile(appid, name)
            cfg.general.appid = appid
            return self._game_to_map(cfg, appid)
        except Exception as e:
            log.warning("profileContent failed: %s", e)
            return {}

    @Slot(str, str, result=bool)
    def markActiveProfile(self, appid: str, name: str) -> bool:
        """Point the live config at a profile (its content untouched)."""
        try:
            cfg = cfgmod.load(appid)
            cfg.general.active_profile = str(name or "")
            cfgmod.save(cfg)
        except Exception as e:
            log.warning("markActiveProfile failed: %s", e)
            return False
        return True

    @Slot(str, str, result=bool)
    def profileExists(self, appid: str, name: str) -> bool:
        """Whether a profile snapshot exists."""
        try:
            return str(name or "").strip() in cfgmod.list_profiles(appid)
        except Exception:
            return False

    @Slot(str, str, "QVariantMap", result=bool)
    def saveGameProfile(self, appid: str, name: str, values) -> bool:
        """Snapshot dialog form state as a named profile."""
        name = str(name or "").strip()
        if not appid or not name:
            return False
        try:
            cfg = cfgmod.load(appid)
            self._apply_map(cfg, dict(values or {}))
            cfgmod.save_profile(appid, name, cfg)
        except Exception as e:
            log.warning("saveGameProfile failed: %s", e)
            return False
        return True

    @Slot(str, str, str, "QVariantMap", result=bool)
    def cloneGameProfile(self, appid: str, src: str, dest: str, values) -> bool:
        """Copy a profile snapshot (or the live dialog state) to a new name."""
        src, dest = str(src or "").strip(), str(dest or "").strip()
        if not appid or not dest or src == dest:
            return False
        try:
            if src:
                if src not in cfgmod.list_profiles(appid):
                    return False
                cfg = cfgmod.load_profile(appid, src)
            else:
                cfg = cfgmod.load(appid)
                self._apply_map(cfg, dict(values or {}))
            cfgmod.save_profile(appid, dest, cfg)
        except Exception as e:
            log.warning("cloneGameProfile failed: %s", e)
            return False
        return True

    @Slot(str, str, result=bool)
    def deleteGameProfile(self, appid: str, name: str) -> bool:
        """Delete a profile snapshot (clears the active marker with it)."""
        name = str(name or "").strip()
        if not appid or not name:
            return False
        try:
            cfgmod.delete_profile(appid, name)
            cfg = cfgmod.load(appid)
            if cfg.general.active_profile == name:
                cfg.general.active_profile = ""
                cfgmod.save(cfg)
        except Exception as e:
            log.warning("deleteGameProfile failed: %s", e)
            return False
        self.refresh()
        return True

    @Slot(list, result=str)
    def envToText(self, rows) -> str:
        """KEY=value lines for the bulk editor."""
        return "\n".join(
            f"{str(row['key']).strip()}={row.get('value', '')}"
            for row in rows or []
            if isinstance(row, dict) and str(row.get("key", "")).strip()
        )

    @Slot(str, result="QVariantList")
    def textToEnv(self, text: str) -> list:
        """Parse bulk-edit text into [{key, value}] rows."""
        out = []
        for line in (text or "").splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, value = line.split("=", 1)
            key = key.strip()
            if key:
                out.append({"key": key, "value": value})
        return out

    @staticmethod
    def _preset_label(name, preset) -> str:
        tags = []
        try:
            if preset.drivers:
                tags.append("/".join(preset.drivers))
            if preset.proton:
                tags.append("/".join(preset.proton))
        except Exception:
            pass
        return f"{name} [{'/'.join(tags)}]" if tags else name

    @Slot(result=list)
    def envPresetLabels(self) -> list:
        """Preset chooser labels, with driver/proton tags."""
        from .. import presets as presetsmod

        try:
            names = sorted(presetsmod.PRESETS)
            return [self._preset_label(n, presetsmod.PRESETS[n]) for n in names]
        except Exception:
            return []

    @Slot(str, result=str)
    def envPresetName(self, label: str) -> str:
        """Preset key for a chooser label, or ''."""
        from .. import presets as presetsmod

        try:
            names = sorted(presetsmod.PRESETS)
            labels = {n: self._preset_label(n, presetsmod.PRESETS[n]) for n in names}
            return next(n for n in names if labels[n] == label)
        except Exception:
            return ""

    def _proton_flavor(self, appid: str) -> tuple[bool, str]:
        """(known, flavor) of the Proton the game would launch with.

        ``known`` is False only when the mapping cannot be read (Steam
        game with no compat-tool mapping, unreadable config): the caller
        keeps offering the preset, as before. A local Wine/native game
        (or umu without a Proton) is known to have none.
        """
        from .. import proton as protonmod

        if steammod.is_steam_id(appid):
            try:
                tool = protonmod.compat_tool_name(appid) or ""
            except Exception:
                tool = ""
            return (bool(tool), protonmod.flavor(tool) if tool else "")
        try:
            cfg = cfgmod.load(appid)
        except Exception:
            return (False, "")
        if cfg.runtime.type != "umu":
            return (True, "")
        try:
            install = self._wine_env(cfg)[2]
        except Exception:
            install = None
        if install is None:
            return (True, "")
        return (True, protonmod.flavor(install.name))

    @Slot(str, str, result=str)
    def envPresetMismatch(self, name: str, appid: str) -> str:
        """Why a preset may not apply here, or '' when it fits."""
        from .. import presets as presetsmod

        try:
            preset = presetsmod.PRESETS.get(name)
            if preset is None:
                return ""
            if preset.drivers:
                from .. import gpu as gpumod

                try:
                    vendors = gpumod.detect_vendors()
                except Exception:
                    vendors = []
                if vendors and not (set(preset.drivers) & set(vendors)):
                    return "/".join(preset.drivers) + " GPUs"
            if preset.proton and appid:
                known, flavor = self._proton_flavor(appid)
                if known and flavor not in preset.proton:
                    return "/".join(preset.proton) + " Proton"
        except Exception as e:
            log.warning("envPresetMismatch failed: %s", e)
        return ""

    @Slot("QVariantList", str, result="QVariantMap")
    def applyEnvPreset(self, rows, name: str) -> dict:
        """Merge missing preset entries. Returns {rows, added}."""
        from .. import presets as presetsmod

        clean = [
            {"key": str(row["key"]).strip(), "value": str(row.get("value", ""))}
            for row in rows or []
            if isinstance(row, dict) and str(row.get("key", "")).strip()
        ]
        env = {r["key"]: r["value"] for r in clean}
        try:
            added = presetsmod.apply_preset(env, name)
        except Exception as e:
            log.warning("applyEnvPreset failed: %s", e)
            return {"rows": clean, "added": 0}
        return {"rows": [{"key": k, "value": v} for k, v in env.items()], "added": len(added)}

    @Slot(str, result=bool)
    def toolAvailable(self, binary: str) -> bool:
        """Whether a helper binary exists on PATH (disables its toggle)."""
        try:
            return shutil.which(binary or "") is not None
        except Exception:
            return False

    @Slot(str, result=str)
    def exportTarball(self, path: str) -> str:
        """Export configs to a tarball; returns the status message ('' skips)."""
        path = (path or "").strip()
        if not path:
            return ""
        try:
            saved = cfgmod.export_configs(path)
        except (OSError, ValueError) as e:
            return f"Export Failed: {e}"
        return f"Exported to {saved}"

    @Slot(str, result=str)
    def importTarball(self, path: str) -> str:
        """Import an export tarball; returns the status message ('' skips)."""
        path = (path or "").strip()
        if not path:
            return ""
        try:
            imported = cfgmod.import_configs(path)
        except (OSError, ValueError) as e:
            return f"Import Failed: {e}"
        self._migrate_ids()
        self.refresh()
        return f"Imported {len(imported)} Game(s)"

    @Slot(result=list)
    def stlCandidates(self) -> list:
        """Configured games that also have an STL config: [[appid, name]]."""
        try:
            names = {a: n for a, n in steammod.list_games()}
        except Exception:
            names = {}
        try:
            configured = set(cfgmod.list_appids())
        except Exception:
            configured = set()
        try:
            from .. import stl_import as stimod

            stl = set(stimod.list_stl_appids())
        except Exception:
            return []
        games = [[a, names.get(a, a)] for a in sorted(configured & stl)]
        return sorted(games, key=lambda g: g[1].lower())

    @Slot(list, result=str)
    def importStl(self, appids) -> str:
        """Import STL snapshots as profiles; returns the usage notice."""
        from .. import stl_import as stimod

        imported, skipped, reports = [], [], {}
        for appid in appids or []:
            numeric = steammod.steam_appid(str(appid))
            raw = (
                stimod.parse_stl_conf(
                    stimod.stl_config_dir() / "gamecfgs" / "id" / f"{numeric}.conf"
                )
                if numeric
                else {}
            )
            if not raw:
                skipped.append(appid)
                continue
            cfg, report = stimod.map_to_gameconfig(appid, raw)
            try:
                cfgmod.save_profile(appid, stimod.PROFILE_NAME, cfg)
            except Exception as e:
                skipped.append(appid)
                reports[appid] = [f"save failed: {e}"]
                continue
            imported.append(appid)
            if report:
                reports[appid] = report
        self.refresh()
        lines = []
        if imported:
            lines.append("Imported as the 'steamtinkerlaunch' Profile (Live Config Untouched):")
            lines += [f"  • {a}" for a in imported]
            lines.append("Open the Game, Pick the Profile in the Profile Row to Try It.")
        if skipped:
            lines.append("Skipped (No STL Config Found):")
            lines += [f"  • {a}" for a in skipped]
        details = "\n".join(f"{a}: {'; '.join(r)}" for a, r in reports.items() if r)
        if details:
            lines += ["", "Notes:", details]
        return "\n".join(lines) or "Nothing Selected."

    @Slot(result=str)
    def importPredecessor(self) -> str:
        """Copy TKSteamLaunch configs (missing files only); status message."""
        try:
            imported, skipped = cfgmod.import_tksteamlaunch()
        except (OSError, ValueError) as e:
            return f"Import Failed: {e}"
        lines = [f"Imported {len(imported)} File(s)."]
        if skipped:
            lines.append(f"Skipped {len(skipped)} Existing File(s).")
        self.refresh()
        return "\n".join(lines)

    @Slot(str, str)
    def refreshDisplayModes(self, provider: str, output: str) -> None:
        """Backend mode query off the GUI thread; rows via displayModesFinished."""
        threading.Thread(target=self._dmodes_worker, args=(provider, output), daemon=True).start()

    def _dmodes_worker(self, provider: str, output: str) -> None:
        from ..backends import display as dispmod

        rows = []
        try:
            for num, text, is_current in dispmod.offered_modes(provider, output):
                label = text if num is None else f"{num}: {text}{'' if not is_current else ' ★'}"
                rows.append([label, text, bool(is_current)])
        except Exception as e:  # backends must never break the dialog
            log.warning("display modes query failed: %s", e)
        self.displayModesFinished.emit(rows)

    @Slot(str, str, result=bool)
    def displayModesMatch(self, a: str, b: str) -> bool:
        """Same WxH (and rate within 1Hz): the dip-workaround condition."""
        from ..backends import display as dispmod

        try:
            want = dispmod.parse_mode((a or "").strip())
            cur = dispmod.parse_mode((b or "").strip())
        except Exception:
            return False
        return (
            want is not None
            and cur is not None
            and want[0] == cur[0]
            and want[1] == cur[1]
            and (want[2] is None or cur[2] is None or abs(want[2] - cur[2]) < 1.0)
        )

    @Slot(result=list)
    def gamescopePresets(self) -> list:
        """Starter Gamescope option sets, by name."""
        from ..backends import overlay as ovmod

        try:
            return sorted(ovmod.GAMESCOPE_PRESETS)
        except Exception:
            return []

    @Slot(str, result=str)
    def gamescopePreset(self, name: str) -> str:
        """Args for a starter preset, or ''."""
        from ..backends import overlay as ovmod

        try:
            return ovmod.GAMESCOPE_PRESETS.get(str(name or ""), "")
        except Exception:
            return ""

    @Slot(result=list)
    def mangohudConfigs(self) -> list:
        """Saved MangoHud config filenames (default covered by entry '')."""
        from ..backends import overlay as ovmod

        try:
            return [n for n in ovmod.list_mangohud_configs() if n != ovmod.DEFAULT_MANGOHUD_CONF]
        except Exception:
            return []

    @Slot(str, str, result=str)
    def createMangohudConfig(self, name: str, template: str) -> str:
        """Create a MangoHud config; returns its path, or '' + logs."""
        from ..backends import overlay as ovmod

        try:
            path, _source, error = ovmod.create_mangohud_config(name, template)
        except Exception as e:
            log.warning("createMangohudConfig failed: %s", e)
            return ""
        if error or path is None:
            log.warning("createMangohudConfig refused: %s", error)
            return ""
        return os.fspath(path)

    @Slot(str, result=str)
    def gameLogFile(self, appid: str) -> str:
        """Per-game log file path (may not exist yet)."""
        try:
            return os.fspath(xdg.game_log_file(appid))
        except Exception:
            return ""

    @Slot(str, result=str)
    def protonLogDir(self, appid: str) -> str:
        """Per-game Proton log dir path (may not exist yet)."""
        try:
            return os.fspath(launchermod.proton_log_dir(appid))
        except Exception:
            return ""

    @Slot(str, str, str)
    def checkCoverage(self, appid: str, name_override: str, game_name: str = "") -> None:
        """Ludusavi coverage check off the GUI thread (coverageFinished).

        game_name is the dialog's (possibly unsaved) name: a local game
        resolves its saves by it, so the check must not wait for a Save.
        """
        threading.Thread(
            target=self._coverage_worker,
            args=(appid, name_override, game_name),
            daemon=True,
        ).start()

    def _coverage_worker(self, appid: str, name_override: str, game_name: str = "") -> None:
        from ..backends import ludusavi as lumod

        try:
            # Without a dialog name, a local game falls back to the saved one.
            if not game_name and not steammod.is_steam_id(appid):
                game_name = cfgmod.load(appid).general.name
            status, detail = lumod.check_coverage(
                appid, lumod.effective_name(appid, name_override, game_name)
            )
        except Exception as e:  # backends must never break the dialog
            status, detail = "unavailable", str(e)
        self.coverageFinished.emit(status, detail)

    @Slot(list, result=str)
    def iconName(self, candidates) -> str:
        """First candidate the icon theme ships (theme-relative icons)."""
        from PySide6.QtGui import QIcon

        try:
            for name in candidates or []:
                if name and QIcon.hasThemeIcon(str(name)):
                    return str(name)
        except Exception:
            pass
        try:
            return str((candidates or [""])[0])
        except Exception:
            return ""

    def _draft_cfg(self, appid: str, values) -> object:
        """Config for the dialog's unsaved state (raises on a load failure)."""
        if appid and cfgmod.game_file(appid).is_file():
            cfg = cfgmod.load(appid)
        else:
            cfg = cfgmod.load_defaults()
            cfg.general.appid = appid
        data = dict(values or {})
        self._apply_map(cfg, data)
        if not steammod.is_steam_id(appid):
            cfg.general.name = str(data.get("name", "")).strip()
        return cfg

    @Slot(str, "QVariantMap", result="QVariantMap")
    def previewCommand(self, appid: str, values) -> dict:
        """Launch command preview for dialog (unsaved) state."""
        try:
            cfg = self._draft_cfg(appid, values)
            cmd, _env, warnings = launchermod.build_final_command(cfg, ["%command%"])
        except launchermod.RuntimeNotSetError:
            return {"command": "(Choose a Runtime to Preview)", "wrappers": "", "warnings": []}
        except Exception as e:  # never break the dialog on preview
            return {"command": f"(Preview Unavailable: {e})", "wrappers": "", "warnings": []}
        try:
            wrappers = launchermod.active_wrappers(cfg)
        except Exception:
            wrappers = []
        return {
            "command": shlex.join(cmd) if cmd else "(Empty Command)",
            "wrappers": " · ".join(wrappers) if wrappers else "No Wrappers Enabled",
            "warnings": warnings,
        }

    @Slot(str, "QVariantMap", result=str)
    def diffDefaults(self, appid: str, values) -> str:
        """Unified diff of dialog state vs Global Defaults ('' when same)."""
        try:
            return cfgmod.diff_vs_defaults(self._draft_cfg(appid, values))
        except Exception as e:
            return f"(Diff Unavailable: {e})"

    def _dep_draft(self, appid: str, values) -> object | None:
        """Config for the dialog (unsaved) state, or None on any failure."""
        try:
            return self._draft_cfg(appid, values)
        except Exception as e:
            log.warning("dependencyStatus failed: %s", e)
            return None

    @staticmethod
    def _dep_prefix_entry(cfg) -> dict:
        """Custom prefix line: no prefix, or the wrapper's own path check."""
        prefix = str(cfg.general.custom_prefix or "").strip()
        if not prefix:
            return {"key": "custom_prefix", "kind": "ok", "msg": "prefix-none"}
        parts = _split_args(prefix)
        if not parts:
            return {}
        return {"key": "custom_prefix", **_dep_binary(parts[0], True, "fail")}

    @staticmethod
    def _dep_path_entries(cfg) -> list[dict]:
        """custom-exe/pre-hook/post-hook lines; empty fields stay hidden."""
        rows: list[dict] = []
        for key, command in (
            ("custom_exe", cfg.general.custom_executable),
            ("pre_hook", cfg.pre_post.pre_command),
            ("post_hook", cfg.pre_post.post_command),
        ):
            parts = _split_args(str(command or "").strip())
            if not parts:
                continue
            first = parts[0]
            name = key.replace("_", "-")
            expanded = os.path.expanduser(first)
            if os.path.exists(expanded) or shutil.which(first):
                rows.append({"key": key, "kind": "ok", "msg": "hook-ok", "args": [name, first]})
                continue
            entry = {"key": key, "kind": "warn", "msg": "hook-missing", "args": [name, first]}
            parent = os.path.dirname(expanded)
            if parent and os.path.isdir(parent):
                entry["link"] = parent
            rows.append(entry)
        return rows

    @staticmethod
    def _dep_tool_entries(cfg) -> list[dict]:
        """Tool lines in the widgets order, missing binaries included."""
        rows: list[dict] = []
        feral = bool(cfg.gamemode.feral_gamemode)
        cachy = bool(cfg.gamemode.cachyos_game_performance)
        if not cachy:  # the wheels are mutually exclusive: hide the sidelined one
            rows.append({"key": "gamemoderun", **_dep_binary("gamemoderun", feral)})
        if not feral:
            rows.append({"key": "game-performance", **_dep_binary("game-performance", cachy)})
        rows.append({"key": "gamescope", **_dep_binary("gamescope", bool(cfg.gamescope.enable))})
        rows.append({"key": "mangohud", **_dep_binary("mangohud", bool(cfg.mangohud.enable))})
        rows.append({"key": "rt-upscale", **_dep_binary("upscale", bool(cfg.rtupscale.enable))})
        rows.append({"key": "ludusavi", **GameListModel._ludusavi_status(cfg)})
        return rows

    @staticmethod
    def _ludusavi_status(cfg) -> dict:
        """Flatpak Ludusavi cannot see Wine/Proton prefixes: always warn."""
        exe = shutil.which("ludusavi")
        if exe and "flatpak" in exe:
            return {"kind": "note", "msg": "ludusavi-flatpak", "args": [exe]}
        return _dep_binary("ludusavi", bool(cfg.ludusavi.enable))

    def _dep_steam_entry(self, appid: str, check_steam: bool) -> dict | None:
        """Steam launch-options line (Steam ids only)."""
        if not steammod.is_steam_id(appid):
            return None
        status, options = self._steam_launch_options(appid, check_steam)
        if status == "ok":
            return self._steam_options_entry(options)
        if status == "missing":
            return {"key": "steam-options", "kind": "warn", "msg": "steam-missing"}
        return {"key": "steam-options", "kind": "ok", "msg": "steam-unknown"}

    @staticmethod
    def _steam_options_entry(options: str) -> dict:
        """Launch-options row, warning when Steam would run another build.

        Steam expands `tkarcade %command%` through PATH, so a system
        package built from another branch silently launches older code:
        name the binary and its version when it differs from this GUI.
        """
        from .. import __version__ as gui_version

        path, version = _path_tkarcade_version()
        if not path:
            return {"key": "steam-options", "kind": "warn", "msg": "steam-no-binary"}
        if version and version != gui_version:
            return {
                "key": "steam-options",
                "kind": "warn",
                "msg": "steam-stale",
                "args": [path, version, gui_version],
            }
        return {"key": "steam-options", "kind": "ok", "msg": "steam-ok", "args": [options]}

    @Slot(str, "QVariantMap", bool, result="QVariantList")
    def dependencyStatus(self, appid: str, values, check_steam: bool = False) -> list[dict]:
        """Widgets Dependency Status lines for the dialog (unsaved) state.

        Only the visible lines come back, in the widgets order: the
        caller packs them into two columns (the widgets reflows the same
        way). Every line is {key, kind, msg, args?}: the QML table
        (`GameSettings.statusText`) owns the wording and its translation,
        so lupdate never has to parse this module. `check_steam` gates
        the launch-options probe, which reads each Steam profile's
        localconfig.vdf: the dialog asks for it on open and on tool
        toggles, never on every keystroke.
        """
        cfg = self._dep_draft(appid, values)
        if cfg is None:
            return []
        rows: list[dict] = []
        prefix = self._dep_prefix_entry(cfg)
        if prefix:
            rows.append(prefix)
        rows.extend(self._dep_path_entries(cfg))
        rows.extend(self._dep_tool_entries(cfg))
        steam = self._dep_steam_entry(appid, check_steam)
        if steam is not None:
            rows.append(steam)
        return rows

    def _steam_launch_options(self, appid: str, check_steam: bool) -> tuple[str, str]:
        """(status, options) for the Steam launch options, cached per game.

        The probe reads and parses every profile's localconfig.vdf, so a
        forced check runs off the GUI thread and reports back through
        ``steamStatusReady``; the dialog re-renders with the cache. Tests
        (and headless runs) keep the synchronous path.
        """
        cached = self._steam_status.get(appid)
        if check_steam:
            if not os.environ.get("TKARCADE_NO_BG_FETCH"):
                self._request_steam_status(appid)
                return cached if cached is not None else ("unknown", "")
            return self._probe_steam_status(appid)
        if cached is not None:
            return cached
        if os.environ.get("TKARCADE_NO_BG_FETCH"):
            return self._probe_steam_status(appid)
        self._request_steam_status(appid)
        return "unknown", ""

    def _request_steam_status(self, appid: str) -> None:
        if appid in self._steam_status_busy:
            return
        self._steam_status_busy.add(appid)
        threading.Thread(target=self._steam_status_worker, args=(appid,), daemon=True).start()

    def _probe_steam_status(self, appid: str) -> tuple[str, str]:
        try:
            status, options = steammod.launch_options_status(appid)
        except Exception as e:
            log.warning("launch_options_status(%s) failed: %s", appid, e)
            status, options = "unknown", ""
        self._steam_status[appid] = (status, options)
        return status, options

    def _steam_status_worker(self, appid: str) -> None:
        self._probe_steam_status(appid)
        self._steam_status_busy.discard(appid)
        try:
            self.steamStatusReady.emit(appid)
        except Exception:
            pass

    @Slot(str, result="QVariantMap")
    @Slot(str, str, result="QVariantMap")
    def protonDBInfo(self, appid: str, target: str = "") -> dict:
        """Cached ProtonDB tier for the settings dialog ({} without a link).

        ``target`` is the unsaved Steam AppID field, so the badge follows
        the dialog before Save.
        """
        numeric = self._steam_target(appid, None, target)
        if not numeric:
            return {}
        try:
            data, _fresh = pdbmod.cached(appid, numeric)
        except Exception:
            data = None
        tier = str((data or {}).get("tier", "") or "").lower()
        bg, fg = pdbmod.TIER_STYLE.get(tier, ("", ""))
        return {"tier": tier.title(), "bg": bg, "fg": fg}

    @Slot(str, result=bool)
    @Slot(str, str, result=bool)
    def openProtonDB(self, appid: str, target: str = "") -> bool:
        """Open the ProtonDB page for a game with a Steam AppID."""
        try:
            numeric = self._steam_target(appid, None, target)
            if not numeric:
                return False
            from PySide6.QtCore import QUrl
            from PySide6.QtGui import QDesktopServices

            return bool(QDesktopServices.openUrl(QUrl(pdbmod.GAME_URL.format(appid=numeric))))
        except Exception as e:  # never crash the list on a browser failure
            log.warning("openProtonDB(%s) failed: %s", appid, e)
            return False

    @Slot(str, result=str)
    def copyText(self, text: str) -> str:
        """Copy text to the clipboard; returns the status message."""
        from PySide6.QtGui import QGuiApplication

        try:
            clipboard = QGuiApplication.clipboard()
        except Exception:
            clipboard = None
        if clipboard is None:  # e.g. offscreen/minimal platform
            return "Clipboard Unavailable on This Platform."
        clipboard.setText(text)
        return f"Copied to Clipboard: {text}"

    @Slot(str, result=str)
    def installDir(self, appid: str) -> str:
        """Install folder: the Steam library dir or the local launch cwd."""
        if steammod.is_steam_id(appid):
            try:
                target = steammod.install_dir(appid)
            except Exception:
                target = None
            return str(target) if target is not None else ""
        try:
            return launchermod.local_run_cwd(appid, cfgmod.load(appid)) or ""
        except Exception:
            return ""

    @Slot(str, result=str)
    def prefixDir(self, appid: str) -> str:
        """Effective prefix: Steam's compatdata (or custom), or the local WINEPREFIX."""
        try:
            cfg = cfgmod.load(appid)
            target = cfgmod.prefix_target(appid, cfg)
        except Exception:
            return ""
        return os.fspath(target.container) if target is not None else ""

    @Slot(str, result="QVariantMap")
    def contextActions(self, appid: str) -> dict:
        """Menu actions that fit this game's origin and runtime."""
        is_steam = steammod.is_steam_id(appid)
        try:
            runtime = cfgmod.normalize_runtime(cfgmod.load(appid).runtime.type)
        except Exception:
            runtime = ""
        prefix = ""
        try:
            candidate = os.path.expanduser(self.prefixDir(appid))
        except Exception:
            candidate = ""
        if candidate and os.path.isdir(candidate):
            prefix = candidate
        if is_steam:
            prefix_applicable = runtime == "proton" or bool(prefix)
        else:
            prefix_applicable = runtime in ("wine", "umu")
        return {
            "is_steam": is_steam,
            "steam_appid": steammod.steam_appid(appid) if is_steam else "",
            "protondb_appid": self._steam_target(appid),
            "install": self.installDir(appid),
            "prefix": prefix,
            "prefix_applicable": prefix_applicable,
            "shader": self.shaderDir(appid) if is_steam else "",
            "shader_size": self.shaderSize(appid) if is_steam else "",
        }

    @Slot(str, result="QVariantMap")
    def runtimeOptions(self, appid: str) -> dict:
        """Global runtime choices and discovered Proton installs for the dialog."""
        prefs = cfgmod.load_preferences()
        protons = runtimes.proton_installs()
        default_proton = runtimes.pick_proton(protons, prefs.proton_default)
        default_prefix = ""
        if appid:
            try:
                cfg = cfgmod.load(appid)
                default_prefix = os.fspath(
                    cfgmod.prefix_dir(
                        appid,
                        "",
                        prefs.prefix_base,
                        cfg.runtime.prefix_name,
                        cfg.general.name,
                    )
                )
            except Exception:
                default_prefix = ""
        return {
            "wine": runtimes.wine_binary(prefs.wine_default, prefs.wine_versions),
            "wine_default": str(prefs.wine_default or ""),
            "wine_versions": [
                {"name": entry.name, "path": entry.path, "ok": entry.ok}
                for entry in runtimes.wine_versions(prefs.wine_versions)
            ],
            "prefix_base": str(prefs.prefix_base or ""),
            "default_prefix": default_prefix,
            "protons": [{"name": p.name, "path": os.fspath(p.path)} for p in protons],
            "proton_default": default_proton.name if default_proton is not None else "",
        }

    @Slot(result=list)
    def protonVersionRows(self) -> list:
        """Proton manager rows: discovered builds, system first."""
        try:
            prefs = cfgmod.load_preferences()
        except Exception:
            return []
        installed = runtimes.proton_installs()
        chosen = runtimes.pick_proton(installed, prefs.proton_default)
        return [
            {
                "name": install.name,
                "path": os.fspath(install.path),
                "default": bool(chosen is not None and install.path == chosen.path),
            }
            for install in installed
        ]

    @Slot(str, result=str)
    def setProtonDefault(self, name: str) -> str:
        """Mark one discovered build as the preselected one ("" = the first)."""
        wanted = str(name or "").strip()
        if wanted:
            names = {install.name.casefold() for install in runtimes.proton_installs()}
            if wanted.casefold() not in names:
                return "Not Installed."
        try:
            prefs = cfgmod.load_preferences()
        except Exception:
            return "Could Not Load Preferences."
        prefs.proton_default = wanted
        cfgmod.save_preferences(prefs)
        return ""

    @Slot(result=str)
    def openProtonManager(self) -> str:
        """Open ProtonPlus, else ProtonUp-Qt, detached from the GUI."""
        for exe in ("protonplus", "protonup-qt"):
            found = shutil.which(exe)
            if not found:
                continue
            try:
                subprocess.Popen(
                    [found],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    start_new_session=True,
                )
            except OSError as e:
                log.warning("proton manager launch failed: %s", e)
                return f"Could Not Start {os.path.basename(found)}."
            return ""
        return "ProtonPlus or ProtonUp-Qt Was Not Found."

    @staticmethod
    def _wine_version(path: str) -> str:
        """`wine --version` for one manager row (cached by binary + mtime)."""
        if not path:
            return ""
        try:
            stamp = os.stat(path).st_mtime
        except OSError:
            return ""
        key = (path, stamp)
        if key in _WINE_VERSION_CACHE:
            return _WINE_VERSION_CACHE[key]
        text = ""
        try:
            done = subprocess.run([path, "--version"], capture_output=True, text=True, timeout=1.5)
            lines = (done.stdout or done.stderr or "").strip().splitlines()
            text = lines[0].strip() if lines else ""
        except (OSError, subprocess.SubprocessError):
            text = ""
        _WINE_VERSION_CACHE[key] = text
        return text

    @Slot(result=list)
    def wineVersionRows(self) -> list:
        """Wine manager rows: PATH first, then the configured entries."""
        try:
            prefs = cfgmod.load_preferences()
        except Exception:
            return []
        path = runtimes.wine_path()
        rows = [
            {
                "name": "",
                "path": path,
                "version": self._wine_version(path),
                "ok": bool(path),
                "default": not str(prefs.wine_default or "").strip(),
            }
        ]
        default = str(prefs.wine_default or "").strip().casefold()
        rows += [
            {
                "name": entry.name,
                "path": entry.path,
                "version": self._wine_version(entry.path) if entry.ok else "",
                "ok": entry.ok,
                "default": entry.name.casefold() == default,
            }
            for entry in runtimes.wine_versions(prefs.wine_versions)
        ]
        return rows

    @Slot(str, result=str)
    def addWineVersion(self, path: str) -> str:
        """Append a Wine binary to the managed list ("" = saved)."""
        resolved = runtimes.wine_executable(str(path or "").strip())
        if not resolved:
            return "Not an Executable Wine Binary."
        try:
            prefs = cfgmod.load_preferences()
        except Exception:
            return "Could Not Load Preferences."
        pairs = cfgmod.parse_wine_versions(prefs.wine_versions)
        real = os.path.realpath(resolved)
        for name, stored in pairs:
            if os.path.realpath(runtimes.wine_executable(stored) or stored) == real:
                return f"{name} Is Already in the List."
        pairs.append((cfgmod.wine_entry_name(resolved, [n for n, _ in pairs]), resolved))
        prefs.wine_versions = cfgmod.format_wine_versions(pairs)
        cfgmod.save_preferences(prefs)
        return ""

    @Slot(str, result=str)
    def removeWineVersion(self, name: str) -> str:
        """Drop one entry ("" = saved); the default falls back to PATH."""
        wanted = str(name or "").strip().casefold()
        try:
            prefs = cfgmod.load_preferences()
        except Exception:
            return "Could Not Load Preferences."
        pairs = cfgmod.parse_wine_versions(prefs.wine_versions)
        kept = [(n, p) for n, p in pairs if n.casefold() != wanted]
        if len(kept) == len(pairs):
            return "Not in the List."
        prefs.wine_versions = cfgmod.format_wine_versions(kept)
        if str(prefs.wine_default or "").strip().casefold() == wanted:
            prefs.wine_default = ""
        cfgmod.save_preferences(prefs)
        return ""

    @Slot(str, str, result=str)
    def renameWineVersion(self, name: str, new_name: str) -> str:
        """Rename one entry and every game that selects it ("" = saved)."""
        old = str(name or "").strip()
        clean = re.sub(r"[=:]", "-", str(new_name or "").strip()).strip()
        if not old or not clean:
            return "The Name Cannot Be Empty."
        try:
            prefs = cfgmod.load_preferences()
        except Exception:
            return "Could Not Load Preferences."
        pairs = cfgmod.parse_wine_versions(prefs.wine_versions)
        if not any(n.casefold() == old.casefold() for n, _ in pairs):
            return "Not in the List."
        if any(
            n.casefold() == clean.casefold() and n.casefold() != old.casefold() for n, _ in pairs
        ):
            return f"{clean} Is Already in the List."
        prefs.wine_versions = cfgmod.format_wine_versions(
            [(clean, path) if n.casefold() == old.casefold() else (n, path) for n, path in pairs]
        )
        if str(prefs.wine_default or "").strip().casefold() == old.casefold():
            prefs.wine_default = clean
        cfgmod.save_preferences(prefs)
        self._rename_wine_in_games(old, clean)
        return ""

    @staticmethod
    def _rename_wine_in_games(old: str, new: str) -> None:
        """Keep [runtime] tool pointing at the entry after a rename."""
        for appid in cfgmod.list_appids():
            try:
                cfg = cfgmod.load(appid)
            except Exception:
                continue
            if cfg.runtime.type != "wine":
                continue
            if cfg.runtime.tool.strip().casefold() != old.casefold():
                continue
            cfg.runtime.tool = new
            cfgmod.save(cfg)

    @Slot(str, result=str)
    def setWineDefault(self, name: str) -> str:
        """Mark one entry as the default ("" = Wine from PATH)."""
        wanted = str(name or "").strip()
        try:
            prefs = cfgmod.load_preferences()
        except Exception:
            return "Could Not Load Preferences."
        if wanted:
            names = {n.casefold() for n, _ in cfgmod.parse_wine_versions(prefs.wine_versions)}
            if wanted.casefold() not in names:
                return "Not in the List."
        prefs.wine_default = wanted
        cfgmod.save_preferences(prefs)
        return ""

    @staticmethod
    def _prefix_users(prefs: cfgmod.Preferences) -> dict[str, list[str]]:
        """AppIDs resolved to each prefix directory they own.

        A Steam game joins only through a custom prefix: its compatdata
        dir is Steam's own layout (a ``pfx`` inside), never a local
        base/subfolder resolution.
        """
        usage: dict[str, list[str]] = {}
        for appid in cfgmod.list_appids():
            try:
                cfg = cfgmod.load(appid)
                target = cfgmod.prefix_target(appid, cfg, prefs)
            except Exception:
                continue
            if target is None or not target.managed:
                continue
            usage.setdefault(os.fspath(target.container), []).append(appid)
        return usage

    @Slot(str, str, str, str, result="QVariantMap")
    def prefixNameState(self, appid: str, name: str, path: str = "", game_name: str = "") -> dict:
        """Resolved prefix for the name and dir fields, plus sharing info.

        A Steam game's field is its compatdata dir itself (empty = Steam's
        default). A local prefix is always ``<base>/<stem>``: the stem is
        the explicit name, else the game name normalised, else the AppID.
        """
        prefs = cfgmod.load_preferences()
        typed = name.strip()
        is_steam = steammod.is_steam_id(appid)
        if is_steam:
            custom = path.strip()
            target = Path(custom).expanduser() if custom else None
        else:
            target = cfgmod.prefix_dir(appid, path.strip(), prefs.prefix_base, name, game_name)
        usage = self._prefix_users(prefs)
        others = []
        if target is not None:
            others = [a for a in usage.get(os.fspath(target), []) if a != appid]
        names = self._all_names()
        sanitized = ""
        renamed = False
        if target is not None and not is_steam:
            sanitized = target.name
            renamed = bool(typed) and target.name != typed
        return {
            "target": os.fspath(target) if target is not None else "",
            "sanitized": sanitized,
            "renamed": renamed,
            "shared": [names.get(a, a) for a in others],
            "exists": target is not None and target.is_dir(),
            "is_prefix": target is not None and xdg.is_wine_prefix(target),
            "steam": is_steam,
        }

    @Slot(str, str, result="QVariantList")
    def prefixChoices(self, appid: str, base: str = "") -> list:
        """Existing Wine prefixes under the base, with the games using each.

        `base` is the game's own `[runtime] prefix` when set; the
        Preferences base is the fallback.
        """
        prefs = cfgmod.load_preferences()
        root = base.strip() or prefs.prefix_base
        usage = self._prefix_users(prefs)
        names = self._all_names()
        out = []
        for path in xdg.iter_prefixes(root):
            users = usage.get(os.fspath(path), [])
            out.append(
                {
                    "name": path.name,
                    "path": os.fspath(path),
                    "games": [names.get(a, a) for a in users],
                    "current": appid in users,
                }
            )
        return out

    @Slot(str, result="QVariantMap")
    def graphicsState(self, appid: str) -> dict:
        """Installed layers (marker) and the installed versions per layer."""
        self._kick_archive_sync()
        prefs = cfgmod.load_preferences()
        prefix = None
        if appid:
            try:
                cfg = cfgmod.load(appid)
                prefix = cfgmod.prefix_dir(
                    appid,
                    cfg.runtime.prefix,
                    prefs.prefix_base,
                    cfg.runtime.prefix_name,
                    cfg.general.name,
                )
            except Exception:
                prefix = None
        available = {}
        versions = {}
        defaults = {}
        for kind in ("dxvk", "vkd3d"):
            found = runtimes.graphics_versions(kind)
            versions[kind] = [v.name for v in found]
            chosen = graphicsmod.selected_version(kind, prefs)
            defaults[kind] = chosen if chosen in versions[kind] else ""
            available[kind] = (
                chosen
                if chosen in versions[kind]
                else (versions[kind][0] if versions[kind] else "")
            )
        return {
            "prefix": os.fspath(prefix) if prefix is not None else "",
            "installed": graphicsmod.installed(prefix) if prefix is not None else {},
            "available": available,
            "defaults": defaults,
            "versions": versions,
        }

    @Slot(str, result=str)
    def removeGraphics(self, appid: str) -> str:
        """Delete the graphics files TKArcade copied into the prefix ('' = ok)."""
        if not appid:
            return "Choose a Game First."
        try:
            cfg = cfgmod.load(appid)
        except Exception as e:
            return f"Could Not Read the Config: {e}"
        prefs = cfgmod.load_preferences()
        prefix = cfgmod.prefix_dir(
            appid,
            cfg.runtime.prefix,
            prefs.prefix_base,
            cfg.runtime.prefix_name,
            cfg.general.name,
        )
        removed, warnings = graphicsmod.uninstall(prefix)
        log.info("graphics: removed %d file(s) from %s", removed, prefix)
        self.refresh()
        return warnings[0] if warnings else ""

    @Slot(result="QVariantMap")
    def runtimeArchiveDirs(self) -> dict:
        """Where downloads land and where dropped archives are picked up."""
        return {
            "managed": os.fspath(xdg.runtimes_dir()),
            "cache": os.fspath(xdg.archives_cache_dir()),
        }

    @Slot(str, result="QVariantList")
    def runtimeVersions(self, kind: str) -> list:
        """Managed versions of one layer with their recorded source."""
        if kind not in runtimes.GRAPHICS_DLLS:
            return []
        prefs = cfgmod.load_preferences()
        default = str(prefs.dxvk_default if kind == "dxvk" else prefs.vkd3d_default).strip()
        managed = xdg.runtimes_dir() / kind
        system_roots = {path.resolve() for path in runtimes.system_graphics_roots(kind)}
        known = archivesmod.sources()
        out = []
        for version in runtimes.graphics_versions(kind):
            source = known.get(f"{kind}/{version.name}", {})
            root = version.root.resolve()
            system = root in system_roots or root.parent in system_roots
            external = system or managed.resolve() not in root.parents
            origin = "system" if system else ("external" if external else "")
            out.append(
                {
                    "name": version.name,
                    "origin": origin or str(source.get("origin") or ""),
                    "repo": str(source.get("repo") or ""),
                    "tag": str(source.get("tag") or ""),
                    "url": str(source.get("url") or ""),
                    "external": external,
                    "system": system,
                    "default": version.name == default,
                }
            )
        return out

    @Slot(str, result=str)
    def graphicsSource(self, kind: str) -> str:
        """Stored source id for a layer (preset id or custom:owner/repo)."""
        try:
            prefs = cfgmod.load_preferences()
        except Exception:
            return "official"
        return str(prefs.dxvk_source if kind == "dxvk" else prefs.vkd3d_source)

    @Slot(str, str, str, result=str)
    def setGraphicsSource(self, kind: str, source: str, repo: str = "") -> str:
        """Store the manager's source picker ("" = saved)."""
        if kind not in runtimes.GRAPHICS_DLLS:
            return "Unknown Runtime Layer."
        value = cfgmod.graphics_source_value(kind, source, repo)
        if str(source or "").strip() == "custom" and not value.startswith("custom:"):
            return "Enter a GitHub owner/repo."
        try:
            prefs = cfgmod.load_preferences()
        except Exception:
            return "Could Not Load Preferences."
        if kind == "dxvk":
            prefs.dxvk_source = value
        else:
            prefs.vkd3d_source = value
        cfgmod.save_preferences(prefs)
        return ""

    @Slot(str, str, result=str)
    def setGraphicsDefault(self, kind: str, name: str) -> str:
        """Mark one installed version as the layer default ("" = newest)."""
        if kind not in runtimes.GRAPHICS_DLLS:
            return "Unknown Runtime Layer."
        wanted = str(name or "").strip()
        if wanted:
            names = {v.name for v in runtimes.graphics_versions(kind)}
            if wanted not in names:
                return "Not Installed."
        try:
            prefs = cfgmod.load_preferences()
        except Exception:
            return "Could Not Load Preferences."
        if kind == "dxvk":
            prefs.dxvk_default = wanted
        else:
            prefs.vkd3d_default = wanted
        cfgmod.save_preferences(prefs)
        return ""

    @Slot(str, result=list)
    def graphicsFolders(self, kind: str) -> list:
        """Extra version roots registered for a layer."""
        return cfgmod.external_dirs(kind)

    @Slot(str, str, result=str)
    def addGraphicsFolder(self, kind: str, path: str) -> str:
        """Register a directory holding versions TKArcade did not install."""
        return cfgmod.add_external_dir(kind, path)

    @Slot(str, str, result=str)
    def removeGraphicsFolder(self, kind: str, path: str) -> str:
        """Forget a registered root; the files stay where they are."""
        return cfgmod.remove_external_dir(kind, path)

    def _runtime_repo(self, kind: str) -> str:
        """GitHub owner/repo behind the layer's source picker ("" = official)."""
        try:
            prefs = cfgmod.load_preferences()
        except Exception:
            return ""
        source = prefs.dxvk_source if kind == "dxvk" else prefs.vkd3d_source
        return runtimes.graphics_repo(source)

    @Slot(str)
    def fetchRuntimeReleases(self, kind: str) -> None:
        """List installable releases for a layer off the GUI thread."""
        if kind not in runtimes.GRAPHICS_DLLS:
            self.runtimeReleases.emit(str(kind), [], "Unknown Runtime Layer.")
            return
        repo = self._runtime_repo(kind)
        threading.Thread(target=self._releases_worker, args=(kind, repo), daemon=True).start()

    def _releases_worker(self, kind: str, repo: str) -> None:
        try:
            rows = [
                {
                    "tag": str(item.get("tag") or ""),
                    "name": str(item.get("name") or ""),
                    "url": str(item.get("url") or ""),
                    "size": int(item.get("size") or 0),
                    "digest": str(item.get("digest") or ""),
                    "prerelease": bool(item.get("prerelease")),
                }
                for item in archivesmod.releases(kind, repo=repo)
            ]
            message = ""
        except Exception as e:
            rows, message = [], str(e)
        self.runtimeReleases.emit(kind, rows, message)

    def _begin_archive(self, kind: str) -> bool:
        """Claim the per-layer install slot (False = one is already running)."""
        with self._archive_lock:
            if kind in self._archive_busy:
                return False
            self._archive_busy.add(kind)
        return True

    def _run_archive(self, kind: str, work) -> None:
        """Run one install worker off the GUI thread."""
        threading.Thread(target=self._archive_worker, args=(kind, work), daemon=True).start()

    def _archive_worker(self, kind: str, work) -> None:
        try:
            with self._archive_work_lock:
                message = work(lambda text: self.archiveProgress.emit(kind, text))
        except Exception as e:  # never kill the signal path on a helper bug
            message = f"{kind} download failed: {e}"
        with self._archive_lock:
            self._archive_busy.discard(kind)
        self.archiveFinished.emit(kind, message)
        if not message:
            self.archivesChanged.emit()

    @Slot(str)
    def downloadLatestGraphics(self, kind: str) -> None:
        """Download and install the latest release off the GUI thread."""
        if kind not in runtimes.GRAPHICS_DLLS:
            self.archiveFinished.emit(str(kind), "Unknown Runtime Layer.")
            return
        if not self._begin_archive(kind):
            return
        self.archiveProgress.emit(kind, "Checking the Latest Release…")
        repo = self._runtime_repo(kind)
        self._run_archive(
            kind, lambda say: archivesmod.download_latest(kind, progress=say, repo=repo)
        )

    @Slot(str, "QVariantMap")
    def installRuntimeRelease(self, kind: str, asset) -> None:
        """Install one release the manager listed."""
        if kind not in runtimes.GRAPHICS_DLLS:
            self.archiveFinished.emit(str(kind), "Unknown Runtime Layer.")
            return
        release = (
            {key: asset.get(key, "") for key in ("name", "url", "size", "digest", "tag")}
            if hasattr(asset, "get")
            else {}
        )
        if not str(release.get("url") or ""):
            self.archiveFinished.emit(str(kind), "Choose a Release First.")
            return
        if not self._begin_archive(kind):
            return
        repo = self._runtime_repo(kind)
        self._run_archive(
            kind,
            lambda say: archivesmod.download_release(kind, release, progress=say, repo=repo),
        )

    @Slot(str, str)
    def installRuntimeFromUrl(self, kind: str, url: str) -> None:
        """Install a layer from an archive URL the user pasted."""
        text = str(url or "").strip()
        if kind not in runtimes.GRAPHICS_DLLS:
            self.archiveFinished.emit(str(kind), "Unknown Runtime Layer.")
            return
        if not text:
            self.archiveFinished.emit(kind, "Enter an Archive URL First.")
            return
        if not self._begin_archive(kind):
            return
        self._run_archive(kind, lambda say: archivesmod.install_from_url(kind, text, progress=say))

    @Slot(str, str, result=str)
    def removeRuntimeVersion(self, kind: str, name: str) -> str:
        """Delete one managed version; "" on success, else a message."""
        message = archivesmod.remove_version(kind, name)
        if not message:
            log.info("runtime: removed %s/%s", kind, name)
            self.archivesChanged.emit()
        return message

    def _kick_archive_sync(self) -> None:
        """Extract pending cache archives in the background (once at a time)."""
        try:
            pending = any(
                entry.is_file()
                and not entry.name.endswith(".part")
                and archivesmod.supported(entry.name)
                for entry in xdg.archives_cache_dir().iterdir()
            )
        except OSError:
            return
        if not pending:
            return
        with self._archive_lock:
            if self._archive_sync_running:
                return
            self._archive_sync_running = True
        threading.Thread(target=self._sync_archive_worker, daemon=True).start()

    def _sync_archive_worker(self) -> None:
        try:
            with self._archive_work_lock:
                changed = archivesmod.sync_archives(
                    progress=lambda text: log.info("runtime archives: %s", text)
                )
        except Exception as e:
            log.warning("runtime archive sync failed: %s", e)
            changed = []
        with self._archive_lock:
            self._archive_sync_running = False
        if changed:
            self.archivesChanged.emit()

    @Slot(str, result=str)
    def shaderDir(self, appid: str) -> str:
        """Shader cache path, or '' when unknown."""
        try:
            target = steammod.shader_dir(appid)
        except Exception:
            target = None
        return str(target) if target is not None else ""

    @Slot(str, result=str)
    def shaderSize(self, appid: str) -> str:
        """Cached shader-cache size; a miss walks it in the background.

        ``dir_size`` can touch thousands of files, so the context menu must
        never wait for it: the first call returns "" and the walk reports
        through ``shaderSizeReady``.
        """
        if appid in self._shader_sizes:
            return self._shader_sizes[appid]
        self._request_shader_size(appid)
        return ""

    def _request_shader_size(self, appid: str) -> None:
        if appid in self._shader_size_busy:
            return
        self._shader_size_busy.add(appid)
        threading.Thread(target=self._shader_size_worker, args=(appid,), daemon=True).start()

    def _shader_size_worker(self, appid: str) -> None:
        try:
            target = steammod.shader_dir(appid)
            size = steammod.format_size(steammod.dir_size(target)) if target else ""
        except Exception:
            size = ""
        self._shader_sizes[appid] = size
        self._shader_size_busy.discard(appid)
        try:
            self.shaderSizeReady.emit(appid, size)
        except Exception:
            pass

    @Slot(str, result=bool)
    def openPath(self, path: str) -> bool:
        """Open a folder with the desktop default app, with fallbacks."""
        import subprocess

        from PySide6.QtCore import QUrl
        from PySide6.QtGui import QDesktopServices

        try:
            if QDesktopServices.openUrl(QUrl.fromLocalFile(path)):
                return True
        except Exception:
            pass
        xdg_open = shutil.which("xdg-open")
        if xdg_open:
            try:
                subprocess.Popen([xdg_open, path])
                return True
            except Exception:
                pass
        return False

    @Slot(str, result=str)
    def clearShaderCache(self, appid: str) -> str:
        """Delete precompiled shaders (Steam rebuilds); status message."""
        try:
            target = steammod.shader_dir(appid)
        except Exception:
            return ""
        if target is None:
            return ""
        try:
            size = steammod.format_size(steammod.dir_size(target))
            shutil.rmtree(target)
        except Exception as e:
            return f"{appid}: {e}"
        self._shader_sizes.pop(appid, None)
        return f"Cleared {size} of Shader Cache."

    @Slot(str, result=list)
    def validateGame(self, appid: str) -> list:
        """Validation issues for one game (same checks as --validate)."""
        from ..launcher import validate_game

        try:
            return list(validate_game(appid))
        except Exception as e:
            return [str(e)]

    @Slot(str, result="QVariantMap")
    def validateReport(self, appid: str) -> dict:
        """Validation report for the dialog: name + issues without the ID prefix.

        validate_game() prefixes every issue with the AppID for the CLI;
        the GUI shows the display name once in the title instead.
        """
        appid = str(appid)
        issues = self.validateGame(appid)
        prefix = f"{appid}: "
        return {
            "name": self._display_name(appid),
            "issues": [i.removeprefix(prefix) for i in issues],
        }

    @Slot(str, result=int)
    def clearHistory(self, appid: str) -> int:
        """Delete session history for one game; returns sessions removed."""
        try:
            removed = histmod.clear_appid(xdg.log_file(), appid)
        except Exception as e:
            log.warning("clearHistory(%s) failed: %s", appid, e)
            return 0
        self.refresh()
        return int(removed)

    @Slot(result=bool)
    def clearAllHistory(self) -> bool:
        """Truncate the session log (bulk "Clear History..."); True on success."""
        try:
            xdg.log_file().write_text("", encoding="utf-8")
        except OSError as e:
            log.warning("clearAllHistory failed: %s", e)
            return False
        self.refresh()
        return True

    @Slot(list, result=list)
    def gameNames(self, appids: list) -> list:
        """Display names for AppIDs (dialog labels)."""
        names = self._all_names()
        return [names.get(str(a), str(a)) for a in appids]

    @Slot(result=list)
    def uninstalledGames(self) -> list:
        """Configured games whose install is gone (hamburger cleanup)."""
        from ..launcher import missing_install

        ids = []
        for appid in cfgmod.list_appids():
            try:
                if missing_install(appid):
                    ids.append(appid)
            except Exception:
                continue
        return ids

    @Slot(list, result=str)
    def removeGames(self, appids: list) -> str:
        """Delete configs; returns '' or joined errors. Refreshes the list."""
        errors = []
        self._removed_prefixes = {}
        self._removed_names = {}
        for appid in [str(a) for a in appids]:
            # Capture name and prefix while the config still exists.
            try:
                self._removed_names[appid] = self._display_name(appid)
            except Exception:
                pass
            try:
                prefix = self._resolved_prefix(appid)
                if prefix is not None:
                    self._removed_prefixes[appid] = str(prefix)
            except Exception as e:
                log.warning("prefix capture(%s) failed: %s", appid, e)
            try:
                cfgmod.game_file(appid).unlink(missing_ok=True)
            except Exception as e:
                errors.append(f"{appid}: {e}")
        self.refresh()
        return "\n".join(errors)

    def _resolved_prefix(self, appid: str) -> Path | None:
        """Prefix owned by a game, excluding Steam's compatdata (Steam's)."""
        appid = str(appid)
        try:
            cfg = cfgmod.load(appid)
        except Exception:
            cfg = None
        try:
            prefs = cfgmod.load_preferences()
        except Exception:
            prefs = None
        try:
            target = cfgmod.prefix_target(appid, cfg, prefs)
            if target is None or not target.managed:
                return None
            resolved = target.container.resolve()
        except Exception:
            return None
        if steammod.origin(appid) == "steam" and "compatdata" in resolved.parts:
            return None
        return resolved if resolved.is_dir() else None

    def _live_prefixes(self) -> set[str]:
        """Prefixes still referenced by configured games (shared = keep)."""
        out = set()
        for appid in cfgmod.list_appids():
            prefix = self._resolved_prefix(appid)
            if prefix is not None:
                out.add(str(prefix))
        return out

    def _leftover_row(self, appid, names, stats, live_prefixes) -> dict | None:
        """One cleanup row for an appid, or None when nothing is left."""
        appid = str(appid)
        try:
            profiles = sum(1 for p in cfgmod.profiles_dir(appid).glob("*.toml") if p.is_file())
        except Exception:
            profiles = 0
        session_log = xdg.game_log_file(appid).is_file()
        proton_log = (xdg.games_log_dir() / xdg.safe_stem(appid)).is_dir()
        game_stats = stats.get(appid)
        history = int(game_stats.runs) if game_stats is not None else 0
        try:
            artwork = len(artmod.cache_files(appid)) + sum(
                1
                for name in ("protondb", "steam-release", *metamod.cache_dirs())
                if (xdg.app_cache_dir() / name / f"{xdg.safe_stem(appid)}.json").is_file()
            )
        except Exception:
            artwork = 0
        prefix = self._removed_prefixes.get(appid, "")
        if not prefix:
            found = self._resolved_prefix(appid)
            prefix = str(found) if found is not None else ""
        if prefix and prefix in live_prefixes:
            prefix = ""
        if not (profiles or session_log or proton_log or history or prefix or artwork):
            return None
        return {
            "appid": appid,
            "name": names.get(appid, appid),
            "profiles": profiles,
            "session_log": session_log,
            "proton_log": proton_log,
            "history": history,
            "artwork": artwork,
            "prefix": prefix,
        }

    @staticmethod
    def _leftover_names() -> dict:
        try:
            return GameListModel._all_names()
        except Exception:
            return {}

    @staticmethod
    def _leftover_stats() -> dict:
        try:
            return histmod.summarize(histmod.parse_log(xdg.log_file()))
        except Exception:
            return {}

    def _leftover_candidates(self, stats: dict) -> set:
        candidates = {appid for appid, _count in cfgmod.orphaned_profiles()}
        games = xdg.games_log_dir()
        if games.is_dir():
            for entry in games.iterdir():
                if entry.is_file() and entry.suffix == ".log":
                    candidates.add(entry.stem)
                elif entry.is_dir():
                    candidates.add(entry.name)
        candidates.update(stats)
        try:
            candidates.update(artmod.cache_keys())
        except Exception:
            pass
        for name in ("protondb", "steam-release", *metamod.cache_dirs()):
            try:
                candidates.update(p.stem for p in (xdg.app_cache_dir() / name).glob("*.json"))
            except OSError:
                pass
        return candidates

    def _leftover_rows(self, appids=None) -> list:
        """Cleanup rows for the given appids (None = every orphan)."""
        names = self._leftover_names()
        names.update(self._removed_names)
        stats = self._leftover_stats()
        live = set(cfgmod.list_appids())
        if appids is None:
            candidates = self._leftover_candidates(stats) - live
        else:
            candidates = [str(a) for a in appids]
        live_prefixes = self._live_prefixes()
        rows = []
        for appid in sorted(candidates):
            if appid in live:
                continue
            row = self._leftover_row(appid, names, stats, live_prefixes)
            if row is not None:
                rows.append(row)
        return rows

    @Slot(result=list)
    def orphanedLeftovers(self) -> list:
        """Profiles, logs and history of games with no live config."""
        try:
            return self._leftover_rows()
        except Exception as e:
            log.warning("orphanedLeftovers failed: %s", e)
            return []

    @Slot(list, result=list)
    def leftoverData(self, appids: list) -> list:
        """Cleanup rows for just-removed appids (prefix captured before)."""
        try:
            return self._leftover_rows(appids)
        except Exception as e:
            log.warning("leftoverData(%s) failed: %s", appids, e)
            return []

    @Slot(list, result=list)
    def leftoverProfiles(self, appids: list) -> list:
        """Subset of appids still holding saved profiles."""
        out = []
        for appid in [str(a) for a in appids]:
            try:
                left = [p for p in cfgmod.profiles_dir(appid).glob("*.toml") if p.is_file()]
            except Exception:
                left = []
            if left:
                out.append(appid)
        return out

    @Slot(list, result=int)
    def cleanProfiles(self, appids: list) -> int:
        """Delete saved profiles; returns games cleaned."""
        cleaned = 0
        for appid in [str(a) for a in appids]:
            try:
                shutil.rmtree(cfgmod.profiles_dir(appid))
                cleaned += 1
            except Exception as e:
                log.warning("cleanProfiles(%s) failed: %s", appid, e)
        return cleaned

    @staticmethod
    def _clean_game_files(appid: str) -> bool:
        """Delete profiles, the per-game session log and the Proton logs."""
        touched = False
        for target in (cfgmod.profiles_dir(appid), xdg.game_log_file(appid)):
            try:
                if target.is_dir():
                    shutil.rmtree(target)
                    touched = True
                elif target.exists():
                    target.unlink()
                    touched = True
            except Exception as e:
                log.warning("cleanLeftovers(%s) %s: %s", appid, target, e)
        game_dir = xdg.games_log_dir() / xdg.safe_stem(appid)
        try:
            if game_dir.is_dir():
                shutil.rmtree(game_dir)
                touched = True
        except Exception as e:
            log.warning("cleanLeftovers(%s) logs: %s", appid, e)
        return touched

    @staticmethod
    def _clean_game_cache(appid: str) -> bool:
        """Delete cached artwork, ProtonDB, release-date and metadata entries."""
        touched = False
        try:
            if artmod.clear_cache(appid):
                touched = True
        except Exception as e:
            log.warning("cleanLeftovers(%s) artwork: %s", appid, e)
        for name in ("protondb", "steam-release", *metamod.cache_dirs()):
            try:
                cached = xdg.app_cache_dir() / name / f"{xdg.safe_stem(appid)}.json"
                if cached.is_file():
                    cached.unlink()
                    touched = True
            except Exception as e:
                log.warning("cleanLeftovers(%s) %s cache: %s", appid, name, e)
        return touched

    @staticmethod
    def _clean_game_leftovers(appid: str) -> bool:
        """Delete profiles, session log, Proton logs, history and cached art."""
        touched = GameListModel._clean_game_files(appid)
        if GameListModel._clean_game_cache(appid):
            touched = True
        try:
            if histmod.clear_appid(xdg.log_file(), appid):
                touched = True
        except Exception as e:
            log.warning("cleanLeftovers(%s) history: %s", appid, e)
        return touched

    def _clean_owned_prefix(self, appid: str, live_prefixes: set[str]) -> bool:
        """Delete the removed game's prefix when no live game shares it."""
        prefix = self._removed_prefixes.pop(appid, "")
        if not prefix:
            found = self._resolved_prefix(appid)
            prefix = str(found) if found is not None else ""
        if not prefix or prefix in live_prefixes:
            return False
        if not self._deletable_prefix(Path(prefix)):
            log.warning("cleanup: refusing to delete %s: not a Wine prefix", prefix)
            return False
        try:
            shutil.rmtree(prefix)
        except Exception as e:
            log.warning("cleanLeftovers(%s) prefix: %s", appid, e)
            return False
        return True

    @Slot(list, bool, result=int)
    def cleanLeftovers(self, appids: list, delete_prefixes: bool = False) -> int:
        """Delete profiles, per-game logs, history and (optionally) the prefix."""
        live_prefixes = self._live_prefixes()
        cleaned = 0
        for appid in [str(a) for a in appids]:
            touched = self._clean_game_leftovers(appid)
            if delete_prefixes and self._clean_owned_prefix(appid, live_prefixes):
                touched = True
            if touched:
                cleaned += 1
        self._removed_prefixes.clear()
        self._removed_names.clear()
        self.refresh()
        return cleaned

    backgroundDone = Signal()
    #: (appid, status, provider) after Fetch Artwork: status is "ok",
    #: "choose" (a title search needs a pick), "no-key", "no-igdb-key",
    #: "no-id", "no-match", "not-a-steam-app", "not-found", "blocked",
    #: "network" or "no-art"; provider is "steam", "sgdb", "igdb" or "".
    artworkFetched = Signal(str, str, str)
    #: (appid, igdb_id) when an explicit art action resolved the IGDB
    #: game; the open dialog writes the draft identity back.
    igdbResolved = Signal(str, str)
    #: (appid, [{"id", "name", "provider"}, ...]) when a title search
    #: needs a choice; provider is "sgdb" or "igdb".
    artworkChoices = Signal(str, "QVariantList")
    #: (appid, kind, error) after an image downloaded from a pasted URL;
    #: error is "", "network", "not-image", "too-large" or "save".
    artworkStored = Signal(str, str, str)
    #: (appid, fields) after Download Metadata; fields is the empty map
    #: when the provider has no target or answered nothing.
    metadataFetched = Signal(str, "QVariantMap")
    #: (appid, rows) when a title search needs a pick: rows are
    #: [{"id": "v2002", "name": "STEINS;GATE (2009)"}, ...].
    metadataChoices = Signal(str, "QVariantList")

    @Slot()
    def fetchMissing(self) -> None:
        """Refresh stale ProtonDB tiers, release dates and missing artwork off-thread.

        Only explicit UI entry calls this (never refresh() itself), so
        headless tests stay offline. Emits backgroundDone -> refresh.
        """
        self._fetch_async()

    def _fetch_async(self, appids=None, enrich: bool = False) -> None:
        """Start the stale-data fetch off-thread: every game, or a subset.

        ``enrich`` also writes the store metadata of a Steam id; only the
        save path asks for it, never the startup pass.
        """
        if os.environ.get("TKARCADE_NO_BG_FETCH"):
            return
        threading.Thread(target=self._fetch_worker, args=(appids, enrich), daemon=True).start()

    def _fetch_worker(self, appids=None, enrich: bool = False) -> None:
        try:
            prefs = cfgmod.load_preferences()
            api_key = prefs.sgdb_api_key.strip()
            default = prefs.artwork_source
        except Exception:
            api_key, default = "", "steam"
        for appid in list(appids) if appids is not None else cfgmod.list_appids():
            self._fetch_game(str(appid), api_key, default, enrich)
        try:
            self.backgroundDone.emit()
        except Exception:
            pass

    def _fetch_game(self, appid: str, api_key: str, default: str, enrich: bool) -> None:
        """Refresh one game's stale tier, release date and art (worker only)."""
        if not steammod.is_steam_id(appid):
            target = self._steam_target(appid)
            if target:
                self._refresh_protondb(appid, target)
        provider = self._game_provider(appid, default)
        source = self._art_source(appid)
        if source.isdigit():
            # The Artwork Source AppID is a plain Steam appid, never a
            # configured one: download it on its own.
            self._fetch_steam_art(source, api_key, provider)
        elif steammod.is_steam_id(appid):
            self._fetch_one(appid, api_key, provider, steammod.steam_appid(appid))
        else:
            # A local game without an AppID: its art comes from the name.
            names = self._name_queries(appid)
            if names:
                self._fetch_local(appid, names, api_key, provider)
        if enrich and steammod.is_steam_id(appid):
            self._enrich_steam(appid)

    def _enrich_steam(self, appid: str) -> None:
        """Write a just-added Steam game's store metadata (background).

        Fill-empty and the locks decide what lands; a failed fetch changes
        nothing, and the metadata cache keeps a re-add from asking twice.
        """
        try:
            data = metamod.download("steam", appid)
        except Exception as e:
            log.debug("steam metadata(%s) failed: %s", appid, e)
            return
        if not data:
            return
        try:
            cfg = cfgmod.load(appid)
        except Exception as e:
            log.debug("steam metadata(%s) load failed: %s", appid, e)
            return
        if not _fill_steam_metadata(cfg, data):
            return
        try:
            cfgmod.save(cfg)
        except Exception as e:
            log.warning("steam metadata(%s) save failed: %s", appid, e)

    def _fetch_one(self, appid, api_key: str, provider: str, target: str) -> None:
        """Refresh ProtonDB, the release date (and art) for one Steam appid."""
        self._refresh_protondb(appid, target)
        try:
            if not cfgmod.load(appid).metadata.date.strip():
                _date, fresh = rdmod.cached(appid)
                if not fresh:
                    rdmod.refresh(appid)
        except Exception:
            pass
        self._fetch_steam_art(target, api_key, provider)

    def _refresh_protondb(self, appid, target: str) -> None:
        """Refresh one game's cached tier; failures leave the cache alone."""
        try:
            _data, fresh = pdbmod.cached(appid, target)
            if not fresh:
                pdbmod.refresh(appid, target)
        except Exception:
            pass

    @Slot(str, str, str)
    def fetchMetadata(self, appid: str, provider: str = "steam", target: str = "") -> None:
        """Download one provider's metadata off-thread for the dialog to fill."""
        if provider not in metamod.PROVIDERS:
            self.metadataFetched.emit(appid, {})
            return
        if os.environ.get("TKARCADE_NO_BG_FETCH"):
            # Headless runs stay offline; the window shows its empty state.
            self.metadataFetched.emit(appid, {})
            return
        if provider == "steam":
            target = self._steam_target(appid, None, target)
            if not target:
                self.metadataFetched.emit(appid, {})
                return
        threading.Thread(
            target=self._metadata_worker, args=(appid, provider, target), daemon=True
        ).start()

    def _metadata_worker(self, appid: str, provider: str, target: str) -> None:
        """Use the fresh cache first; the provider call only when stale/missing."""
        try:
            data = metamod.download(provider, appid, target)
        except Exception:
            data = None
        self.metadataFetched.emit(appid, data or {})

    @Slot(str, str, str)
    def searchMetadata(self, appid: str, provider: str, title: str = "") -> None:
        """Search a provider by title off-thread; the dialog picks a candidate."""
        query = str(title or "").strip()
        if not query or provider not in metamod.PROVIDERS:
            self.metadataChoices.emit(appid, [])
            return
        if os.environ.get("TKARCADE_NO_BG_FETCH"):
            self.metadataChoices.emit(appid, [])
            return
        threading.Thread(
            target=self._metadata_search_worker, args=(appid, provider, query), daemon=True
        ).start()

    def _metadata_search_worker(self, appid: str, provider: str, query: str) -> None:
        try:
            rows = metamod.search(provider, query)
        except Exception:
            rows = []
        self.metadataChoices.emit(appid, rows)

    @Slot(result=bool)
    def igdbConfigured(self) -> bool:
        """Whether the IGDB provider has its Twitch client id and secret."""
        try:
            prefs = cfgmod.load_preferences()
        except Exception:
            return False
        return bool(prefs.igdb_client_id.strip() and prefs.igdb_client_secret.strip())

    def _fetch_steam_art(self, target: str, api_key: str, provider: str) -> None:
        """Download whatever art kinds are missing for one Steam AppID."""
        numeric = steammod.steam_appid(target)
        if not numeric:
            return
        try:
            artmod.fetch_best(numeric, provider, api_key)
        except Exception as e:
            log.warning("artwork fetch(%s) failed: %s", target, e)

    def _fetch_local(self, appid: str, names, api_key: str, provider: str) -> None:
        """Download a local game's art by name (exact match only, no UI)."""
        try:
            artmod.fetch_best(appid, provider, api_key, names=tuple(names))
        except Exception as e:
            log.warning("artwork name fetch(%s) failed: %s", appid, e)

    @Slot(result=list)
    def scanCandidates(self) -> list:
        """Unconfigured Steam games as [appid, name] pairs."""
        try:
            configured = set(cfgmod.list_appids())
            cands = steammod.unconfigured_games(configured)
        except Exception:
            return []
        return [[str(a), str(n)] for a, n in cands]

    @Slot(result=list)
    def orphanedProfiles(self) -> list:
        """Orphaned profiles as [appid, name, count] rows."""
        try:
            names = self._all_names()
            rows = cfgmod.orphaned_profiles()
        except Exception:
            return []
        return [[a, names.get(a, a), c] for a, c in rows]

    @Slot(result=list)
    def historySummary(self) -> list:
        """Per-game session aggregates (newest first), for the history view."""
        try:
            names = self._all_names()
            stats = histmod.summarize(histmod.parse_log(xdg.log_file()))
        except Exception:
            return []
        rows = sorted(stats.values(), key=lambda s: s.last, reverse=True)
        out = []
        for s in rows[:500]:
            try:
                cfg = cfgmod.load(s.appid)
            except Exception:
                cfg = None
            out.append(
                {
                    "appid": s.appid,
                    "name": names.get(s.appid, s.appid),
                    "last": s.last.replace("T", " "),
                    "installed": self._row_installed(s.appid, cfg),
                    "runs": s.runs,
                    "total": format_duration(s.total_dur),
                    "fails": s.fails,
                }
            )
        return out

    @Slot(result=str)
    def openLudusavi(self) -> str:
        """Launch Ludusavi; returns '' or the warning/status message."""
        import subprocess

        exe = shutil.which("ludusavi")
        if not exe:
            return "Ludusavi Was Not Found in PATH."
        if "/flatpak/" in exe or "flatpak" in exe:
            return (
                "Flatpak Ludusavi Detected: It May Not See Proton Prefixes. "
                "Prefer the Standalone Binary."
            )
        try:
            subprocess.Popen([exe])
        except Exception as e:
            return f"Could Not Open Ludusavi: {e}"
        return ""

    @Slot(result=str)
    def logsDir(self) -> str:
        """Per-game logs folder path (created on demand)."""
        try:
            d = xdg.games_log_dir()
            d.mkdir(parents=True, exist_ok=True)
            return str(d)
        except Exception:
            return ""

    @Slot(result=str)
    def aboutText(self) -> str:
        """About body: versions, licenses, file locations."""
        import platform

        try:
            from PySide6 import __version__ as pyside_version
            from PySide6.QtCore import qVersion

            qt_version = qVersion()
        except Exception:
            pyside_version, qt_version = "unknown", "unknown"
        try:
            from importlib.metadata import version as _version

            vdf_version, jeepney_version = _version("vdf"), _version("jeepney")
        except Exception:
            vdf_version, jeepney_version = "unknown", "unknown"
        from .. import __version__

        lines = [
            f"TKArcade {__version__}",
            "Steam and Local Game Launch Wrapper. License: GPL-3.0-or-later.",
            "",
            f"Python {platform.python_version()} On {platform.system()}",
            f"PySide6 {pyside_version} (Qt {qt_version})",
            f"vdf {vdf_version} (MIT) · jeepney {jeepney_version} (MIT)",
            "",
            f"Config: {xdg.app_config_dir()}",
            f"Logs: {xdg.app_state_dir()}",
        ]
        return "\n".join(lines)

    def _issue_report(self, appid: str) -> list[tuple[str, str]]:
        if not hasattr(self, "_issues_cache"):
            self._issues_cache: dict[str, list[tuple[str, str]]] = {}
        if appid not in self._issues_cache:
            from ..launcher import validate_issues

            try:
                self._issues_cache[appid] = list(validate_issues(appid))
            except Exception as e:
                self._issues_cache[appid] = [("error", str(e))]
        return self._issues_cache[appid]

    def _issue_level(self, appid: str) -> str:
        levels = {severity for severity, _message in self._issue_report(appid)}
        if "error" in levels:
            return "error"
        return "warning" if "warning" in levels else ""

    def _issue_tip(self, appid: str) -> str:
        prefix = f"{appid}: "
        return "\n".join(
            f"{severity.capitalize()}: {message.removeprefix(prefix)}"
            for severity, message in self._issue_report(appid)
        )

    @Slot(str, result=list)
    def gameIssues(self, appid: str) -> list:
        """Cached validation issues (powers the issues-only filter)."""
        return [message for _severity, message in self._issue_report(appid)]

    @Slot(result="QVariantList")
    def ageRatingGroups(self) -> list:
        """Picker groups as [{name, ratings}], same source as the loader."""
        return [
            {
                "name": board,
                "ratings": list(ratings),
                "default": board in cfgmod.DEFAULT_AGE_RATING_BOARDS,
            }
            for board, ratings in sorted(cfgmod.AGE_RATING_GROUPS, key=lambda item: item[0].lower())
        ]

    @Slot(result=str)
    def symbolFontFamily(self) -> str:
        """First installed symbol font for the Unicode status glyphs."""
        global _SYMBOL_FONT_FAMILY
        if _SYMBOL_FONT_FAMILY is None:
            from PySide6.QtGui import QFontDatabase

            installed = set(QFontDatabase.families())
            _SYMBOL_FONT_FAMILY = next((name for name in SYMBOL_FONTS if name in installed), "")
        return _SYMBOL_FONT_FAMILY

    @Slot(result="QVariantMap")
    def loadPrefs(self) -> dict:
        """App preferences for the QML form."""
        try:
            prefs = cfgmod.load_preferences()
        except Exception:
            return {}
        return {
            "showPreview": bool(prefs.show_preview),
            "showDependencyStatus": bool(prefs.show_dependency_status),
            "showProfileBar": bool(prefs.show_profile_bar),
            "trayEnable": bool(prefs.tray_enable),
            "trayIcon": str(prefs.tray_icon),
            "minimizeToTray": bool(prefs.minimize_to_tray),
            "closeToTray": bool(prefs.close_to_tray),
            "trayQuickLaunch": bool(prefs.tray_quick_launch),
            "trayQuickCount": int(prefs.tray_quick_count),
            "sgdbApiKey": str(prefs.sgdb_api_key),
            "igdbClientId": str(prefs.igdb_client_id),
            "igdbClientSecret": str(prefs.igdb_client_secret),
            "artworkSource": str(prefs.artwork_source),
            "language": str(prefs.language),
            "prefixBase": str(prefs.prefix_base),
            "wineVersions": str(prefs.wine_versions),
            "wineDefault": str(prefs.wine_default),
            "protonDefault": str(prefs.proton_default),
            "dxvkDefault": str(prefs.dxvk_default),
            "vkd3dDefault": str(prefs.vkd3d_default),
            "dxvkSource": str(prefs.dxvk_source),
            "vkd3dSource": str(prefs.vkd3d_source),
            "downloadMirror": str(prefs.download_mirror),
        }

    @Slot("QVariantMap", result=bool)
    def savePrefs(self, values) -> bool:
        """Persist app preferences from the QML form."""
        try:
            prefs = cfgmod.load_preferences()
        except Exception:
            return False
        try:
            get = values.get if hasattr(values, "get") else lambda k, d=None: d
            prefs.show_preview = bool(get("showPreview", prefs.show_preview))
            prefs.show_dependency_status = bool(
                get("showDependencyStatus", prefs.show_dependency_status)
            )
            prefs.show_profile_bar = bool(get("showProfileBar", prefs.show_profile_bar))
            prefs.tray_enable = bool(get("trayEnable", prefs.tray_enable))
            prefs.tray_icon = str(get("trayIcon", prefs.tray_icon))
            prefs.minimize_to_tray = bool(get("minimizeToTray", prefs.minimize_to_tray))
            prefs.close_to_tray = bool(get("closeToTray", prefs.close_to_tray))
            prefs.tray_quick_launch = bool(get("trayQuickLaunch", prefs.tray_quick_launch))
            prefs.tray_quick_count = max(
                1, min(10, int(get("trayQuickCount", prefs.tray_quick_count)))
            )
            prefs.sgdb_api_key = str(get("sgdbApiKey", prefs.sgdb_api_key))
            prefs.igdb_client_id = str(get("igdbClientId", prefs.igdb_client_id)).strip()
            prefs.igdb_client_secret = str(
                get("igdbClientSecret", prefs.igdb_client_secret)
            ).strip()
            pref_source = str(get("artworkSource", prefs.artwork_source)).strip()
            prefs.artwork_source = cfgmod.normalize_artwork_provider(pref_source) or "steam"
            lang = str(get("language", prefs.language)).strip() or "system"
            prefs.language = lang
            prefs.prefix_base = str(get("prefixBase", prefs.prefix_base)).strip()
            prefs.wine_versions = cfgmod.clean_wine_versions(
                get("wineVersions", prefs.wine_versions)
            )
            prefs.wine_default = str(get("wineDefault", prefs.wine_default)).strip()
            prefs.proton_default = str(get("protonDefault", prefs.proton_default)).strip()
            prefs.dxvk_default = str(get("dxvkDefault", prefs.dxvk_default)).strip()
            prefs.vkd3d_default = str(get("vkd3dDefault", prefs.vkd3d_default)).strip()
            prefs.dxvk_source = str(get("dxvkSource", prefs.dxvk_source)).strip()
            prefs.vkd3d_source = str(get("vkd3dSource", prefs.vkd3d_source)).strip()
            prefs.download_mirror = cfgmod.clean_download_mirror(
                get("downloadMirror", prefs.download_mirror)
            )
            cfgmod.save_preferences(prefs)
        except Exception as e:
            log.warning("savePrefs failed: %s", e)
            return False
        refresher = self._tray_refresher
        if callable(refresher):
            try:
                self.setTrayActive(bool(refresher()))
            except Exception as e:
                log.warning("tray refresh failed: %s", e)
        return True

    @Slot(result=list)
    def audioSinks(self) -> list:
        """[[name, label]] output sinks for the audio picker."""
        from ..backends import audio as aubackend

        try:
            return [[n, desc or n] for n, desc in aubackend.list_sinks()]
        except Exception:
            return []

    @Slot(result=list)
    def languageOptions(self) -> list:
        """[[code, label]] languages for the prefs picker."""
        from . import i18n as i18nmod

        try:
            return [[code, label] for code, label in i18nmod.available_languages()]
        except Exception:
            return [["system", "System"], ["en", "English"]]

    @Slot(bool)
    def setTrayActive(self, active: bool) -> None:
        """Whether kirigami_app currently shows a tray icon."""
        self._tray_active = bool(active)

    @Slot(result=list)
    def trayRecentGames(self) -> list:
        """Recent launches for the tray menu as [appid, label] rows."""
        try:
            prefs = cfgmod.load_preferences()
        except Exception:
            return []
        if not prefs.tray_quick_launch:
            return []
        try:
            limit = max(0, int(prefs.tray_quick_count or 0))
        except (TypeError, ValueError):
            limit = 0
        out = []
        for row in (self.historySummary() or [])[:limit]:
            try:
                out.append([str(row["appid"]), f"{row['name']} ({row['total']})"])
            except (KeyError, TypeError):
                continue
        return out

    @Slot(result=bool)
    def trayDefaultsAvailable(self) -> bool:
        """Whether a Global Defaults entry was registered (tray menu)."""
        return "defaults" in self._tray_actions

    @Slot(str)
    def trayAction(self, name: str) -> None:
        """Run a tray entry: a registered action, or "play:<appid>"."""
        action = str(name or "")
        if action.startswith("play:"):
            self.play(action[len("play:") :])
            return
        handler = self._tray_actions.get(action)
        if handler is None:
            return
        try:
            handler()
        except Exception as e:
            log.warning("tray action %s failed: %s", action, e)

    @Slot(QObject)
    def watchQuitKeys(self, window) -> None:
        """Install the Ctrl+Q filter on a top-level window (best effort)."""
        try:
            if window is not None:
                window.installEventFilter(self._quit_filter)
        except Exception as e:
            log.warning("watchQuitKeys failed: %s", e)

    @Slot(QObject)
    def watchDialogKeys(self, window) -> None:
        """Ctrl+Q, Escape-to-cancel and Enter-to-accept on a dialog window.

        `watchQuitKeys` stays for the main window: Escape must never close
        the shell. This is for the separate dialog `Window`s, where Escape
        cancels like the widgets QDialog reject() and a close runs each
        dialog's own onClosing (settings, picker and pre-launch report
        their cancel outcome there). Enter is routed only while a popup of
        the window is open (the body's own Keys handler owns the rest).
        """
        try:
            if window is not None:
                window.installEventFilter(self._quit_filter)
                window.installEventFilter(self._dialog_key_filter)
        except Exception as e:
            log.warning("watchDialogKeys failed: %s", e)

    @Slot(QObject, list)
    def pressDefault(self, window, names) -> None:
        """Enter in a dialog: press the first visible, named button.

        The widgets QDialogs sent Enter to their default button. QML
        buttons ignore Enter, so each dialog body calls this from its
        `Keys.onReturnPressed` (a window `Shortcut` would steal the key
        from an editable TextArea, which has to keep it). `names` lists
        the dialog's default buttons in priority order; the first visible,
        enabled one fires — the settings window uses that to make
        Save & Launch the default in launch mode, while a combo page keeps
        Enter on its own Import.
        """
        try:
            for name in names or ():
                candidate = window.findChild(QObject, str(name))
                if candidate is None:
                    continue
                if candidate.property("visible") and candidate.property("enabled"):
                    QMetaObject.invokeMethod(candidate, "clicked")
                    return
        except Exception as e:
            log.warning("pressDefault failed: %s", e)

    @Slot(result=bool)
    def hideOnClose(self) -> bool:
        """Close-to-tray: hide instead of closing when a tray is up."""
        try:
            return bool(cfgmod.load_preferences().close_to_tray) and self._tray_active
        except Exception:
            return False

    @Slot(result=bool)
    def hideOnMinimize(self) -> bool:
        """Minimize-to-tray: hide when minimized while a tray is up."""
        try:
            return bool(cfgmod.load_preferences().minimize_to_tray) and self._tray_active
        except Exception:
            return False

    @Slot(result=str)
    def drawerMode(self) -> str:
        """Persisted Kirigami drawer mode (overlay|collapsible)."""
        try:
            return cfgmod.load_preferences().drawer_mode
        except Exception:
            return "collapsible"

    @Slot(str)
    def saveDrawerMode(self, mode: str) -> None:
        """Persist the drawer mode (best effort, never raises)."""
        try:
            prefs = cfgmod.load_preferences()
        except Exception:
            prefs = cfgmod.Preferences()
        prefs.drawer_mode = mode if mode in ("overlay", "collapsible") else "collapsible"
        try:
            cfgmod.save_preferences(prefs)
        except Exception as e:
            log.warning("saveDrawerMode failed: %s", e)

    @Slot(result=bool)
    def drawerCollapsed(self) -> bool:
        """Persisted collapsible-drawer state (open by default is False)."""
        try:
            return bool(cfgmod.load_preferences().drawer_collapsed)
        except Exception:
            return True

    @Slot(bool)
    def saveDrawerCollapsed(self, collapsed: bool) -> None:
        """Persist the collapsible-drawer state (best effort)."""
        try:
            prefs = cfgmod.load_preferences()
        except Exception:
            prefs = cfgmod.Preferences()
        prefs.drawer_collapsed = bool(collapsed)
        try:
            cfgmod.save_preferences(prefs)
        except Exception as e:
            log.warning("saveDrawerCollapsed failed: %s", e)

    @Slot(str, result=bool)
    def play(self, appid: str) -> bool:
        """Play routing: Steam ids via the client, local ids direct."""
        kind = "steam" if steammod.is_steam_id(appid) else "local"
        try:
            if kind == "steam":
                numeric = steammod.steam_appid(appid)
                if not numeric:
                    log.warning("play refused: not a Steam App ID: %s", appid)
                    self.launchReported.emit(False, kind, self._display_name(appid), "")
                    return False
                from PySide6.QtCore import QUrl
                from PySide6.QtGui import QDesktopServices

                launchermod.plant_menu_skip(appid)
                ok = bool(QDesktopServices.openUrl(QUrl(f"steam://rungameid/{numeric}")))
                if not ok:
                    launchermod.consume_menu_skip(appid)
                    self.launchReported.emit(False, kind, self._display_name(appid), "")
                return ok
            launchermod.launch_local_detached(appid)
            # Steam handoffs report nothing: the client owns the launch.
            self.launchReported.emit(True, kind, self._display_name(appid), "")
            return True
        except Exception as e:  # never crash the list on a launch failure
            log.warning("play(%s) failed: %s", appid, e)
            self.launchReported.emit(False, kind, self._display_name(appid), str(e))
            return False

    def _display_name(self, appid: str) -> str:
        """Name for status messages: the loaded row, else the AppID."""
        for row in self._rows:
            if row[0] == appid:
                return str(row[1])
        return str(appid or "")


class GameFilterModel(QSortFilterProxyModel):
    """Source + text filter over a GameListModel (drawer + search drive it).

    Also a real table model for QtQuick TableView: fixed logical columns
    [#, name, appid, played, tier, source] with order/visibility owned
    here (persisted to the same prefs keys). Custom roles stay
    row-based (column-independent), so delegates keep working.
    """

    sourceChanged = Signal()
    textChanged = Signal()
    issuesChanged = Signal()

    TABLE_COLUMNS = (
        "#",
        "gameName",
        "gameId",
        "gamePlayed",
        "gameTier",
        "gameOrigin",
        "gameLastPlayed",
        "gamePlatform",
        "gameRuntime",
        "gameWine",
        "gameInstallDir",
        "gameReleaseDate",
        "gameInstalledAt",
    )
    COLUMN_TITLES = {
        "#": "#",
        "gameName": "Game",
        "gameId": "Game ID",
        "gamePlayed": "Played",
        "gameTier": "ProtonDB",
        "gameOrigin": "Origin",
        "gameLastPlayed": "Last Played",
        "gamePlatform": "Platform",
        "gameRuntime": "Runtime",
        "gameWine": "Wine",
        "gameInstallDir": "Install Dir",
        "gameReleaseDate": "Release Date",
        "gameInstalledAt": "Installed",
    }

    #: Default view order: Release Date, Origin, Platform, Played, Last
    #: Played and Installed show after the game name; the rest hide.
    _DEFAULT_ORDER = (0, 1, 11, 5, 7, 3, 6, 12, 8, 9, 4, 2, 10)
    _DEFAULT_HIDDEN = frozenset({2, 4, 8, 9, 10})

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._source = "all"
        self._category = ""
        self._text = ""
        self._issues = False
        self._order, self._hidden = self._load_columns()
        self._widths = self._load_widths()
        self._sort_role = "gameName"
        self._sort_role_id = GameListModel.NameRole
        self._sort_descending = False

    @staticmethod
    def _load_columns() -> tuple[list[int], set[int]]:
        """Column order + hidden set from prefs (garbage means defaults)."""
        prefs = cfgmod.load_preferences()
        try:
            version = int(prefs.column_layout_version or 0)
        except (TypeError, ValueError):
            version = 0
        if version < cfgmod.COLUMN_LAYOUT_VERSION:
            # One-time reset to the current defaults; fitted widths
            # survive because they stay keyed by logical column.
            order = list(GameFilterModel._DEFAULT_ORDER)
            hidden = set(GameFilterModel._DEFAULT_HIDDEN)
            prefs.column_order = ",".join(map(str, order))
            prefs.hidden_columns = ",".join(map(str, sorted(hidden)))
            prefs.column_layout_version = cfgmod.COLUMN_LAYOUT_VERSION
            try:
                cfgmod.save_preferences(prefs)
            except OSError:
                pass
            return order, hidden
        try:
            order = [int(x) for x in prefs.column_order.split(",")]
        except Exception:
            order = []
        try:
            hidden = {int(x) for x in prefs.hidden_columns.split(",")}
        except Exception:
            hidden = set()
        if sorted(order) != list(range(13)):
            order = list(GameFilterModel._DEFAULT_ORDER)
            hidden = set(GameFilterModel._DEFAULT_HIDDEN)
        return order, {h for h in hidden if 1 <= h <= 12}

    def _view_columns(self) -> list[int]:
        """Logical columns in view order (hidden stay mapped, QML widths them 0)."""
        return list(self._order)

    @staticmethod
    def _load_widths() -> dict[int, int]:
        """Fitted column widths from prefs (garbage means no overrides)."""
        try:
            raw = cfgmod.load_preferences().column_widths
        except Exception:
            return {}
        return cfgmod.parse_width_map(raw)

    def _save_columns(self) -> None:
        try:
            prefs = cfgmod.load_preferences()
        except Exception:
            return
        prefs.column_order = ",".join(map(str, self._order))
        prefs.hidden_columns = ",".join(map(str, sorted(self._hidden)))
        prefs.column_widths = ",".join(f"{k}={v}" for k, v in sorted(self._widths.items()))
        prefs.column_layout_version = cfgmod.COLUMN_LAYOUT_VERSION
        try:
            cfgmod.save_preferences(prefs)
        except OSError:
            pass

    def columnCount(self, parent: QModelIndex | None = None) -> int:
        if parent is not None and parent.isValid():
            return 0
        return len(self.TABLE_COLUMNS)

    @Slot(int, result=int)
    def columnLogical(self, section: int) -> int:
        """Logical column at a view position (-1 when out of range)."""
        order = self._view_columns()
        return order[section] if 0 <= section < len(order) else -1

    @Slot(result=str)
    def columnOrderJson(self) -> str:
        """View column order as JSON (QML parses to a fresh JS array).

        A Property(list) would arrive as QVariantList, which lays out
        at zero width on Qt 6.11 — never feed Repeaters from Python.
        """
        import json

        return json.dumps(list(self._order))

    @Slot(result=str)
    def columnWidthsJson(self) -> str:
        """Fitted widths as JSON ({logical: px}); empty object by default.

        Fresh JS object per call (same QVariantList rule as the order).
        """
        import json

        return json.dumps({str(k): v for k, v in sorted(self._widths.items())})

    @Slot(int, result=int)
    def columnWidth(self, logical: int) -> int:
        """Fitted width for a logical column (0 means default sizing)."""
        try:
            return int(self._widths.get(int(logical), 0))
        except (TypeError, ValueError):
            return 0

    @Slot(int, int)
    def setColumnWidth(self, logical: int, width: int) -> None:
        """Store a width without saving (drag preview; save on release)."""
        try:
            logical, width = int(logical), int(width)
        except (TypeError, ValueError):
            return
        if not 1 <= logical <= 12 or not 20 <= width <= 2000:
            return
        if self._widths.get(logical) != width:
            self._widths[logical] = width
            self.widthsChanged.emit()

    @Slot()
    def saveColumnWidths(self) -> None:
        """Persist the current widths (drag release)."""
        self._save_columns()

    #: Fresh/reset default: fit every column, capped so one monster
    #: cell cannot eat the table.
    DEFAULT_FIT_MAX = 300

    def _measure_column(self, logical: int) -> int:
        """Content width (rows + title/glyph/icon), unclamped, 0 on error."""
        try:
            from PySide6.QtGui import QFontMetrics, QGuiApplication

            metrics = QFontMetrics(QGuiApplication.font())
        except Exception:
            return 0
        order = self._view_columns()
        try:
            section = order.index(int(logical))
        except ValueError:
            return 0
        widest = 0
        rows = self.rowCount()
        for row in range(rows):
            text = self.data(self.index(row, section))
            if text:
                widest = max(widest, metrics.horizontalAdvance(str(text)))
        title = self.COLUMN_TITLES.get(self.TABLE_COLUMNS[logical], "")
        if title:
            # Title plus the sort glyph room: a fitted sort column must
            # never print under its own triangle.
            glyph = metrics.horizontalAdvance("▲")
            widest = max(widest, metrics.horizontalAdvance(title) + glyph + 8)
        if logical == 1:
            # Game cells lead with a 32px icon plus row margins.
            widest += 48
        return widest + 24

    @Slot(int, result=int)
    def autofitColumn(self, logical: int) -> int:
        """Fit a column to its contents (header + every row), persist it.

        Measures the exact DisplayRole strings the delegates show, so no
        delegate instantiation (the view virtualizes rows). Returns the
        stored width.
        """
        try:
            logical = int(logical)
        except (TypeError, ValueError):
            return 0
        if not 0 <= logical <= 12:
            return 0
        measured = self._measure_column(logical)
        if not measured:
            return self.columnWidth(logical)
        width = min(1200, max(40, measured))
        self._widths[logical] = width
        self._save_columns()
        self.widthsChanged.emit()
        return width

    @Slot()
    def fitDefaults(self) -> None:
        """Fit visible content columns capped: fresh starts and resets."""
        for logical in range(1, 13):
            measured = self._measure_column(logical)
            if measured:
                self._widths[logical] = min(max(40, measured), self.DEFAULT_FIT_MAX)
        self._save_columns()
        self.widthsChanged.emit()

    def data(self, index: QModelIndex, role: int = Qt.ItemDataRole.DisplayRole):
        # Presentation permutation only: view column c shows logical
        # _order[c]; rows/filters/sorts stay base-mapped, so no
        # index/map overrides exist (hand-made indexes segfault).
        if not index.isValid():
            return None
        order = self._view_columns()
        if not (0 <= index.row() < self.rowCount() and 0 <= index.column() < len(order)):
            return None
        if role == Qt.ItemDataRole.DisplayRole:
            logical = order[index.column()]
            if logical == 0:
                return str(index.row() + 1)
            model = self.sourceModel()
            sidx = super().mapToSource(index)
            if model is None or not sidx.isValid():
                return None
            roles = {
                1: GameListModel.NameRole,
                2: GameListModel.IdRole,
                3: GameListModel.PlayedRole,
                4: GameListModel.TierRole,
                5: GameListModel.OriginRole,
                6: GameListModel.LastPlayedRole,
                7: GameListModel.PlatformRole,
                8: GameListModel.RuntimeRole,
                9: GameListModel.WineRole,
                10: GameListModel.InstallDirRole,
                11: GameListModel.ReleaseDateRole,
                12: GameListModel.InstalledAtRole,
            }
            return str(model.data(sidx, roles[logical]) or "")
        return super().data(index, role)

    def headerData(self, section: int, orientation: Qt.Orientation, role: int = 0):
        if orientation == Qt.Orientation.Horizontal and role in (
            Qt.ItemDataRole.DisplayRole,
            0,
        ):
            order = self._view_columns()
            if 0 <= section < len(order):
                return self.COLUMN_TITLES[self.TABLE_COLUMNS[order[section]]]
        return None

    @Slot(int, int)
    def moveColumn(self, logical: int, direction: int) -> None:
        """Swap a logical column with its neighbour (-1 left, +1 right)."""
        order = list(self._order)
        if logical not in order:
            return
        pos, swap = order.index(logical), order.index(logical) + int(direction)
        if not 0 <= swap < len(order):
            return
        order[pos], order[swap] = order[swap], order[pos]
        self._order = order
        self._save_columns()
        self.layoutChanged.emit()
        self.columnsChanged.emit()

    @Slot()
    def resetColumns(self) -> None:
        """Default order and visibility, columns fitted capped."""
        self._order = list(self._DEFAULT_ORDER)
        self._hidden = set(self._DEFAULT_HIDDEN)
        self._widths = {}
        self._save_columns()
        self.layoutChanged.emit()
        self.columnsChanged.emit()
        self.fitDefaults()

    def _get_source(self) -> str:
        return self._source

    def _set_source(self, key: str) -> None:
        key = key if key in ("all", "steam", "local") else "all"
        if key != self._source:
            self._source = key
            self.invalidate()
            self.sourceChanged.emit()

    sourceKey = Property(str, _get_source, _set_source, notify=sourceChanged)

    def _get_category(self) -> str:
        return self._category

    def _set_category(self, key: str) -> None:
        key = str(key or "")
        if key != self._category:
            self._category = key
            self.invalidate()
            self.sourceChanged.emit()

    categoryKey = Property(str, _get_category, _set_category, notify=sourceChanged)

    def _get_text(self) -> str:
        return self._text

    def _set_text(self, query: str) -> None:
        query = query or ""
        if query != self._text:
            self._text = query
            self.invalidate()
            self.textChanged.emit()

    textQuery = Property(str, _get_text, _set_text, notify=textChanged)

    def _get_issues(self) -> bool:
        return self._issues

    def _set_issues(self, value: bool) -> None:
        value = bool(value)
        if value != self._issues:
            self._issues = value
            self.invalidate()
            self.issuesChanged.emit()

    issuesOnly = Property(bool, _get_issues, _set_issues, notify=issuesChanged)

    columnsChanged = Signal()
    widthsChanged = Signal()

    _FLAG_COLUMNS = {
        "showAppId": 2,
        "showPlayed": 3,
        "showTier": 4,
        "showOrigin": 5,
        "showLastPlayed": 6,
        "showPlatform": 7,
        "showRuntime": 8,
        "showWine": 9,
        "showInstallDir": 10,
        "showReleaseDate": 11,
        "showInstalled": 12,
    }

    def _get_flag(self, name: str) -> bool:
        return self._FLAG_COLUMNS[name] not in self._hidden

    def _set_flag(self, name: str, value: bool) -> None:
        logical = self._FLAG_COLUMNS[name]
        value = bool(value)
        if (logical in self._hidden) == (not value):
            return
        if value:
            self._hidden.discard(logical)
        else:
            self._hidden.add(logical)
        self._save_columns()
        self.layoutChanged.emit()
        self.columnsChanged.emit()

    def _get_showAppId(self) -> bool:
        return self._get_flag("showAppId")

    def _set_showAppId(self, value: bool) -> None:
        self._set_flag("showAppId", value)

    def _get_showPlayed(self) -> bool:
        return self._get_flag("showPlayed")

    def _set_showPlayed(self, value: bool) -> None:
        self._set_flag("showPlayed", value)

    def _get_showTier(self) -> bool:
        return self._get_flag("showTier")

    def _set_showTier(self, value: bool) -> None:
        self._set_flag("showTier", value)

    def _get_showOrigin(self) -> bool:
        return self._get_flag("showOrigin")

    def _set_showOrigin(self, value: bool) -> None:
        self._set_flag("showOrigin", value)

    def _get_showLastPlayed(self) -> bool:
        return self._get_flag("showLastPlayed")

    def _set_showLastPlayed(self, value: bool) -> None:
        self._set_flag("showLastPlayed", value)

    def _get_showPlatform(self) -> bool:
        return self._get_flag("showPlatform")

    def _set_showPlatform(self, value: bool) -> None:
        self._set_flag("showPlatform", value)

    def _get_showRuntime(self) -> bool:
        return self._get_flag("showRuntime")

    def _set_showRuntime(self, value: bool) -> None:
        self._set_flag("showRuntime", value)

    def _get_showWine(self) -> bool:
        return self._get_flag("showWine")

    def _set_showWine(self, value: bool) -> None:
        self._set_flag("showWine", value)

    def _get_showInstallDir(self) -> bool:
        return self._get_flag("showInstallDir")

    def _set_showInstallDir(self, value: bool) -> None:
        self._set_flag("showInstallDir", value)

    def _get_showReleaseDate(self) -> bool:
        return self._get_flag("showReleaseDate")

    def _set_showReleaseDate(self, value: bool) -> None:
        self._set_flag("showReleaseDate", value)

    def _get_showInstalled(self) -> bool:
        return self._get_flag("showInstalled")

    def _set_showInstalled(self, value: bool) -> None:
        self._set_flag("showInstalled", value)

    showAppId = Property(bool, _get_showAppId, _set_showAppId, notify=columnsChanged)
    showPlayed = Property(bool, _get_showPlayed, _set_showPlayed, notify=columnsChanged)
    showTier = Property(bool, _get_showTier, _set_showTier, notify=columnsChanged)
    showOrigin = Property(bool, _get_showOrigin, _set_showOrigin, notify=columnsChanged)
    showLastPlayed = Property(bool, _get_showLastPlayed, _set_showLastPlayed, notify=columnsChanged)
    showPlatform = Property(bool, _get_showPlatform, _set_showPlatform, notify=columnsChanged)
    showRuntime = Property(bool, _get_showRuntime, _set_showRuntime, notify=columnsChanged)
    showWine = Property(bool, _get_showWine, _set_showWine, notify=columnsChanged)
    showInstallDir = Property(bool, _get_showInstallDir, _set_showInstallDir, notify=columnsChanged)
    showReleaseDate = Property(
        bool, _get_showReleaseDate, _set_showReleaseDate, notify=columnsChanged
    )
    showInstalled = Property(bool, _get_showInstalled, _set_showInstalled, notify=columnsChanged)

    @Slot(int, result="QVariantMap")
    def rowData(self, row: int) -> dict:
        """Display roles for one proxy row (QML table delegates)."""
        model = self.sourceModel()
        if model is None or not 0 <= row < self.rowCount():
            return {}
        try:
            source_row = self.mapToSource(self.index(row, 0)).row()
        except Exception:
            return {}
        try:
            return dict(model.rowData(source_row))
        except Exception:
            return {}

    @Slot(int, result="QModelIndex")
    def proxyIndex(self, row: int):
        """Index for a proxy row (QML-callable; index() defaults misfire)."""
        if 0 <= row < self.rowCount():
            return self.index(row, 0)
        return QModelIndex()

    @Slot(str, result=int)
    def indexOf(self, appid: str) -> int:
        """Proxy row for an AppID (-1 when filtered out). Drives selection."""
        for row in range(self.rowCount()):
            if str(self.data(self.index(row, 0), GameListModel.IdRole) or "") == appid:
                return row
        return -1

    @Slot(int, result=str)
    def idAt(self, row: int) -> str:
        """AppID at a proxy row ('' out of range). Keeps highlight on keys."""
        if 0 <= row < self.rowCount():
            return str(self.data(self.index(row, 0), GameListModel.IdRole) or "")
        return ""

    @Slot(str, bool)
    def sortBy(self, roleName: str, descending: bool) -> None:
        """Sort by a role name (header clicks); numeric-aware."""
        self._sort_role = roleName if roleName in GameListModel.ROLE_NAMES else "gameName"
        model = self.sourceModel()
        ids = (
            {bytes(v).decode(): k for k, v in model.roleNames().items()}
            if model is not None
            else {}
        )
        self._sort_role_id = ids.get(self._sort_role, GameListModel.NameRole)
        self._sort_descending = bool(descending)
        self.sort(
            0,
            Qt.SortOrder.DescendingOrder if descending else Qt.SortOrder.AscendingOrder,
        )

    def lessThan(self, left: QModelIndex, right: QModelIndex) -> bool:
        model = self.sourceModel()
        if model is None:
            return False
        role = self._sort_role_id
        lang = str(model.data(left, role) or "")
        rang = str(model.data(right, role) or "")
        try:
            return float(lang) < float(rang)
        except (TypeError, ValueError):
            return lang.lower() < rang.lower()

    def filterAcceptsRow(self, source_row: int, source_parent: QModelIndex) -> bool:
        model = self.sourceModel()
        if model is None:
            return False
        index = model.index(source_row, 0, source_parent)
        appid = model.data(index, GameListModel.IdRole) or ""
        return (
            self._accepts_source(appid)
            and self._accepts_text(model, index, appid)
            and self._accepts_issues(model, appid)
            and self._accepts_category(model, index)
        )

    def _accepts_source(self, appid) -> bool:
        if self._source == "all":
            return True
        return steammod.origin(str(appid)) == self._source

    def _accepts_text(self, model, index, appid) -> bool:
        if not self._text:
            return True
        query = self._text.lower()
        name = str(model.data(index, GameListModel.NameRole) or "").lower()
        return query in name or query in str(appid).lower()

    def _accepts_issues(self, model, appid) -> bool:
        if not self._issues:
            return True
        try:
            return bool(model.gameIssues(str(appid)))
        except Exception:
            return False

    def _accepts_category(self, model, index) -> bool:
        if not self._category:
            return True
        cats = str(model.data(index, GameListModel.CategoryRole) or "")
        return self._category.lower() in [c.strip().lower() for c in cats.split(",")]
