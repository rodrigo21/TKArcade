"""Desktop notifications (best-effort via notify-send)."""
from __future__ import annotations

import logging
import os
import shutil
import subprocess

log = logging.getLogger("tksteamlaunch.notify")


def available() -> bool:
    return bool(shutil.which("notify-send")) and bool(
        os.environ.get("DISPLAY") or os.environ.get("WAYLAND_DISPLAY")
    )


def send(
    summary: str,
    body: str = "",
    urgency: str = "normal",
    icon: str = "",
    expire_ms: int = 0,
) -> None:
    """Fire-and-forget notification. Never raises; no-op when unavailable."""
    if not available():
        return
    cmd = ["notify-send", "--app-name=TKSteamLaunch", f"--urgency={urgency}"]
    if expire_ms > 0:
        cmd.append(f"--expire-time={expire_ms}")
    if icon:
        cmd.append(f"--icon={icon}")
    cmd += [summary, body]
    try:
        subprocess.Popen(
            cmd,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
    except Exception as e:
        log.debug("notify-send failed: %s", e)


def launch_summary(
    *,
    appid: str,
    name: str = "",
    game_type: str = "proton",
    wrappers: list[str] | None = None,
    custom_executable: str = "",
    proton_version: str | None = None,
    runtime: str | None = None,
) -> tuple[str, str]:
    """Build (title, body) for the game-start notification. Pure function."""
    import os

    title = f"TKSteamLaunch — {name.strip() or appid}"
    if game_type == "native":
        head = f"Native · {runtime}" if runtime else "Native"
    elif proton_version:
        head = f"Proton {proton_version}"
    else:
        head = "Proton"
    lines = [head]
    if wrappers:
        lines.append(" · ".join(wrappers))
    if (custom_executable or "").strip():
        lines.append(f"Exe: {os.path.basename(custom_executable.strip())}")
    return title, "\n".join(lines)
