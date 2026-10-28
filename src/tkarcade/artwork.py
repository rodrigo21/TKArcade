"""Game artwork: official Steam assets first, then SteamGridDB.

Official art comes from Steam's public CDN and needs no key at all: the
library capsule (portrait), the library hero (wide) and the client icon
(the square one Steam itself shows). SteamGridDB is the community
fallback and needs a key; a game can point at another AppID's art
(`[artwork] artwork_appid`), installed or not.

Downloaded files live in our own cache and never touch Steam's files;
the per-kind provider is recorded next to them so the dialog can say
where a given image came from.
"""

from __future__ import annotations

import html
import json
import logging
import struct
import urllib.error
import urllib.request
from pathlib import Path

from . import steam as steammod
from . import xdg

log = logging.getLogger("tkarcade.artwork")

#: SteamGridDB API (community art; needs a key).
GAME_URL = "https://www.steamgriddb.com/api/v2/games/steam/{appid}"
GRIDS_URL = (
    "https://www.steamgriddb.com/api/v2/grids/game/{game_id}"
    "?dimensions=512x512,460x215,920x430,600x900&types=static"
)
HEROES_URL = "https://www.steamgriddb.com/api/v2/heroes/game/{game_id}?types=static"
ICONS_URL = "https://www.steamgriddb.com/api/v2/icons/game/{game_id}"

#: Public Steam endpoints (official art; no key).
APP_INFO_URL = "https://api.steampowered.com/ICommunityService/GetApps/v1/?appids[0]={appid}"
STEAM_CDN = "https://cdn.cloudflare.steamstatic.com/steam/apps/{appid}/{name}"
COMMUNITY_CDN = (
    "https://cdn.akamai.steamstatic.com/steamcommunity/public/images/apps/{appid}/{name}"
)

#: Steam answers a plain-urllib request from Cloudflare-protected hosts
#: with `403 error code: 1010`; every call here goes out with this.
USER_AGENT = "tkarcade (+https://github.com/rodrigo21/TKArcade)"

#: Artwork the dialog and the views ask for. `icon` is the small/square
#: art, `cover` the portrait one, `banner` the wide one.
ART_KINDS = ("icon", "cover", "banner")

#: Manual artwork slots per game (user-picked files, copied in).
MANUAL_KINDS = ART_KINDS

#: Where a game's art comes from, in the order the fetch tries it.
PROVIDERS = ("steam", "sgdb")

#: Shape of the SteamGridDB entry each kind wants.
_KIND_SHAPE = {"icon": "square", "cover": "portrait", "banner": "landscape"}

#: Official Steam files per kind, best first. The client icon has no
#: square sibling besides the .ico, and a few apps ship only the small
#: 32x32 jpg: `header.jpg` is the last resort (the views crop it).
_OFFICIAL_FILES = {
    "icon": ("header.jpg",),
    "cover": ("library_600x900_2x.jpg", "library_600x900.jpg", "header.jpg"),
    "banner": ("library_hero.jpg", "header.jpg"),
}

#: An entry within 15% of square counts as square (512x512, but also the
#: odd 500x500 submission).
_SQUARE_TOLERANCE = 0.15

#: Suffixes a cached file may carry; the first present one wins.
_CACHE_SUFFIXES = (".png", ".jpg", ".jpeg", ".webp", ".ico")

#: Sidecar key: the user removed this AppID's art, the background fetch
#: must not fill it back until Fetch Artwork is pressed.
CLEARED_KEY = "cleared"


# --------------------------------------------------------------------
# Cache paths


def grid_path(appid: str, kind: str = "cover") -> Path:
    """Canonical cache path for one kind (always the .png name).

    `cover` keeps the flat `grids/<appid>.png` name it has always had, so
    existing caches and the rename migration still apply to it.
    """
    base = xdg.app_cache_dir() / "grids"
    if kind not in ("icon", "banner"):
        return base / f"{appid}.png"
    return base / f"{appid}-{kind}.png"


def cached_path(appid: str, kind: str) -> Path | None:
    """The cached file for one kind, whatever its real suffix is."""
    stem = grid_path(appid, kind).with_suffix("")
    for suffix in _CACHE_SUFFIXES:
        cand = stem.with_suffix(suffix)
        try:
            if cand.is_file():
                return cand
        except Exception:
            continue
    return None


