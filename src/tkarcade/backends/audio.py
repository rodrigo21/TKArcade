"""Per-game audio output with restore on exit (stdlib only).

Routes new audio streams to a chosen sink for the session: the default
sink switches on enter and switches back on exit. Streams opened before
the switch stay where they are (PipeWire/PulseAudio semantics); games
open theirs after launch, so this covers the common case.
"""

from __future__ import annotations

import logging
import shutil
import subprocess

log = logging.getLogger("tkarcade.audio")


def _pactl() -> str | None:
    try:
        return shutil.which("pactl")
    except Exception:
        return None


def _parse_sinks(text: str) -> list[tuple[str, str]]:
    """[(name, description)] from `pactl list sinks` (description or name).

    The short form reports the node name only; the long form carries the
    human `Description:` the picker shows (the config still stores the
    name). A sink without one falls back to its name.
    """
    out: list[tuple[str, str]] = []
    name = ""
    for line in text.splitlines():
        stripped = line.strip()
        if stripped.startswith("Name:"):
            name = stripped[len("Name:") :].strip()
        elif stripped.startswith("Description:") and name:
            desc = stripped[len("Description:") :].strip()
            out.append((name, desc or name))
            name = ""
    if name:  # trailing sink without a Description
        out.append((name, name))
    return out


def list_sinks() -> list[tuple[str, str]]:
    """[(name, description)] output sinks, [] when pactl is missing."""
    exe = _pactl()
    if not exe:
        return []
    try:
        proc = subprocess.run(
            [exe, "list", "sinks"],
            capture_output=True,
            text=True,
            timeout=15,
            check=False,
        )
    except Exception as e:
        log.debug("pactl list sinks failed: %s", e)
        return []
    if proc.returncode != 0:
        return []
    return _parse_sinks(proc.stdout)


def default_sink() -> str:
    """Current default sink name ("" when unknown)."""
    exe = _pactl()
    if not exe:
        return ""
    try:
        proc = subprocess.run(
            [exe, "get-default-sink"],
            capture_output=True,
            text=True,
            timeout=15,
            check=False,
        )
    except Exception:
        return ""
    return proc.stdout.strip() if proc.returncode == 0 else ""


def set_default_sink(name: str) -> bool:
    """Switch the default sink. False on any failure."""
    exe = _pactl()
    if not exe or not (name or "").strip():
        return False
    try:
        proc = subprocess.run(
            [exe, "set-default-sink", name.strip()],
            capture_output=True,
            timeout=15,
            check=False,
        )
    except Exception as e:
        log.debug("pactl set-default-sink failed: %s", e)
        return False
    return proc.returncode == 0


class AudioSession:
    """RAII session: route to a sink on enter, restore on exit."""

    def __init__(self, sink: str = "") -> None:
        self.sink = (sink or "").strip()
        self._saved = ""

    def start(self) -> list[str]:
        """Switch to the sink. Returns warnings (empty sink = no-op)."""
        if not self.sink:
            return []
        if _pactl() is None:
            log.warning("pactl not found, skipping audio routing")
            return ["pactl not found, skipping audio routing"]
        self._saved = default_sink()
        if self._saved == self.sink:
            return []
        if not set_default_sink(self.sink):
            log.warning("could not route audio to %s", self.sink)
            return [f"could not route audio to {self.sink}"]
        return []

    def stop(self) -> None:
        """Restore the saved default sink (best effort)."""
        if self._saved and self._saved != self.sink:
            try:
                set_default_sink(self._saved)
            except Exception as e:
                log.debug("audio restore failed: %s", e)
        self._saved = ""

    def __enter__(self) -> list[str]:
        return self.start()

    def __exit__(self, *args: object) -> None:
        self.stop()
