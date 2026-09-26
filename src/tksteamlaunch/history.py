"""Session history parsed from the global launcher.log (tolerant reader)."""

from __future__ import annotations

import re
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


def summarize(sessions: list[Session]) -> dict[str, GameStats]:
    """Aggregate sessions per game (unknown durations count as 0)."""
    stats: dict[str, GameStats] = {}
    for s in sessions:
        entry = stats.setdefault(s.appid, GameStats(appid=s.appid))
        entry.last = s.stamp
        entry.runs += 1
        entry.total_dur += s.duration or 0
        if s.exit != 0:
            entry.fails += 1
    return stats
