"""Per-game display mode (resolution/refresh) with restore on exit.

Phase 1 providers: Plasma (kscreen-doctor) and X11 (xrandr). GNOME and
wlroots detect by name but warn as unsupported until phase 2. Empty
mode disables the feature: nothing is queried, applied or restored.
"""

from __future__ import annotations

import logging
import os
import re
import shutil
import subprocess

from ..config import DisplayProvider

log = logging.getLogger("tksteamlaunch.display")

_ANSI = re.compile(r"\x1b\[[0-9;]*m")
_MODE_RE = re.compile(r"^(\d{2,5})x(\d{2,5})(?:@(\d+(?:\.\d+)?))?$")


def detect_provider(requested: str = "auto") -> str:
    """Resolve a provider name; auto-detects from session/binaries."""
    req = (requested or "auto").strip().lower()
    for known in (
        DisplayProvider.PLASMA,
        DisplayProvider.GNOME,
        DisplayProvider.WLROOTS,
        DisplayProvider.X11,
        DisplayProvider.OFF,
    ):
        if req == str(known):
            return str(known)
    desktop = (
        os.environ.get("XDG_CURRENT_DESKTOP", "") + " " + os.environ.get("DESKTOP_SESSION", "")
    ).lower()
    if "kde" in desktop or "plasma" in desktop:
        return str(DisplayProvider.PLASMA)
    if "gnome" in desktop:
        return str(DisplayProvider.GNOME)
    if os.environ.get("WAYLAND_DISPLAY", "") and shutil.which("wlr-randr"):
        return str(DisplayProvider.WLROOTS)
    if os.environ.get("DISPLAY", "") and shutil.which("xrandr"):
        return str(DisplayProvider.X11)
    return str(DisplayProvider.OFF)


def parse_mode(text: str) -> tuple[int, int, float | None] | None:
    """Parse WIDTHxHEIGHT[@RATE]; None when malformed or non-positive."""
    m = _MODE_RE.match((text or "").strip())
    if not m:
        return None
    w, h = int(m.group(1)), int(m.group(2))
    if w <= 0 or h <= 0:
        return None
    return (w, h, float(m.group(3)) if m.group(3) else None)


def _strip_ansi(text: str) -> str:
    return _ANSI.sub("", text)


def current_plasma() -> dict[str, list[tuple[int, int, float, bool]]]:
    """Connected outputs with modes: {name: [(w, h, rate, current)]}.

    Real kscreen-doctor -o layout: `Output: <id> <NAME> [<uuid>]` header,
    `enabled`/`connected` on their own indented lines, then a `Modes:`
    line (ANSI codes may sit inside mode tokens).
    """
    r = subprocess.run(["kscreen-doctor", "-o"], capture_output=True, text=True, timeout=15)
    if r.returncode != 0:
        raise RuntimeError(f"kscreen-doctor -o failed: {(r.stderr or '').strip()[:200]}")
    blocks: list[dict] = []
    current: dict | None = None
    for line in _strip_ansi(r.stdout).splitlines():
        m = re.match(r"^Output:\s+\d+\s+(\S+)", line.strip())
        if m:
            current = {"name": m.group(1), "flags": set(), "modes": []}
            blocks.append(current)
            continue
        if current is None:
            continue
        if line.strip() in ("enabled", "connected"):
            current["flags"].add(line.strip())
        for mode in re.finditer(r"(\d+):(\d+)x(\d+)@([\d.]+)([*+]?)", line):
            current["modes"].append(
                (
                    int(mode.group(2)),
                    int(mode.group(3)),
                    float(mode.group(4)),
                    mode.group(5) == "*",
                )
            )
    return {
        b["name"]: b["modes"]
        for b in blocks
        if {"enabled", "connected"} <= b["flags"] and b["modes"]
    }


