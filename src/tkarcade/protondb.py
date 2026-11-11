"""ProtonDB tier lookups with a 30-day disk cache (stdlib urllib)."""

from __future__ import annotations

import json
import logging
import time
import urllib.request
from typing import TYPE_CHECKING

from . import steam as steammod
from . import xdg

if TYPE_CHECKING:
    from pathlib import Path

log = logging.getLogger("tkarcade.protondb")

ENDPOINT = "https://www.protondb.com/api/v1/reports/summaries/{appid}.json"
GAME_URL = "https://www.protondb.com/app/{appid}"
CACHE_TTL = 30 * 24 * 3600

# (background, foreground) per tier.
TIER_STYLE: dict[str, tuple[str, str]] = {
    "platinum": ("#BDBDBD", "#000000"),
    "gold": ("#FFC107", "#000000"),
    "silver": ("#E0E0E0", "#000000"),
    "bronze": ("#CD7F32", "#FFFFFF"),
    "borked": ("#F44336", "#FFFFFF"),
    # ProtonDB reports "pending" for a game with no reports yet.
    "pending": ("#757575", "#000000"),
}


def cache_path(appid: str) -> Path:
    return xdg.app_cache_dir() / "protondb" / f"{xdg.safe_stem(appid)}.json"


def _numeric(appid: str, target: str = "") -> str:
    """Numeric Steam AppID to query: the explicit target wins."""
    return str(target or "").strip() or steammod.steam_appid(appid)


def cached(appid: str, target: str = "") -> tuple[dict | None, bool]:
    """Return (data, is_fresh). Stale data is returned for instant display.

    ``target`` is a local game's Steam store link. The cache stays keyed
    by the game ID (so cleanup finds it) and records the AppID it was
    fetched for: a changed link reads as not cached instead of showing
    the previous game's tier.
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
    """Fetch the tier summary from ProtonDB. None on any failure."""
    numeric = _numeric(appid, target)
    if not numeric:
        return None
    try:
        with urllib.request.urlopen(ENDPOINT.format(appid=numeric), timeout=timeout) as response:
            data = json.loads(response.read().decode("utf-8"))
    except Exception as e:
        log.debug("protondb fetch failed for %s: %s", appid, e)
        return None
    return data if isinstance(data, dict) else None


def refresh(appid: str, target: str = "") -> dict | None:
    """Fetch and cache; returns fresh data or None (cache untouched)."""
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
        log.debug("protondb cache write failed: %s", e)
    return data
