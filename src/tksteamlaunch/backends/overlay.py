"""gamescope / mangohud prefix builders."""
from __future__ import annotations

import os
from pathlib import Path

from .. import xdg
from . import split_args, which

DEFAULT_MANGOHUD_CONF = "MangoHud.conf"

GAMESCOPE_PRESETS: dict[str, str] = {
    "1080p 144Hz Fullscreen": "-f -W 1920 -H 1080 -r 144",
    "1440p 165Hz Fullscreen": "-f -W 2560 -H 1440 -r 165",
    "4K 60Hz Fullscreen": "-f -W 3840 -H 2160 -r 60",
    "Borderless Windowed": "-b -W 1920 -H 1080",
    "Steam Deck 1280x800": "-f -W 1280 -H 800 -r 60",
}

MANGOHUD_TEMPLATES: dict[str, str] = {
    "minimal": "# Minimal MangoHud overlay\nfps\nframetime\n",
    "fps-cap": "# FPS limiter overlay\nfps_limit=60\nfps\nframetime\n",
    "full": (
        "# Full metrics overlay\nfps\nframetime\nframe_timing\n"
        "cpu_stats\ngpu_stats\nram\nvram\n"
    ),
}


def mangohud_config_dir() -> Path:
    return xdg.config_home() / "MangoHud"


def list_mangohud_configs() -> list[str]:
    """Return sorted *.conf filenames in the MangoHud config dir."""
    d = mangohud_config_dir()
    try:
        return sorted(p.name for p in d.glob("*.conf") if p.is_file())
    except Exception:
        return []


def mangohud_config_path(name: str) -> Path | None:
    """Resolve a config filename to an existing absolute path."""
    name = (name or "").strip()
    if not name:
        return None
    cand = mangohud_config_dir() / Path(name).name  # stay inside the dir
    try:
        return cand if cand.is_file() else None
    except Exception:
        return None


def mangohud_env(config_file: str) -> tuple[dict[str, str], list[str]]:
    """Return (env overrides, warnings) for the selected MangoHud config."""
    if not (config_file or "").strip():
        return {}, []
    path = mangohud_config_path(config_file)
    if path is None:
        return {}, [f"MangoHud config '{config_file}' not found, using default"]
    return {"MANGOHUD_CONFIGFILE": os.fspath(path)}, []


def create_mangohud_config(name: str, template: str = "default") -> tuple[Path | None, str, str]:
    """Create a new MangoHud config file. Returns (path, source, error).

    The new file copies the default (MangoHud.conf) with template="default",
    uses a starter template ("minimal", "fps-cap", "full") or an "empty"
    file. The name is sanitized to stay inside the config dir. source is
    one of default/minimal/fps-cap/full/empty/exists; error is '' on success.
    """
    clean = Path((name or "").strip()).name
    if not clean:
        return None, "", "empty file name"
    if not clean.endswith(".conf"):
        clean += ".conf"
    d = mangohud_config_dir()
    try:
        d.mkdir(parents=True, exist_ok=True)
    except Exception as e:
        return None, "", f"Could not create {d}: {e}"
    path = d / clean
    if path.exists():
        return path, "exists", ""
    try:
        if template in MANGOHUD_TEMPLATES:
            path.write_text(MANGOHUD_TEMPLATES[template], encoding="utf-8")
            return path, template, ""
        if template == "empty":
            path.write_text("# MangoHud configuration\n", encoding="utf-8")
            return path, "empty", ""
        default = d / DEFAULT_MANGOHUD_CONF
        if default.is_file():
            path.write_bytes(default.read_bytes())
            return path, "default", ""
        path.write_text("# MangoHud configuration\n", encoding="utf-8")
        return path, "empty", ""
    except Exception as e:
        return None, "", f"Could not write {path}: {e}"


def apply_mangohud(cmd: list[str], enable: bool, args: str) -> tuple[list[str], list[str]]:
    warnings: list[str] = []
    if not enable:
        return cmd, warnings
    if not which("mangohud"):
        return cmd, ["mangohud not found, skipping MangoHud"]
    return ["mangohud", *split_args(args), *cmd], warnings


def apply_gamescope(cmd: list[str], enable: bool, args: str) -> tuple[list[str], list[str]]:
    warnings: list[str] = []
    if not enable:
        return cmd, warnings
    if not which("gamescope"):
        return cmd, ["gamescope not found, skipping gamescope"]
    return ["gamescope", *split_args(args), "--", *cmd], warnings
