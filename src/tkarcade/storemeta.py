"""Steam store metadata payload (stdlib urllib).

The same ``appdetails`` payload backs the release date: a Steam game
derives its AppID, a local game passes its ``[metadata] steam_appid``
store link. Only fields the user can also type by hand are extracted;
the cache and the rate gate live in ``metadata.py``.
"""

from __future__ import annotations

import html
import json
import logging
import urllib.request

from . import releasedate as rdmod
from . import steam as steammod

log = logging.getLogger("tkarcade.storemeta")

ENDPOINT = "https://store.steampowered.com/api/appdetails?appids={appid}&l=english&cc=us"

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


def resolve(appid: str, target: str = "") -> str:
    """Numeric Steam AppID to query: the explicit target wins."""
    return str(target or "").strip() or steammod.steam_appid(appid)


def _joined(value: object) -> str:
    if not isinstance(value, list):
        return ""
    return ", ".join(str(part).strip() for part in value if str(part).strip())


def _descriptions(value: object) -> list[str]:
    """Description strings of a Steam genres/categories list, deduped."""
    if not isinstance(value, list):
        return []
    out: list[str] = []
    for part in value:
        name = str(part.get("description", "")).strip() if isinstance(part, dict) else ""
        if name and name not in out:
            out.append(name)
    return out


def _tags(data: dict) -> list[str]:
    """Genres, store features and the franchise, as one tag list."""
    out: list[str] = []
    seen: set[str] = set()
    for part in _descriptions(data.get("genres")) + _descriptions(data.get("categories")):
        if part.casefold() not in seen:
            seen.add(part.casefold())
            out.append(part)
    franchise = str(data.get("franchise", "") or "").strip()
    if franchise and franchise.casefold() not in seen:
        out.append(franchise)
    return out


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
    release = data.get("release_date")
    date = rdmod.parse_date(release.get("date", "")) if isinstance(release, dict) else ""
    return {
        "description": html.unescape(str(data.get("short_description") or "")).strip(),
        "developer": _joined(data.get("developers")),
        "publisher": _joined(data.get("publishers")),
        "genre": genre,
        "series": franchise.strip() if isinstance(franchise, str) else "",
        "age_ratings": _age_ratings(data.get("ratings")),
        "date": date,
        "tags": _tags(data),
    }


def fetch(appid: str, target: str = "", timeout: int = 15) -> dict | None:
    """Fetch the store metadata. None on any failure or no entry."""
    numeric = resolve(appid, target)
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
