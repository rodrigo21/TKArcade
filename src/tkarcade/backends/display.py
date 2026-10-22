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
import time
from typing import NamedTuple

from ..config import DisplayProvider

log = logging.getLogger("tkarcade.display")

_ANSI = re.compile(r"\x1b\[[0-9;]*m")
_MODE_RE = re.compile(r"^(\d{2,5})x(\d{2,5})(?:@(\d+(?:\.\d+)?))?$")


class _Mode(NamedTuple):
    """One reported mode. num is the kscreen N: id (None for xrandr)."""

    num: int | None
    w: int
    h: int
    rate: float
    current: bool


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


def current_plasma() -> dict[str, list[_Mode]]:
    """Connected outputs with modes: {name: [_Mode]}.

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
                _Mode(
                    int(mode.group(1)),
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


def current_x11() -> dict[str, list[_Mode]]:
    """Connected outputs with modes: {name: [_Mode]}."""
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
        m2 = re.match(r"^\s+(\d+)x(\d+)\s+(.*)$", line)
        if m2:
            w, h = int(m2.group(1)), int(m2.group(2))
            # One line carries every rate for the resolution
            # (e.g. "2560x1440 164.96*+ 60.00"): keep them all.
            for rate in re.finditer(r"([\d.]+)([*+]?)", m2.group(3)):
                out[name].append(_Mode(None, w, h, float(rate.group(1)), "*" in rate.group(2)))
    return {k: v for k, v in out.items() if v}


def _match_mode(modes: list[_Mode], want: tuple[int, int, float | None]) -> bool:
    """True when WxH exists (and the rate, if given, within 1 Hz)."""
    ww, hh, wr = want
    cands = [m for m in modes if m.w == ww and m.h == hh]
    if not cands:
        return False
    return wr is None or any(abs(m.rate - wr) < 1.0 for m in cands)


def _mode_number(modes: list[_Mode], want: tuple[int, int, float | None]) -> int | None:
    """kscreen N: id matching want (same tolerance as _match_mode)."""
    ww, hh, wr = want
    for m in modes:
        if m.num is not None and m.w == ww and m.h == hh and (wr is None or abs(m.rate - wr) < 1.0):
            return m.num
    return None


def _plasma_spec(mode: _Mode) -> str:
    """kscreen-doctor mode spec: the N: index when known, else WxH@R."""
    return str(mode.num) if mode.num is not None else f"{mode.w}x{mode.h}@{mode.rate:g}"


#: Seconds on the dip mode before returning (AMD VRAM clock workaround).
#: Generous so the dip is actually observable; tune down if annoying.
DIP_SECONDS = 8


def _dip_candidate(modes: list[_Mode], current: _Mode) -> _Mode | None:
    """A lower mode to dip through when target == current.

    Same resolution and closest lower refresh first (avoids a resolution
    flicker); any other mode as fallback. None when already lowest.
    """
    same_res = [m for m in modes if (m.w, m.h) == (current.w, current.h) and m != current]
    lower = sorted(
        (m for m in same_res if m.rate < current.rate),
        key=lambda m: m.rate,
        reverse=True,
    )
    if lower:
        return lower[0]
    others = sorted(
        (m for m in modes if m != current),
        key=lambda m: (m.w, m.h, m.rate),
    )
    return others[0] if others else None


def _wants_current(want: tuple[int, int, float | None], current: _Mode | None) -> bool:
    """True when the requested mode is already active (dip case)."""
    return (
        current is not None
        and current.w == want[0]
        and current.h == want[1]
        and (want[2] is None or abs(current.rate - want[2]) < 1.0)
    )


def offered_modes(provider: str = "auto", output: str = "") -> list[tuple]:
    """Offered modes as (number|None, 'WxH@R', is_current), resolution first.

    Numbers are kscreen N: ids (None for xrandr); manual entry stays
    valid. Empty when the provider is unsupported or unreadable.
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
    ordered = sorted(modes, key=lambda m: (-m.w, -m.h, -m.rate))
    return [(m.num, f"{m.w}x{m.h}@{m.rate:g}", m.current) for m in ordered]


