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


def create_mangohud_config(name: str) -> tuple[Path | None, str, str]:
    """Create a new MangoHud config file. Returns (path, source, error).

    The new file copies the default (MangoHud.conf) when present, else a
    minimal template. The name is sanitized to stay inside the config dir.
    source is 'default', 'template', or 'exists'; error is '' on success.
    """
    clean = Path((name or "").strip()).name
    if not clean:
        return None, "", "empty file name"
    if not clean.endswith(".conf"):
        clean += ".conf"
    d = mangohud_config_dir()
    try:
        d.mkdir(parents=True, exist_ok=True)
    except Exception as e:  # noqa: BLE001
        return None, "", f"Could not create {d}: {e}"
    path = d / clean
    if path.exists():
        return path, "exists", ""
    default = d / DEFAULT_MANGOHUD_CONF
    try:
        if default.is_file():
            path.write_bytes(default.read_bytes())
            return path, "default", ""
        path.write_text("# MangoHud configuration\n", encoding="utf-8")
        return path, "template", ""
    except Exception as e:  # noqa: BLE001
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
