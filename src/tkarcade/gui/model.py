"""QML game list model: stdlib core underneath, QtCore only on top."""

from __future__ import annotations

import logging
import os
import shlex
import shutil
import threading

from PySide6.QtCore import (
    Property,
    QAbstractTableModel,
    QEvent,
    QModelIndex,
    QObject,
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


def _split_args(text: str) -> list[str]:
    """Shell-like split for the args fields (falls back to whitespace)."""
    try:
        return shlex.split(text)
    except ValueError:
        return text.split()


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


class GameListModel(QAbstractTableModel):
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
    displayModesFinished = Signal("QVariantList")
    coverageFinished = Signal(str, str)

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
        self._quit_filter = _QuitFilter()
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

    def columnCount(self, parent: QModelIndex | None = None) -> int:
        # Fixed logical columns (proxy permutes/hides them for the view).
        return 0 if (parent is not None and parent.isValid()) else 6

    def index(self, row: int, column: int, parent: QModelIndex | None = None):
        # Table models own their indexes (unlike proxy mapping, this is safe).
        if parent is not None and parent.isValid():
            return QModelIndex()
        if 0 <= row < len(self._rows) and 0 <= column < 6:
            return self.createIndex(row, column)
        return QModelIndex()

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

    @Slot(int, result="QVariantMap")
    def rowData(self, row: int) -> dict:
        """Display roles for one source row (feeds the proxy rowData)."""
        keys = (
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
        if not 0 <= row < len(self._rows):
            return {}
        return dict(zip(keys, self._rows[row], strict=True))

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
        threading.Thread(
            target=self._pick_worker,
            args=("Game executable", "Select", False, ""),
            daemon=True,
        ).start()

    @Slot(str, str)
    def pickPath(self, title: str, accept_label: str) -> None:
        """Generic open picker off the GUI thread; result via browseFinished."""
        threading.Thread(
            target=self._pick_worker,
            args=(title or "Pick a file", accept_label or "Open", False, ""),
            daemon=True,
        ).start()

    @Slot(str, str, str)
    def pickSavePath(self, title: str, accept_label: str, filename: str) -> None:
        """Generic save picker off the GUI thread; result via browseFinished."""
        threading.Thread(
            target=self._pick_worker,
            args=(title or "Save file", accept_label or "Save", True, filename or ""),
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

    @Slot(str, result="QVariantMap")
    def loadGame(self, appid: str) -> dict:
        """General-section fields plus profile names for the settings UI."""
        try:
            cfg = cfgmod.load(appid)
        except Exception as e:  # unknown id: empty form, never a traceback
            log.warning("loadGame(%s) failed: %s", appid, e)
            return {}
        try:
            profiles = cfgmod.list_profiles(appid)
        except Exception:
            profiles = []
        g = cfg.general
        return {
            "appid": g.appid,
            "name": g.name,
            "custom_executable": g.custom_executable,
            "game_type": g.game_type if g.game_type in ("auto", "proton", "native") else "auto",
            "show_menu": bool(g.show_menu),
            "menu_timeout": max(0, min(600, int(g.menu_timeout or 0))),
            "custom_prefix": g.custom_prefix,
            "active_profile": g.active_profile,
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
            "rt_enable": bool(cfg.rtupscale.enable),
            "rt_args": cfg.rtupscale.args,
            "ludusavi_enable": bool(cfg.ludusavi.enable),
            "ludusavi_restore": bool(cfg.ludusavi.restore),
            "ludusavi_backup": bool(cfg.ludusavi.backup),
            "ludusavi_name": cfg.ludusavi.name_override,
            "ludusavi_gui": bool(cfg.ludusavi.use_gui),
            "notify_on_launch": bool(cfg.notifications.notify_on_launch),
            "inhibit_idle": bool(cfg.session.inhibit_idle),
            "nl_disable": bool(cfg.nightlight.disable_during_game),
            "nl_provider": cfg.nightlight.provider
            if cfg.nightlight.provider in ("auto", "plasma", "gnome", "off")
            else "auto",
        }

    @Slot(str, "QVariantMap", result=str)
    def saveGame(self, appid: str, values) -> str:
        """Persist the General-section fields. Returns the id, or ''."""
        data = dict(values or {})
        if not appid:
            err = validate_local_game(
                str(data.get("name", "")), str(data.get("custom_executable", ""))
            )
            if err:
                log.warning("saveGame create rejected: %s", err)
                return ""
            appid = cfgmod.new_local_id(str(data.get("name", "")).strip())
            cfg = cfgmod.load_defaults()
            cfg.general.appid = appid
            cfg.general.name = str(data.get("name", "")).strip()
        else:
            if not cfgmod.game_file(appid).is_file():
                log.warning("saveGame(%s) rejected: unknown game", appid)
                return ""
            try:
                cfg = cfgmod.load(appid)
            except Exception as e:
                log.warning("saveGame(%s) failed: %s", appid, e)
                return ""
            if not steammod.is_steam_id(appid):
                cfg.general.name = str(data.get("name", "")).strip()
        cfg.general.custom_executable = str(data.get("custom_executable", "")).strip()
        game_type = str(data.get("game_type", "auto"))
        cfg.general.game_type = game_type if game_type in ("auto", "proton", "native") else "auto"
        cfg.general.show_menu = bool(data.get("show_menu", False))
        try:
            cfg.general.menu_timeout = max(0, min(600, int(data.get("menu_timeout", 0) or 0)))
        except (TypeError, ValueError):
            cfg.general.menu_timeout = 0
        cfg.general.custom_prefix = str(data.get("custom_prefix", "")).strip()
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
        cfg.rtupscale.enable = bool(data.get("rt_enable", False))
        cfg.rtupscale.args = str(data.get("rt_args", "")).strip()
        cfg.ludusavi.enable = bool(data.get("ludusavi_enable", False))
        cfg.ludusavi.restore = bool(data.get("ludusavi_restore", True))
        cfg.ludusavi.backup = bool(data.get("ludusavi_backup", True))
        cfg.ludusavi.name_override = str(data.get("ludusavi_name", "")).strip()
        cfg.ludusavi.use_gui = bool(data.get("ludusavi_gui", True))
        cfg.notifications.notify_on_launch = bool(data.get("notify_on_launch", True))
        cfg.session.inhibit_idle = bool(data.get("inhibit_idle", False))
        cfg.nightlight.disable_during_game = bool(data.get("nl_disable", False))
        nl_provider = str(data.get("nl_provider", "auto"))
        cfg.nightlight.provider = (
            nl_provider if nl_provider in ("auto", "plasma", "gnome", "off") else "auto"
        )
        try:
            cfgmod.save(cfg)
        except Exception as e:
            log.warning("saveGame(%s) failed: %s", appid, e)
            return ""
        self.refresh()
        return appid

    @Slot(str, str, result=bool)
    def loadGameProfile(self, appid: str, name: str) -> bool:
        """Switch the live config to a saved profile snapshot."""
        name = str(name or "").strip()
        try:
            known = cfgmod.list_profiles(appid)
        except Exception:
            known = []
        if not appid or not name or name not in known:
            return False
        try:
            cfg = cfgmod.load_profile(appid, name)
            cfg.general.appid = appid
            cfg.general.active_profile = name
            cfgmod.save(cfg)
        except Exception as e:
            log.warning("loadGameProfile failed: %s", e)
            return False
        self.refresh()
        return True

    @Slot(str, str, result=bool)
    def saveGameProfile(self, appid: str, name: str) -> bool:
        """Snapshot the live config as a named profile."""
        name = str(name or "").strip()
        if not appid or not name:
            return False
        try:
            cfgmod.save_profile(appid, name, cfgmod.load(appid))
        except Exception as e:
            log.warning("saveGameProfile failed: %s", e)
            return False
        return True

    @Slot(str, str, str, result=bool)
    def cloneGameProfile(self, appid: str, src: str, dest: str) -> bool:
        """Copy profile snapshot src to a new name dest."""
        src, dest = str(src or "").strip(), str(dest or "").strip()
        if not appid or not src or not dest or src == dest:
            return False
        try:
            if src not in cfgmod.list_profiles(appid):
                return False
            cfgmod.save_profile(appid, dest, cfgmod.load_profile(appid, src))
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

    @Slot(str, result=str)
    def exportTarball(self, path: str) -> str:
        """Export configs to a tarball; returns the status message ('' skips)."""
        path = (path or "").strip()
        if not path:
            return ""
        try:
            saved = cfgmod.export_configs(path)
        except (OSError, ValueError) as e:
            return f"Export failed: {e}"
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
            return f"Import failed: {e}"
        self.refresh()
        return f"Imported {len(imported)} game(s)"

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
            raw = stimod.parse_stl_conf(
                stimod.stl_config_dir() / "gamecfgs" / "id" / f"{appid}.conf"
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
            lines.append("Imported as the 'steamtinkerlaunch' profile (live config untouched):")
            lines += [f"  • {a}" for a in imported]
            lines.append("Open the game, pick the profile in the Profile row to try it.")
        if skipped:
            lines.append("Skipped (no STL config found):")
            lines += [f"  • {a}" for a in skipped]
        details = "\n".join(f"{a}: {'; '.join(r)}" for a, r in reports.items() if r)
        if details:
            lines += ["", "Notes:", details]
        return "\n".join(lines) or "Nothing selected."

    @Slot(result=str)
    def importPredecessor(self) -> str:
        """Copy TKSteamLaunch configs (missing files only); status message."""
        try:
            imported, skipped = cfgmod.import_tksteamlaunch()
        except (OSError, ValueError) as e:
            return f"Import failed: {e}"
        lines = [f"Imported {len(imported)} file(s)."]
        if skipped:
            lines.append(f"Skipped {len(skipped)} existing file(s).")
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

    @Slot(str, str)
    def checkCoverage(self, appid: str, name_override: str) -> None:
        """Ludusavi coverage check off the GUI thread (coverageFinished)."""
        threading.Thread(
            target=self._coverage_worker,
            args=(appid, name_override),
            daemon=True,
        ).start()

    def _coverage_worker(self, appid: str, name_override: str) -> None:
        from ..backends import ludusavi as lumod

        try:
            status, detail = lumod.check_coverage(appid, name_override)
        except Exception as e:  # backends must never break the dialog
            status, detail = "unavailable", str(e)
        self.coverageFinished.emit(status, detail)

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
        refresher = self._tray_refresher
        if callable(refresher):
            try:
                refresher()
            except Exception as e:
                log.warning("tray refresh failed: %s", e)
        return True

    @Slot(bool)
    def setTrayActive(self, active: bool) -> None:
        """Whether kirigami_app currently shows a tray icon."""
        self._tray_active = bool(active)

    @Slot(QObject)
    def watchQuitKeys(self, window) -> None:
        """Install the Ctrl+Q filter on a top-level window (best effort)."""
        try:
            if window is not None:
                window.installEventFilter(self._quit_filter)
        except Exception as e:
            log.warning("watchQuitKeys failed: %s", e)

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
    """Source + text filter over a GameListModel (drawer + search drive it).

    Also a real table model for QtQuick TableView: fixed logical columns
    [#, name, appid, played, tier, source] with order/visibility owned
    here (persisted to the same prefs keys). Custom roles stay
    row-based (column-independent), so delegates keep working.
    """

    sourceChanged = Signal()
    textChanged = Signal()
    issuesChanged = Signal()

    TABLE_COLUMNS = ("#", "gameName", "gameId", "gamePlayed", "gameTier", "gameSource")
    COLUMN_TITLES = {
        "#": "#",
        "gameName": "Game",
        "gameId": "App ID",
        "gamePlayed": "Played",
        "gameTier": "ProtonDB",
        "gameSource": "Source",
    }
    _COLUMN_ROLES = (
        None,
        "gameName",
        "gameId",
        "gamePlayed",
        "gameTier",
        "gameSource",
    )

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._source = "all"
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
        try:
            order = [int(x) for x in cfgmod.load_preferences().column_order.split(",")]
        except Exception:
            order = []
        if sorted(order) != [0, 1, 2, 3, 4, 5]:
            order = [0, 1, 2, 3, 4, 5]
        try:
            hidden = {int(x) for x in cfgmod.load_preferences().hidden_columns.split(",")}
        except Exception:
            hidden = set()
        return order, {h for h in hidden if h in (1, 2, 3, 4, 5)}

    def _view_columns(self) -> list[int]:
        """Logical columns in view order (hidden stay mapped, QML widths them 0)."""
        return list(self._order)

    @staticmethod
    def _load_widths() -> dict[int, int]:
        """Fitted column widths from prefs (garbage means no overrides)."""
        widths: dict[int, int] = {}
        try:
            raw = cfgmod.load_preferences().column_widths
        except Exception:
            return widths
        for part in str(raw or "").split(","):
            if "=" not in part:
                continue
            left, _, right = part.partition("=")
            try:
                logical, width = int(left.strip()), int(right.strip())
            except ValueError:
                continue
            if 0 <= logical <= 5 and 20 <= width <= 2000:
                widths[logical] = width
        return widths

    def _save_columns(self) -> None:
        try:
            prefs = cfgmod.load_preferences()
        except Exception:
            return
        prefs.column_order = ",".join(map(str, self._order))
        prefs.hidden_columns = ",".join(map(str, sorted(self._hidden)))
        prefs.column_widths = ",".join(f"{k}={v}" for k, v in sorted(self._widths.items()))
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
        if logical not in (1, 2, 3, 4, 5) or not 20 <= width <= 2000:
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
        if logical not in (0, 1, 2, 3, 4, 5):
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
        """Fit columns 1-5 capped: fresh starts and resets show content."""
        for logical in (1, 2, 3, 4, 5):
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
                5: GameListModel.SourceRole,
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
        """Default order, everything visible, columns fitted capped."""
        self._order = [0, 1, 2, 3, 4, 5]
        self._hidden = set()
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
        "showSource": 5,
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

    def _get_showSource(self) -> bool:
        return self._get_flag("showSource")

    def _set_showSource(self, value: bool) -> None:
        self._set_flag("showSource", value)

    showAppId = Property(bool, _get_showAppId, _set_showAppId, notify=columnsChanged)
    showPlayed = Property(bool, _get_showPlayed, _set_showPlayed, notify=columnsChanged)
    showTier = Property(bool, _get_showTier, _set_showTier, notify=columnsChanged)
    showSource = Property(bool, _get_showSource, _set_showSource, notify=columnsChanged)

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
