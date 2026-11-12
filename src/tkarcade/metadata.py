"""Metadata provider registry: one download path, one cache per provider.

A provider declares how a game resolves to a target and how a payload
becomes the shared field map; ``download()`` adds the 30-day disk cache
and the per-provider rate gate. Steam, VNDB and IGDB are the adapters so
far.
"""

from __future__ import annotations

import json
import logging
import threading
import time
from dataclasses import dataclass
from typing import TYPE_CHECKING

from . import igdb, storemeta, vndb, xdg

if TYPE_CHECKING:
    from collections.abc import Callable
    from pathlib import Path

log = logging.getLogger("tkarcade.metadata")

#: Metadata fields a provider may fill, in the order the preview lists them.
FIELDS = (
    "description",
    "developer",
    "publisher",
    "genre",
    "series",
    "age_ratings",
    "date",
)

CACHE_TTL = 30 * 24 * 3600

#: Cache payload version: a payload written by an older build reads as
#: cold, so a new field (the online tags) is fetched instead of showing
#: a fresh cache that cannot answer for it.
CACHE_VERSION = 2


@dataclass(frozen=True)
class Provider:
    """One metadata source: how to reach it and how to cache it."""

    label: str
    cache_dir: str
    fields: tuple[str, ...]
    resolve: Callable[[str, str], str]
    fetch: Callable[[str, str], dict | None]
    search: Callable[[str], list[dict]] | None = None
    needs_key: bool = False
    min_interval: float = 0.0


PROVIDERS: dict[str, Provider] = {
    "steam": Provider(
        label="Steam",
        cache_dir="steam-meta",
        fields=FIELDS,
        resolve=storemeta.resolve,
        fetch=storemeta.fetch,
    ),
    "vndb": Provider(
        label="VNDB",
        cache_dir="vndb-meta",
        fields=("description", "developer", "date"),
        resolve=vndb.resolve,
        fetch=vndb.fetch,
        search=vndb.search,
        min_interval=1.0,
    ),
    "igdb": Provider(
        label="IGDB",
        cache_dir="igdb-meta",
        fields=FIELDS,
        resolve=igdb.resolve,
        fetch=igdb.fetch,
        search=igdb.search,
        needs_key=True,
        min_interval=0.25,
    ),
}

_gate_lock = threading.Lock()
_next_call: dict[str, float] = {}


def cache_path(provider: str, game_id: str) -> Path:
    entry = PROVIDERS[provider]
    return xdg.app_cache_dir() / entry.cache_dir / f"{xdg.safe_stem(game_id)}.json"


def cache_dirs() -> tuple[str, ...]:
    """Cache namespaces a removed game's cleanup must delete."""
    return tuple(entry.cache_dir for entry in PROVIDERS.values())


def cached(provider: str, game_id: str, target: str = "") -> tuple[dict | None, bool]:
    """Return (fields, is_fresh). Stale fields are returned for display.

    The cache stays keyed by the game ID and records the target it was
    fetched for: a changed match reads as not cached instead of filling
    the previous game's metadata.
    """
    entry = PROVIDERS.get(provider)
    if entry is None:
        return None, False
    wanted = entry.resolve(game_id, target)
    if not wanted:
        return None, False
    try:
        payload = json.loads(cache_path(provider, game_id).read_text(encoding="utf-8"))
    except Exception:
        return None, False
    if not isinstance(payload, dict):
        return None, False
    if payload.get("version") != CACHE_VERSION:
        return None, False
    stored = str(payload.get("target", "") or "")
    if stored and stored != wanted:
        return None, False
    data = payload.get("data")
    try:
        age = time.time() - float(payload.get("saved", 0))
    except (TypeError, ValueError):
        return None, False
    fresh = isinstance(data, dict) and age < CACHE_TTL
    return (data if isinstance(data, dict) else None), fresh


def _gate(provider: str) -> None:
    """Space provider calls out; Steam declares no interval and never waits."""
    interval = PROVIDERS[provider].min_interval
    if interval <= 0:
        return
    with _gate_lock:
        now = time.monotonic()
        start = max(now, _next_call.get(provider, 0.0))
        _next_call[provider] = start + interval
    if start > now:
        time.sleep(start - now)


def download(provider: str, game_id: str, target: str = "") -> dict | None:
    """Cached answer first, then one provider call. None on any failure."""
    entry = PROVIDERS.get(provider)
    if entry is None:
        return None
    wanted = entry.resolve(game_id, target)
    if not wanted:
        return None
    data, fresh = cached(provider, game_id, wanted)
    if fresh:
        return data
    _gate(provider)
    data = entry.fetch(game_id, wanted)
    if data is None:
        return None
    path = cache_path(provider, game_id)
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            json.dumps(
                {
                    "version": CACHE_VERSION,
                    "saved": int(time.time()),
                    "target": wanted,
                    "data": data,
                }
            ),
            encoding="utf-8",
        )
    except Exception as e:
        log.debug("metadata cache write failed: %s", e)
    return data


def search(provider: str, query: str) -> list[dict]:
    """Name search: gated and failure-tolerant, like ``download()``."""
    entry = PROVIDERS.get(provider)
    if entry is None or entry.search is None:
        return []
    _gate(provider)
    try:
        return list(entry.search(query))
    except Exception as e:
        log.debug("metadata search failed for %s: %s", provider, e)
        return []
