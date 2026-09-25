"""ProtonDB tier lookups with a 30-day disk cache (stdlib urllib)."""
from __future__ import annotations

import json
import logging
import time
import urllib.error
import urllib.request
from pathlib import Path

from . import xdg

log = logging.getLogger("tksteamlaunch.protondb")

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
}


def cache_path(appid: str) -> Path:
    return xdg.app_cache_dir() / "protondb" / f"{appid}.json"


def cached(appid: str) -> tuple[dict | None, bool]:
    """Return (data, is_fresh). Stale data is returned for instant display."""
    try:
        payload = json.loads(cache_path(appid).read_text(encoding="utf-8"))
    except Exception:
        return None, False
    if not isinstance(payload, dict):
        return None, False
    data = payload.get("data")
    saved = payload.get("saved", 0)
    fresh = isinstance(data, dict) and time.time() - saved < CACHE_TTL
    return (data if isinstance(data, dict) else None), fresh


def fetch(appid: str, timeout: int = 15) -> dict | None:
    """Fetch the tier summary from ProtonDB. None on any failure."""
    if not str(appid).isdigit():
        return None
    try:
        with urllib.request.urlopen(
            ENDPOINT.format(appid=appid), timeout=timeout
        ) as response:
            data = json.loads(response.read().decode("utf-8"))
    except Exception as e:
        log.debug("protondb fetch failed for %s: %s", appid, e)
        return None
    return data if isinstance(data, dict) else None


def refresh(appid: str) -> dict | None:
    """Fetch and cache; returns fresh data or None (cache untouched)."""
    data = fetch(appid)
    if data is None:
        return None
    path = cache_path(appid)
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            json.dumps({"saved": int(time.time()), "data": data}),
            encoding="utf-8",
        )
    except Exception as e:
        log.debug("protondb cache write failed: %s", e)
    return data