def manifest_path(appid: str) -> Path:
    """Sidecar recording which provider produced each cached kind."""
    return xdg.app_cache_dir() / "grids" / f"{appid}.json"


def read_manifest(appid: str) -> dict:
    """{kind: {"provider": ..., "appid": ...}} for one game (may be empty).

    One file per kind cannot say where it came from; the sidecar does,
    and the status row needs it to name the provider honestly.
    """
    try:
        data = json.loads(manifest_path(appid).read_text(encoding="utf-8"))
    except Exception:
        return {}
    return data if isinstance(data, dict) else {}


def _write_manifest(appid: str, kind: str, provider: str, source: str) -> None:
    data = read_manifest(appid)
    data[kind] = {"provider": provider, "appid": str(source)}
    data.pop(CLEARED_KEY, None)
    path = manifest_path(appid)
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(data, indent=2, sort_keys=True), encoding="utf-8")
    except Exception as e:
        log.debug("artwork manifest write failed: %s", e)


def _mark_cleared(appid: str) -> None:
    """Record that the user removed this AppID's art on purpose.

    The background fetch fills every hole on each window open, so without
    the mark a "Clear" would be undone by the next launch and the button
    would be cosmetic. `fetch_best(force=True)` (the Fetch Artwork button)
    is the way back.
    """
    path = manifest_path(appid)
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps({CLEARED_KEY: True}, indent=2), encoding="utf-8")
    except Exception as e:
        log.warning("artwork: could not mark %s cleared: %s", appid, e)


def is_cleared(appid: str) -> bool:
    """True when the user cleared this AppID's downloaded art on purpose."""
    return bool(read_manifest(appid).get(CLEARED_KEY))


def _unmark_cleared(appid: str) -> None:
    """Drop the cleared mark (an explicit fetch asked for the art again)."""
    data = read_manifest(appid)
    if not data.pop(CLEARED_KEY, None):
        return
    path = manifest_path(appid)
    try:
        if data:
            path.write_text(json.dumps(data, indent=2, sort_keys=True), encoding="utf-8")
        else:
            path.unlink(missing_ok=True)
    except Exception as e:
        log.debug("artwork manifest update failed: %s", e)


def clear_fetched(appid: str) -> int:
    """Delete the downloaded art of one AppID, kinds and sidecar. Count files.

    The cache belongs to the AppID, not the game: a local game borrowing a
    Steam AppID's art shares it with every other game pointing there.
    Manual slots live in their own directory and are never touched.
    """
    gid = str(appid)
    removed = 0
    for kind in ART_KINDS:
        stem = grid_path(gid, kind).with_suffix("")
        for suffix in _CACHE_SUFFIXES:
            cand = stem.with_suffix(suffix)
            try:
                if cand.is_file():
                    cand.unlink()
                    removed += 1
            except OSError as e:
                log.warning("artwork: could not remove %s: %s", cand, e)
    _mark_cleared(gid)
    return removed


def provider_for(appid: str, kind: str) -> str:
    """Recorded provider of one kind ("steam", "sgdb") or ""."""
    entry = read_manifest(appid).get(kind)
    if isinstance(entry, dict):
        value = str(entry.get("provider", "")).strip()
        if value in PROVIDERS:
            return value
    return ""


# --------------------------------------------------------------------
# Manual slots


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


# --------------------------------------------------------------------
# Resolution (local only, never the network)


def _steam_art(appid: str, kind: str) -> Path | None:
    """Steam's locally cached art for one kind (installed games only)."""
    try:
        if kind == "banner":
            return steammod.find_game_icon(appid, landscape=True)
        if kind == "cover":
            return steammod.find_game_icon(appid, portrait=True)
        return steammod.find_game_icon(appid)
    except Exception:
        return None


def resolve(appid: str, kind: str = "icon", donor: str = "") -> tuple[Path | None, str]:
    """Where the art for one kind comes from, without touching the network.

    Order: the game's manual slot, its downloaded cache, Steam's own
    cache, then the same three for `donor` — the Artwork Source AppID a
    local game borrows art from. Returns `(path, source)`, where source
    is "manual", "cache", "steam", the `donor-` prefixed versions of
    those, or "" when nothing answered.

    Downloading is the caller's job (see `fetch_best`): this runs for
    every row on every refresh, so it must stay local and cheap.
    """
    if kind not in ART_KINDS:
        kind = "icon"
    chain = [(str(appid), "")]
    donor = str(donor or "").strip()
    if donor and donor != str(appid):
        chain.append((donor, "donor-"))
    for gid, prefix in chain:
        path, source = _local_art(gid, kind)
        if path is not None:
            return path, prefix + source
    return None, ""


