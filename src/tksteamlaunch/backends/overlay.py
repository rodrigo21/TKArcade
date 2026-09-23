"""gamescope / mangohud prefix builders."""
from __future__ import annotations

import logging
import os
from pathlib import Path

from .. import xdg
from . import split_args, which

log = logging.getLogger("tksteamlaunch.overlay")

DEFAULT_MANGOHUD_CONF = "MangoHud.conf"


def mangohud_config_dir() -> Path:
    return xdg.config_home() / "MangoHud"


def list_mangohud_configs() -> list[str]:
    """Return sorted *.conf filenames in the MangoHud config dir."""
    d = mangohud_config_dir()
    try:
        return sorted(p.name for p in d.glob("*.conf") if p.is_file())
    except Exception:  # noqa: BLE001
        return []


def mangohud_config_path(name: str) -> Path | None:
    """Resolve a config filename to an existing absolute path."""
    name = (name or "").strip()
    if not name:
        return None
    cand = mangohud_config_dir() / Path(name).name  # stay inside the dir
    try:
        return cand if cand.is_file() else None
    except Exception:  # noqa: BLE001
        return None


def mangohud_env(config_file: str) -> tuple[dict[str, str], list[str]]:
    """Return (env overrides, warnings) for the selected MangoHud config."""
    if not (config_file or "").strip():
        return {}, []
    path = mangohud_config_path(config_file)
    if path is None:
        return {}, [f"MangoHud config '{config_file}' not found, using default"]
    return {"MANGOHUD_CONFIGFILE": os.fspath(path)}, []


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
