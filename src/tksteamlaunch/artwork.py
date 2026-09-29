"""Game artwork via SteamGridDB with local-cache fallback (stdlib only).

Downloaded grids live in our own cache and never touch Steam's files;
the GUI prefers them over librarycache art when present.
"""

from __future__ import annotations

import json
import logging
import urllib.error
import urllib.request
from pathlib import Path

from . import steam as steammod
from . import xdg

log = logging.getLogger("tksteamlaunch.artwork")

GAME_URL = "https://www.steamgriddb.com/api/v2/games/steam/{appid}"
GRIDS_URL = (
    "https://www.steamgriddb.com/api/v2/grids/game/{game_id}"
    "?dimensions=512x512,460x215,920x430,600x900&types=static"
)


def grid_path(appid: str) -> Path:
    return xdg.app_cache_dir() / "grids" / f"{appid}.png"


def resolve_icon(appid: str, landscape: bool = False) -> Path | None:
    """Our cached grid first, then Steam librarycache art."""
    grid = grid_path(appid)
    try:
        if grid.is_file():
            return grid
    except Exception:
        pass
    return steammod.find_game_icon(appid, landscape=landscape)


def _get_json(url: str, api_key: str, timeout: int = 15) -> dict | list | None:
    try:
        request = urllib.request.Request(url, headers={"Authorization": f"Bearer {api_key}"})
        with urllib.request.urlopen(request, timeout=timeout) as response:
            data = json.loads(response.read().decode("utf-8"))
    except Exception as e:
        log.debug("steamgriddb request failed: %s", e)
        return None
    return data if isinstance(data, (dict, list)) else None


def fetch_missing(appid: str, api_key: str) -> Path | None:
    """Download artwork for a game without local art. None on any failure."""
    if not (api_key or "").strip() or not str(appid).isdigit():
        return None
    if grid_path(appid).exists():
        return grid_path(appid)
    games = _get_json(GAME_URL.format(appid=appid), api_key)
    entries = games.get("data", []) if isinstance(games, dict) else []
    if isinstance(entries, dict):
        # /games/steam/{appid} returns a single object, not a list.
        entries = [entries]
    if not entries or not isinstance(entries[0], dict):
        return None
    game_id = entries[0].get("id")
    grids = _get_json(GRIDS_URL.format(game_id=game_id), api_key)
    thumbs = grids.get("data", []) if isinstance(grids, dict) else []
    thumb = next(
        (g.get("thumb") for g in thumbs if isinstance(g, dict) and g.get("thumb")),
        "",
    )
    if not thumb or not str(thumb).startswith("https://"):
        return None
    try:
        with urllib.request.urlopen(thumb, timeout=30) as response:
            blob = response.read()
    except Exception as e:
        log.debug("steamgriddb download failed: %s", e)
        return None
    if not blob:
        return None
    path = grid_path(appid)
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(blob)
    except Exception as e:
        log.debug("steamgriddb cache write failed: %s", e)
        return None
    return path
