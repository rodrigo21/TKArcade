"""ludusavi integration (simple level: CLI delegation only).

Uses `ludusavi wrap` as the game invocation: it restores before launch and
backs up after exit. NOTE: `backup`/`restore` subcommands do NOT accept
`--infer` (only `wrap` does), and game names there are positional, so the
split approach cannot address games by Steam AppID. `wrap` supports both
`--infer steam` and `--name`, plus `--no-restore`/`--no-backup` for the
independent toggles.
"""
from __future__ import annotations

import logging
import subprocess

from . import is_flatpak_path, which

log = logging.getLogger("tksteamlaunch.ludusavi")


def find() -> tuple[str | None, str | None]:
    """Return (path, warning). Warning set for flatpak builds."""
    path = which("ludusavi")
    if not path:
        return None, "ludusavi not found in PATH"
    if is_flatpak_path(path):
        return path, "flatpak ludusavi may not see Proton prefixes; prefer standalone binary"
    try:
        r = subprocess.run(
            ["flatpak", "info", "com.github.mtkennerly.ludusavi"],
            capture_output=True, timeout=5,
        )
        if r.returncode == 0 and path.endswith("ludusavi"):
            # heuristic only; real check is path-based
            pass
    except Exception:  # noqa: BLE001
        pass
    # generic flatpak binary wrapper detection
    if "flatpak" in (path or ""):
        return path, "flatpak ludusavi may not see Proton prefixes; prefer standalone binary"
    return path, None


def wrap_command(
    game_cmd: list[str],
    *,
    name_override: str = "",
    enabled: bool = False,
    restore: bool = True,
    backup: bool = True,
    use_gui: bool = True,
) -> tuple[list[str], list[str]]:
    """Wrap game_cmd with `ludusavi wrap`.

    Returns (new_cmd, warnings). new_cmd == game_cmd unchanged when ludusavi
    is off (enabled=False, or neither restore nor backup). When enabled but
    the binary is missing, returns game_cmd + warning.
    """
    warnings: list[str] = []
    if not enabled or (not restore and not backup):
        return list(game_cmd), warnings
    path, warn = find()
    if warn:
        warnings.append(warn)
    if not path:
        return list(game_cmd), warnings
    cmd = [path, "wrap"]
    if (name_override or "").strip():
        cmd += ["--name", name_override.strip()]
    else:
        cmd += ["--infer", "steam"]
    if not restore:
        cmd += ["--no-restore"]
    if not backup:
        cmd += ["--no-backup"]
    if use_gui:
        cmd += ["--gui"]
    cmd += ["--", *game_cmd]
    return cmd, warnings
