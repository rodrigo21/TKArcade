"""Per-game TOML config model + XDG load/save (stdlib only).

Snapshot semantics: each games/<appid>.toml stores the game's complete
config. defaults.toml is only a template, copied when a new game is added
or when a game is reset — editing defaults never changes existing games.
Games without a file fall back to the defaults template at load time.
"""

from __future__ import annotations

import copy
import logging
import re
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


class GameType(StrEnum):
    AUTO = "auto"
    PROTON = "proton"
    NATIVE = "native"


@dataclass
class GeneralConfig:
    appid: str = ""
    custom_executable: str = ""
    game_type: str = "auto"  # auto|proton|native
    custom_prefix: str = ""  # e.g. "zink-run", innermost command wrapper


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
class NotificationsConfig:
    notify_on_launch: bool = True


@dataclass
class NotesConfig:
    text: str = ""


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
    notifications: NotificationsConfig = field(default_factory=NotificationsConfig)
    notes: NotesConfig = field(default_factory=NotesConfig)
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
        "general": _to_toml_value(cfg.general),
        "env": {"vars": dict(cfg.env.vars)},
        "pre_post": _to_toml_value(cfg.pre_post),
        "gamemode": _to_toml_value(cfg.gamemode),
        "gamescope": _to_toml_value(cfg.gamescope),
        "mangohud": _to_toml_value(cfg.mangohud),
        "ludusavi": _to_toml_value(cfg.ludusavi),
        "nightlight": _to_toml_value(cfg.nightlight),
        "notifications": _to_toml_value(cfg.notifications),
        "notes": _to_toml_value(cfg.notes),
    }
    for section, keys in cfg.extra.items():
        if section in data and isinstance(data[section], dict):
            for k, v in keys.items():
                if k not in data[section]:
                    data[section][k] = v
        else:
            data[section] = dict(keys)
    return data


def _fmt_value(v: object) -> str:
    if isinstance(v, bool):
        return "true" if v else "false"
    if isinstance(v, (int, float)):
        return str(v)
    if isinstance(v, list):
        return "[" + ", ".join(_fmt_value(x) for x in v) + "]"
    if isinstance(v, dict):
        items = ", ".join(f'"{k}" = {_fmt_value(v2)}' for k, v2 in v.items())
        return "{ " + items + " }"
    s = str(v).replace("\\", "\\\\").replace('"', '\\"').replace("\n", "\\n")
    return f'"{s}"'


def _render_toml(data: dict) -> str:
    """Minimal TOML writer (avoid extra deps)."""
    lines: list[str] = []
    for section, body in data.items():
        lines.append(f"[{section}]")
        for key, val in body.items():
            lines.append(f"{key} = {_fmt_value(val)}")
        lines.append("")
    return "\n".join(lines)


def game_file(appid: str) -> Path:
    """Config path for an AppID. The stem is sanitized so crafted AppIDs
    (e.g. from manual GUI input) cannot escape games_dir()."""
    return xdg.games_dir() / f"{_safe_stem(appid)}.toml"


def _safe_stem(name: str) -> str:
    return re.sub(r"[^A-Za-z0-9._-]", "_", name).strip("._") or "unknown"


def profiles_dir(appid: str = "") -> Path:
    """Profiles base dir, or per-game dir when appid is given."""
    base = xdg.app_config_dir() / "profiles"
    return base / _safe_stem(appid) if appid else base


def list_profiles(appid: str) -> list[str]:
    d = profiles_dir(appid)
    if not d.exists():
        return []
    return [p.stem for p in sorted(d.glob("*.toml"))]


def _profile_file(appid: str, name: str) -> Path:
    return profiles_dir(appid) / f"{_safe_stem(name)}.toml"


def load_profile(appid: str, name: str) -> GameConfig:
    """Load a profile snapshot (falls back to defaults template)."""
    cfg = GameConfig()
    cfg.general.appid = appid
    return _build(_read_toml(_profile_file(appid, name)), cfg)


def save_profile(appid: str, name: str, cfg: GameConfig) -> Path:
    """Save cfg as a named profile snapshot."""
    path = _profile_file(appid, name)
    path.parent.mkdir(parents=True, exist_ok=True)
    data = to_toml_dict(cfg)
    data.setdefault("general", {})["appid"] = appid
    path.write_text(_render_toml(data), encoding="utf-8")
    return path


def delete_profile(appid: str, name: str) -> None:
    _profile_file(appid, name).unlink(missing_ok=True)


def _read_toml(path: Path) -> dict:
    if not path.exists():
        return {}
    try:
        with path.open("rb") as f:
            data = tomllib.load(f)
    except tomllib.TOMLDecodeError as e:
        log.warning("ignoring invalid TOML %s: %s", path, e)
        return {}
    return data if isinstance(data, dict) else {}


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
    path.parent.mkdir(parents=True, exist_ok=True)
    data = to_toml_dict(cfg)
    data.get("general", {}).pop("appid", None)
    path.write_text(_render_toml(data), encoding="utf-8")
    return path


