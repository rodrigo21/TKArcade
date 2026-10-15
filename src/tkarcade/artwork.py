"""Game artwork via SteamGridDB with local-cache fallback (stdlib only).

Downloaded grids live in our own cache and never touch Steam's files;
the GUI prefers them over librarycache art when present.
"""

from __future__ import annotations

import json
import logging
import urllib.request
from pathlib import Path

from . import steam as steammod
from . import xdg

log = logging.getLogger("tkarcade.artwork")

GAME_URL = "https://www.steamgriddb.com/api/v2/games/steam/{appid}"
GRIDS_URL = (
    "https://www.steamgriddb.com/api/v2/grids/game/{game_id}"
    "?dimensions=512x512,460x215,920x430,600x900&types=static"
)


def grid_path(appid: str) -> Path:
    return xdg.app_cache_dir() / "grids" / f"{appid}.png"


#: Manual artwork slots per game (user-picked files, copied in).
MANUAL_KINDS = ("icon", "cover", "banner")


def manual_dir(appid: str) -> Path:
    return xdg.app_cache_dir() / "artwork" / xdg.safe_stem(str(appid))


def manual_path(appid: str, kind: str) -> Path | None:
    """Stored manual file for a slot, or None (unknown kind or missing)."""
    if kind not in MANUAL_KINDS:
        return None
    for suffix in (".png", ".jpg", ".jpeg", ".webp"):
        cand = manual_dir(appid) / f"{kind}{suffix}"
        try:
            if cand.is_file():
                return cand
        except Exception:
            continue
    return None


def store_manual(appid: str, kind: str, src: str) -> Path | None:
    """Copy an image into the manual slot. None on any failure."""
    if kind not in MANUAL_KINDS:
        return None
    try:
        origin = Path(src).expanduser()
        if not origin.is_file() or origin.suffix.lower() not in (
            ".png",
            ".jpg",
            ".jpeg",
            ".webp",
        ):
            return None
        dest_dir = manual_dir(appid)
        dest_dir.mkdir(parents=True, exist_ok=True)
        dest = dest_dir / f"{kind}{origin.suffix.lower()}"
        # Drop the other suffix variants of this same slot so it keeps
        # exactly one file; the other kinds are left untouched.
        for suffix in (".png", ".jpg", ".jpeg", ".webp"):
            old = dest_dir / f"{kind}{suffix}"
            if old != dest:
                try:
                    old.unlink()
                except OSError:
                    pass
        import shutil

        shutil.copyfile(origin, dest)
        return dest
    except Exception as e:
        log.debug("store_manual failed: %s", e)
        return None


def clear_manual(appid: str, kind: str) -> bool:
    """Remove a manual slot. True when something was deleted."""
    try:
        found = manual_path(appid, kind)
    except Exception:
        return False
    if found is None:
        return False
    try:
        found.unlink()
        return True
    except OSError:
        return False


def resolve_icon(appid: str, landscape: bool = False) -> Path | None:
    """Manual override first, then our cached grid, then Steam art."""
    try:
        manual = manual_path(appid, "icon" if not landscape else "banner")
        if manual is not None:
            return manual
    except Exception:
        pass
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