def _local_art(gid: str, kind: str) -> tuple[Path | None, str]:
    """(path, "manual"|"cache"|"steam") for one game, no network."""
    try:
        manual = manual_path(gid, kind)
    except Exception:
        manual = None
    if manual is not None:
        return manual, "manual"
    # Before the per-kind cache existed, the downloaded cover was what the
    # list and the cards showed as icon: keep those profiles looking the
    # same until a square one is fetched.
    names = ("cover", kind) if kind == "icon" else (kind,)
    for name in names:
        cached = cached_path(gid, name)
        if cached is not None:
            return cached, "cache"
    art = _steam_art(gid, kind)
    if art is not None:
        return art, "steam"
    return None, ""


def resolve_icon(appid: str, landscape: bool = False) -> Path | None:
    """Manual override first, then our cached grid, then Steam art."""
    return resolve(appid, "banner" if landscape else "icon")[0]


# --------------------------------------------------------------------
# HTTP


def _get(url: str, api_key: str = "", timeout: int = 30) -> tuple[bytes | None, str]:
    """Fetch a URL. Returns (body, error), error "" on success.

    Error tokens: "blocked" (403, Cloudflare's browser check),
    "not-found" (404), "http" (anything else) and "network".
    """
    headers = {"User-Agent": USER_AGENT}
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"
    try:
        request = urllib.request.Request(url, headers=headers)
        with urllib.request.urlopen(request, timeout=timeout) as response:
            return response.read(), ""
    except urllib.error.HTTPError as e:
        if e.code == 403:
            log.warning("artwork: %s refused the request (403)", url)
            return None, "blocked"
        if e.code == 404:
            return None, "not-found"
        log.warning("artwork: %s answered HTTP %s", url, e.code)
        return None, "http"
    except Exception as e:
        log.warning("artwork: %s failed: %s", url, e)
        return None, "network"


def _get_json(url: str, api_key: str = "") -> dict | list | None:
    body, error = _get(url, api_key, timeout=20)
    if body is None:
        return None
    try:
        data = json.loads(body.decode("utf-8"))
    except Exception as e:
        log.warning("artwork: %s returned invalid JSON: %s", url, e)
        return None
    return data if isinstance(data, (dict, list)) else None


def steam_app(appid: str) -> dict | None:
    """Official Steam record for an AppID: {"name", "icon"}, or None.

    Doubles as validation: Steam answers a bare `{"appid": N}` (no name)
    for numbers that are not apps, which is the usual mistake of pasting a
    SteamGridDB game id instead of a Steam AppID.
    """
    if not str(appid).isdigit():
        return None
    body, _error = _get(APP_INFO_URL.format(appid=appid), timeout=15)
    if body is None:
        return None
    try:
        apps = json.loads(body.decode("utf-8"))["response"]["apps"]
    except Exception:
        return None
    if not apps or not isinstance(apps[0], dict):
        return None
    name = str(apps[0].get("name") or "").strip()
    if not name:
        return None
    return {
        "appid": str(apps[0].get("appid", appid)),
        "name": html.unescape(name),
        "icon": str(apps[0].get("icon") or ""),
    }


# --------------------------------------------------------------------
# Fetching


def ico_png_frame(blob: bytes) -> bytes | None:
    """The largest PNG frame inside an .ico file, or None.

    Steam's client icons are multi-size ICOs whose biggest frame is a
    plain PNG; Qt reads the first (16x16) frame of the container, so the
    frame is unwrapped here and stored as a normal image. Icons with only
    BMP frames return None (the caller falls back to the jpg).
    """
    if len(blob) < 22 or blob[:4] != b"\x00\x00\x01\x00":
        return None
    try:
        count = struct.unpack("<H", blob[4:6])[0]
    except struct.error:
        return None
    best: tuple[int, bytes] | None = None
    for index in range(count):
        offset = 6 + index * 16
        entry = blob[offset : offset + 16]
        if len(entry) < 16:
            continue
        width, height, _colors, _res, _planes, _bpp, size, start = struct.unpack("<BBBBHHII", entry)
        frame = blob[start : start + size]
        if frame[:8] != b"\x89PNG\r\n\x1a\n":
            continue
        area = (width or 256) * (height or 256)
        if best is None or area > best[0]:
            best = (area, frame)
    return best[1] if best else None