def current_x11() -> dict[str, list[tuple[int, int, float, bool]]]:
    """Connected outputs with modes: {name: [(w, h, rate, current)]}."""
    r = subprocess.run(["xrandr", "--query"], capture_output=True, text=True, timeout=15)
    if r.returncode != 0:
        raise RuntimeError(f"xrandr --query failed: {(r.stderr or '').strip()[:200]}")
    out: dict[str, list[tuple[int, int, float, bool]]] = {}
    name: str | None = None
    for line in r.stdout.splitlines():
        m = re.match(r"^(\S+)\s+(connected|disconnected)\b", line)
        if m:
            name = m.group(1) if m.group(2) == "connected" else None
            if name is not None:
                out.setdefault(name, [])
            continue
        if name is None:
            continue
        m2 = re.match(r"^\s+(\d+)x(\d+)\s+([\d.]+)(\*?).*$", line)
        if m2:
            out[name].append(
                (int(m2.group(1)), int(m2.group(2)), float(m2.group(3)), m2.group(4) == "*")
            )
    return {k: v for k, v in out.items() if v}


def _match_mode(
    modes: list[tuple[int, int, float, bool]], want: tuple[int, int, float | None]
) -> bool:
    """True when WxH exists (and the rate, if given, within 1 Hz)."""
    ww, hh, wr = want
    cands = [(w, h, r) for w, h, r, _ in modes if w == ww and h == hh]
    if not cands:
        return False
    return wr is None or any(abs(r - wr) < 1.0 for _, _, r in cands)


def offered_modes(provider: str = "auto", output: str = "") -> list[str]:
    """Mode strings the backend reports (e.g. '1920x1080@60').

    For the GUI picker; manual entry stays valid. Empty when the
    provider is unsupported or outputs are unreadable.
    """
    provider = detect_provider(provider)
    try:
        if provider == DisplayProvider.PLASMA:
            outputs = current_plasma()
        elif provider == DisplayProvider.X11:
            outputs = current_x11()
        else:
            return []
    except Exception:
        return []
    if output and output in outputs:
        modes = outputs[output]
    elif outputs:
        modes = next(iter(outputs.values()))
    else:
        return []
    return [f"{w}x{h}@{r:g}" for w, h, r, _ in modes]


