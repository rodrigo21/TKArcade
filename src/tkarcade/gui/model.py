"""QML game list model: stdlib core underneath, QtCore only on top."""

from __future__ import annotations

import logging
import os
import shlex
import shutil
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
    Signal,
    Slot,
)

from .. import artwork as artmod
from .. import config as cfgmod
from .. import graphics as graphicsmod
from .. import history as histmod
from .. import launcher as launchermod
from .. import protondb as pdbmod
from .. import runtimes, xdg
from .. import steam as steammod
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
        return "—", -1, "No recorded sessions", "—", -1
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
    """Escape closes a watched dialog; Enter takes its open popup's default.

    A QML `Window` is not a `QDialog`: nothing maps Escape to reject() for
    it, and with no field focused its focus item is the window root, so the
    key never reaches a QML `Keys` handler on the body. The popups go
    first, and they own the focus chain while they are open: a prompt's own
    CloseOnEscape never sees an Escape and the body's
    `Keys.onReturnPressed` never sees an Enter. Both are routed to the
    popup here (a widgets modal's default button took Enter first).
    """

    def eventFilter(self, watched, event):
        try:
            if (
                event.type() == QEvent.Type.KeyPress
                and not event.isAutoRepeat()
                and event.key() in (Qt.Key.Key_Escape, Qt.Key.Key_Return, Qt.Key.Key_Enter)
            ):
                if event.key() == Qt.Key.Key_Escape:
                    if not self._close_popup(watched):
                        watched.close()
                    return True
                # Enter: with no popup open the body's own Keys handler runs
                # (it knows the window's default buttons); with one open,
                # press its accept button and swallow the key.
                opened = _opened_popups(watched)
                target = _highlighted_button(opened[-1]) if opened else None
                if target is None:
                    return False
                QMetaObject.invokeMethod(target, "clicked")
                return True
        except Exception:
            pass
        return False

    @staticmethod
    def _close_popup(window) -> bool:
        """Close the last opened popup under `window` (False when none)."""
        try:
            opened = _opened_popups(window)
            return bool(opened) and QMetaObject.invokeMethod(opened[-1], "close")
        except Exception:
            return False


def _opened_popups(window) -> list:
    """The opened popups under `window`, in tree order (never raises).

    Everything that can be dismissed or accepted exposes `opened` (Popup,
    Kirigami.Dialog, Menu); the last one is the innermost of the open ones.
    """
    opened = []
    try:
        for child in window.findChildren(QObject):
            if child.metaObject().indexOfProperty("opened") < 0:
                continue
            if child.property("opened"):
                opened.append(child)
    except Exception:
        pass
    return opened


