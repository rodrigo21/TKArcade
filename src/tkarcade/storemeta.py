"""Steam store metadata with a 30-day disk cache (stdlib urllib).

The same ``appdetails`` payload backs the release date: a Steam game
derives its AppID, a local game passes its ``[metadata] steam_appid``
store link. Only fields the user can also type by hand are extracted;
the manual date is left alone (the Release Date column owns the store
date).
"""

from __future__ import annotations

import html
import json
import logging
import time
import urllib.request
from typing import TYPE_CHECKING

from . import steam as steammod
from . import xdg

if TYPE_CHECKING:
    from pathlib import Path

log = logging.getLogger("tkarcade.storemeta")

ENDPOINT = "https://store.steampowered.com/api/appdetails?appids={appid}&l=english&cc=us"
CACHE_TTL = 30 * 24 * 3600

#: Steam board key -> payload value -> ``config.AGE_RATINGS`` entry.
#: Boards whose codes do not map cleanly (igrs, cero, ...) are ignored.
RATINGS: dict[str, dict[str, str]] = {
    "esrb": {
        "e": "ESRB E",
        "e10": "ESRB E10+",
        "t": "ESRB T",
        "m": "ESRB M",
        "ao": "ESRB AO",
        "rp": "ESRB RP",
    },
    "pegi": {"3": "PEGI 3", "7": "PEGI 7", "12": "PEGI 12", "16": "PEGI 16", "18": "PEGI 18"},
    "usk": {"0": "USK 0", "6": "USK 6", "12": "USK 12", "16": "USK 16", "18": "USK 18"},
}


def cache_path(appid: str) -> Path:
    return xdg.app_cache_dir() / "steam-meta" / f"{xdg.safe_stem(appid)}.json"


def _numeric(appid: str, target: str = "") -> str:
    """Numeric Steam AppID to query: the explicit target wins."""
    return str(target or "").strip() or steammod.steam_appid(appid)


def _joined(value: object) -> str:
    if not isinstance(value, list):
        return ""
    return ", ".join(str(part).strip() for part in value if str(part).strip())


def _age_ratings(ratings: object) -> list[str]:
    if not isinstance(ratings, dict):
        return []
    out: list[str] = []
    for board, values in RATINGS.items():
        entry = ratings.get(board)
        if not isinstance(entry, dict):
            continue
        rating = str(entry.get("rating", "") or "").strip().lower()
        label = values.get(rating)
        if label and label not in out:
            out.append(label)
    return out


def normalize(data: dict) -> dict:
    """Metadata fields from an appdetails payload ("" when missing)."""
    genres = data.get("genres")
    genre = ""
    if isinstance(genres, list):
        names = [
            str(part.get("description", "")).strip() for part in genres if isinstance(part, dict)
        ]
        genre = ", ".join(name for name in names if name)
    franchise = data.get("franchise")
    return {
        "description": html.unescape(str(data.get("short_description") or "")).strip(),
        "developer": _joined(data.get("developers")),
        "publisher": _joined(data.get("publishers")),
        "genre": genre,
        "series": franchise.strip() if isinstance(franchise, str) else "",
        "age_ratings": _age_ratings(data.get("ratings")),
    }


def cached(appid: str, target: str = "") -> tuple[dict | None, bool]:
    """Return (fields, is_fresh). Stale fields are returned for display.

    The cache stays keyed by the game ID and records the AppID it was
    fetched for: a changed store link reads as not cached instead of
    filling the previous game's metadata.
    """
    numeric = _numeric(appid, target)
    if not numeric:
        return None, False
    try:
        payload = json.loads(cache_path(appid).read_text(encoding="utf-8"))
    except Exception:
        return None, False
    if not isinstance(payload, dict):
        return None, False
    stored = str(payload.get("target", "") or "")
    if stored and stored != numeric:
        return None, False
    data = payload.get("data")
    try:
        age = time.time() - float(payload.get("saved", 0))
    except (TypeError, ValueError):
        return None, False
    fresh = isinstance(data, dict) and age < CACHE_TTL
    return (data if isinstance(data, dict) else None), fresh


def fetch(appid: str, target: str = "", timeout: int = 15) -> dict | None:
    """Fetch the store metadata. None on any failure or no entry."""
    numeric = _numeric(appid, target)
    if not numeric:
        return None
    try:
        with urllib.request.urlopen(ENDPOINT.format(appid=numeric), timeout=timeout) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except Exception as e:
        log.debug("metadata fetch failed for %s: %s", appid, e)
        return None
    if not isinstance(payload, dict):
        return None
    entry = payload.get(numeric)
    data = entry.get("data") if isinstance(entry, dict) else None
    if not isinstance(data, dict):
        return None
    return normalize(data)


def refresh(appid: str, target: str = "") -> dict | None:
    """Fetch and cache; returns the fields or None (cache untouched)."""
    numeric = _numeric(appid, target)
    if not numeric:
        return None
    data = fetch(appid, numeric)
    if data is None:
        return None
    path = cache_path(appid)
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            json.dumps({"saved": int(time.time()), "target": numeric, "data": data}),
            encoding="utf-8",
        )
    except Exception as e:
        log.debug("metadata cache write failed: %s", e)
    return data