def _store(appid: str, kind: str, url: str) -> Path | None:
    """Download one URL into the kind's cache slot, keeping its suffix."""
    body, _error = _get(url)
    if not body:
        return None
    if body[:4] == b"\x00\x00\x01\x00":
        frame = ico_png_frame(body)
        if frame is None:
            return None
        body = frame
    suffix = _stored_suffix(url, body)
    dest = grid_path(appid, kind).with_suffix(suffix)
    try:
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(body)
    except Exception as e:
        log.warning("artwork: could not write %s: %s", dest, e)
        return None
    # One file per kind: drop the other suffixes (only after the new file
    # landed) so the cache and the manifest never disagree.
    stem = grid_path(appid, kind).with_suffix("")
    for other in _CACHE_SUFFIXES:
        if other != suffix:
            try:
                stem.with_suffix(other).unlink()
            except OSError:
                pass
    return dest


def _stored_suffix(url: str, body: bytes) -> str:
    """Suffix for a downloaded body: the URL's, unless it was unwrapped."""
    suffix = Path(url.split("?")[0]).suffix.lower()
    if suffix not in _CACHE_SUFFIXES:
        return ".png"
    if suffix == ".ico" and body[:8] == b"\x89PNG\r\n\x1a\n":
        # The ICO was unwrapped: the cache holds a real PNG now.
        return ".png"
    return suffix


def _official_candidates(appid: str, kind: str, info: dict | None) -> list[str]:
    """Official Steam URLs to try for one kind, best first."""
    urls = [STEAM_CDN.format(appid=appid, name=name) for name in _OFFICIAL_FILES.get(kind, ())]
    hash_ = (info or {}).get("icon", "")
    if kind == "icon" and hash_:
        # Steam's own client icon: a multi-size .ico (up to 256x256),
        # with the 32x32 jpg as the fallback some apps ship alone.
        urls = [
            COMMUNITY_CDN.format(appid=appid, name=f"{hash_}.ico"),
            COMMUNITY_CDN.format(appid=appid, name=f"{hash_}.jpg"),
        ] + urls
    return urls


def fetch_official(
    appid: str, kinds=ART_KINDS, info: dict | None = None, force: bool = False
) -> dict[str, Path]:
    """Download the official Steam art of `appid` (no key needed).

    `info` is an already-resolved `steam_app()` record; it is looked up
    when omitted. With force, cached kinds are refreshed too.
    """
    gid = str(appid)
    if not gid.isdigit():
        return {}
    if not force and is_cleared(gid):
        return {}
    wanted = [kind for kind in kinds if force or cached_path(gid, kind) is None]
    if not wanted:
        return {}
    if info is None and "icon" in wanted:
        info = steam_app(gid)
    out: dict[str, Path] = {}
    for kind in wanted:
        for url in _official_candidates(gid, kind, info):
            path = _store(gid, kind, url)
            if path is not None:
                out[kind] = path
                _write_manifest(gid, kind, "steam", gid)
                break
    return out


def _sgdb_thumbs(appid: str, kind: str, api_key: str) -> list[dict]:
    """SteamGridDB entries for one kind, official ones first."""
    game = _get_json(GAME_URL.format(appid=appid), api_key)
    entries = game.get("data", []) if isinstance(game, dict) else []
    if isinstance(entries, dict):
        # /games/steam/{appid} returns a single object, not a list.
        entries = [entries]
    if not entries or not isinstance(entries[0], dict):
        return []
    game_id = entries[0].get("id")
    if kind == "icon":
        data = _get_json(ICONS_URL.format(game_id=game_id), api_key)
    elif kind == "banner":
        data = _get_json(HEROES_URL.format(game_id=game_id), api_key)
    else:
        data = _get_json(GRIDS_URL.format(game_id=game_id), api_key)
    rows = data.get("data", []) if isinstance(data, dict) else []
    rows = [row for row in rows if isinstance(row, dict) and _is_image(row)]
    shape = _KIND_SHAPE.get(kind, "")
    # Valve's own assets are tagged `official` by the site: they win. The
    # requested shape comes first, but an entry without dimensions is
    # still usable (it is the old SteamGridDB answer) and stays last.
    return sorted(
        rows,
        key=lambda row: (
            _entry_shape(row) != shape,
            row.get("style") != "official",
            -(row.get("score") or 0),
        ),
    )


