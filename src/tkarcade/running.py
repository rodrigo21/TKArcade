"""Running-game records and clean termination (stdlib only).

The launcher writes `$XDG_STATE_HOME/tkarcade/running/<appid>.json`
before it spawns the game and removes it when the game exits, so the GUI
can show a running indicator without owning the process. The record
holds the launcher's PID and its start time (a PID alone can be reused).

Terminate goes to the launcher, never to the game: the wrappers
(gamemoderun, gamescope, ludusavi) sit between the two, and only the
launcher can restore the display, audio and nightlight sessions on the
way out. `forward_signals` turns that SIGTERM into a SIGTERM for the
game's whole process group and keeps the launcher alive for the cleanup.

Every game start loads this module, so it stays stdlib-only.
"""

from __future__ import annotations

import contextlib
import json
import os
import signal
import time
from pathlib import Path

from . import xdg

# Signals that mean "stop the game": the GUI sends SIGTERM, a terminal
# sends SIGINT, and the session may send SIGHUP.
TERMINATION_SIGNALS = (signal.SIGTERM, signal.SIGINT, signal.SIGHUP)


def running_dir() -> Path:
    return xdg.app_state_dir() / "running"


def record_path(appid: str) -> Path:
    return running_dir() / f"{xdg.safe_stem(appid)}.json"


def process_start_time(pid: int) -> int | None:
    """Start time of a PID in clock ticks (`/proc/<pid>/stat` field 22).

    None when the process is gone or /proc is unreadable.
    """
    try:
        raw = Path(f"/proc/{pid}/stat").read_text()
        # comm sits in parentheses and may itself contain ") ".
        return int(raw.rsplit(")", 1)[1].split()[19])
    except (OSError, IndexError, ValueError):
        return None


def is_alive(record: dict) -> bool:
    """A record is live only while the same process still holds the PID."""
    try:
        pid = int(record.get("pid", 0))
        start = record.get("start")
    except (TypeError, ValueError):
        return False
    if pid <= 0:
        return False
    return process_start_time(pid) == start


def _write(record: dict) -> None:
    path = record_path(str(record["appid"]))
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(record))
    os.replace(tmp, path)


def _read_file(path: Path) -> dict | None:
    try:
        data = json.loads(path.read_text())
    except (OSError, ValueError):
        return None
    return data if isinstance(data, dict) else None


def read(appid: str) -> dict | None:
    """The live record for an AppID, or None (stale files are removed)."""
    path = record_path(appid)
    record = _read_file(path)
    if record is None:
        return None
    record.setdefault("appid", appid)
    if not is_alive(record):
        with contextlib.suppress(OSError):
            path.unlink()
        return None
    return record


def sweep() -> None:
    """Drop records whose launcher died without cleaning up (crash, kill)."""
    try:
        paths = list(running_dir().glob("*.json"))
    except OSError:
        return
    for path in paths:
        record = _read_file(path)
        if record is not None and is_alive(record):
            continue
        with contextlib.suppress(OSError):
            path.unlink()


def list_running() -> dict[str, dict]:
    """Live records by AppID, sweeping stale ones on the way."""
    sweep()
    running: dict[str, dict] = {}
    try:
        paths = list(running_dir().glob("*.json"))
    except OSError:
        return running
    for path in paths:
        record = _read_file(path)
        if record is not None:
            running[str(record.get("appid", path.stem))] = record
    return running


class Record:
    """`with Record(appid):` marks this launcher as running a game."""

    def __init__(self, appid: str) -> None:
        self.appid = str(appid)
        self.pid = 0

    def __enter__(self) -> Record:
        self.pid = os.getpid()
        _write(
            {
                "appid": self.appid,
                "pid": self.pid,
                "start": process_start_time(self.pid),
                "started": time.time(),
            }
        )
        return self

    def clear(self) -> None:
        with contextlib.suppress(OSError):
            record_path(self.appid).unlink()

    def __exit__(self, *exc_info) -> None:
        self.clear()


@contextlib.contextmanager
def forward_signals(proc):
    """Turn "stop the launcher" into "stop the game's process group".

    Games and wrappers share the launcher's process group, so the group
    SIGTERM also reaches the launcher; repeats are ignored and the
    launcher stays alive to undo the display/audio/nightlight sessions
    once the game is gone.
    """
    try:
        pgid = os.getpgid(proc.pid)
    except OSError:
        pgid = proc.pid
    previous = {sig: signal.getsignal(sig) for sig in TERMINATION_SIGNALS}
    stopping = False

    def handler(signum, frame) -> None:
        nonlocal stopping
        if stopping:
            return
        stopping = True
        with contextlib.suppress(OSError):
            os.killpg(pgid, signal.SIGTERM)

    for sig in TERMINATION_SIGNALS:
        signal.signal(sig, handler)
    try:
        yield
    finally:
        for sig, old in previous.items():
            signal.signal(sig, old)


def terminate(appid: str) -> dict | None:
    """Ask the launcher running `appid` to stop the game (SIGTERM).

    Returns the record it signalled, or None when nothing is running.
    The launcher still has to exit: callers escalate with `kill`.
    """
    record = read(appid)
    if record is None:
        return None
    try:
        os.kill(int(record["pid"]), signal.SIGTERM)
    except (OSError, KeyError, TypeError):
        return None
    return record


def kill(record: dict) -> bool:
    """Last resort: SIGKILL the launcher's whole process group.

    Only when the recorded process is still the one we signalled, so a
    reused PID cannot take an unrelated tree down.
    """
    if not is_alive(record):
        return False
    try:
        pid = int(record["pid"])
        os.killpg(os.getpgid(pid), signal.SIGKILL)
    except (OSError, KeyError, TypeError):
        return False
    return True
