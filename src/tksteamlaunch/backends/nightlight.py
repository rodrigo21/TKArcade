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

log = logging.getLogger("tksteamlaunch.nightlight")


def detect_provider(requested: str = "auto") -> str:
    req = (requested or "auto").strip().lower()
    match req:
        case (
            NightlightProvider.PLASMA
            | NightlightProvider.GNOME
            | NightlightProvider.OFF
        ):
            return str(req)
    desktop = (
        os.environ.get("XDG_CURRENT_DESKTOP", "")
        + " "
        + os.environ.get("DESKTOP_SESSION", "")
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
            ["gsettings", "get", "org.gnome.settings-daemon.plugins.color",
             "night-light-enabled"],
            capture_output=True, text=True, timeout=5,
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

    def start(self) -> list[str]:
        warnings: list[str] = []
        if self.provider == NightlightProvider.OFF:
            return warnings
        if self.provider == NightlightProvider.GNOME:
            if not shutil.which("gsettings"):
                return ["gsettings not found, skipping night light"]
            self._gnome_prev = _read_gnome()
            try:
                subprocess.run(
                    ["gsettings", "set",
                     "org.gnome.settings-daemon.plugins.color",
                     "night-light-enabled", "false"],
                    timeout=5,
                )
            except Exception as e:
                warnings.append(f"failed to disable GNOME night light: {e}")
            return warnings
        if self.provider == NightlightProvider.PLASMA:
            # spawn persistent holder (jeepney-based)
            try:
                self._holder = subprocess.Popen(
                    [sys.executable, "-m", "tksteamlaunch.nightlight_holder"],
                    stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True,
                )
                # holder prints "cookie=N" on success; give it a moment
                deadline = time.time() + 5
                cookie_seen = False
                assert self._holder.stdout is not None
                while time.time() < deadline:
                    if self._holder.poll() is not None:
                        out = self._holder.stdout.read()
                        warnings.append(f"nightlight holder exited early: {out.strip()}")
                        self._holder = None
                        break
                    r, _, _ = select.select([self._holder.stdout], [], [], 0.5)
                    if r:
                        line = self._holder.stdout.readline()
                        log.info("nightlight holder: %s", line.strip())
                        if "cookie=" in line:
                            cookie_seen = True
                            break
                    else:
                        continue
                if self._holder is not None and not cookie_seen:
                    # holder may still be running but silent; keep it, warn
                    log.warning("nightlight holder did not confirm cookie in time")
            except FileNotFoundError:
                warnings.append("python executable not found for nightlight holder")
            except Exception as e:
                warnings.append(f"failed to start nightlight holder: {e}")
            return warnings
        return [f"unknown nightlight provider: {self.provider}"]

    def stop(self) -> None:
        if self.provider == NightlightProvider.GNOME and self._gnome_prev is not None:
            try:
                val = "true" if self._gnome_prev == "true" else "false"
                subprocess.run(
                    ["gsettings", "set",
                     "org.gnome.settings-daemon.plugins.color",
                     "night-light-enabled", val],
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
        self.start()
        return self

    def __exit__(self, *exc) -> None:
        self.stop()