class DisplaySession:
    """RAII session: apply a display mode on enter, restore on exit."""

    def __init__(self, provider: str = "auto", output: str = "", mode: str = "") -> None:
        self.provider = provider
        self.output = (output or "").strip()
        self.mode = (mode or "").strip()
        self._prev: tuple[str, str, str, str | None] | None = None
        self._started = False

    def start(self) -> list[str]:
        if self._started:
            return []  # idempotent like NightlightSession
        self._started = True
        if not self.mode:
            return []
        want = parse_mode(self.mode)
        if want is None:
            return [f"invalid display mode {self.mode!r}; use WIDTHxHEIGHT[@RATE]"]
        provider = detect_provider(self.provider)
        if provider == DisplayProvider.OFF:
            return []
        if provider in (DisplayProvider.GNOME, DisplayProvider.WLROOTS):
            return [f"display provider {provider} is not supported yet"]
        if provider == DisplayProvider.PLASMA:
            return self._start_plasma(want)
        if provider == DisplayProvider.X11:
            return self._start_x11(want)
        return [f"unknown display provider: {provider}"]

    def _pick_output(self, outputs: dict[str, list[tuple[int, int, float, bool]]]) -> str | None:
        if self.output:
            return self.output if self.output in outputs else None
        return next(iter(outputs), None)

    def _start_plasma(self, want: tuple[int, int, float | None]) -> list[str]:
        if not shutil.which("kscreen-doctor"):
            return ["kscreen-doctor not found, skipping display mode"]
        try:
            outputs = current_plasma()
        except Exception as e:
            return [f"could not read outputs: {e}"]
        name = self._pick_output(outputs)
        if name is None:
            avail = ", ".join(sorted(outputs)) or "none detected"
            return [f"output {self.output!r} not found (available: {avail})"]
        if not _match_mode(outputs[name], want):
            return [f"mode {self.mode} not offered by {name}; leaving display untouched"]
        prev = next(((w, h, r) for w, h, r, cur in outputs[name] if cur), None)
        try:
            r = subprocess.run(
                ["kscreen-doctor", f"output.{name}.mode.{self.mode}"],
                capture_output=True,
                text=True,
                timeout=15,
            )
        except FileNotFoundError:
            return ["kscreen-doctor not found, skipping display mode"]
        except Exception as e:
            return [f"failed to set display mode: {e}"]
        if r.returncode != 0:
            return [f"kscreen-doctor failed: {(r.stderr or r.stdout or '').strip()[:200]}"]
        if prev is not None:
            pw, ph, pr = prev
            self._prev = ("plasma", name, f"{pw}x{ph}@{pr:g}", None)
            log.info("display: %s -> %s on %s (plasma)", self._prev[2], self.mode, name)
        else:
            log.warning(
                "display: current mode of %s not detected; applied %s without restore",
                name,
                self.mode,
            )
        return []

    def _start_x11(self, want: tuple[int, int, float | None]) -> list[str]:
        if not shutil.which("xrandr"):
            return ["xrandr not found, skipping display mode"]
        try:
            outputs = current_x11()
        except Exception as e:
            return [f"could not read outputs: {e}"]
        name = self._pick_output(outputs)
        if name is None:
            avail = ", ".join(sorted(outputs)) or "none detected"
            return [f"output {self.output!r} not found (available: {avail})"]
        if not _match_mode(outputs[name], want):
            return [f"mode {self.mode} not offered by {name}; leaving display untouched"]
        prev = next(((w, h, r) for w, h, r, cur in outputs[name] if cur), None)
        ww, hh, wr = want
        cmd = ["xrandr", "--output", name, "--mode", f"{ww}x{hh}"]
        if wr is not None:
            cmd += ["--rate", f"{wr:g}"]
        try:
            r = subprocess.run(cmd, capture_output=True, text=True, timeout=15)
        except FileNotFoundError:
            return ["xrandr not found, skipping display mode"]
        except Exception as e:
            return [f"failed to set display mode: {e}"]
        if r.returncode != 0:
            return [f"xrandr failed: {(r.stderr or r.stdout or '').strip()[:200]}"]
        if prev is not None:
            pw, ph, pr = prev
            self._prev = ("x11", name, f"{pw}x{ph}", f"{pr:g}")
            log.info("display: %s -> %s on %s (x11)", f"{pw}x{ph}@{pr:g}", self.mode, name)
        else:
            log.warning(
                "display: current mode of %s not detected; applied %s without restore",
                name,
                self.mode,
            )
        return []

    def stop(self) -> None:
        self._started = False
        if self._prev is None:
            return
        kind, name, mode, rate = self._prev
        self._prev = None
        try:
            if kind == "plasma":
                if not shutil.which("kscreen-doctor"):
                    log.warning("display: kscreen-doctor gone, cannot restore %s", mode)
                    return
                cmd = ["kscreen-doctor", f"output.{name}.mode.{mode}"]
                r = subprocess.run(cmd, capture_output=True, text=True, timeout=15)
                if r.returncode != 0:
                    log.warning(
                        "display: restore %s failed: %s",
                        mode,
                        (r.stderr or r.stdout or "").strip()[:200],
                    )
                else:
                    log.info("display: restored %s on %s", mode, name)
            elif kind == "x11":
                if not shutil.which("xrandr"):
                    log.warning("display: xrandr gone, cannot restore %s", mode)
                    return
                cmd = ["xrandr", "--output", name, "--mode", mode]
                if rate is not None:
                    cmd += ["--rate", rate]
                r = subprocess.run(cmd, capture_output=True, text=True, timeout=15)
                if r.returncode != 0:
                    log.warning(
                        "display: restore %s failed: %s",
                        mode,
                        (r.stderr or r.stdout or "").strip()[:200],
                    )
                else:
                    log.info("display: restored %s on %s", mode, name)
        except Exception as e:
            log.error("failed to restore display mode: %s", e)

    def __enter__(self) -> DisplaySession:
        for w in self.start():
            log.warning("display: %s", w)
        return self

    def __exit__(self, *exc) -> None:
        self.stop()