class DisplaySession:
    """RAII session: apply a display mode on enter, restore on exit."""

    def __init__(
        self,
        provider: str = "auto",
        output: str = "",
        mode: str = "",
        dip_seconds: int = DIP_SECONDS,
    ) -> None:
        self.provider = provider
        self.output = (output or "").strip()
        self.mode = (mode or "").strip()
        try:
            self.dip_seconds = min(15, max(3, int(dip_seconds)))
        except (TypeError, ValueError):
            self.dip_seconds = DIP_SECONDS
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
        log.info(
            "display: start provider=%s output=%r mode=%r "
            "(DISPLAY=%r WAYLAND_DISPLAY=%r XDG_CURRENT_DESKTOP=%r)",
            provider,
            self.output,
            self.mode,
            os.environ.get("DISPLAY", ""),
            os.environ.get("WAYLAND_DISPLAY", ""),
            os.environ.get("XDG_CURRENT_DESKTOP", ""),
        )
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
        name, prev, modes, error = self._prepare_output("kscreen-doctor", current_plasma, want)
        if error:
            return error
        num = _mode_number(modes, want)
        target = str(num) if num is not None else self.mode
        cmds = [["kscreen-doctor", f"output.{name}.mode.{target}"]]
        if _wants_current(want, prev):
            # Already there (e.g. AMD VRAM clock stuck): dip one mode
            # down and back so the switch actually happens.
            dip_spec = self._plasma_dip_spec(modes, prev)
            if dip_spec is not None:
                cmds.insert(0, ["kscreen-doctor", f"output.{name}.mode.{dip_spec}"])
        return self._apply_cmds("plasma", name, prev, cmds, "kscreen-doctor", target)

    def _plasma_dip_spec(self, modes: list[_Mode], prev: _Mode) -> str | None:
        """Spec to dip through when the requested mode is already current."""
        dip = _dip_candidate(modes, prev)
        if dip is None:
            log.warning("display: already on %s; no lower mode to dip through", self.mode)
            return None
        spec = _plasma_spec(dip)
        log.info("display: target is current; dipping through %s first", spec)
        return spec

    def _start_x11(self, want: tuple[int, int, float | None]) -> list[str]:
        name, prev, modes, error = self._prepare_output("xrandr", current_x11, want)
        if error:
            return error
        ww, hh, wr = want
        cmds = [
            [
                "xrandr",
                "--output",
                name,
                "--mode",
                f"{ww}x{hh}",
                *(["--rate", f"{wr:g}"] if wr is not None else []),
            ]
        ]
        if _wants_current(want, prev):
            dip_cmd = self._x11_dip_cmd(name, modes, prev)
            if dip_cmd is not None:
                cmds.insert(0, dip_cmd)
        return self._apply_cmds("x11", name, prev, cmds, "xrandr", self.mode)

    def _x11_dip_cmd(self, name: str, modes: list[_Mode], prev: _Mode) -> list[str] | None:
        """xrandr argv to dip through when the requested mode is current."""
        dip = _dip_candidate(modes, prev)
        if dip is None:
            log.warning("display: already on %s; no lower mode to dip through", self.mode)
            return None
        log.info(
            "display: target is current; dipping through %sx%s@%s first",
            dip.w,
            dip.h,
            f"{dip.rate:g}",
        )
        return [
            "xrandr",
            "--output",
            name,
            "--mode",
            f"{dip.w}x{dip.h}",
            "--rate",
            f"{dip.rate:g}",
        ]

    def _prepare_output(
        self, tool: str, reader, want: tuple[int, int, float | None]
    ) -> tuple[str, _Mode | None, list[_Mode], list[str]]:
        """Tool check, output choice and current mode (shared by providers).

        Returns (name, prev, modes, error); error is non-empty when the
        caller should return it as-is.
        """
        if not shutil.which(tool):
            return "", None, [], [f"{tool} not found, skipping display mode"]
        try:
            outputs = reader()
        except Exception as e:
            return "", None, [], [f"could not read outputs: {e}"]
        name = self._pick_output(outputs)
        if name is None:
            avail = ", ".join(sorted(outputs)) or "none detected"
            return "", None, [], [f"output {self.output!r} not found (available: {avail})"]
        modes = outputs[name]
        if not _match_mode(modes, want):
            return (
                "",
                None,
                [],
                [f"mode {self.mode} not offered by {name}; leaving display untouched"],
            )
        return name, next((m for m in modes if m.current), None), modes, []

    def _apply_cmds(
        self, kind: str, name: str, prev: _Mode | None, cmds: list[list[str]], tool: str, label: str
    ) -> list[str]:
        """Run each command in order (a dip first when restoring is needed)."""
        try:
            for i, cmd in enumerate(cmds):
                error = self._run_mode_cmd(cmd, i > 0, tool)
                if error is not None:
                    return error
                if self._prev is None and prev is not None and i < len(cmds) - 1:
                    # The dip (cmds[0]) applied: the restore point is known
                    # from here on, so a later failure must undo it.
                    self._prev = self._restore_point(kind, name, prev)
                if i < len(cmds) - 1:
                    time.sleep(self.dip_seconds)
        except BaseException:
            # Interrupted mid-dip (SIGTERM/Ctrl-C): never leave the dip live.
            self.stop()
            raise
        self._log_applied(kind, name, prev, label)
        return []

    def _run_mode_cmd(self, cmd: list[str], is_dip: bool, tool: str) -> list[str] | None:
        """Run one mode command: None on success, an error list otherwise."""
        try:
            r = subprocess.run(cmd, capture_output=True, text=True, timeout=15)
        except FileNotFoundError:
            if is_dip:
                self.stop()
            return [f"{tool} not found, skipping display mode"]
        except Exception as e:
            if is_dip:
                self.stop()
            return [f"failed to set display mode: {e}"]
        if r.returncode != 0:
            if is_dip:
                self.stop()
            return [f"{tool} failed: {(r.stderr or r.stdout or '').strip()[:200]}"]
        return None

    @staticmethod
    def _restore_point(kind: str, name: str, prev: _Mode) -> tuple[str, str, str, str | None]:
        """The `_prev` tuple `stop()` uses to undo the switch."""
        if kind == "plasma":
            return ("plasma", name, _plasma_spec(prev), None)
        return ("x11", name, f"{prev.w}x{prev.h}", f"{prev.rate:g}")

    def _log_applied(self, kind: str, name: str, prev: _Mode | None, label: str) -> None:
        """Log the applied switch, or warn when there is no restore point."""
        if prev is None:
            log.warning(
                "display: current mode of %s not detected; applied %s without restore",
                name,
                label,
            )
            return
        if self._prev is None:
            self._prev = self._restore_point(kind, name, prev)
        from_label = _plasma_spec(prev) if kind == "plasma" else f"{prev.w}x{prev.h}@{prev.rate:g}"
        log.info("display: %s -> %s on %s (%s)", from_label, label, name, kind)

    def stop(self) -> None:
        self._started = False
        if self._prev is None:
            return
        kind, name, mode, rate = self._prev
        self._prev = None
        try:
            cmd = self._restore_cmd(kind, name, mode, rate)
            if cmd is None:
                return
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

    @staticmethod
    def _restore_cmd(kind: str, name: str, mode: str, rate: str | None) -> list[str] | None:
        """Tool command that restores the saved mode (None when unusable)."""
        if kind == "plasma":
            if not shutil.which("kscreen-doctor"):
                log.warning("display: kscreen-doctor gone, cannot restore %s", mode)
                return None
            return ["kscreen-doctor", f"output.{name}.mode.{mode}"]
        if kind == "x11":
            if not shutil.which("xrandr"):
                log.warning("display: xrandr gone, cannot restore %s", mode)
                return None
            cmd = ["xrandr", "--output", name, "--mode", mode]
            if rate is not None:
                cmd += ["--rate", rate]
            return cmd
        return None

    def __enter__(self) -> DisplaySession:
        for w in self.start():
            log.warning("display: %s", w)
        return self

    def __exit__(self, *exc) -> None:
        self.stop()
