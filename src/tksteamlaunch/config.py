"""Per-game TOML config model + XDG load/save (stdlib only).

Snapshot semantics: each games/<appid>.toml stores the game's complete
config. defaults.toml is only a template, copied when a new game is added
or when a game is reset — editing defaults never changes existing games.
Games without a file fall back to the defaults template at load time.
"""

from __future__ import annotations

import copy
import logging
import os
import re
import tempfile
import tomllib
from dataclasses import asdict, dataclass, field
from enum import StrEnum
from pathlib import Path

from . import xdg

log = logging.getLogger("tksteamlaunch.config")


class NightlightProvider(StrEnum):
    AUTO = "auto"
    PLASMA = "plasma"
    GNOME = "gnome"
    OFF = "off"


class DisplayProvider(StrEnum):
    AUTO = "auto"
    PLASMA = "plasma"
    GNOME = "gnome"
    WLROOTS = "wlroots"
    X11 = "x11"
    OFF = "off"


class GameType(StrEnum):
    AUTO = "auto"
    PROTON = "proton"
    NATIVE = "native"


@dataclass
class GeneralConfig:
    appid: str = ""
    custom_executable: str = ""
    game_type: str = "auto"  # auto|proton|native
    show_menu: bool = False  # pre-launch menu (also forced by --menu flag)
    menu_timeout: int = 0  # auto-launch countdown in seconds (0 = wait forever)
    custom_prefix: str = ""  # e.g. "zink-run", innermost command wrapper
    active_profile: str = ""  # last used profile (GUI selection memory)


@dataclass
class EnvConfig:
    vars: dict[str, str] = field(default_factory=dict)


@dataclass
class PrePostConfig:
    pre_command: str = ""
    pre_args: list[str] = field(default_factory=list)
    post_command: str = ""
    post_args: list[str] = field(default_factory=list)
    timeout: int = 60
    run_in_shell: bool = False


@dataclass
class GamemodeConfig:
    feral_gamemode: bool = False
    cachyos_game_performance: bool = False


@dataclass
class GamescopeConfig:
    enable: bool = False
    args: str = ""  # e.g. "-f -H 1080 -r 144"


@dataclass
class MangohudConfig:
    enable: bool = False
    args: str = ""
    config_file: str = ""  # filename inside MangoHud config dir, "" = default


@dataclass
class LudusaviConfig:
    enable: bool = False
    restore: bool = True
    backup: bool = True
    name_override: str = ""
    use_gui: bool = True


@dataclass
class NightlightConfig:
    disable_during_game: bool = False
    provider: str = "auto"  # auto|plasma|gnome|off


@dataclass
class DisplayConfig:
    provider: str = "auto"  # auto|plasma|gnome|wlroots|x11|off
    output: str = ""  # empty = current output
    mode: str = ""  # WIDTHxHEIGHT[@RATE]; empty = feature off
    dip_seconds: int = 8  # same-mode dip dwell (VRAM workaround), 3-15


@dataclass
class NotificationsConfig:
    notify_on_launch: bool = True


@dataclass
class NotesConfig:
    text: str = ""


@dataclass
class DebugConfig:
    proton_log: bool = False
    winedebug: str = ""


@dataclass
class SessionConfig:
    inhibit_idle: bool = False


@dataclass
class RtUpscaleConfig:
    enable: bool = False
    args: str = ""


@dataclass
class ProtonConfig:
    fresh_prefix: bool = False
    winetricks_verbs: list[str] = field(default_factory=list)


@dataclass
class Preferences:
    """Program-level preferences (never per-game)."""

    show_preview: bool = True
    tray_enable: bool = False
    tray_icon: str = "normal"  # normal|mono
    minimize_to_tray: bool = False
    close_to_tray: bool = False
    sgdb_api_key: str = ""
    column_order: str = ""  # visual order of logical columns, e.g. "0,1,3,2"
    hidden_columns: str = ""  # hidden logical columns, e.g. "1,3"
    tray_quick_launch: bool = True  # recent games section in the tray menu
    tray_quick_count: int = 5  # recent games shown (1-10)
    language: str = "system"  # system locale, "en" for English, or a locale code


