"""Steam store release dates with a 30-day disk cache (stdlib urllib)."""

from __future__ import annotations

import datetime
import json
import logging
import time
import urllib.request
from typing import TYPE_CHECKING

from . import steam as steammod
from . import xdg

if TYPE_CHECKING:
    from pathlib import Path

log = logging.getLogger("tkarcade.releasedate")

ENDPOINT = (
    "https://store.steampowered.com/api/appdetails"
    "?appids={appid}&filters=release_date&l=english&cc=us"
)
CACHE_TTL = 30 * 24 * 3600

# Hardcoded: strptime("%b") follows the process locale, not l=english.
_MONTHS = {
    "jan": 1,
    "feb": 2,
    "mar": 3,
    "apr": 4,
    "may": 5,
    "jun": 6,
    "jul": 7,
    "aug": 8,
    "sep": 9,
    "oct": 10,
    "nov": 11,
    "dec": 12,
}


def cache_path(appid: str) -> Path:
    return xdg.app_cache_dir() / "steam-release" / f"{xdg.safe_stem(appid)}.json"


def parse_date(text: object) -> str:
    """Steam's store date as ISO; '' for coming-soon or unknown dates.

    The store answers the English locale in both orders — "28 Aug, 2025"
    and "Jun 11, 2021" — so the month name decides the position and the
    two numbers are the day and the 4-digit year.
    """
    parts = str(text or "").replace(",", " ").split()
    if len(parts) != 3:
        return ""
    months = [_MONTHS.get(part.lower()) for part in parts]
    known = [index for index, month in enumerate(months) if month is not None]
    if len(known) != 1:
        return ""
    month_num = months[known[0]]
    rest = [part for index, part in enumerate(parts) if index != known[0]]
    if not all(part.isdecimal() for part in rest):
        return ""
    year = next((part for part in rest if len(part) == 4), "")
    day = next((part for part in rest if part != year), "")
    if not day:
        return ""
    try:
        return datetime.date(int(year), month_num, int(day)).isoformat()
    except ValueError:
        return ""


def cached(appid: str) -> tuple[str, bool]:
    """Return (ISO date or '', is_fresh). Stale dates still display."""
    try:
        payload = json.loads(cache_path(appid).read_text(encoding="utf-8"))
    except Exception:
        return "", False
    if not isinstance(payload, dict):
        return "", False
    date = str(payload.get("date", "") or "")
    try:
        age = time.time() - float(payload.get("saved", 0))
    except (TypeError, ValueError):
        return "", False
    return date, age < CACHE_TTL


def fetch(appid: str, timeout: int = 15) -> str | None:
    """Fetch the store release date. None on any failure."""
    numeric = steammod.steam_appid(appid)
    if not numeric:
        return None
    try:
        with urllib.request.urlopen(ENDPOINT.format(appid=numeric), timeout=timeout) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except Exception as e:
        log.debug("release date fetch failed for %s: %s", appid, e)
        return None
    if not isinstance(payload, dict):
        return None
    entry = payload.get(numeric)
    data = entry.get("data") if isinstance(entry, dict) else None
    if not isinstance(data, dict):
        return None
    release = data.get("release_date")
    if release is None:
        return ""
    if not isinstance(release, dict):
        return None
    return parse_date(release.get("date", ""))


def refresh(appid: str) -> str | None:
    """Fetch and cache; returns the date or None (cache untouched)."""
    date = fetch(appid)
    if date is None:
        return None
    path = cache_path(appid)
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            json.dumps({"saved": int(time.time()), "date": date}),
            encoding="utf-8",
        )
    except Exception as e:
        log.debug("release date cache write failed: %s", e)
    return date
