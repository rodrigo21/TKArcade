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


def send(summary: str, body: str = "", urgency: str = "normal") -> None:
    """Fire-and-forget notification. Never raises; no-op when unavailable."""
    if not available():
        return
    try:
        subprocess.Popen(
            [
                "notify-send",
                "--app-name=TKSteamLaunch",
                f"--urgency={urgency}",
                summary,
                body,
            ],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
    except Exception as e:
        log.debug("notify-send failed: %s", e)
