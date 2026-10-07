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

from .. import artwork as artmod
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
    IconRole = Qt.ItemDataRole.UserRole + 8
    PlayedSecsRole = Qt.ItemDataRole.UserRole + 9
    PlayedTipRole = Qt.ItemDataRole.UserRole + 10

    ROLE_NAMES = (
        "gameId",
        "gameName",
        "gameSource",
        "gamePlayed",
        "gameTier",
        "gameTierBg",
        "gameTierFg",
        "gameIcon",
        "gamePlayedSecs",
        "gamePlayedTip",
    )

    refreshed = Signal()
    browseFinished = Signal(str)

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._rows: list[tuple[str, ...]] = []
        self._steam_detected = 0
        self.backgroundDone.connect(self.refresh)
        self.refresh()

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
            GameListModel.SourceRole: b"gameSource",
            GameListModel.PlayedRole: b"gamePlayed",
            GameListModel.TierRole: b"gameTier",
            GameListModel.TierBgRole: b"gameTierBg",
            GameListModel.TierFgRole: b"gameTierFg",
            GameListModel.IconRole: b"gameIcon",
            GameListModel.PlayedSecsRole: b"gamePlayedSecs",
            GameListModel.PlayedTipRole: b"gamePlayedTip",
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
            GameListModel.IconRole: 7,
            GameListModel.PlayedSecsRole: 8,
            GameListModel.PlayedTipRole: 9,
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
            played_secs = st.total_dur if st is not None else -1
            if st is None:
                played_tip = "No recorded sessions"
            else:
                last = st.last.replace("T", " ")
                played_tip = f"{st.runs} sessions · last {last} · {st.fails} failures"
            icon = artmod.resolve_icon(appid)
            data, _fresh = pdbmod.cached(appid)
            tier = str(((data or {}).get("tier", "")) or "").lower()
            bg, fg = pdbmod.TIER_STYLE.get(tier, ("", ""))
            rows.append(
                (
                    appid,
                    names.get(appid, appid),
                    source,
                    played,
                    tier.title(),
                    bg,
                    fg,
                    str(icon) if icon else "",
                    played_secs,
                    played_tip,
                )
            )
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
    def openProtonDB(self, appid: str) -> bool:
        """Open the ProtonDB page for a Steam game in the browser."""
        try:
            if not steammod.is_steam_id(appid) or not appid.isdigit():
                return False
            from PySide6.QtCore import QUrl
            from PySide6.QtGui import QDesktopServices

            return bool(QDesktopServices.openUrl(QUrl(pdbmod.GAME_URL.format(appid=appid))))
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
            return "Clipboard unavailable on this platform."
        clipboard.setText(text)
        return f"Copied to clipboard: {text}"

    @Slot(str, result=str)
    def installDir(self, appid: str) -> str:
        """Install folder path, or '' when unknown."""
        try:
            target = steammod.install_dir(appid)
        except Exception:
            target = None
        return str(target) if target is not None else ""

    @Slot(str, result=str)
    def prefixDir(self, appid: str) -> str:
        """Proton prefix path, or '' when unknown."""
        try:
            target = steammod.prefix_dir(appid)
        except Exception:
            target = None
        return str(target) if target is not None else ""

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
        """Human shader cache size, or '' when unknown."""
        try:
            target = steammod.shader_dir(appid)
        except Exception:
            return ""
        if target is None:
            return ""
        try:
            return steammod.format_size(steammod.dir_size(target))
        except Exception:
            return ""

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
        return f"Cleared {size} of shader cache."

    @Slot(str, result=list)
    def validateGame(self, appid: str) -> list:
        """Validation issues for one game (same checks as --validate)."""
        from ..launcher import validate_game

        try:
            return list(validate_game(appid))
        except Exception as e:
            return [str(e)]

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

    @Slot(list, result=list)
    def gameNames(self, appids: list) -> list:
        """Display names for AppIDs (dialog labels)."""
        names = {a: n for a, n in steammod.list_games()}
        names.update(steammod.local_names())
        return [names.get(str(a), str(a)) for a in appids]

    @Slot(list, result=str)
    def removeGames(self, appids: list) -> str:
        """Delete configs; returns '' or joined errors. Refreshes the list."""
        errors = []
        for appid in [str(a) for a in appids]:
            try:
                cfgmod.game_file(appid).unlink(missing_ok=True)
            except Exception as e:
                errors.append(f"{appid}: {e}")
        self.refresh()
        return "\n".join(errors)

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

    backgroundDone = Signal()

    @Slot()
    def fetchMissing(self) -> None:
        """Refresh stale ProtonDB tiers and missing artwork off-thread.

        Only explicit UI entry calls this (never refresh() itself), so
        headless tests stay offline. Emits backgroundDone -> refresh.
        """
        if os.environ.get("TKARCADE_NO_BG_FETCH"):
            return
        threading.Thread(target=self._fetch_worker, daemon=True).start()

    def _fetch_worker(self) -> None:
        try:
            api_key = cfgmod.load_preferences().sgdb_api_key.strip()
        except Exception:
            api_key = ""
        for appid in cfgmod.list_appids():
            if not steammod.is_steam_id(str(appid)):
                continue
            try:
                data, fresh = pdbmod.cached(appid)
            except Exception:
                continue
            if not fresh:
                try:
                    pdbmod.refresh(appid)
                except Exception:
                    continue
            if api_key and artmod.resolve_icon(appid) is None:
                try:
                    artmod.fetch_missing(appid, api_key)
                except Exception:
                    continue
        try:
            self.backgroundDone.emit()
        except Exception:
            pass

    @Slot(result=list)
    def scanCandidates(self) -> list:
        """Unconfigured Steam games as [appid, name] pairs."""
        try:
            configured = set(cfgmod.list_appids())
            cands = steammod.unconfigured_games(configured)
        except Exception:
            return []
        return [[str(a), str(n)] for a, n in cands]

    @Slot(list, result=int)
    def addScanned(self, appids: list) -> int:
        """Batch-add Steam games from the defaults template."""
        added = 0
        for appid in [str(a) for a in appids]:
            try:
                if cfgmod.game_file(appid).exists():
                    continue
                cfg = cfgmod.load_defaults()
                cfg.general.appid = appid
                cfgmod.save(cfg)
                added += 1
            except Exception as e:
                log.warning("addScanned(%s) failed: %s", appid, e)
        self.refresh()
        return added

    @Slot(result=list)
    def orphanedProfiles(self) -> list:
        """Orphaned profiles as [appid, name, count] rows."""
        try:
            names = {a: n for a, n in steammod.list_games()}
            names.update(steammod.local_names())
            rows = cfgmod.orphaned_profiles()
        except Exception:
            return []
        return [[a, names.get(a, a), c] for a, c in rows]

    @Slot(result=list)
    def historySummary(self) -> list:
        """Per-game session aggregates (newest first), for the history view."""
        try:
            names = {a: n for a, n in steammod.list_games()}
            names.update(steammod.local_names())
            stats = histmod.summarize(histmod.parse_log(xdg.log_file()))
        except Exception:
            return []
        rows = sorted(stats.values(), key=lambda s: s.last, reverse=True)
        return [
            {
                "appid": s.appid,
                "name": names.get(s.appid, s.appid),
                "last": s.last.replace("T", " "),
                "runs": s.runs,
                "total": format_duration(s.total_dur),
                "fails": s.fails,
            }
            for s in rows[:500]
        ]

    @Slot(result=str)
    def openLudusavi(self) -> str:
        """Launch Ludusavi; returns '' or the warning/status message."""
        import subprocess

        exe = shutil.which("ludusavi")
        if not exe:
            return "Ludusavi was not found in PATH."
        if "/flatpak/" in exe or "flatpak" in exe:
            return (
                "Flatpak Ludusavi detected: it may not see Proton prefixes. "
                "Prefer the standalone binary."
            )
        try:
            subprocess.Popen([exe])
        except Exception as e:
            return f"Could not open Ludusavi: {e}"
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
            "Minimal Steam launch wrapper. License: GPL-3.0-or-later.",
            "",
            f"Python {platform.python_version()} on {platform.system()}",
            f"PySide6 {pyside_version} (Qt {qt_version})",
            f"vdf {vdf_version} (MIT) · jeepney {jeepney_version} (MIT)",
            "",
            f"Config: {xdg.app_config_dir()}",
            f"Logs: {xdg.app_state_dir()}",
        ]
        return "\n".join(lines)

    @Slot(str, result=list)
    def gameIssues(self, appid: str) -> list:
        """Cached validation issues (powers the issues-only filter)."""
        if not hasattr(self, "_issues_cache"):
            self._issues_cache: dict[str, list[str]] = {}
        if appid not in self._issues_cache:
            self._issues_cache[appid] = list(self.validateGame(appid))
        return self._issues_cache[appid]

    @Slot(result="QVariantMap")
    def loadPrefs(self) -> dict:
        """App preferences for the QML form."""
        try:
            prefs = cfgmod.load_preferences()
        except Exception:
            return {}
        return {
            "showPreview": bool(prefs.show_preview),
            "trayEnable": bool(prefs.tray_enable),
            "trayIcon": str(prefs.tray_icon),
            "minimizeToTray": bool(prefs.minimize_to_tray),
            "closeToTray": bool(prefs.close_to_tray),
            "trayQuickLaunch": bool(prefs.tray_quick_launch),
            "trayQuickCount": int(prefs.tray_quick_count),
            "sgdbApiKey": str(prefs.sgdb_api_key),
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
            prefs.tray_enable = bool(get("trayEnable", prefs.tray_enable))
            prefs.tray_icon = str(get("trayIcon", prefs.tray_icon))
            prefs.minimize_to_tray = bool(get("minimizeToTray", prefs.minimize_to_tray))
            prefs.close_to_tray = bool(get("closeToTray", prefs.close_to_tray))
            prefs.tray_quick_launch = bool(get("trayQuickLaunch", prefs.tray_quick_launch))
            prefs.tray_quick_count = max(
                1, min(10, int(get("trayQuickCount", prefs.tray_quick_count)))
            )
            prefs.sgdb_api_key = str(get("sgdbApiKey", prefs.sgdb_api_key))
            cfgmod.save_preferences(prefs)
        except Exception as e:
            log.warning("savePrefs failed: %s", e)
            return False
        return True

    @Slot(str, result=bool)
    def play(self, appid: str) -> bool:
        """Play routing: Steam ids via the client, local ids direct."""
        try:
            if steammod.is_steam_id(appid):
                if not appid.isdigit():
                    log.warning("play refused: not a Steam App ID: %s", appid)
                    return False
                from PySide6.QtCore import QUrl
                from PySide6.QtGui import QDesktopServices

                launchermod.plant_menu_skip(appid)
                ok = bool(QDesktopServices.openUrl(QUrl(f"steam://rungameid/{appid}")))
                if not ok:
                    launchermod.consume_menu_skip(appid)
                return ok
            launchermod.launch_local_detached(appid)
            return True
        except Exception as e:  # never crash the list on a launch failure
            log.warning("play(%s) failed: %s", appid, e)
            return False


class GameFilterModel(QSortFilterProxyModel):
    """Source + text filter over a GameListModel (drawer + search drive it)."""

    sourceChanged = Signal()
    textChanged = Signal()
    issuesChanged = Signal()

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._source = "all"
        self._text = ""
        self._issues = False
        self._flags: dict[str, bool] = {}
        self._sort_role = "gameName"
        self._sort_role_id = GameListModel.NameRole
        self._sort_descending = False

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

    def _get_flag(self, name: str) -> bool:
        return bool(self._flags.get(name, True))

    def _set_flag(self, name: str, value: bool) -> None:
        value = bool(value)
        if self._flags.get(name, True) != value:
            self._flags[name] = value
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

    def _get_showSource(self) -> bool:
        return self._get_flag("showSource")

    def _set_showSource(self, value: bool) -> None:
        self._set_flag("showSource", value)

    showAppId = Property(bool, _get_showAppId, _set_showAppId, notify=columnsChanged)
    showPlayed = Property(bool, _get_showPlayed, _set_showPlayed, notify=columnsChanged)
    showTier = Property(bool, _get_showTier, _set_showTier, notify=columnsChanged)
    showSource = Property(bool, _get_showSource, _set_showSource, notify=columnsChanged)

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
        if self._source != "all":
            want_steam = self._source == "steam"
            if steammod.is_steam_id(str(appid)) != want_steam:
                return False
        if self._text:
            query = self._text.lower()
            name = str(model.data(index, GameListModel.NameRole) or "").lower()
            if query not in name and query not in str(appid).lower():
                return False
        if self._issues:
            try:
                issues = model.gameIssues(str(appid))
            except Exception:
                issues = []
            if not issues:
                return False
        return True