@dataclass
class GameConfig:
    general: GeneralConfig = field(default_factory=GeneralConfig)
    env: EnvConfig = field(default_factory=EnvConfig)
    pre_post: PrePostConfig = field(default_factory=PrePostConfig)
    gamemode: GamemodeConfig = field(default_factory=GamemodeConfig)
    gamescope: GamescopeConfig = field(default_factory=GamescopeConfig)
    mangohud: MangohudConfig = field(default_factory=MangohudConfig)
    ludusavi: LudusaviConfig = field(default_factory=LudusaviConfig)
    nightlight: NightlightConfig = field(default_factory=NightlightConfig)
    display: DisplayConfig = field(default_factory=DisplayConfig)
    notifications: NotificationsConfig = field(default_factory=NotificationsConfig)
    notes: NotesConfig = field(default_factory=NotesConfig)
    debug: DebugConfig = field(default_factory=DebugConfig)
    session: SessionConfig = field(default_factory=SessionConfig)
    proton: ProtonConfig = field(default_factory=ProtonConfig)
    rtupscale: RtUpscaleConfig = field(default_factory=RtUpscaleConfig)
    # Unknown keys preserved per section for forward-compat round-trip:
    # {section: {key: value}}. Written back verbatim on save.
    extra: dict[str, dict[str, object]] = field(default_factory=dict)

    @property
    def appid(self) -> str:
        return self.general.appid


def _to_toml_value(obj) -> dict:
    d = asdict(obj)
    d.pop("extra", None)
    return d


def to_toml_dict(cfg: GameConfig) -> dict:
    data = {
        "general": {"config_version": CONFIG_VERSION, **_to_toml_value(cfg.general)},
        "env": {"vars": dict(cfg.env.vars)},
        "pre_post": _to_toml_value(cfg.pre_post),
        "gamemode": _to_toml_value(cfg.gamemode),
        "gamescope": _to_toml_value(cfg.gamescope),
        "mangohud": _to_toml_value(cfg.mangohud),
        "ludusavi": _to_toml_value(cfg.ludusavi),
        "nightlight": _to_toml_value(cfg.nightlight),
        "display": _to_toml_value(cfg.display),
        "notifications": _to_toml_value(cfg.notifications),
        "notes": _to_toml_value(cfg.notes),
        "debug": _to_toml_value(cfg.debug),
        "session": _to_toml_value(cfg.session),
        "proton": _to_toml_value(cfg.proton),
        "rtupscale": _to_toml_value(cfg.rtupscale),
    }
    for section, keys in cfg.extra.items():
        if section in data and isinstance(data[section], dict):
            for k, v in keys.items():
                if k not in data[section]:
                    data[section][k] = v
        else:
            data[section] = dict(keys)
    return data


_SIMPLE_ESCAPES = {"\b": "\\b", "\t": "\\t", "\n": "\\n", "\f": "\\f", "\r": "\\r"}
_BARE_KEY = re.compile(r"[A-Za-z0-9_-]+")


def _escape_str(s: str) -> str:
    """Escape a Python string as a TOML basic string.

    TOML forbids every control character except a literal tab; without
    this, a pasted CR produced an unreadable file and the next load
    silently fell back to defaults.
    """
    out: list[str] = []
    for ch in s:
        esc = _SIMPLE_ESCAPES.get(ch)
        if esc is not None:
            out.append(esc)
        elif ch in ("\\", '"'):
            out.append("\\" + ch)
        elif ord(ch) < 0x20 or ord(ch) == 0x7F:
            out.append(f"\\u{ord(ch):04X}")
        else:
            out.append(ch)
    return "".join(out)


def _fmt_key(k: object) -> str:
    """Render a key bare when possible, quoted otherwise."""
    key = str(k)
    return key if _BARE_KEY.fullmatch(key) else '"' + _escape_str(key) + '"'


def _fmt_value(v: object) -> str:
    if isinstance(v, bool):
        return "true" if v else "false"
    if isinstance(v, (int, float)):
        return str(v)
    if isinstance(v, list):
        return "[" + ", ".join(_fmt_value(x) for x in v) + "]"
    if isinstance(v, dict):
        items = ", ".join(f'"{_escape_str(str(k))}" = {_fmt_value(v2)}' for k, v2 in v.items())
        return "{ " + items + " }"
    return '"' + _escape_str(str(v)) + '"'


def _render_toml(data: dict) -> str:
    """Minimal TOML writer (avoid extra deps)."""
    lines: list[str] = []
    for section, body in data.items():
        lines.append(f"[{_fmt_key(section)}]")
        for key, val in body.items():
            lines.append(f"{_fmt_key(key)} = {_fmt_value(val)}")
        lines.append("")
    return "\n".join(lines)


