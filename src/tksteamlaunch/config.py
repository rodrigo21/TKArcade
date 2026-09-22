"""Per-game TOML config model + XDG load/save (stdlib only)."""
from __future__ import annotations

import tomllib
from dataclasses import asdict, dataclass, field
from pathlib import Path

from . import xdg


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
    enable_restore: bool = False
    enable_backup: bool = False
    name_override: str = ""
    use_gui_progress: bool = True


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

    @property
    def appid(self) -> str:
        return self.general.appid


def _to_toml_value(obj) -> dict:
    return asdict(obj)


def to_toml_dict(cfg: GameConfig) -> dict:
    return {
        "general": _to_toml_value(cfg.general),
        "env": {"vars": dict(cfg.env.vars)},
        "pre_post": _to_toml_value(cfg.pre_post),
        "gamemode": _to_toml_value(cfg.gamemode),
        "gamescope": _to_toml_value(cfg.gamescope),
        "mangohud": _to_toml_value(cfg.mangohud),
        "ludusavi": _to_toml_value(cfg.ludusavi),
        "nightlight": _to_toml_value(cfg.nightlight),
    }


def _render_toml(data: dict) -> str:
    """Minimal TOML writer (avoid extra deps). Handles str/bool/int/list/dict."""
    lines: list[str] = []

    def fmt_scalar(v) -> str:
        if isinstance(v, bool):
            return "true" if v else "false"
        if isinstance(v, int):
            return str(v)
        s = str(v).replace("\\", "\\\\").replace('"', '\\"')
        return f'"{s}"'

    def fmt_list(v: list) -> str:
        return "[" + ", ".join(fmt_scalar(x) for x in v) + "]"

    for section, body in data.items():
        lines.append(f"[{section}]")
        for key, val in body.items():
            if isinstance(val, dict):
                # inline table, used for env.vars
                items = ", ".join(
                    f"{fmt_scalar(k)} = {fmt_scalar(v2)}" for k, v2 in val.items()
                )
                lines.append(f"{key} = {{ {items} }}")
            elif isinstance(val, list):
                lines.append(f"{key} = {fmt_list(val)}")
            else:
                lines.append(f"{key} = {fmt_scalar(val)}")
        lines.append("")
    return "\n".join(lines)


def game_file(appid: str) -> Path:
    return xdg.games_dir() / f"{appid}.toml"


def load(appid: str) -> GameConfig:
    path = game_file(appid)
    cfg = GameConfig()
    cfg.general.appid = appid
    if not path.exists():
        return cfg
    with path.open("rb") as f:
        data = tomllib.load(f)
    g = data.get("general", {})
    cfg.general.custom_executable = str(g.get("custom_executable", ""))
    e = data.get("env", {})
    raw_vars = e.get("vars", {})
    cfg.env.vars = {str(k): str(v) for k, v in dict(raw_vars).items()}
    p = data.get("pre_post", {})
    cfg.pre_post.pre_command = str(p.get("pre_command", ""))
    cfg.pre_post.pre_args = [str(x) for x in p.get("pre_args", [])]
    cfg.pre_post.post_command = str(p.get("post_command", ""))
    cfg.pre_post.post_args = [str(x) for x in p.get("post_args", [])]
    cfg.pre_post.timeout = int(p.get("timeout", 60))
    cfg.pre_post.run_in_shell = bool(p.get("run_in_shell", False))
    gm = data.get("gamemode", {})
    cfg.gamemode.feral_gamemode = bool(gm.get("feral_gamemode", False))
    cfg.gamemode.cachyos_game_performance = bool(gm.get("cachyos_game_performance", False))
    gs = data.get("gamescope", {})
    cfg.gamescope.enable = bool(gs.get("enable", False))
    cfg.gamescope.args = str(gs.get("args", ""))
    mh = data.get("mangohud", {})
    cfg.mangohud.enable = bool(mh.get("enable", False))
    cfg.mangohud.args = str(mh.get("args", ""))
    lu = data.get("ludusavi", {})
    cfg.ludusavi.enable_restore = bool(lu.get("enable_restore", False))
    cfg.ludusavi.enable_backup = bool(lu.get("enable_backup", False))
    cfg.ludusavi.name_override = str(lu.get("name_override", ""))
    cfg.ludusavi.use_gui_progress = bool(lu.get("use_gui_progress", True))
    nl = data.get("nightlight", {})
    cfg.nightlight.disable_during_game = bool(nl.get("disable_during_game", False))
    cfg.nightlight.provider = str(nl.get("provider", "auto"))
    return cfg


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
