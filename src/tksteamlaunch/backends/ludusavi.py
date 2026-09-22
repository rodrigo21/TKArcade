"""ludusavi integration (simple level: CLI delegation only)."""
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


def build_backup_cmd(name_override: str = "", use_gui: bool = True) -> list[str] | None:
    path, _ = find()
    if not path:
        return None
    cmd = [path, "backup"]
    if (name_override or "").strip():
        cmd += ["--name", name_override.strip()]
    else:
        cmd += ["--infer", "steam"]
    if use_gui:
        cmd += ["--gui"]
    return cmd


def build_restore_cmd(name_override: str = "", use_gui: bool = True) -> list[str] | None:
    path, _ = find()
    if not path:
        return None
    cmd = [path, "restore"]
    if (name_override or "").strip():
        cmd += ["--name", name_override.strip()]
    else:
        cmd += ["--infer", "steam"]
    if use_gui:
        cmd += ["--gui"]
    return cmd


def run(cmd: list[str] | None, what: str) -> int:
    if not cmd:
        log.warning("ludusavi %s skipped (binary not found)", what)
        return -1
    log.info("ludusavi %s: %r", what, cmd)
    try:
        r = subprocess.run(cmd)
        log.info("ludusavi %s exit=%s", what, r.returncode)
        return r.returncode
    except FileNotFoundError:
        log.error("ludusavi binary not found: %r", cmd)
        return -2
    except Exception as e:  # noqa: BLE001
        log.error("ludusavi %s failed: %s", what, e)
        return -2
