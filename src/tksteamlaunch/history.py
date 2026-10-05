"""Session history parsed from the global launcher.log (tolerant reader)."""

from __future__ import annotations

import os
import re
import tempfile
from dataclasses import dataclass
from pathlib import Path

_LINE_RE = re.compile(
    r"^(?P<stamp>\S+)\s+appid=(?P<appid>\S+)\s+exit=(?P<exit>-?\d+)"
    r"(?:\s+dur=(?P<dur>\d+))?\s+cmd=(?P<cmd>.*)$"
)


@dataclass(frozen=True)
class Session:
    stamp: str
    appid: str
    exit: int
    duration: int | None
    cmd: str


@dataclass
class GameStats:
    appid: str
    last: str = ""
    runs: int = 0
    total_dur: int = 0
    fails: int = 0


def parse_log(path: Path | str) -> list[Session]:
    """Parse global log lines; skips malformed ones. Old lines lack dur=."""
    try:
        text = Path(path).read_text(encoding="utf-8", errors="replace")
    except Exception:
        return []
    out = []
    for line in text.splitlines():
        match = _LINE_RE.match(line.strip())
        if not match:
            continue
        try:
            out.append(
                Session(
                    stamp=match.group("stamp"),
                    appid=match.group("appid"),
                    exit=int(match.group("exit")),
                    duration=int(match.group("dur")) if match.group("dur") is not None else None,
                    cmd=match.group("cmd"),
                )
            )
        except ValueError:
            continue
    return out


def clear_appid(path: Path | str, appid: str) -> int:
    """Drop one game's lines from the launcher log. Returns lines removed.

    Matches the exact `appid=` token (`8` never catches `80`). Atomic
    rewrite; missing file counts as zero.
    """
    log = Path(path)
    try:
        text = log.read_text(encoding="utf-8", errors="replace")
    except Exception:
        return 0
    token = re.compile(rf"(?:^|\s)appid={re.escape(appid)}(?=\s|$)")
    kept = [line for line in text.splitlines(keepends=True) if not token.search(line)]
    removed = len(text.splitlines()) - len(kept)
    if not removed:
        return 0
    fd, tmp = tempfile.mkstemp(
        prefix=f".{log.name}.", suffix=".tmp", dir=log.parent if log.parent.exists() else None
    )
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.writelines(kept)
        os.replace(tmp, log)
    except BaseException:
        Path(tmp).unlink(missing_ok=True)
        raise
    return removed


def summarize(sessions: list[Session]) -> dict[str, GameStats]:
    """Aggregate sessions per game (unknown durations count as 0)."""
    stats: dict[str, GameStats] = {}
    for s in sessions:
        entry = stats.setdefault(s.appid, GameStats(appid=s.appid))
        entry.last = max(entry.last, s.stamp)
        entry.runs += 1
        entry.total_dur += s.duration or 0
        if s.exit != 0:
            entry.fails += 1
    return stats
