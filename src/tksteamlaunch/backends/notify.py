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
    proton_display: str = "Proton",
    runtime: str | None = None,
) -> tuple[str, str]:
    """Build (title, body) for the game-start notification. Pure function.

    The first body line folds runtime and wrappers together so no part
    ever stands alone; blank parts are dropped (no trailing separators).
    """
    title = f"TKSteamLaunch — {name.strip() or appid}"
    if game_type == "native":
        head = f"Native · {runtime}" if runtime else "Native"
    else:
        head = (proton_display or "").strip() or "Proton"
    parts = [head, *(wrappers or [])]
    lines = [" · ".join(p for p in parts if p.strip())]
    if (custom_executable or "").strip():
        lines.append(f"Exe: {os.path.basename(custom_executable.strip())}")
    return title, "\n".join(lines)


def format_duration(seconds: float) -> str:
    """Format playtime compactly: 38s, 45m 12s, 2h 13m."""
    total = max(0, int(seconds))
    hours, rem = divmod(total, 3600)
    minutes, secs = divmod(rem, 60)
    if hours:
        return f"{hours}h {minutes}m"
    if minutes:
        return f"{minutes}m {secs:02d}s"
    return f"{secs}s"
