"""Per-game TOML config model + XDG load/save (stdlib only)."""
from __future__ import annotations

import logging
import tomllib
from dataclasses import asdict, dataclass, field
from pathlib import Path

from . import xdg

log = logging.getLogger("tksteamlaunch.config")

# Legacy ludusavi keys (pre-wrap schema) auto-migrated on load.
_LEGACY_LUDUSAVI = {
    "enable_restore": "restore",
    "enable_backup": "backup",
    "use_gui_progress": "use_gui",
}


@dataclass
class GeneralConfig:
    appid: str = ""
    custom_executable: str = ""


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
    provider: str = "auto"  # auto|kde|gnome|off


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
    return xdg.games_dir() / f"{appid}.toml"


def _split_known(raw: dict, known: set[str]) -> tuple[dict, dict]:
    have = {k: raw[k] for k in known if k in raw}
    rest = {k: raw[k] for k in raw if k not in known}
    return have, rest


def load(appid: str) -> GameConfig:
    path = game_file(appid)
    cfg = GameConfig()
    cfg.general.appid = appid
    if not path.exists():
        return cfg
    with path.open("rb") as f:
        data = tomllib.load(f)

    known_sections = {
        "general", "env", "pre_post", "gamemode",
        "gamescope", "mangohud", "ludusavi", "nightlight",
    }
    for section, body in data.items():
        if section not in known_sections or not isinstance(body, dict):
            cfg.extra.setdefault(section, {}).update(body if isinstance(body, dict) else {})
            continue
        if section != "ludusavi":
            rest = {k: v for k, v in body.items() if k not in _section_known_keys(section)}
            if rest:
                cfg.extra.setdefault(section, {}).update(rest)

    g, _ = _split_known(data.get("general", {}), {"appid", "custom_executable"})
    cfg.general.custom_executable = str(g.get("custom_executable", ""))
    e = data.get("env", {})
    raw_vars = e.get("vars", {})
    cfg.env.vars = {str(k): str(v) for k, v in dict(raw_vars).items()}
    p, _ = _split_known(
        data.get("pre_post", {}),
        {"pre_command", "pre_args", "post_command", "post_args", "timeout", "run_in_shell"},
    )
    cfg.pre_post.pre_command = str(p.get("pre_command", ""))
    cfg.pre_post.pre_args = [str(x) for x in p.get("pre_args", [])]
    cfg.pre_post.post_command = str(p.get("post_command", ""))
    cfg.pre_post.post_args = [str(x) for x in p.get("post_args", [])]
    cfg.pre_post.timeout = int(p.get("timeout", 60))
    cfg.pre_post.run_in_shell = bool(p.get("run_in_shell", False))
    gm, _ = _split_known(data.get("gamemode", {}), {"feral_gamemode", "cachyos_game_performance"})
    cfg.gamemode.feral_gamemode = bool(gm.get("feral_gamemode", False))
    cfg.gamemode.cachyos_game_performance = bool(gm.get("cachyos_game_performance", False))
    gs, _ = _split_known(data.get("gamescope", {}), {"enable", "args"})
    cfg.gamescope.enable = bool(gs.get("enable", False))
    cfg.gamescope.args = str(gs.get("args", ""))
    mh, _ = _split_known(data.get("mangohud", {}), {"enable", "args"})
    cfg.mangohud.enable = bool(mh.get("enable", False))
    cfg.mangohud.args = str(mh.get("args", ""))
    cfg.ludusavi = _load_ludusavi(data.get("ludusavi", {}), cfg.extra)
    nl, _ = _split_known(data.get("nightlight", {}), {"disable_during_game", "provider"})
    cfg.nightlight.disable_during_game = bool(nl.get("disable_during_game", False))
    cfg.nightlight.provider = str(nl.get("provider", "auto"))
    return cfg


def _section_known_keys(section: str) -> set[str]:
    return {
        "general": {"appid", "custom_executable"},
        "env": {"vars"},
        "pre_post": {"pre_command", "pre_args", "post_command", "post_args", "timeout", "run_in_shell"},
        "gamemode": {"feral_gamemode", "cachyos_game_performance"},
        "gamescope": {"enable", "args"},
        "mangohud": {"enable", "args"},
        "ludusavi": {"enable", "restore", "backup", "name_override", "use_gui"},
        "nightlight": {"disable_during_game", "provider"},
    }.get(section, set())


def _load_ludusavi(raw: dict, extra: dict) -> LudusaviConfig:
    """Load ludusavi section with legacy-key migration.

    Legacy keys (enable_restore/enable_backup/use_gui_progress) are honored
    when the new equivalents are absent, so old files keep working. Anything
    else unknown is preserved verbatim in extra[] for round-trip.
    """
    out = LudusaviConfig()
    if not isinstance(raw, dict):
        return out
    migrated: list[str] = []
    for legacy, new in _LEGACY_LUDUSAVI.items():
        if legacy in raw and new not in raw:
            migrated.append(f"{legacy} -> {new}")
    if migrated:
        log.warning("legacy ludusavi keys migrated: %s", ", ".join(migrated))

    def pick(new: str, legacy: str | None, default: bool) -> bool:
        if new in raw:
            return bool(raw[new])
        if legacy and legacy in raw:
            return bool(raw[legacy])
        return default

    out.restore = pick("restore", "enable_restore", True)
    out.backup = pick("backup", "enable_backup", True)
    out.use_gui = pick("use_gui", "use_gui_progress", True)
    if "enable" in raw:
        out.enable = bool(raw["enable"])
    else:
        out.enable = out.restore or out.backup
    out.name_override = str(raw.get("name_override", ""))

    rest = {
        k: v for k, v in raw.items()
        if k not in _section_known_keys("ludusavi") and k not in _LEGACY_LUDUSAVI
    }
    if rest:
        extra.setdefault("ludusavi", {}).update(rest)
    return out


def save(cfg: GameConfig) -> Path:
    path = game_file(cfg.general.appid or "unknown")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(_render_toml(to_toml_dict(cfg)), encoding="utf-8")
    return path


def list_appids() -> list[str]:
    d = xdg.games_dir()
    if not d.exists():
        return []
    out = []
    for p in sorted(d.glob("*.toml")):
        out.append(p.stem)
    return out
