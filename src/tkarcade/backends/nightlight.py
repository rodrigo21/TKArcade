"""Night light handling.

KDE Plasma 6: org.kde.KWin.NightLight at /org/kde/KWin/NightLight with
inhibit() -> cookie and uninhibit(cookie). The inhibition is scoped to the
D-Bus connection lifetime, so a persistent holder process is required
(see nightlight_holder.py, jeepney/MIT). One-shot qdbus6 calls release
immediately (verified: only "return" notification visible).

GNOME: gsettings night-light-enabled (persistent, no holder needed).
"""

from __future__ import annotations

import logging
import os
import select
import shutil
import subprocess
import sys
import time

from ..config import NightlightProvider

log = logging.getLogger("tkarcade.nightlight")


def detect_provider(requested: str = "auto") -> str:
    req = (requested or "auto").strip().lower()
    match req:
        case NightlightProvider.PLASMA | NightlightProvider.GNOME | NightlightProvider.OFF:
            return str(req)
    desktop = (
        os.environ.get("XDG_CURRENT_DESKTOP", "") + " " + os.environ.get("DESKTOP_SESSION", "")
    ).lower()
    if "kde" in desktop or "plasma" in desktop:
        return str(NightlightProvider.PLASMA)
    if "gnome" in desktop:
        return str(NightlightProvider.GNOME)
    # fallback: binary hints
    if shutil.which("kreadconfig6") or shutil.which("qdbus6"):
        return str(NightlightProvider.PLASMA)
    if shutil.which("gsettings"):
        return str(NightlightProvider.GNOME)
    return str(NightlightProvider.OFF)


def _read_gnome() -> str | None:
    try:
        r = subprocess.run(
            ["gsettings", "get", "org.gnome.settings-daemon.plugins.color", "night-light-enabled"],
            capture_output=True,
            text=True,
            timeout=5,
        )
        return r.stdout.strip() or None
    except Exception:
        return None


class NightlightSession:
    """RAII session: enter() disables, exit() restores. Plasma uses holder proc."""

    def __init__(self, provider: str = NightlightProvider.AUTO):
        self.provider = detect_provider(provider)
        self._holder: subprocess.Popen | None = None
        self._gnome_prev: str | None = None
        self._started = False

    def start(self) -> list[str]:
        if self._started:
            return []  # idempotent: never spawn a second holder
        self._started = True
        if self.provider == NightlightProvider.OFF:
            return []
        if self.provider == NightlightProvider.GNOME:
            return self._start_gnome()
        if self.provider == NightlightProvider.PLASMA:
            return self._start_holder()
        return [f"unknown nightlight provider: {self.provider}"]

    def _start_gnome(self) -> list[str]:
        """Disable GNOME's night light, remembering the previous value."""
        if not shutil.which("gsettings"):
            return ["gsettings not found, skipping night light"]
        self._gnome_prev = _read_gnome()
        try:
            subprocess.run(
                [
                    "gsettings",
                    "set",
                    "org.gnome.settings-daemon.plugins.color",
                    "night-light-enabled",
                    "false",
                ],
                timeout=5,
            )
        except Exception as e:
            return [f"failed to disable GNOME night light: {e}"]
        return []

    def _start_holder(self) -> list[str]:
        """Spawn the persistent Plasma holder and wait for its cookie."""
        try:
            self._holder = subprocess.Popen(
                [sys.executable, "-m", "tkarcade.nightlight_holder"],
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
            )
        except FileNotFoundError:
            return ["python executable not found for nightlight holder"]
        except Exception as e:
            return [f"failed to start nightlight holder: {e}"]
        try:
            return self._await_cookie()
        except Exception as e:
            return [f"failed to start nightlight holder: {e}"]

    def _await_cookie(self) -> list[str]:
        """Watch the holder for its "cookie=N" line (or an early exit)."""
        assert self._holder is not None
        stdout = self._holder.stdout
        assert stdout is not None
        deadline = time.time() + 5
        cookie_seen = False
        warnings: list[str] = []
        while time.time() < deadline:
            if self._holder.poll() is not None:
                warnings.append(f"nightlight holder exited early: {stdout.read().strip()}")
                self._holder = None
                break
            ready, _, _ = select.select([stdout], [], [], 0.5)
            if not ready:
                continue
            line = stdout.readline()
            log.info("nightlight holder: %s", line.strip())
            if "cookie=" in line:
                cookie_seen = True
                break
        if self._holder is not None and not cookie_seen:
            # holder may still be running but silent; keep it, warn
            log.warning("nightlight holder did not confirm cookie in time")
        return warnings

    def stop(self) -> None:
        self._started = False
        if self.provider == NightlightProvider.GNOME and self._gnome_prev is not None:
            try:
                val = "true" if self._gnome_prev == "true" else "false"
                subprocess.run(
                    [
                        "gsettings",
                        "set",
                        "org.gnome.settings-daemon.plugins.color",
                        "night-light-enabled",
                        val,
                    ],
                    timeout=5,
                )
            except Exception as e:
                log.error("failed to restore GNOME night light: %s", e)
            finally:
                self._gnome_prev = None
        if self._holder is not None:
            try:
                self._holder.terminate()
                self._holder.wait(timeout=5)
            except Exception as e:
                log.error("nightlight holder stop failed: %s", e)
                try:
                    self._holder.kill()
                except Exception:
                    pass
            finally:
                self._holder = None

    def __enter__(self) -> NightlightSession:
        for w in self.start():
            log.warning("nightlight: %s", w)
        return self

    def __exit__(self, *exc) -> None:
        self.stop()