def _highlighted_button(popup):
    """The popup's clickable accept button: its highlighted one, or None.

    Our dialog button rows keep the accept button `highlighted` (see
    AGENTS.md), which is what Enter has to hit inside an open popup.
    """
    for child in popup.findChildren(QObject):
        try:
            if child.metaObject().indexOfProperty("highlighted") < 0:
                continue
            if (
                child.property("highlighted")
                and child.property("visible")
                and child.property("enabled")
            ):
                return child
        except Exception:
            continue
    return None


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
    LastPlayedRole = Qt.ItemDataRole.UserRole + 11
    LastSecsRole = Qt.ItemDataRole.UserRole + 12
    PlatformRole = Qt.ItemDataRole.UserRole + 13
    RunnerRole = Qt.ItemDataRole.UserRole + 14
    WineRole = Qt.ItemDataRole.UserRole + 15
    InstallDirRole = Qt.ItemDataRole.UserRole + 16
    CategoryRole = Qt.ItemDataRole.UserRole + 17

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
        "gameLastPlayed",
        "gameLastSecs",
        "gamePlatform",
        "gameRunner",
        "gameWine",
        "gameInstallDir",
        "gameCategory",
    )

    refreshed = Signal()
    browseFinished = Signal(str)
    displayModesFinished = Signal("QVariantList")
    coverageFinished = Signal(str, str)
    # Widgets parity: every launch path reported itself (the status line
    # said "Launched X.", the handoff failures warned — the tray recents
    # ran the same code). The model only says what happened; the QML side
    # owns the wording. kind is "steam" or "local".
    launchReported = Signal(bool, str, str, str)

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
        self._steam_status: tuple[str, str, str] | None = None
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
            GameListModel.LastPlayedRole: b"gameLastPlayed",
            GameListModel.LastSecsRole: b"gameLastSecs",
            GameListModel.PlatformRole: b"gamePlatform",
            GameListModel.RunnerRole: b"gameRunner",
            GameListModel.WineRole: b"gameWine",
            GameListModel.InstallDirRole: b"gameInstallDir",
            GameListModel.CategoryRole: b"gameCategory",
        }

    def rowCount(self, parent: QModelIndex | None = None) -> int:
        return 0 if (parent is not None and parent.isValid()) else len(self._rows)

    def columnCount(self, parent: QModelIndex | None = None) -> int:
        # Fixed logical columns (proxy permutes/hides them for the view).
        return 0 if (parent is not None and parent.isValid()) else 12

    def index(self, row: int, column: int, parent: QModelIndex | None = None):
        # Table models own their indexes (unlike proxy mapping, this is safe).
        if parent is not None and parent.isValid():
            return QModelIndex()
        if 0 <= row < len(self._rows) and 0 <= column < 12:
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
            GameListModel.LastPlayedRole: 10,
            GameListModel.LastSecsRole: 11,
            GameListModel.PlatformRole: 12,
            GameListModel.RunnerRole: 13,
            GameListModel.WineRole: 14,
            GameListModel.InstallDirRole: 15,
            GameListModel.CategoryRole: 16,
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
            "gameLastPlayed",
            "gameLastSecs",
            "gamePlatform",
            "gameRunner",
            "gameWine",
            "gameInstallDir",
            "gameCategory",
        )
        if not 0 <= row < len(self._rows):
            return {}
        return dict(zip(keys, self._rows[row], strict=True))

    @Slot()
    def refresh(self) -> None:
        """Reload rows from disk (Steam names first, local names merged)."""
        names = {a: n for a, n in steammod.list_games()}
        self._steam_detected = len(names)
        names.update(steammod.local_names())
        # Drop stale validation results: configs may have changed on disk.
        self._issues_cache = {}
        try:
            stats = histmod.summarize(histmod.parse_log(xdg.log_file()))
        except Exception:
            stats = {}
        rows = [self._row(appid, names, stats) for appid in cfgmod.list_appids()]
        rows.sort(key=lambda r: r[1].lower())
        self.beginResetModel()
        self._rows = rows
        self.endResetModel()
        self.refreshed.emit()

    def _row(self, appid: str, names: dict, stats: dict) -> tuple:
        """One table row for an AppID (column order mirrors `rowData`)."""
        played, played_secs, played_tip, last_played, last_secs = _played_cells(stats.get(appid))
        try:
            gcfg = cfgmod.load(appid)
        except Exception:
            gcfg = None
        is_steam = steammod.is_steam_id(appid)
        data, _fresh = pdbmod.cached(appid)
        tier = str(((data or {}).get("tier", "")) or "").lower()
        bg, fg = pdbmod.TIER_STYLE.get(tier, ("", ""))
        icon = self._row_icon(appid, gcfg)
        return (
            appid,
            names.get(appid, appid),
            "Steam" if is_steam else "Local",
            played,
            tier.title(),
            bg,
            fg,
            str(icon) if icon else "",
            played_secs,
            played_tip,
            last_played,
            last_secs,
            gcfg.general.platform if gcfg is not None else "",
            cfgmod.normalize_game_type(gcfg.general.game_type).title()
            if gcfg is not None and cfgmod.normalize_game_type(gcfg.general.game_type)
            else ("Not set" if gcfg is not None else ""),
            self._row_wine(appid, gcfg, is_steam),
            self._row_install_dir(appid, gcfg),
            ", ".join(gcfg.general.categories) if gcfg is not None else "",
        )

    @staticmethod
    def _row_icon(appid: str, gcfg) -> Path | None:
        """Artwork icon: the game's own, a donor's, else the resolved one."""
        icon = artmod.resolve_icon(appid)
        try:
            if gcfg is None:
                return icon
            art, donor = gcfg.artwork, gcfg.artwork.donor_appid.strip()
            if art.icon and Path(art.icon).is_file():
                return Path(art.icon)
            if donor and donor != appid:
                donor_icon = artmod.resolve_icon(donor)
                if donor_icon is not None:
                    return donor_icon
        except Exception as e:
            log.warning("artwork resolve(%s) failed: %s", appid, e)
        return icon

    @staticmethod
    def _row_wine(appid: str, gcfg, is_steam: bool) -> str:
        """Proton tool label for Steam ids, else the configured Wine version."""
        if is_steam:
            from .. import proton as protonmod

            try:
                return protonmod.tool_display(appid)
            except Exception:
                return "Proton"
        if gcfg is not None and gcfg.proton.wine_version:
            return gcfg.proton.wine_version
        return ""

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
    def pickDir(self, title: str, accept_label: str) -> None:
        """Generic folder picker off the GUI thread; result via browseFinished."""
        threading.Thread(
            target=self._pick_dir_worker,
            args=(title or "Pick a folder", accept_label or "Select"),
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
            "custom_executable": g.custom_executable,
            "game_type": cfgmod.normalize_game_type(g.game_type),
            "show_menu": bool(g.show_menu),
            "menu_timeout": max(0, min(600, int(g.menu_timeout or 0))),
            "custom_prefix": g.custom_prefix,
            "active_profile": g.active_profile,
            "categories": list(g.categories),
            "platform": g.platform,
            "launch_args": g.launch_args,
            "launch_cwd": g.launch_cwd,
            "art_icon": cfg.artwork.icon,
            "art_cover": cfg.artwork.cover,
            "art_banner": cfg.artwork.banner,
            "art_donor": cfg.artwork.donor_appid,
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
            "nl_disable": bool(cfg.nightlight.disable_during_game),
            "nl_provider": cfg.nightlight.provider
            if cfg.nightlight.provider in ("auto", "plasma", "gnome", "off")
            else "auto",
            "fresh_prefix": bool(cfg.proton.fresh_prefix),
            "audio_sink": cfg.audio.sink,
            "winetricks_verbs": " ".join(cfg.proton.winetricks_verbs),
            "wine_prefix": cfg.proton.wine_prefix,
            "wine_version": cfg.proton.wine_version,
            "proton_log": bool(cfg.debug.proton_log),
            "winedebug": cfg.debug.winedebug,
            "runtime_wine_binary": cfg.runtime.wine_binary,
            "runtime_proton_path": cfg.runtime.proton_path,
            "runtime_prefix_dir": cfg.runtime.prefix_dir,
            "runtime_prefix_name": cfg.runtime.prefix_name,
            "runtime_winetricks_verbs": " ".join(cfg.runtime.winetricks_verbs),
            "graphics_dxvk": bool(cfg.graphics.dxvk),
            "graphics_vkd3d": cfgmod.normalize_graphics_vkd3d(cfg.graphics.vkd3d),
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

    @Slot(str, result="QVariantMap")
    def templateGame(self, appid: str) -> dict:
        """The user's Global Defaults template as fields for one game.

        Widgets parity (_on_reset): Reset applies defaults.toml, never the
        built-in factory values, and the AppID is kept. Profiles are not
        touched (the caller clears the active profile).
        """
        try:
            cfg = cfgmod.load_defaults()
        except Exception as e:
            log.warning("templateGame(%s) failed: %s", appid, e)
            return {}
        cfg.general.appid = appid
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

    @Slot(str, "QVariantMap", result=str)
    def saveGame(self, appid: str, values) -> str:
        """Persist the General-section fields. Returns the id, or ''."""
        data = dict(values or {})
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
        self._apply_map(cfg, data)
        try:
            cfgmod.save(cfg)
        except Exception as e:
            log.warning("saveGame(%s) failed: %s", appid, e)
            return ""
        self.refresh()
        return appid

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
    def _apply_map(cfg, data: dict) -> None:
        """Write settings form fields into a config (no save, no refresh)."""
        cfg.general.custom_executable = str(data.get("custom_executable", "")).strip()
        cfg.general.game_type = cfgmod.normalize_game_type(data.get("game_type", ""))
        cfg.general.show_menu = bool(data.get("show_menu", False))
        try:
            cfg.general.menu_timeout = max(0, min(600, int(data.get("menu_timeout", 0) or 0)))
        except (TypeError, ValueError):
            cfg.general.menu_timeout = 0
        cfg.general.custom_prefix = str(data.get("custom_prefix", "")).strip()
        cfg.runtime.wine_binary = str(data.get("runtime_wine_binary", "")).strip()
        cfg.runtime.proton_path = str(data.get("runtime_proton_path", "")).strip()
        cfg.runtime.prefix_dir = str(data.get("runtime_prefix_dir", "")).strip()
        cfg.runtime.prefix_name = str(data.get("runtime_prefix_name", "")).strip()
        cfg.runtime.winetricks_verbs = _split_args(str(data.get("runtime_winetricks_verbs", "")))
        cfg.graphics.dxvk = bool(data.get("graphics_dxvk", False))
        cfg.graphics.vkd3d = cfgmod.normalize_graphics_vkd3d(data.get("graphics_vkd3d", ""))
        cats = data.get("categories", [])
        if isinstance(cats, str):
            cats = [c.strip() for c in cats.split(",")]
        cfg.general.categories = [str(c).strip() for c in cats or [] if str(c).strip()]
        cfg.general.platform = str(data.get("platform", "")).strip()
        cfg.general.launch_args = str(data.get("launch_args", "")).strip()
        cfg.general.launch_cwd = str(data.get("launch_cwd", "")).strip()
        cfg.artwork.icon = str(data.get("art_icon", "")).strip()
        cfg.artwork.cover = str(data.get("art_cover", "")).strip()
        cfg.artwork.banner = str(data.get("art_banner", "")).strip()
        cfg.artwork.donor_appid = str(data.get("art_donor", "")).strip()
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
        cfg.nightlight.disable_during_game = bool(data.get("nl_disable", False))
        nl_provider = str(data.get("nl_provider", "auto"))
        cfg.nightlight.provider = (
            nl_provider if nl_provider in ("auto", "plasma", "gnome", "off") else "auto"
        )
        cfg.proton.fresh_prefix = bool(data.get("fresh_prefix", False))
        cfg.proton.winetricks_verbs = _split_args(str(data.get("winetricks_verbs", "")))
        cfg.proton.wine_prefix = str(data.get("wine_prefix", "")).strip()
        cfg.proton.wine_version = str(data.get("wine_version", "")).strip()
        cfg.audio.sink = str(data.get("audio_sink", "")).strip()
        cfg.debug.proton_log = bool(data.get("proton_log", False))
        winedebug = str(data.get("winedebug", ""))
        cfg.debug.winedebug = winedebug if winedebug in ("", "-all", "+err", "+warn,+err") else ""

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
            names = {a: n for a, n in steammod.list_games()}
            names.update(steammod.local_names())
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
            names = {a: n for a, n in steammod.list_games()}
            names.update(steammod.local_names())
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
            return self._row_wine(appid, None, True)
        except Exception:
            return ""

    @Slot(str, result=str)
    def landscapeArt(self, appid: str) -> str:
        """Landscape artwork path for the pre-launch menu ('' when none)."""
        try:
            if not appid:
                return ""
            path = artmod.resolve_icon(appid, landscape=True)
            return str(path) if path else ""
        except Exception:
            return ""

    @Slot(str, result=str)
    def protonLabel(self, appid: str) -> str:
        """Proton tool/version label for the pre-launch menu (widgets parity)."""
        if not appid:
            return "—"
        from .. import proton as protonmod

        try:
            return protonmod.tool_display(appid)
        except Exception:
            return "Proton"

    @Slot(result=list)
    def allCategories(self) -> list:
        """Every category tag in use, sorted case-insensitively."""
        found: set[str] = set()
        try:
            for appid in cfgmod.list_appids():
                try:
                    found.update(cfgmod.load(appid).general.categories)
                except Exception:
                    continue
        except Exception:
            return []
        return sorted(found, key=str.lower)

    @Slot(list, str, result=str)
    def setCategories(self, appids, text: str) -> str:
        """Bulk-set category tags from comma text. Returns a status message."""
        ids = [str(a) for a in appids or []]
        if not ids:
            return "Select games first."
        cats = [c.strip() for c in str(text or "").split(",") if c.strip()]
        count = 0
        for appid in ids:
            try:
                cfg = cfgmod.load(appid)
                cfg.general.categories = cats
                cfgmod.save(cfg)
                count += 1
            except Exception as e:
                log.warning("setCategories(%s) failed: %s", appid, e)
        self.refresh()
        return f"Set {len(cats)} categor(ies) on {count} game(s)."

    @Slot(str, str, str, result=str)
    def storeArtwork(self, appid: str, kind: str, src: str) -> str:
        """Copy an image into the manual slot and point the config at it."""
        dest = artmod.store_manual(appid, kind, src)
        if dest is None:
            return "Pick a PNG, JPG or WebP image file."
        try:
            cfg = cfgmod.load(appid)
            setattr(cfg.artwork, kind, os.fspath(dest))
            cfgmod.save(cfg)
        except Exception as e:
            log.warning("storeArtwork(%s) failed: %s", appid, e)
            return "Could not save the artwork path."
        self.refresh()
        return ""

    @Slot(str, str, result=bool)
    def clearArtwork(self, appid: str, kind: str) -> bool:
        """Remove a manual artwork slot and clear the config path."""
        try:
            cfg = cfgmod.load(appid)
            if kind in artmod.MANUAL_KINDS:
                setattr(cfg.artwork, kind, "")
            cfgmod.save(cfg)
        except Exception as e:
            log.warning("clearArtwork(%s) failed: %s", appid, e)
            return False
        artmod.clear_manual(appid, kind)
        self.refresh()
        return True

    @Slot(str, result=list)
    def donorCandidates(self, query: str) -> list:
        """[[appid, name]] games matching a donor search, by name."""
        q = str(query or "").strip().lower()
        try:
            names = {a: n for a, n in steammod.list_games()}
            names.update(steammod.local_names())
            rows = [[a, n] for a, n in names.items() if not q or q in n.lower() or q in a]
        except Exception:
            return []
        return sorted(rows, key=lambda r: r[1].lower())[:50]

    @Slot(result=list)
    def wineTools(self) -> list:
        """[[tool, version]] installed compat tools plus system Wine."""
        from .. import proton as protonmod

        try:
            rows = [[t, protonmod.tool_version(t) or ""] for t in protonmod.list_compat_tools()]
        except Exception:
            rows = []
        try:
            system = protonmod.system_wine()
        except Exception:
            system = None
        if system:
            rows.append([f"system wine ({system})", ""])
        return rows

    @Slot(result=bool)
    def steamRunning(self) -> bool:
        """Whether a Steam process is alive (mapping writes need it idle)."""
        import subprocess

        try:
            proc = subprocess.run(
                ["pgrep", "-x", "steam"], capture_output=True, timeout=10, check=False
            )
        except Exception:
            return True
        return proc.returncode == 0

    @Slot(str, str, result=str)
    def applyWineVersion(self, appid: str, tool: str) -> str:
        """Point Steam's compat mapping at a tool. '' on success, else why."""
        if not steammod.is_steam_id(appid) or not appid.isdigit():
            return "Version selection needs a Steam game."
        tool = str(tool or "").strip()
        if not tool:
            return "Pick a compat tool first."
        if self.steamRunning():
            return "Quit Steam first: it rewrites config.vdf on exit."
        try:
            import vdf
        except ImportError:
            return "The vdf module is missing."
        for root in steammod.steam_roots():
            path = root / "config" / "config.vdf"
            if not path.is_file():
                continue
            try:
                with open(path, encoding="utf-8") as handle:
                    data = vdf.load(handle)
                node = data["InstallConfigStore"]["Software"]["Valve"]["Steam"]
                mapping = node.setdefault("CompatToolMapping", {})
                mapping[str(appid)] = {"name": tool}
                backup = path.with_suffix(".vdf.tkarcade-bak")
                backup.write_bytes(path.read_bytes())
                with open(path, "w", encoding="utf-8") as handle:
                    vdf.dump(data, handle, pretty=True)
            except Exception as e:
                log.warning("applyWineVersion(%s) failed: %s", appid, e)
                return f"Could not update {path}: {e}"
            try:
                cfg = cfgmod.load(appid)
                cfg.proton.wine_version = tool
                cfgmod.save(cfg)
            except Exception as e:
                log.warning("applyWineVersion record failed: %s", e)
            from .. import proton as protonmod

            protonmod.clear_tool_cache()
            self.refresh()
            return ""
        return "No Steam config.vdf found."

    @Slot(str, result=str)
    def ensurePrefix(self, appid: str) -> str:
        """Create the custom prefix dir now. '' on success, else why."""
        try:
            custom = cfgmod.load(appid).proton.wine_prefix.strip()
        except Exception as e:
            return f"Could not read the config: {e}"
        if not custom:
            return "Set a custom prefix dir first (Steam creates its own)."
        try:
            Path(custom).expanduser().mkdir(parents=True, exist_ok=True)
        except Exception as e:
            return f"Could not create {custom}: {e}"
        return ""

    @Slot(str, result=str)
    def clearCustomPrefix(self, appid: str) -> str:
        """Delete the custom prefix dir (guarded). '' on success, else why."""
        import shutil as _shutil

        try:
            custom = cfgmod.load(appid).proton.wine_prefix.strip()
        except Exception as e:
            return f"Could not read the config: {e}"
        if not custom:
            return "No custom prefix set."
        target = Path(custom).expanduser()
        try:
            resolved = target.resolve()
            home = Path.home().resolve()
            if resolved == home or resolved == home.parent or len(resolved.parts) <= 2:
                return f"Refusing to delete {resolved}."
            if not target.is_dir():
                return f"Not a directory: {target}."
        except Exception as e:
            return f"Could not inspect {target}: {e}"
        try:
            _shutil.rmtree(target)
        except Exception as e:
            return f"Could not delete {target}: {e}"
        return f"Cleared {target}."

    @Slot(str, str, result=str)
    def artworkPath(self, appid: str, kind: str) -> str:
        """Stored config path for a manual artwork slot ('' when none)."""
        try:
            art = cfgmod.load(appid).artwork
            value = getattr(art, kind, "") if kind in artmod.MANUAL_KINDS else ""
            return str(value or "")
        except Exception:
            return ""

    @Slot(str, str, bool, result=str)
    def cloneGameTo(self, src: str, dest: str, force: bool) -> str:
        """Clone live config plus profiles; '' on success, else a message."""
        import re

        m = re.search(r"\[(.+)\]\s*$", dest or "")
        cand = (m.group(1) if m else (dest or "")).strip()
        if not cand or xdg.safe_stem(cand) != cand:
            return f"Invalid game ID: {dest}"
        if cand == src:
            return "Source and target are the same."
        if cfgmod.game_file(cand).is_file() and not force:
            return "OVERWRITE"
        try:
            cfgmod.clone_game(src, cand)
        except (OSError, ValueError) as e:
            return str(e)
        self.refresh()
        return f"Cloned {src} to {cand}."

    @Slot(list, result=str)
    def resetGames(self, appids) -> str:
        """Reset live configs to the Global Defaults template (keeps profiles)."""
        ids = [str(a) for a in appids or []]
        if not ids:
            return "Select games first."
        count = 0
        for appid in ids:
            try:
                cfg = cfgmod.load_defaults()
                cfg.general.appid = appid
                cfgmod.save(cfg)
                count += 1
            except Exception as e:
                log.warning("resetGames(%s) failed: %s", appid, e)
        self.refresh()
        return f"Reset {count} game(s) to the Global Defaults template."

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
                from .. import proton as protonmod

                try:
                    tool = protonmod.compat_tool_name(appid) or ""
                    flavor = protonmod.flavor(tool) if tool else ""
                except Exception:
                    tool, flavor = "", ""
                if tool and flavor not in preset.proton:
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

    @Slot(str, result=str)
    def protonLogDir(self, appid: str) -> str:
        """Per-game Proton log dir path (may not exist yet)."""
        try:
            return os.fspath(launchermod.proton_log_dir(appid))
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

    @Slot(str, "QVariantMap", result="QVariantMap")
    def previewCommand(self, appid: str, values) -> dict:
        """Launch command preview for dialog (unsaved) state."""
        try:
            if appid and cfgmod.game_file(appid).is_file():
                cfg = cfgmod.load(appid)
            else:
                cfg = cfgmod.load_defaults()
                cfg.general.appid = appid
            self._apply_map(cfg, dict(values or {}))
            if not steammod.is_steam_id(appid):
                cfg.general.name = str(dict(values or {}).get("name", "")).strip()
            cmd, _env, warnings = launchermod.build_final_command(cfg, ["%command%"])
        except launchermod.GameTypeNotSetError:
            return {"command": "(choose a game type to preview)", "wrappers": "", "warnings": []}
        except Exception as e:  # never break the dialog on preview
            return {"command": f"(preview unavailable: {e})", "wrappers": "", "warnings": []}
        try:
            wrappers = launchermod.active_wrappers(cfg)
        except Exception:
            wrappers = []
        return {
            "command": shlex.join(cmd) if cmd else "(empty command)",
            "wrappers": " · ".join(wrappers) if wrappers else "No wrappers enabled",
            "warnings": warnings,
        }

    @Slot(str, "QVariantMap", result=str)
    def diffDefaults(self, appid: str, values) -> str:
        """Unified diff of dialog state vs Global Defaults ('' when same)."""
        try:
            if appid and cfgmod.game_file(appid).is_file():
                cfg = cfgmod.load(appid)
            else:
                cfg = cfgmod.load_defaults()
                cfg.general.appid = appid
            self._apply_map(cfg, dict(values or {}))
            if not steammod.is_steam_id(appid):
                cfg.general.name = str(dict(values or {}).get("name", "")).strip()
            return cfgmod.diff_vs_defaults(cfg)
        except Exception as e:
            return f"(diff unavailable: {e})"

    def _dep_draft(self, appid: str, values) -> object | None:
        """Config for the dialog (unsaved) state, or None on any failure."""
        try:
            if appid and cfgmod.game_file(appid).is_file():
                cfg = cfgmod.load(appid)
            else:
                cfg = cfgmod.load_defaults()
                cfg.general.appid = appid
            data = dict(values or {})
            self._apply_map(cfg, data)
            if not steammod.is_steam_id(appid):
                cfg.general.name = str(data.get("name", "")).strip()
        except Exception as e:  # never break the dialog on a status probe
            log.warning("dependencyStatus failed: %s", e)
            return None
        return cfg

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
        """Flatpak Ludusavi cannot see Proton prefixes: always warn."""
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
            return {"key": "steam-options", "kind": "ok", "msg": "steam-ok", "args": [options]}
        if status == "missing":
            return {"key": "steam-options", "kind": "warn", "msg": "steam-missing"}
        return {"key": "steam-options", "kind": "ok", "msg": "steam-unknown"}

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
        """(status, options) for the Steam launch options, cached per game."""
        cached = self._steam_status
        if not check_steam and cached is not None and cached[0] == appid:
            return cached[1], cached[2]
        try:
            status, options = steammod.launch_options_status(appid)
        except Exception as e:
            log.warning("launch_options_status(%s) failed: %s", appid, e)
            status, options = "unknown", ""
        self._steam_status = (appid, status, options)
        return status, options

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
        """Effective Proton prefix: custom dir or Steam's compatdata ('' unknown)."""
        try:
            custom = cfgmod.load(appid).proton.wine_prefix.strip()
        except Exception:
            custom = ""
        if custom:
            return custom
        try:
            target = steammod.prefix_dir(appid)
        except Exception:
            target = None
        return str(target) if target is not None else ""

    @Slot(str, result="QVariantMap")
    def runtimeOptions(self, appid: str) -> dict:
        """Global runtime choices and discovered Proton installs for the dialog."""
        prefs = cfgmod.load_preferences()
        protons = runtimes.proton_installs(prefs.proton_dirs)
        default_prefix = ""
        if appid:
            try:
                cfg = cfgmod.load(appid)
                default_prefix = os.fspath(
                    cfgmod.prefix_dir(appid, "", prefs.prefix_base, cfg.runtime.prefix_name)
                )
            except Exception:
                default_prefix = ""
        return {
            "wine": str(prefs.wine_binary or ""),
            "prefix_base": str(prefs.prefix_base or ""),
            "default_prefix": default_prefix,
            "protons": [{"name": p.name, "path": os.fspath(p.path)} for p in protons],
        }

    @staticmethod
    def _prefix_users(prefs: cfgmod.Preferences) -> dict[str, list[str]]:
        """AppIDs resolved to each prefix directory (names and full overrides)."""
        usage: dict[str, list[str]] = {}
        for appid in cfgmod.list_appids():
            try:
                cfg = cfgmod.load(appid)
            except Exception:
                continue
            path = cfgmod.prefix_dir(
                appid, cfg.runtime.prefix_dir, prefs.prefix_base, cfg.runtime.prefix_name
            )
            usage.setdefault(os.fspath(path), []).append(appid)
        return usage

    @Slot(str, str, result="QVariantMap")
    def prefixNameState(self, appid: str, name: str) -> dict:
        """Resolved prefix for a friendly name, sanitization and sharing info."""
        prefs = cfgmod.load_preferences()
        target = cfgmod.prefix_dir(appid, "", prefs.prefix_base, name)
        others = [a for a in self._prefix_users(prefs).get(os.fspath(target), []) if a != appid]
        names = {a: n for a, n in steammod.list_games()}
        names.update(steammod.local_names())
        typed = name.strip()
        return {
            "target": os.fspath(target),
            "sanitized": target.name,
            "renamed": bool(typed) and target.name != typed,
            "shared": [names.get(a, a) for a in others],
            "exists": target.is_dir(),
            "is_prefix": xdg.is_wine_prefix(target),
        }

    @Slot(str, result="QVariantList")
    def prefixChoices(self, appid: str) -> list:
        """Existing Wine prefixes under the base, with the games using each."""
        prefs = cfgmod.load_preferences()
        usage = self._prefix_users(prefs)
        names = {a: n for a, n in steammod.list_games()}
        names.update(steammod.local_names())
        out = []
        for path in xdg.iter_prefixes(prefs.prefix_base):
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
        """Installed layers (marker) and newest available versions for a game."""
        prefs = cfgmod.load_preferences()
        prefix = None
        if appid:
            try:
                cfg = cfgmod.load(appid)
                prefix = cfgmod.prefix_dir(
                    appid, cfg.runtime.prefix_dir, prefs.prefix_base, cfg.runtime.prefix_name
                )
            except Exception:
                prefix = None
        available = {}
        for kind in ("dxvk", "vkd3d"):
            found = runtimes.pick_graphics(kind, graphicsmod.layer_dirs(kind, prefs))
            available[kind] = found.name if found else ""
        return {
            "prefix": os.fspath(prefix) if prefix is not None else "",
            "installed": graphicsmod.installed(prefix) if prefix is not None else {},
            "available": available,
        }

    @Slot(str, result=str)
    def removeGraphics(self, appid: str) -> str:
        """Delete the graphics files TKArcade copied into the prefix ('' = ok)."""
        if not appid:
            return "Choose a game first."
        try:
            cfg = cfgmod.load(appid)
        except Exception as e:
            return f"Could not read the config: {e}"
        prefs = cfgmod.load_preferences()
        prefix = cfgmod.prefix_dir(
            appid, cfg.runtime.prefix_dir, prefs.prefix_base, cfg.runtime.prefix_name
        )
        removed, warnings = graphicsmod.uninstall(prefix)
        log.info("graphics: removed %d file(s) from %s", removed, prefix)
        self.refresh()
        return warnings[0] if warnings else ""

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
            if steammod.is_steam_id(str(appid)):
                self._fetch_one(appid, api_key)
        try:
            self.backgroundDone.emit()
        except Exception:
            pass

    def _fetch_one(self, appid, api_key: str) -> None:
        """Refresh ProtonDB (and art, when a key is set) for one Steam appid."""
        try:
            _data, fresh = pdbmod.cached(appid)
        except Exception:
            return
        if not fresh:
            try:
                pdbmod.refresh(appid)
            except Exception:
                return
        if api_key and artmod.resolve_icon(appid) is None:
            try:
                artmod.fetch_missing(appid, api_key)
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
            "showDependencyStatus": bool(prefs.show_dependency_status),
            "trayEnable": bool(prefs.tray_enable),
            "trayIcon": str(prefs.tray_icon),
            "minimizeToTray": bool(prefs.minimize_to_tray),
            "closeToTray": bool(prefs.close_to_tray),
            "trayQuickLaunch": bool(prefs.tray_quick_launch),
            "trayQuickCount": int(prefs.tray_quick_count),
            "sgdbApiKey": str(prefs.sgdb_api_key),
            "language": str(prefs.language),
            "prefixBase": str(prefs.prefix_base),
            "wineBinary": str(prefs.wine_binary),
            "protonDirs": str(prefs.proton_dirs),
            "dxvkDirs": str(prefs.dxvk_dirs),
            "vkd3dDirs": str(prefs.vkd3d_dirs),
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
            prefs.tray_enable = bool(get("trayEnable", prefs.tray_enable))
            prefs.tray_icon = str(get("trayIcon", prefs.tray_icon))
            prefs.minimize_to_tray = bool(get("minimizeToTray", prefs.minimize_to_tray))
            prefs.close_to_tray = bool(get("closeToTray", prefs.close_to_tray))
            prefs.tray_quick_launch = bool(get("trayQuickLaunch", prefs.tray_quick_launch))
            prefs.tray_quick_count = max(
                1, min(10, int(get("trayQuickCount", prefs.tray_quick_count)))
            )
            prefs.sgdb_api_key = str(get("sgdbApiKey", prefs.sgdb_api_key))
            lang = str(get("language", prefs.language)).strip() or "system"
            prefs.language = lang
            prefs.prefix_base = str(get("prefixBase", prefs.prefix_base)).strip()
            prefs.wine_binary = str(get("wineBinary", prefs.wine_binary)).strip()
            prefs.proton_dirs = str(get("protonDirs", prefs.proton_dirs)).strip()
            prefs.dxvk_dirs = str(get("dxvkDirs", prefs.dxvk_dirs)).strip()
            prefs.vkd3d_dirs = str(get("vkd3dDirs", prefs.vkd3d_dirs)).strip()
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
        """Enter in a dialog: the popup's accept button, else the named one.

        The widgets QDialogs sent Enter to their default button, and an
        open modal QMessageBox took it first. QML buttons ignore Enter, so
        each dialog body calls this from its `Keys.onReturnPressed` (a
        window `Shortcut` would steal the key from an editable TextArea,
        which has to keep it). `names` lists the dialog's default buttons
        in priority order; the first visible, enabled one fires — the
        settings window uses that to make Save & Launch the default in
        launch mode, while a combo page keeps Enter on its own Import.
        """
        try:
            opened = _opened_popups(window)
            target = _highlighted_button(opened[-1]) if opened else None
            if target is None:
                for name in names or ():
                    candidate = window.findChild(QObject, str(name))
                    if candidate is None:
                        continue
                    if candidate.property("visible") and candidate.property("enabled"):
                        target = candidate
                        break
            if target is not None:
                QMetaObject.invokeMethod(target, "clicked")
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
                if not appid.isdigit():
                    log.warning("play refused: not a Steam App ID: %s", appid)
                    self.launchReported.emit(False, kind, self._display_name(appid), "")
                    return False
                from PySide6.QtCore import QUrl
                from PySide6.QtGui import QDesktopServices

                launchermod.plant_menu_skip(appid)
                ok = bool(QDesktopServices.openUrl(QUrl(f"steam://rungameid/{appid}")))
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
        "gameSource",
        "gameLastPlayed",
        "gamePlatform",
        "gameRunner",
        "gameWine",
        "gameInstallDir",
        "gameCategory",
    )
    COLUMN_TITLES = {
        "#": "#",
        "gameName": "Game",
        "gameId": "App ID",
        "gamePlayed": "Played",
        "gameTier": "ProtonDB",
        "gameSource": "Source",
        "gameLastPlayed": "Last Played",
        "gamePlatform": "Platform",
        "gameRunner": "Runner",
        "gameWine": "Wine",
        "gameInstallDir": "Install Dir",
        "gameCategory": "Category",
    }
    _COLUMN_ROLES = (
        None,
        "gameName",
        "gameId",
        "gamePlayed",
        "gameTier",
        "gameSource",
        "gameLastPlayed",
        "gamePlatform",
        "gameRunner",
        "gameWine",
        "gameInstallDir",
        "gameCategory",
    )

    #: Fresh/hidden-by-default library columns (Last Played shows).
    _DEFAULT_HIDDEN = frozenset({7, 8, 9, 10, 11})

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
        try:
            order = [int(x) for x in cfgmod.load_preferences().column_order.split(",")]
        except Exception:
            order = []
        try:
            hidden = {int(x) for x in cfgmod.load_preferences().hidden_columns.split(",")}
        except Exception:
            hidden = set()
        if sorted(order) != [0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11]:
            # Old/short orders reset (no migration shims); keep the old
            # hides, new library columns stay hidden except Last Played.
            order = [0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11]
            hidden = (hidden & {1, 2, 3, 4, 5}) | set(GameFilterModel._DEFAULT_HIDDEN)
        return order, {h for h in hidden if h in (1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11)}

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
            if 0 <= logical <= 11 and 20 <= width <= 2000:
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
        if logical not in (1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11) or not 20 <= width <= 2000:
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
        if logical not in (0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11):
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
        for logical in (1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11):
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
                6: GameListModel.LastPlayedRole,
                7: GameListModel.PlatformRole,
                8: GameListModel.RunnerRole,
                9: GameListModel.WineRole,
                10: GameListModel.InstallDirRole,
                11: GameListModel.CategoryRole,
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
        self._order = [0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11]
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
        "showSource": 5,
        "showLastPlayed": 6,
        "showPlatform": 7,
        "showRunner": 8,
        "showWine": 9,
        "showInstallDir": 10,
        "showCategory": 11,
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

    def _get_showLastPlayed(self) -> bool:
        return self._get_flag("showLastPlayed")

    def _set_showLastPlayed(self, value: bool) -> None:
        self._set_flag("showLastPlayed", value)

    def _get_showPlatform(self) -> bool:
        return self._get_flag("showPlatform")

    def _set_showPlatform(self, value: bool) -> None:
        self._set_flag("showPlatform", value)

    def _get_showRunner(self) -> bool:
        return self._get_flag("showRunner")

    def _set_showRunner(self, value: bool) -> None:
        self._set_flag("showRunner", value)

    def _get_showWine(self) -> bool:
        return self._get_flag("showWine")

    def _set_showWine(self, value: bool) -> None:
        self._set_flag("showWine", value)

    def _get_showInstallDir(self) -> bool:
        return self._get_flag("showInstallDir")

    def _set_showInstallDir(self, value: bool) -> None:
        self._set_flag("showInstallDir", value)

    def _get_showCategory(self) -> bool:
        return self._get_flag("showCategory")

    def _set_showCategory(self, value: bool) -> None:
        self._set_flag("showCategory", value)

    showAppId = Property(bool, _get_showAppId, _set_showAppId, notify=columnsChanged)
    showPlayed = Property(bool, _get_showPlayed, _set_showPlayed, notify=columnsChanged)
    showTier = Property(bool, _get_showTier, _set_showTier, notify=columnsChanged)
    showSource = Property(bool, _get_showSource, _set_showSource, notify=columnsChanged)
    showLastPlayed = Property(bool, _get_showLastPlayed, _set_showLastPlayed, notify=columnsChanged)
    showPlatform = Property(bool, _get_showPlatform, _set_showPlatform, notify=columnsChanged)
    showRunner = Property(bool, _get_showRunner, _set_showRunner, notify=columnsChanged)
    showWine = Property(bool, _get_showWine, _set_showWine, notify=columnsChanged)
    showInstallDir = Property(bool, _get_showInstallDir, _set_showInstallDir, notify=columnsChanged)
    showCategory = Property(bool, _get_showCategory, _set_showCategory, notify=columnsChanged)

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
        return steammod.is_steam_id(str(appid)) == (self._source == "steam")

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
        return self._category in [c.strip() for c in cats.split(",")]