def _is_image(entry: dict) -> bool:
    """A thumb we can hand to Qt (it cannot read the .ico submissions)."""
    thumb = str(entry.get("thumb") or "")
    mime = str(entry.get("mime") or "")
    if not thumb.startswith("https://"):
        return False
    return mime in ("", "image/png", "image/jpeg", "image/webp")


def fetch_sgdb(
    appid: str,
    api_key: str,
    kinds=ART_KINDS,
    force: bool = False,
) -> tuple[dict[str, Path], str]:
    """Download community art from SteamGridDB. (paths, error token)."""
    gid = str(appid)
    if not (api_key or "").strip() or not gid.isdigit():
        return {}, "no-key"
    if not force and is_cleared(gid):
        return {}, ""
    wanted = [kind for kind in kinds if force or cached_path(gid, kind) is None]
    if not wanted:
        return {}, ""
    if not _sgdb_game_exists(gid, api_key):
        return {}, "not-found"
    out: dict[str, Path] = {}
    for kind in wanted:
        for entry in _sgdb_thumbs(gid, kind, api_key):
            path = _store(gid, kind, str(entry["thumb"]))
            if path is not None:
                out[kind] = path
                _write_manifest(gid, kind, "sgdb", gid)
                break
    return out, ""


def _sgdb_game_exists(appid: str, api_key: str) -> bool:
    data = _get_json(GAME_URL.format(appid=appid), api_key)
    entries = data.get("data", []) if isinstance(data, dict) else []
    if isinstance(entries, dict):
        entries = [entries]
    return bool(entries) and isinstance(entries[0], dict)


def fetch_best(
    appid: str,
    provider: str = "steam",
    api_key: str = "",
    kinds=ART_KINDS,
    force: bool = False,
) -> dict:
    """Download a game's art with the chosen provider first.

    Returns {"art": {kind: Path}, "provider": "steam"|"sgdb", "error":
    token, "name": Steam name or "", "valid": whether the AppID is a real
    Steam app}. The first provider fills what it can; the second one only
    covers the kinds still missing. Official Steam art never needs a key.
    """
    gid = str(appid)
    result = {"art": {}, "provider": "", "error": "", "name": "", "valid": False}
    if not gid.isdigit():
        result["error"] = "no-appid"
        return result
    if force:
        # Fetch Artwork is explicit: the user wants the art back, so the
        # marker that keeps the background fetch away goes.
        _unmark_cleared(gid)
    info = steam_app(gid)
    result["valid"] = info is not None
    result["name"] = (info or {}).get("name", "")
    order = PROVIDERS if provider == "steam" else tuple(reversed(PROVIDERS))
    missing = [kind for kind in kinds if kind in ART_KINDS]
    first = True
    for source in order:
        if not missing:
            break
        art, error = _fetch_from(source, gid, missing, info, api_key, force and first)
        first = False
        for kind, path in art.items():
            result["art"][kind] = path
            missing = [item for item in missing if item != kind]
        if art and not result["provider"]:
            result["provider"] = source
        if error and not result["error"]:
            result["error"] = error
    if not result["art"] and not result["error"]:
        result["error"] = "no-art" if result["valid"] else "not-a-steam-app"
    return result


def _fetch_from(
    source: str, gid: str, kinds, info: dict | None, api_key: str, force: bool
) -> tuple[dict[str, Path], str]:
    """One provider pass: (paths, error token)."""
    if source == "steam":
        return fetch_official(gid, kinds, info, force), ""
    return fetch_sgdb(gid, api_key, kinds, force)


def fetch_missing(appid: str, api_key: str) -> Path | None:
    """Download the portrait grid of a game without local art.

    Kept for the cover-only callers: the per-provider entry point is
    `fetch_best`.
    """
    cached = cached_path(str(appid), "cover")
    if cached is not None:
        return cached
    art = fetch_best(str(appid), "sgdb", api_key, ("cover",))["art"]
    return art.get("cover")


def _entry_shape(entry: dict) -> str:
    """square / portrait / landscape for a SteamGridDB asset entry."""
    try:
        width = int(entry.get("width") or 0)
        height = int(entry.get("height") or 0)
    except (TypeError, ValueError):
        return ""
    if not width or not height:
        return ""
    if abs(width - height) <= max(width, height) * _SQUARE_TOLERANCE:
        return "square"
    return "portrait" if height > width else "landscape"