def _write_atomic(path: Path, text: str) -> None:
    """Write via temp file + rename so a crash never truncates the config."""
    path.parent.mkdir(parents=True, exist_ok=True)
    for stale in path.parent.glob(f".{path.name}.*.tmp"):
        try:
            stale.unlink()
        except OSError:
            pass  # best effort: leftovers from a previous crash
    fd, tmp = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=path.parent)
    tmp_path = Path(tmp)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(text)
        try:
            os.chmod(tmp, path.stat().st_mode & 0o777)
        except OSError:
            pass  # new file: keep mkstemp's owner-only mode
        os.replace(tmp, path)
    except BaseException:
        tmp_path.unlink(missing_ok=True)
        raise


def game_file(appid: str) -> Path:
    """Config path for an AppID. The stem is sanitized so crafted AppIDs
    (e.g. from manual GUI input) cannot escape games_dir()."""
    return xdg.games_dir() / f"{xdg.safe_stem(appid)}.toml"


def profiles_dir(appid: str = "") -> Path:
    """Profiles base dir, or per-game dir when appid is given."""
    base = xdg.app_config_dir() / "profiles"
    return base / xdg.safe_stem(appid) if appid else base


def list_profiles(appid: str) -> list[str]:
    d = profiles_dir(appid)
    if not d.exists():
        return []
    return [p.stem for p in sorted(d.glob("*.toml"))]


def profile_file(appid: str, name: str) -> Path:
    return profiles_dir(appid) / f"{xdg.safe_stem(name)}.toml"


def load_profile(appid: str, name: str) -> GameConfig:
    """Load a profile snapshot (falls back to defaults template)."""
    cfg = GameConfig()
    cfg.general.appid = appid
    return _build(_read_toml(profile_file(appid, name)), cfg)


def save_profile(appid: str, name: str, cfg: GameConfig) -> Path:
    """Save cfg as a named profile snapshot (selection memory stripped)."""
    path = profile_file(appid, name)
    data = to_toml_dict(cfg)
    data.setdefault("general", {})["appid"] = appid
    data["general"]["active_profile"] = ""
    _write_atomic(path, _render_toml(data))
    return path


def delete_profile(appid: str, name: str) -> None:
    profile_file(appid, name).unlink(missing_ok=True)


def clone_game(src_appid: str, dest_appid: str) -> None:
    """Copy a game's live config plus profiles to another AppID.

    Overwrites the destination (callers confirm first). Raises
    ValueError when the source has nothing saved.
    """
    import shutil

    src, dest = xdg.safe_stem(src_appid), xdg.safe_stem(dest_appid)
    if not src or not dest or src == dest:
        raise ValueError(f"invalid clone: {src_appid!r} -> {dest_appid!r}")
    live = game_file(src)
    if not live.is_file():
        raise ValueError(f"no saved config for {src!r}")
    shutil.copyfile(live, game_file(dest))
    profiles = profiles_dir(src)
    if profiles.is_dir():
        dest_profiles = profiles_dir(dest)
        shutil.rmtree(dest_profiles, ignore_errors=True)
        shutil.copytree(profiles, dest_profiles)


def orphaned_profiles() -> list[tuple[str, int]]:
    """Leftover profiles whose game has no live config: [(appid, count)]."""
    base = profiles_dir()
    if not base.is_dir():
        return []
    live = set(list_appids())
    out = []
    for d in sorted(base.iterdir()):
        if not d.is_dir():
            continue
        count = sum(1 for p in d.glob("*.toml") if p.is_file())
        if count and d.name not in live:
            out.append((d.name, count))
    return out


def _read_toml(path: Path) -> dict:
    if not path.exists():
        return {}
    try:
        with path.open("rb") as f:
            data = tomllib.load(f)
    except tomllib.TOMLDecodeError as e:
        log.warning("ignoring invalid TOML %s: %s", path, e)
        return {}
    except OSError as e:
        log.warning("ignoring unreadable TOML %s: %s", path, e)
        return {}
    return data if isinstance(data, dict) else {}


def toml_error(path: Path) -> str | None:
    """Parse error of an existing config file; None when missing or valid.

    Unreadable files report as errors too (never raises), so GUI callers
    can warn instead of crashing the dialog open.
    """
    if not path.exists():
        return None
    try:
        with path.open("rb") as f:
            tomllib.load(f)
    except OSError as e:
        return f"unreadable: {e}"
    except tomllib.TOMLDecodeError as e:
        return str(e)
    return None