# Single source of truth for known sections/keys (load, save, extra).
SECTION_KEYS: dict[str, set[str]] = {
    "general": {"appid", "custom_executable", "game_type", "custom_prefix"},
    "env": {"vars"},
    "pre_post": {"pre_command", "pre_args", "post_command", "post_args", "timeout", "run_in_shell"},
    "gamemode": {"feral_gamemode", "cachyos_game_performance"},
    "gamescope": {"enable", "args"},
    "mangohud": {"enable", "args", "config_file"},
    "ludusavi": {"enable", "restore", "backup", "name_override", "use_gui"},
    "nightlight": {"disable_during_game", "provider"},
    "notifications": {"notify_on_launch"},
    "notes": {"text"},
}


def _section_known_keys(section: str) -> set[str]:
    return SECTION_KEYS.get(section, set())


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


def _str_list(value: object) -> list[str]:
    return [str(x) for x in value] if isinstance(value, (list, tuple)) else []


def _build(data: dict, cfg: GameConfig) -> GameConfig:
    _collect_extra(data, cfg.extra)

    g = _section(data, "general")
    cfg.general.custom_executable = str(g.get("custom_executable", ""))
    cfg.general.game_type = str(g.get("game_type", "auto"))
    cfg.general.custom_prefix = str(g.get("custom_prefix", ""))
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
    cfg.pre_post.run_in_shell = bool(p.get("run_in_shell", False))
    gm = _section(data, "gamemode")
    cfg.gamemode.feral_gamemode = bool(gm.get("feral_gamemode", False))
    cfg.gamemode.cachyos_game_performance = bool(gm.get("cachyos_game_performance", False))
    gs = _section(data, "gamescope")
    cfg.gamescope.enable = bool(gs.get("enable", False))
    cfg.gamescope.args = str(gs.get("args", ""))
    mh = _section(data, "mangohud")
    cfg.mangohud.enable = bool(mh.get("enable", False))
    cfg.mangohud.args = str(mh.get("args", ""))
    cfg.mangohud.config_file = str(mh.get("config_file", ""))
    cfg.ludusavi = _load_ludusavi(data.get("ludusavi", {}), cfg.extra)
    nl = _section(data, "nightlight")
    cfg.nightlight.disable_during_game = bool(nl.get("disable_during_game", False))
    cfg.nightlight.provider = str(nl.get("provider", "auto"))
    nt = _section(data, "notifications")
    cfg.notifications.notify_on_launch = bool(nt.get("notify_on_launch", True))
    cfg.notes.text = str(_section(data, "notes").get("text", ""))
    return cfg


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


def _load_ludusavi(raw: dict, extra: dict) -> LudusaviConfig:
    """Load ludusavi section (current keys only; unknown kept in extra[])."""
    out = LudusaviConfig()
    if not isinstance(raw, dict):
        return out
    out.enable = bool(raw.get("enable", False))
    out.restore = bool(raw.get("restore", True))
    out.backup = bool(raw.get("backup", True))
    out.use_gui = bool(raw.get("use_gui", True))
    out.name_override = str(raw.get("name_override", ""))

    rest = {k: v for k, v in raw.items() if k not in _section_known_keys("ludusavi")}
    if rest:
        extra.setdefault("ludusavi", {}).update(rest)
    return out


def save(cfg: GameConfig) -> Path:
    """Save a game's complete config snapshot."""
    path = game_file(cfg.general.appid or "unknown")
    path.parent.mkdir(parents=True, exist_ok=True)
    data = to_toml_dict(cfg)
    data.setdefault("general", {})["appid"] = cfg.general.appid
    path.write_text(_render_toml(data), encoding="utf-8")
    return path


def list_appids() -> list[str]:
    d = xdg.games_dir()
    if not d.exists():
        return []
    return [p.stem for p in sorted(d.glob("*.toml"))]


def export_configs(dest: str | Path) -> Path:
    """Pack games/*.toml + defaults.toml into a tar.gz for migration."""
    import tarfile

    dest = Path(dest)
    if not dest.suffixes[-2:] == [".tar", ".gz"]:
        dest = dest.with_suffix(".tar.gz") if dest.suffix != ".gz" else dest
    with tarfile.open(dest, "w:gz") as tar:
        defaults = xdg.defaults_file()
        if defaults.exists():
            tar.add(defaults, arcname="defaults.toml")
        games = xdg.games_dir()
        if games.exists():
            for path in sorted(games.glob("*.toml")):
                tar.add(path, arcname=f"games/{path.name}")
    return dest


def import_configs(src: str | Path) -> list[str]:
    """Restore an export tarball. Only games/*.toml + defaults.toml accepted.

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
            if name == "defaults.toml" or (
                name.startswith("games/")
                and name.endswith(".toml")
                and "/" not in name[len("games/") :]
            ):
                members.append(member)
        if not members:
            raise ValueError("archive contains no TKSteamLaunch configs")
        tar.extractall(path=base, members=members, filter="data")
    return sorted(Path(m.name).stem for m in members if m.name.startswith("games/"))