def load_with_warning(appid: str) -> tuple[GameConfig, str | None]:
    """Load a game's config without ever raising on disk errors.

    Returns ``(cfg, warning)``: warning is None when the file parses (or
    is absent — a new game starts from the defaults template); otherwise
    it explains the fallback so callers can surface it instead of silently
    showing defaults that the next save would write over the file.
    """
    path = game_file(appid)
    if not path.exists():
        try:
            cfg = load_defaults()
        except OSError:
            cfg = GameConfig()
        cfg.general.appid = appid
        return cfg, None
    try:
        cfg = load(appid)
    except OSError as e:
        fresh = GameConfig()
        fresh.general.appid = appid
        return fresh, (
            f"The saved settings for this game could not be read: {e}\n"
            "Showing built-in defaults instead. Saving will overwrite the file."
        )
    except ConfigVersionError as e:
        fresh = GameConfig()
        fresh.general.appid = appid
        return fresh, (
            f"The saved settings need a newer TKSteamLaunch ({e}).\n"
            "Showing built-in defaults instead. Saving will overwrite the file."
        )
    err = toml_error(path)
    if err:
        return cfg, (
            "The saved settings for this game could not be read "
            f"(invalid TOML): {err}\n"
            "Showing defaults instead. Saving will overwrite the file."
        )
    return cfg, None


def defaults_dict() -> dict:
    return _read_toml(xdg.defaults_file())


def load_defaults() -> GameConfig:
    """Load the global defaults file as a GameConfig (appid empty)."""
    cfg = GameConfig()
    data = defaults_dict()
    if not data:
        return cfg
    return _build(copy.deepcopy(data), cfg)


def save_defaults(cfg: GameConfig) -> Path:
    """Save the global defaults file (complete values, no appid)."""
    path = xdg.defaults_file()
    data = to_toml_dict(cfg)
    data.get("general", {}).pop("appid", None)
    _write_atomic(path, _render_toml(data))
    return path


# Single source of truth for known sections/keys (load, save, extra).
SECTION_KEYS: dict[str, set[str]] = {
    "general": {
        "appid",
        "config_version",
        "custom_executable",
        "game_type",
        "show_menu",
        "menu_timeout",
        "custom_prefix",
        "active_profile",
    },
    "env": {"vars"},
    "pre_post": {"pre_command", "pre_args", "post_command", "post_args", "timeout", "run_in_shell"},
    "gamemode": {"feral_gamemode", "cachyos_game_performance"},
    "gamescope": {"enable", "args"},
    "mangohud": {"enable", "args", "config_file"},
    "ludusavi": {"enable", "restore", "backup", "name_override", "use_gui"},
    "nightlight": {"disable_during_game", "provider"},
    "display": {"provider", "output", "mode", "dip_seconds"},
    "notifications": {"notify_on_launch"},
    "notes": {"text"},
    "debug": {"proton_log", "winedebug"},
    "session": {"inhibit_idle"},
    "proton": {"fresh_prefix", "winetricks_verbs"},
    "rtupscale": {"enable", "args"},
}


def _section_known_keys(section: str) -> set[str]:
    return SECTION_KEYS.get(section, set())


def _ensure_version(data: dict) -> None:
    """Reject configs newer than this build (loud, never silent)."""
    general = data.get("general", {})
    version = general.get("config_version", 0) if isinstance(general, dict) else 0
    try:
        version = int(version)
    except (TypeError, ValueError):
        return  # malformed stamp: tolerant load, same as unknown keys
    if version > CONFIG_VERSION:
        raise ConfigVersionError(version)


def _collect_extra(data: dict, extra: dict) -> None:
    for section, body in data.items():
        if not isinstance(body, dict):
            continue
        if section == "ludusavi":
            continue  # handled by _load_ludusavi
        if section in SECTION_KEYS:
            rest = {k: v for k, v in body.items() if k not in _section_known_keys(section)}
        else:
            rest = dict(body)
        if rest:
            extra.setdefault(section, {}).update(rest)


def _section(data: dict, name: str) -> dict:
    """Return a section mapping; wrong-shaped values become {} (fresh)."""
    body = data.get(name, {})
    return body if isinstance(body, dict) else {}


def _as_int(value: object, default: int) -> int:
    try:
        return int(value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return default


def _as_bool(value: object, default: bool) -> bool:
    """Tolerant bool: plain bool() misreads "false"/"0" strings as True."""
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return value != 0
    if isinstance(value, str):
        low = value.strip().lower()
        if low in ("1", "true", "yes", "y", "on"):
            return True
        if low in ("0", "false", "no", "n", "off", ""):
            return False
    return default


def _str_list(value: object) -> list[str]:
    return [str(x) for x in value] if isinstance(value, (list, tuple)) else []


class ConfigVersionError(Exception):
    """Config file needs a newer TKSteamLaunch than this one."""

    def __init__(self, version: object) -> None:
        super().__init__(f"config version {version} is newer than supported 1")
        self.version = version


#: Config schema version, stamped on every save. Missing stamp means
#: pre-versioning (treated as current shape). Newer stamps never load
#: silently: callers fall back loudly instead of resetting user data.
CONFIG_VERSION = 1


def _build(data: dict, cfg: GameConfig) -> GameConfig:
    _ensure_version(data)
    _collect_extra(data, cfg.extra)

    g = _section(data, "general")
    cfg.general.custom_executable = str(g.get("custom_executable", ""))
    cfg.general.game_type = str(g.get("game_type", "auto"))
    cfg.general.show_menu = _as_bool(g.get("show_menu", False), False)
    cfg.general.menu_timeout = max(0, _as_int(g.get("menu_timeout", 0), 0))
    cfg.general.custom_prefix = str(g.get("custom_prefix", ""))
    cfg.general.active_profile = str(g.get("active_profile", ""))
    raw_vars = _section(data, "env").get("vars", {})
    cfg.env.vars = (
        {str(k): str(v) for k, v in raw_vars.items()} if isinstance(raw_vars, dict) else {}
    )
    p = _section(data, "pre_post")
    cfg.pre_post.pre_command = str(p.get("pre_command", ""))
    cfg.pre_post.pre_args = _str_list(p.get("pre_args", []))
    cfg.pre_post.post_command = str(p.get("post_command", ""))
    cfg.pre_post.post_args = _str_list(p.get("post_args", []))
    cfg.pre_post.timeout = _as_int(p.get("timeout", 60), 60)
    cfg.pre_post.run_in_shell = _as_bool(p.get("run_in_shell", False), False)
    gm = _section(data, "gamemode")
    cfg.gamemode.feral_gamemode = _as_bool(gm.get("feral_gamemode", False), False)
    cfg.gamemode.cachyos_game_performance = _as_bool(
        gm.get("cachyos_game_performance", False), False
    )
    gs = _section(data, "gamescope")
    cfg.gamescope.enable = _as_bool(gs.get("enable", False), False)
    cfg.gamescope.args = str(gs.get("args", ""))
    mh = _section(data, "mangohud")
    cfg.mangohud.enable = _as_bool(mh.get("enable", False), False)
    cfg.mangohud.args = str(mh.get("args", ""))
    cfg.mangohud.config_file = str(mh.get("config_file", ""))
    cfg.ludusavi = _load_ludusavi(data.get("ludusavi", {}), cfg.extra)
    nl = _section(data, "nightlight")
    cfg.nightlight.disable_during_game = _as_bool(nl.get("disable_during_game", False), False)
    cfg.nightlight.provider = str(nl.get("provider", "auto"))
    dp = _section(data, "display")
    cfg.display.provider = str(dp.get("provider", "auto"))
    cfg.display.output = str(dp.get("output", ""))
    cfg.display.mode = str(dp.get("mode", ""))
    cfg.display.dip_seconds = min(15, max(3, _as_int(dp.get("dip_seconds", 8), 8)))
    nt = _section(data, "notifications")
    cfg.notifications.notify_on_launch = _as_bool(nt.get("notify_on_launch", True), True)
    cfg.notes.text = str(_section(data, "notes").get("text", ""))
    cfg.debug.proton_log = _as_bool(_section(data, "debug").get("proton_log", False), False)
    cfg.debug.winedebug = str(_section(data, "debug").get("winedebug", ""))
    cfg.session.inhibit_idle = _as_bool(_section(data, "session").get("inhibit_idle", False), False)
    cfg.proton.fresh_prefix = _as_bool(_section(data, "proton").get("fresh_prefix", False), False)
    cfg.proton.winetricks_verbs = _str_list(_section(data, "proton").get("winetricks_verbs", []))
    rt = _section(data, "rtupscale")
    cfg.rtupscale.enable = _as_bool(rt.get("enable", False), False)
    cfg.rtupscale.args = str(rt.get("args", ""))
    return cfg


def load_preferences() -> Preferences:
    """Load program preferences (all defaults when the file is missing)."""
    out = Preferences()
    data = _read_toml(xdg.preferences_file())
    ui = data.get("ui", {}) if isinstance(data, dict) else {}
    if not isinstance(ui, dict):
        return out
    out.show_preview = _as_bool(ui.get("show_preview", True), True)
    out.tray_enable = _as_bool(ui.get("tray_enable", False), False)
    out.tray_icon = str(ui.get("tray_icon", "normal") or "normal")
    if out.tray_icon not in ("normal", "mono"):
        out.tray_icon = "normal"
    out.minimize_to_tray = _as_bool(ui.get("minimize_to_tray", False), False)
    out.close_to_tray = _as_bool(ui.get("close_to_tray", False), False)
    out.sgdb_api_key = str(ui.get("sgdb_api_key", "") or "")
    out.column_order = _clean_int_list(str(ui.get("column_order", "") or ""))
    out.hidden_columns = _clean_int_list(str(ui.get("hidden_columns", "") or ""))
    out.tray_quick_launch = _as_bool(ui.get("tray_quick_launch", True), True)
    out.tray_quick_count = _clamp_quick_count(ui.get("tray_quick_count", 5))
    lang = str(ui.get("language", "system") or "system").strip()
    out.language = (
        lang if lang == "system" or re.fullmatch(r"[A-Za-z]+(_[A-Za-z]+)?", lang) else "system"
    )
    if not out.tray_enable:
        out.minimize_to_tray = False
        out.close_to_tray = False
    return out


def _clean_int_list(text: str) -> str:
    """Normalize a comma list to digits-only, preserving order ("" stays "")."""
    return ",".join(p for p in (x.strip() for x in text.split(",")) if p.isdigit())


def _clamp_quick_count(value: object) -> int:
    """Clamp the tray quick-launch count into 1-10 (default 5)."""
    try:
        return min(10, max(1, int(value)))  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return 5


def save_preferences(prefs: Preferences) -> Path:
    """Save program preferences (flat [ui] table)."""
    path = xdg.preferences_file()
    data = {
        "ui": {
            "show_preview": bool(prefs.show_preview),
            "tray_enable": bool(prefs.tray_enable),
            "tray_icon": prefs.tray_icon if prefs.tray_icon in ("normal", "mono") else "normal",
            "minimize_to_tray": bool(prefs.minimize_to_tray),
            "close_to_tray": bool(prefs.close_to_tray),
            "sgdb_api_key": prefs.sgdb_api_key,
            "column_order": _clean_int_list(prefs.column_order),
            "hidden_columns": _clean_int_list(prefs.hidden_columns),
            "tray_quick_launch": bool(prefs.tray_quick_launch),
            "tray_quick_count": _clamp_quick_count(prefs.tray_quick_count),
            "language": prefs.language if isinstance(prefs.language, str) else "system",
        }
    }
    _write_atomic(path, _render_toml(data))
    return path


def load(appid: str) -> GameConfig:
    """Load a game's complete config snapshot.

    Games without a file fall back to the global defaults template (with
    the appid set), so unconfigured games still launch.
    """
    cfg = GameConfig()
    cfg.general.appid = appid
    data = _read_toml(game_file(appid))
    if not data:
        return _build(copy.deepcopy(defaults_dict()), cfg)
    return _build(data, cfg)


def load_effective(appid: str) -> GameConfig:
    """Load the config that should launch: the active profile when set.

    Returns the selected profile's content when live's active_profile
    names an existing, parseable profile; otherwise the live config (with
    a warning logged for dangling/unreadable selections). A dangling
    selection must never resolve to template defaults: the check requires
    the profile file to exist and parse.
    """
    try:
        cfg = load(appid)
    except ConfigVersionError as e:
        log.error("game config needs a newer app (%s); launching built-in defaults", e)
        cfg = GameConfig()
        cfg.general.appid = appid
        return cfg
    name = cfg.general.active_profile
    if not name:
        return cfg
    path = profile_file(appid, name)
    if not path.exists():
        log.warning("profile %r for %s is gone; launching live config", name, appid)
        return cfg
    if toml_error(path) is not None:
        log.warning("profile %r for %s is unreadable; launching live config", name, appid)
        return cfg
    try:
        prof = load_profile(appid, name)
    except ConfigVersionError as e:
        log.error("profile %r for %s needs a newer app (%s); launching live", name, appid, e)
        return cfg
    prof.general.appid = appid
    log.info("launching with profile %r for %s", name, appid)
    return prof


def _load_ludusavi(raw: dict, extra: dict) -> LudusaviConfig:
    """Load ludusavi section (current keys only; unknown kept in extra[])."""
    out = LudusaviConfig()
    if not isinstance(raw, dict):
        return out
    out.enable = _as_bool(raw.get("enable", False), False)
    out.restore = _as_bool(raw.get("restore", True), True)
    out.backup = _as_bool(raw.get("backup", True), True)
    out.use_gui = _as_bool(raw.get("use_gui", True), True)
    out.name_override = str(raw.get("name_override", ""))

    rest = {k: v for k, v in raw.items() if k not in _section_known_keys("ludusavi")}
    if rest:
        extra.setdefault("ludusavi", {}).update(rest)
    return out


def save(cfg: GameConfig) -> Path:
    """Save a game's complete config snapshot."""
    path = game_file(cfg.general.appid or "unknown")
    data = to_toml_dict(cfg)
    data.setdefault("general", {})["appid"] = cfg.general.appid
    _write_atomic(path, _render_toml(data))
    return path


def diff_vs_defaults(cfg: GameConfig) -> str:
    """Unified diff of a game config against global defaults (no appid)."""
    import difflib

    base = to_toml_dict(load_defaults())
    full = to_toml_dict(cfg)
    base.get("general", {}).pop("appid", None)
    full.get("general", {}).pop("appid", None)
    return "\n".join(
        difflib.unified_diff(
            _render_toml(base).splitlines(),
            _render_toml(full).splitlines(),
            "defaults",
            "this game",
            lineterm="",
        )
    )


def list_appids() -> list[str]:
    d = xdg.games_dir()
    if not d.exists():
        return []
    return [p.stem for p in sorted(d.glob("*.toml"))]


def export_configs(dest: str | Path) -> Path:
    """Pack games/profiles/defaults/preferences TOML files for migration."""
    import tarfile

    dest = Path(dest)
    if not dest.suffixes[-2:] == [".tar", ".gz"]:
        dest = dest.with_suffix(".tar.gz") if dest.suffix != ".gz" else dest
    with tarfile.open(dest, "w:gz") as tar:
        defaults = xdg.defaults_file()
        if defaults.exists():
            tar.add(defaults, arcname="defaults.toml")
        preferences = xdg.preferences_file()
        if preferences.exists():
            tar.add(preferences, arcname="preferences.toml")
        games = xdg.games_dir()
        if games.exists():
            for path in sorted(games.glob("*.toml")):
                tar.add(path, arcname=f"games/{path.name}")
        profiles = profiles_dir()
        if profiles.is_dir():
            for path in sorted(profiles.rglob("*.toml")):
                rel = path.relative_to(profiles)
                if len(rel.parts) == 2 and path.is_file():
                    tar.add(path, arcname=f"profiles/{rel.as_posix()}")
    return dest


def import_configs(src: str | Path) -> list[str]:
    """Restore an export tarball. Only known TOML files accepted.

    Returns imported appids. Raises ValueError on invalid archives.
    """
    import tarfile

    src = Path(src)
    if not src.is_file():
        raise ValueError(f"not found: {src}")
    base = xdg.app_config_dir()
    try:
        tar = tarfile.open(src, "r:gz")
    except (tarfile.TarError, OSError) as e:
        raise ValueError(f"invalid archive: {e}") from e
    with tar:
        members = []
        for member in tar.getmembers():
            name = member.name
            if (
                name in ("defaults.toml", "preferences.toml")
                or (
                    name.startswith("games/")
                    and name.endswith(".toml")
                    and "/" not in name[len("games/") :]
                )
                or (
                    name.startswith("profiles/")
                    and name.endswith(".toml")
                    and len(Path(name).parts) == 3
                    and ".." not in Path(name).parts
                    and "." not in Path(name).parts
                )
            ):
                members.append(member)
        if not members:
            raise ValueError("archive contains no TKSteamLaunch configs")
        tar.extractall(path=base, members=members, filter="data")
    return sorted(Path(m.name).stem for m in members if m.name.startswith("games/"))
