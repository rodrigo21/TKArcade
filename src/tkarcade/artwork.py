"""Game artwork: official Steam assets first, then SteamGridDB, then IGDB.

Official art comes from Steam's public CDN and needs no key at all: the
library capsule (portrait), the library hero (wide) and the client icon
(the square one Steam itself shows). SteamGridDB is the community
fallback and needs a key; IGDB is the other community source, needs a
Twitch application and serves the game whose ``[metadata] igdb_id`` is
known, or resolves it by title. VNDB serves a visual novel's cover and a
screenshot, needs no key and resolves ``[metadata] vndb_id`` the same
way. IGDB and VNDB have no square icon. A game can point at any Steam
AppID's art (`[artwork] artwork_appid`), installed or not. A local game
without one is looked up by name and the chosen SteamGridDB, IGDB or
VNDB game id is remembered in the cache.

Downloaded files live in our own cache and never touch Steam's files;
the per-kind provider is recorded next to them so the dialog can say
where a given image came from.
"""

from __future__ import annotations

import html
import json
import logging
import re
import struct
import unicodedata
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

from . import config as cfgmod
from . import exeicon as exeiconmod
from . import igdb as igdbmod
from . import steam as steammod
from . import vndb as vndbmod
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
#: Name lookup for games without a Steam AppID (local games).
SEARCH_URL = "https://www.steamgriddb.com/api/v2/search/autocomplete/{term}"

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
#: art, `cover` the portrait one, `banner` the wide one and `background`
#: the wide backdrop, which falls back to the banner.
ART_KINDS = ("icon", "cover", "banner", "background")

#: Kinds the providers download. `background` has no asset of its own:
#: both providers only serve the hero the banner already takes, so its
#: resolution falls back to the banner instead of a second download.
FETCH_KINDS = ("icon", "cover", "banner")

#: Manual artwork slots per game (user-picked files, copied in).
MANUAL_KINDS = ART_KINDS

#: Where a game's art comes from, in the order the fetch tries it.
PROVIDERS = ("steam", "sgdb", "igdb", "vndb")

#: Kinds IGDB can fill: it has no square icon, so `icon` stays with the
#: other providers.
IGDB_KINDS = ("cover", "banner")

#: Kinds VNDB can fill: the visual novel cover and a screenshot as the
#: wide art. It has no square icon either.
VNDB_KINDS = ("cover", "banner")

#: Shape of the SteamGridDB entry each kind wants.
_KIND_SHAPE = {"icon": "square", "cover": "portrait", "banner": "landscape"}

#: Most candidates the chooser offers per kind: the list is already sorted
#: best first, so the automatic pick never falls outside the cap.
GALLERY_LIMIT = 60

#: Human labels for the official Steam files in the chooser.
_STEAM_LABELS = {
    "library_600x900_2x.jpg": "Library Cover (2x)",
    "library_600x900.jpg": "Library Cover",
    "library_hero.jpg": "Library Hero",
    "header.jpg": "Header",
}

#: Official Steam files per kind, best first. The client icon has no
#: square sibling besides the .ico, and a few apps ship only the small
#: 32x32 jpg: `header.jpg` is the last resort (the views crop it).
_OFFICIAL_FILES = {
    "icon": ("header.jpg",),
    "cover": ("library_600x900_2x.jpg", "library_600x900.jpg", "header.jpg"),
    "banner": ("library_hero.jpg", "header.jpg"),
}

#: Sidecar key: the SteamGridDB entry a name lookup resolved and the user
#: chose. Kept across Clear so Fetch restores the same game's art.
SGDB_KEY = "sgdb"

#: Sidecar key: the IGDB game id resolved by a title search or a pick.
#: Kept across Clear; a stored ``[metadata] igdb_id`` still wins.
IGDB_KEY = "igdb"

#: Sidecar key: the VNDB visual novel id resolved by a title search or a
#: pick. Kept across Clear; a stored ``[metadata] vndb_id`` still wins.
VNDB_KEY = "vndb"

#: Version of the icon precedence. A numeric AppID's cached icon whose
#: provider is "sgdb" and lacks this marker came from the old
#: SteamGridDB-first chain; it is dropped once so the Steam client icon can
#: replace it. Manual slots and the other kinds are never touched.
ICON_CHAIN_KEY = "icon_chain"
ICON_CHAIN = 2

#: An entry within 15% of square counts as square (512x512, but also the
#: odd 500x500 submission).
_SQUARE_TOLERANCE = 0.15

#: Suffixes a cached file may carry; the first present one wins.
_CACHE_SUFFIXES = (".png", ".jpg", ".jpeg", ".webp", ".avif", ".ico")

#: Suffixes an image file in our cache or manual slot may carry.
IMAGE_SUFFIXES = _CACHE_SUFFIXES

#: Suffixes a manual slot may carry; the first present one wins.
_MANUAL_SUFFIXES = (".png", ".jpg", ".jpeg", ".webp", ".avif")

#: Sidecar key: the user removed this AppID's art, the background fetch
#: must not fill it back until Fetch Artwork is pressed.
CLEARED_KEY = "cleared"

#: Sidecar key: kinds the user cleared one tile at a time. A cleared kind
#: shows nothing — Steam's own art, the exe icon and the cover/banner
#: fallbacks included — until Fetch Artwork is pressed.
CLEARED_KINDS_KEY = "cleared_kinds"

#: Sidecar key: the local executable an icon was extracted from, with its
#: stat, so a changed executable is re-extracted and an unchanged one is not.
EXE_ICON_KEY = "exe_icon"

#: Version of the extracted icon. 2 stores the best frame (a PNG frame
#: extracted, a BMP-only icon reordered largest first); an entry from an
#: older version is re-extracted once.
EXE_ICON_VERSION = 2

#: Largest side a stored `icon` keeps; a bigger source is downscaled.
#: 1024 covers the dialog tooltip (~378 logical px at 2x) and the card
#: fallback (~648), and keeps a square icon cheap.
ICON_MAX_SIDE = 1024

#: Largest image a pasted URL may deliver; anything bigger is refused
#: before it reaches the disk.
URL_IMAGE_LIMIT = 20 * 1024 * 1024

#: Largest API or store JSON body; a bigger answer is refused unread.
JSON_LIMIT = 8 * 1024 * 1024

#: Stored art warns above 4K and is refused above 8K or 32 megapixels.
#: The refusal keeps a small file from decoding into hundreds of MB.
IMAGE_SOFT_SIDE = 4096
IMAGE_MAX_SIDE = 8192
IMAGE_MAX_PIXELS = 33_554_432


def image_size_token(width: int, height: int) -> str:
    """Pixel-size token: "huge" (refuse), "large" (warn) or ""."""
    if width <= 0 or height <= 0:
        return ""
    if width > IMAGE_MAX_SIDE or height > IMAGE_MAX_SIDE or width * height > IMAGE_MAX_PIXELS:
        return "huge"
    if max(width, height) > IMAGE_SOFT_SIDE:
        return "large"
    return ""


# --------------------------------------------------------------------
# Cache paths


def _art_key(appid: str) -> str:
    """Steam art is keyed by AppID; local art by the game ID."""
    return steammod.steam_appid(appid) or str(appid)


def _cache_key(appid: str) -> str:
    """Cache name: `steam-<appid>` for Steam, the local ID otherwise."""
    numeric = steammod.steam_appid(appid)
    return f"steam-{numeric}" if numeric else str(appid)


def grid_path(appid: str, kind: str = "cover") -> Path:
    """Canonical cache path for one kind (always the .png name).

    `cover` keeps the flat `grids/<appid>.png` name it has always had, so
    existing caches and the rename migration still apply to it.
    """
    base = xdg.app_cache_dir() / "grids"
    key = xdg.safe_stem(_cache_key(appid))
    if kind not in ("icon", "banner", "background"):
        return base / f"{key}.png"
    return base / f"{key}-{kind}.png"


def exe_icon_path(appid: str, suffix: str = ".ico") -> Path:
    """Cache path of the icon extracted from a local game's executable.

    Deliberately not `<key>-icon.*`: that name belongs to downloaded
    client icons, and Clear must not delete a file the game ships. The
    suffix is `.png` when the executable's icon had a PNG frame and
    `.ico` otherwise.
    """
    base = xdg.app_cache_dir() / "grids"
    return base / f"{xdg.safe_stem(_cache_key(appid))}-exe{suffix}"


def cached_path(appid: str, kind: str) -> Path | None:
    """The cached file for one kind, whatever its real suffix is."""
    path = grid_path(appid, kind)
    stem = path.stem  # removes only ".png": an AppID may contain dots
    for suffix in _CACHE_SUFFIXES:
        cand = path.with_name(stem + suffix)
        try:
            if cand.is_file():
                return cand
        except Exception:
            continue
    return None


def manifest_path(appid: str) -> Path:
    """Sidecar recording which provider produced each cached kind."""
    return xdg.app_cache_dir() / "grids" / f"{xdg.safe_stem(_cache_key(appid))}.json"


def read_manifest(appid: str) -> dict:
    """{kind: {"provider": ...}} for one game (may be empty).

    One file per kind cannot say where it came from; the sidecar does,
    and the status row needs it to name the provider honestly.
    """
    try:
        data = json.loads(manifest_path(appid).read_text(encoding="utf-8"))
    except Exception:
        return {}
    return data if isinstance(data, dict) else {}


def _store_manifest(appid: str, data: dict) -> None:
    """Persist the sidecar atomically: a crash or a second writer must not
    truncate it, since an empty read loses every provider and cached id."""
    path = manifest_path(appid)
    if not data:
        path.unlink(missing_ok=True)
        return
    cfgmod.write_atomic(path, json.dumps(data, indent=2, sort_keys=True))


def _write_manifest(appid: str, kind: str, provider: str) -> None:
    data = read_manifest(appid)
    data[kind] = {"provider": provider}
    data.pop(CLEARED_KEY, None)
    marked = data.get(CLEARED_KINDS_KEY)
    if isinstance(marked, list):
        left = [item for item in marked if item != kind]
        if left:
            data[CLEARED_KINDS_KEY] = left
        else:
            data.pop(CLEARED_KINDS_KEY, None)
    try:
        _store_manifest(appid, data)
    except Exception as e:
        log.debug("artwork manifest write failed: %s", e)


def _mark_cleared(appid: str) -> None:
    """Record that the user removed this AppID's art on purpose.

    The background fetch fills every hole on each window open, so without
    the mark a "Clear" would be undone by the next launch and the button
    would be cosmetic. The mark also hides every fallback (Steam's own
    art, the exe icon, the cover/banner siblings), so the tiles go empty.
    `fetch_best(force=True)` (the Fetch Artwork button) is the way back. A
    name lookup's SGDB or IGDB entry survives the Clear, so the next Fetch
    restores the same game's art.
    """
    data = read_manifest(appid)
    kept = {key: value for key, value in data.items() if key in (SGDB_KEY, IGDB_KEY, VNDB_KEY)}
    kept[CLEARED_KEY] = True
    try:
        _store_manifest(appid, kept)
    except Exception as e:
        log.warning("artwork: could not mark %s cleared: %s", appid, e)


def is_cleared(appid: str) -> bool:
    """True when the user cleared this AppID's downloaded art on purpose."""
    return bool(read_manifest(appid).get(CLEARED_KEY))


def is_kind_cleared(appid: str, kind: str) -> bool:
    """True when one kind is cleared, by its own mark or the whole AppID's."""
    data = read_manifest(appid)
    if data.get(CLEARED_KEY):
        return True
    marked = data.get(CLEARED_KINDS_KEY)
    return isinstance(marked, list) and kind in marked


def unmark_cleared(appid: str, kinds=()) -> None:
    """Drop the cleared marks: an explicit fetch or pick asked for the art."""
    data = read_manifest(appid)
    changed = bool(data.pop(CLEARED_KEY, None))
    marked = data.get(CLEARED_KINDS_KEY)
    if isinstance(marked, list):
        left = [item for item in marked if item not in kinds] if kinds else []
        if left != marked:
            changed = True
        if left:
            data[CLEARED_KINDS_KEY] = left
        else:
            data.pop(CLEARED_KINDS_KEY, None)
    if not changed:
        return
    try:
        _store_manifest(appid, data)
    except Exception as e:
        log.debug("artwork manifest update failed: %s", e)


def clear_fetched(appid: str) -> int:
    """Delete the downloaded art of one AppID, kinds and sidecar. Count files.

    The cache belongs to the AppID, not the game: a local game borrowing a
    Steam AppID's art shares it with every other game pointing there.
    Manual slots live in their own directory and are never touched, but
    the mark hides them: the game shows no art until Fetch Artwork.
    """
    gid = _art_key(appid)
    removed = 0
    for kind in ART_KINDS:
        path = grid_path(gid, kind)
        stem = path.stem  # removes only ".png": an AppID may contain dots
        for suffix in _CACHE_SUFFIXES:
            cand = path.with_name(stem + suffix)
            try:
                if cand.is_file():
                    cand.unlink()
                    removed += 1
            except OSError as e:
                log.warning("artwork: could not remove %s: %s", cand, e)
    _mark_cleared(gid)
    return removed


def clear_kind(appid: str, kind: str) -> bool:
    """Delete one kind's downloaded file and keep every fallback away.

    Only that kind goes: clearing `background` leaves the banner file and
    clearing `icon` leaves the cover, but the mark hides both so the tile
    stays empty until Fetch Artwork. True when a file was deleted.
    """
    if kind not in ART_KINDS:
        return False
    gid = _art_key(appid)
    removed = False
    path = grid_path(gid, kind)
    stem = path.stem  # removes only ".png": an AppID may contain dots
    for suffix in _CACHE_SUFFIXES:
        cand = path.with_name(stem + suffix)
        try:
            if cand.is_file():
                cand.unlink()
                removed = True
        except OSError as e:
            log.warning("artwork: could not remove %s: %s", cand, e)
    data = read_manifest(gid)
    data.pop(kind, None)
    marked = data.get(CLEARED_KINDS_KEY)
    marked = [item for item in marked if item != kind] if isinstance(marked, list) else []
    marked.append(kind)
    data[CLEARED_KINDS_KEY] = marked
    try:
        _store_manifest(gid, data)
    except Exception as e:
        log.warning("artwork: could not mark %s/%s cleared: %s", gid, kind, e)
    return removed


def provider_for(appid: str, kind: str) -> str:
    """Recorded provider of one kind ("steam", "sgdb", "igdb", "vndb") or ""."""
    entry = read_manifest(appid).get(kind)
    if isinstance(entry, dict):
        value = str(entry.get("provider", "")).strip()
        if value in PROVIDERS:
            return value
    return ""


def stored_sgdb_id(appid: str) -> str:
    """SteamGridDB game id a name lookup resolved for this game ("" one)."""
    entry = read_manifest(appid).get(SGDB_KEY)
    if isinstance(entry, dict):
        return str(entry.get("game_id", "")).strip()
    return ""


def store_sgdb_id(appid: str, game_id: str, name: str) -> None:
    """Remember the resolved SteamGridDB entry for the next fetch."""
    data = read_manifest(appid)
    data[SGDB_KEY] = {"game_id": str(game_id), "name": str(name)}
    data.pop(CLEARED_KEY, None)
    try:
        _store_manifest(appid, data)
    except Exception as e:
        log.debug("artwork sgdb id write failed: %s", e)


def stored_igdb_id(appid: str) -> str:
    """IGDB game id a title search or a pick resolved for this game ("" one)."""
    entry = read_manifest(appid).get(IGDB_KEY)
    if isinstance(entry, dict):
        return str(entry.get("game_id", "")).strip()
    return ""


def store_igdb_id(appid: str, game_id: str, name: str = "") -> None:
    """Remember the resolved IGDB entry for the next fetch."""
    data = read_manifest(appid)
    data[IGDB_KEY] = {"game_id": str(game_id), "name": str(name)}
    try:
        _store_manifest(appid, data)
    except Exception as e:
        log.debug("artwork igdb id write failed: %s", e)


def stored_vndb_id(appid: str) -> str:
    """VNDB id a title search or a pick resolved for this game ("" one)."""
    entry = read_manifest(appid).get(VNDB_KEY)
    if isinstance(entry, dict):
        return str(entry.get("game_id", "")).strip()
    return ""


def store_vndb_id(appid: str, vn_id: str, name: str = "") -> None:
    """Remember the resolved VNDB visual novel for the next fetch."""
    data = read_manifest(appid)
    data[VNDB_KEY] = {"game_id": str(vn_id), "name": str(name)}
    try:
        _store_manifest(appid, data)
    except Exception as e:
        log.debug("artwork vndb id write failed: %s", e)


def _safe_downloads() -> bool:
    """True when the preference asks providers to hide explicit art."""
    try:
        return bool(cfgmod.load_preferences().hide_explicit_artwork)
    except Exception:
        return False


def _mark_icon_chain(appid: str) -> None:
    """Record that this cache's icon came from the current chain."""
    data = read_manifest(appid)
    data[ICON_CHAIN_KEY] = ICON_CHAIN
    try:
        _store_manifest(appid, data)
    except Exception as e:
        log.debug("artwork icon chain write failed: %s", e)


def _drop_stale_sgdb_icon(appid: str) -> None:
    """Drop an icon left by the old SteamGridDB-first chain, once.

    A numeric AppID's real icon is Steam's; the marker tells a post-fix
    download from an old one, and the next fetch replaces it. Manual slots,
    covers and banners are untouched.
    """
    gid = str(appid)
    if not gid.isdigit():
        return
    data = read_manifest(gid)
    entry = data.get("icon")
    if not isinstance(entry, dict) or entry.get("provider") != "sgdb":
        return
    if data.get(ICON_CHAIN_KEY) == ICON_CHAIN:
        return
    path = grid_path(gid, "icon")
    for suffix in _CACHE_SUFFIXES:
        try:
            path.with_suffix(suffix).unlink()
        except OSError:
            pass
    data.pop("icon", None)
    try:
        _store_manifest(gid, data)
    except Exception as e:
        log.debug("artwork: stale icon cleanup failed: %s", e)


# --------------------------------------------------------------------
# Manual slots


def manual_dir(appid: str) -> Path:
    return xdg.app_cache_dir() / "artwork" / xdg.safe_stem(_cache_key(appid))


def manual_path(appid: str, kind: str) -> Path | None:
    """Stored manual file for a slot, or None (unknown kind or missing)."""
    if kind not in MANUAL_KINDS:
        return None
    for suffix in _MANUAL_SUFFIXES:
        cand = manual_dir(appid) / f"{kind}{suffix}"
        try:
            if cand.is_file():
                return cand
        except Exception:
            continue
    return None


def _manual_dest(appid: str, kind: str, suffix: str) -> Path:
    """Destination for one manual slot, dropping its other suffix variants.

    The other kinds are left untouched.
    """
    dest_dir = manual_dir(appid)
    dest_dir.mkdir(parents=True, exist_ok=True)
    dest = dest_dir / f"{kind}{suffix}"
    for other in _MANUAL_SUFFIXES:
        old = dest_dir / f"{kind}{other}"
        if old != dest:
            try:
                old.unlink()
            except OSError:
                pass
    return dest


def store_manual(appid: str, kind: str, src: str) -> Path | None:
    """Copy an image into the manual slot. None on any failure."""
    if kind not in MANUAL_KINDS:
        return None
    try:
        origin = Path(src).expanduser()
        if not origin.is_file() or origin.suffix.lower() not in _MANUAL_SUFFIXES:
            return None
        dest = _manual_dest(appid, kind, origin.suffix.lower())
        import shutil

        shutil.copyfile(origin, dest)
        return dest
    except Exception as e:
        log.debug("store_manual failed: %s", e)
        return None


def image_suffix(data: bytes) -> str:
    """Suffix for the detected image type ("" when the bytes are not one)."""
    if data.startswith(b"\x89PNG\r\n\x1a\n"):
        return ".png"
    if data.startswith(b"\xff\xd8\xff"):
        return ".jpg"
    if data[:4] == b"RIFF" and data[8:12] == b"WEBP":
        return ".webp"
    if _is_avif(data):
        return ".avif"
    return ""


def _is_avif(data: bytes) -> bool:
    """True for AVIF/AVIF-sequence: an ISO-BMFF box with that brand."""
    if len(data) < 16 or data[4:8] != b"ftyp":
        return False
    size = int.from_bytes(data[:4], "big")
    end = min(len(data), size if size >= 16 else len(data))
    brands = data[8:end]
    return any(
        brands[index : index + 4] in (b"avif", b"avis") for index in range(0, len(brands) - 3, 4)
    )


def store_manual_bytes(appid: str, kind: str, data: bytes) -> Path | None:
    """Store an image already in memory into the manual slot."""
    if kind not in MANUAL_KINDS:
        return None
    suffix = image_suffix(data)
    if not suffix:
        return None
    try:
        dest = _manual_dest(appid, kind, suffix)
        dest.write_bytes(data)
        return dest
    except Exception as e:
        log.debug("store_manual_bytes failed: %s", e)
        return None


def fetch_image(url: str, limit: int = URL_IMAGE_LIMIT) -> tuple[bytes | None, str]:
    """Download one pasted URL: (body, error token).

    The payload is not sniffed here: the GUI decodes it through Qt, which
    accepts every format the installed plugins read.
    """
    return _get(url, limit=limit)


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


def cache_files(appid: str) -> list[Path]:
    """Every cached artifact for one game: grids, sidecar, exe icon, manual art."""
    base = xdg.app_cache_dir() / "grids"
    key = xdg.safe_stem(_cache_key(appid))
    candidates = [base / f"{key}{ext}" for ext in _CACHE_SUFFIXES]
    candidates += [
        base / f"{key}-{kind}{ext}"
        for kind in ("icon", "banner", "background")
        for ext in _CACHE_SUFFIXES
    ]
    candidates.append(base / f"{key}.json")
    candidates += [base / f"{key}-exe{ext}" for ext in (".avif", ".png", ".ico")]
    out: list[Path] = []
    for cand in candidates:
        try:
            if cand.is_file():
                out.append(cand)
        except OSError:
            continue
    try:
        out.extend(p for p in manual_dir(appid).iterdir() if p.is_file())
    except OSError:
        pass
    return out


def clear_cache(appid: str) -> bool:
    """Delete every cached artifact for one game. True when something went."""
    removed = False
    for path in cache_files(appid):
        try:
            path.unlink()
            removed = True
        except OSError as e:
            log.debug("artwork: cannot remove %s: %s", path, e)
    try:
        manual_dir(appid).rmdir()
    except OSError:
        pass
    return removed


def cache_keys() -> set[str]:
    """Game IDs that still have artwork in the cache (grids or manual slots)."""
    keys: set[str] = set()
    try:
        names = [p.name for p in (xdg.app_cache_dir() / "grids").iterdir() if p.is_file()]
    except OSError:
        names = []
    for name in names:
        for ext in (".json", *_CACHE_SUFFIXES):
            if not name.endswith(ext):
                continue
            stem = name[: -len(ext)]
            for suffix in ("-icon", "-banner", "-background", "-exe"):
                if stem.endswith(suffix):
                    stem = stem[: -len(suffix)]
                    break
            keys.add(stem)
            break
    try:
        keys.update(p.name for p in (xdg.app_cache_dir() / "artwork").iterdir() if p.is_dir())
    except OSError:
        pass
    return keys


def migrate_cache_keys() -> list[tuple[str, str]]:
    """Rename numeric Steam cache names to `steam-<appid>` (idempotent).

    Steam art used to be keyed by the bare AppID. Every cache directory
    that still carries the old name is renamed in place; an existing
    target is left alone, never overwritten.
    """
    renamed: list[tuple[str, str]] = []
    cache = xdg.app_cache_dir()
    for base in ("grids", "artwork", "protondb", "steam-release"):
        try:
            entries = list((cache / base).iterdir())
        except OSError:
            continue
        for entry in entries:
            digits = len(entry.name) - len(entry.name.lstrip("0123456789"))
            if not digits:
                continue
            rest = entry.name[digits:]
            if rest and not rest.startswith(("-", ".")):
                continue
            dest = entry.with_name(f"steam-{entry.name}")
            try:
                if dest.exists():
                    continue
                entry.rename(dest)
                renamed.append((entry.name, dest.name))
            except OSError as e:
                log.debug("artwork: cannot rename %s: %s", entry, e)
    return renamed


# --------------------------------------------------------------------
# Resolution (local only, never the network)


def _steam_art(appid: str, kind: str) -> Path | None:
    """Steam's locally cached art for one kind (installed games only)."""
    try:
        if kind in ("banner", "background"):
            return steammod.find_game_icon(appid, landscape=True)
        if kind == "cover":
            return steammod.find_game_icon(appid, portrait=True)
        return steammod.find_game_icon(appid)
    except Exception:
        return None


def resolve(
    appid: str, kind: str = "icon", source_appid: str = "", exe: str = ""
) -> tuple[Path | None, str]:
    """Where the art for one kind comes from, without touching the network.

    Order: the game's own manual slot, then the Artwork Source AppID
    (manual slot, downloaded cache, Steam's own cache), then the game's
    downloaded cache, Steam art and — for a local game's icon only — the
    image embedded in its executable, with the cover as the icon's last
    resort. `source_appid` is a Steam AppID typed in the dialog: it wins
    over the game's own art, which is what the field means. Its sources
    come back prefixed `appid-`. `exe` is a local game's executable; it
    is ignored for a Steam game. Returns `(path, source)`, or
    `(None, "")` when nothing answered.

    Downloading is the caller's job (see `fetch_best`): this runs for
    every row on every refresh, so it must stay local and cheap.
    """
    if kind not in ART_KINDS:
        kind = "icon"
    if is_cleared(str(appid)):
        # Clear hides the manual slot too: the user asked for an empty
        # tile, and only Fetch Artwork brings the art back.
        return None, ""
    own_manual = _safe_manual(str(appid), kind)
    if own_manual is not None:
        return own_manual, "manual"
    if is_kind_cleared(str(appid), kind):
        # A cleared kind blocks the Artwork Source AppID too: the tile the
        # user emptied must stay empty, whatever sits under it.
        return None, ""
    source_appid = str(source_appid or "").strip()
    if kind == "icon" and str(appid).startswith("local-"):
        local = _local_exe_icon(str(appid), kind, exe, source_appid)
        if local is not None:
            return local
    return _fallback_art(str(appid), kind, source_appid, exe)


def _fallback_art(appid: str, kind: str, source_appid: str, exe: str) -> tuple[Path | None, str]:
    """The Artwork Source AppID, then the game's own art, no network."""
    if source_appid and source_appid != appid:
        if is_kind_cleared(source_appid, kind):
            return None, ""
        path, source = _local_art(source_appid, kind)
        if path is not None:
            return path, "appid-" + source
    return _local_art(appid, kind, exe)


def _safe_manual(gid: str, kind: str) -> Path | None:
    """A game's manual slot, or None when the cache is unreadable."""
    try:
        return manual_path(gid, kind)
    except Exception:
        return None


def _community_icon(gid: str) -> Path | None:
    """Cached icon not from Steam's official client icon.

    A provider-less file is a download from before the sidecar recorded
    providers: it is treated as downloaded art, not as the official
    32x32 client icon, and keeps winning over the executable's icon.
    """
    path = cached_path(gid, "icon")
    if path is None or provider_for(str(gid), "icon") == "steam":
        return None
    return path


def _local_exe_icon(appid: str, kind: str, exe: str, source_appid: str) -> tuple[Path, str] | None:
    """A local game's icon when it has an executable icon to show.

    Manual and community art still win; Steam's own art (the 32x32
    client icon, or the Artwork Source AppID's cover used as an icon)
    does not: the image the game ships is the better icon. The rest of
    the chain stays as a fallback when the executable has no icon.
    """
    from_exe = exe_icon(appid, exe)
    if from_exe is None:
        return None
    if source_appid and source_appid != appid and not is_kind_cleared(source_appid, kind):
        manual = _safe_manual(source_appid, kind)
        if manual is not None:
            return manual, "appid-manual"
        community = _community_icon(source_appid)
        if community is not None:
            return community, "appid-cache"
    community = _community_icon(appid)
    if community is not None:
        return community, "cache"
    return from_exe, "exe"


def _local_art(gid: str, kind: str, exe: str = "") -> tuple[Path | None, str]:
    """(path, "manual"|"cache"|"steam"|"exe") for one game, no network."""
    manual = _safe_manual(gid, kind)
    if manual is not None:
        return manual, "manual"
    # Before the per-kind cache existed, the downloaded cover was what the
    # list and the cards showed as icon. It now only fills the hole when
    # no square icon was fetched: the icon a fetch just downloaded must
    # not lose to the cover sitting next to it. `background` defaults to
    # the banner art, since no provider serves a separate wide asset.
    if kind == "icon":
        names = (kind, "cover")
    elif kind == "background":
        names = (kind, "banner")
    else:
        names = (kind,)
    for name in names:
        cached = cached_path(gid, name)
        if cached is not None:
            return cached, "cache"
    art = _steam_art(gid, kind)
    if art is not None:
        return art, "steam"
    if kind == "icon" and str(gid).startswith("local-"):
        from_exe = exe_icon(gid, exe)
        if from_exe is not None:
            return from_exe, "exe"
    return None, ""


def _exe_icon_source(path: Path) -> Path | None:
    """The .exe whose icon represents a game's configured executable.

    A `.exe` uses itself. A native launcher (the `.sh` a Ren'Py port
    ships) uses the same-stem `.exe` beside it, or the only `.exe` in
    that directory; several candidates and no match mean no icon, never
    a guess.
    """
    if path.suffix.lower() == ".exe":
        return path
    try:
        siblings = [
            entry
            for entry in path.parent.iterdir()
            if entry.is_file() and entry.suffix.lower() == ".exe"
        ]
    except OSError:
        return None
    if len(siblings) == 1:
        return siblings[0]
    stem = path.stem.lower()
    for entry in siblings:
        if entry.stem.lower() == stem:
            return entry
    return None


def exe_icon(appid: str, exe: str = "") -> Path | None:
    """The icon embedded in a local game's executable, extracted once.

    The cached copy is reused while the executable's path, size and
    mtime stay the same, so a refresh only stats the file. The cache
    keeps the best frame the executable has: a PNG frame extracted as
    `.png`, a BMP-only icon as a `.ico` sorted largest first. A native
    launcher falls back to the `.exe` shipped beside it (see
    `_exe_icon_source`).
    """
    source = str(exe or "").strip()
    if not source:
        return None
    try:
        exe_path = _exe_icon_source(Path(source).expanduser())
        if exe_path is None:
            return None
        stat = exe_path.stat()
    except OSError:
        return None
    known = read_manifest(appid).get(EXE_ICON_KEY)
    if (
        isinstance(known, dict)
        and known.get("icon_version") == EXE_ICON_VERSION
        and known.get("path") == str(exe_path)
        and known.get("mtime_ns") == stat.st_mtime_ns
        and known.get("size") == stat.st_size
    ):
        dest = exe_icon_path(appid, str(known.get("suffix") or ".ico"))
        if dest.is_file():
            return dest
    icon = exeiconmod.icon_bytes(exe_path)
    if icon is None:
        return None
    body, suffix = best_ico_frame(icon)
    dest = replace_image(exe_icon_path(appid), body, suffix)
    if dest is None:
        return None
    try:
        data = read_manifest(appid)
        data[EXE_ICON_KEY] = {
            "path": str(exe_path),
            "mtime_ns": stat.st_mtime_ns,
            "size": stat.st_size,
            "suffix": suffix,
            "icon_version": EXE_ICON_VERSION,
        }
        _store_manifest(appid, data)
    except Exception as e:
        log.debug("artwork exe icon write failed: %s", e)
        return None
    return dest


def record_exe_icon(appid: str, path: Path) -> None:
    """Point the sidecar at the suffix a converted exe icon now uses.

    The extraction itself is stdlib and writes PNG/ICO; the GUI's
    conversion rewrites it and calls this so the next cache hit finds
    the new file instead of re-extracting the executable.
    """
    data = read_manifest(appid)
    entry = data.get(EXE_ICON_KEY)
    if not isinstance(entry, dict):
        return
    entry["suffix"] = Path(path).suffix.lower()
    # The conversion decoded the best frame, so an icon extracted before
    # the frame rule is good now and must not be re-extracted once more.
    entry["icon_version"] = EXE_ICON_VERSION
    data[EXE_ICON_KEY] = entry
    try:
        _store_manifest(appid, data)
    except Exception as e:
        log.debug("artwork exe icon suffix write failed: %s", e)


def resolve_icon(appid: str, landscape: bool = False) -> Path | None:
    """Manual override first, then our cached grid, then Steam art."""
    return resolve(appid, "banner" if landscape else "icon")[0]


# --------------------------------------------------------------------
# HTTP


def _get(
    url: str, api_key: str = "", timeout: int = 30, limit: int = JSON_LIMIT
) -> tuple[bytes | None, str]:
    """Fetch a URL. Returns (body, error), error "" on success.

    Error tokens: "blocked" (403, Cloudflare's browser check),
    "not-found" (404), "http" (anything else), "too-large" (body over
    `limit`) and "network".
    """
    headers = {"User-Agent": USER_AGENT}
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"
    try:
        request = urllib.request.Request(url, headers=headers)
        with urllib.request.urlopen(request, timeout=timeout) as response:
            body = response.read(limit + 1)
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
    if len(body) > limit:
        # Read one byte past the cap: a huge body must not reach memory.
        log.warning("artwork: %s answered more than %s bytes", url, limit)
        return None, "too-large"
    return body, ""


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


def _url_exists(url: str, timeout: int = 5) -> bool:
    """True when a HEAD request says a Steam asset exists.

    Only a 404 hides a candidate; a network or CDN failure keeps it, so a
    hiccup never removes the automatic pick from the chooser.
    """
    request = urllib.request.Request(url, method="HEAD", headers={"User-Agent": USER_AGENT})
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            return 200 <= getattr(response, "status", 200) < 400
    except urllib.error.HTTPError as e:
        return e.code != 404
    except Exception:
        return True


def steam_app(appid: str) -> dict | None:
    """Official Steam record for an AppID: {"name", "icon"}, or None.

    Doubles as validation: Steam answers a bare `{"appid": N}` (no name)
    for numbers that are not apps, which is the usual mistake of pasting a
    SteamGridDB game id instead of a Steam AppID.
    """
    gid = steammod.steam_appid(appid)
    if not gid:
        return None
    body, _error = _get(APP_INFO_URL.format(appid=gid), timeout=15)
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
        "appid": str(apps[0].get("appid", gid)),
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


def _ico_entries(blob: bytes) -> list[tuple[int, bytes, bytes]] | None:
    """(area, directory entry, frame bytes) per ICO entry, or None."""
    if len(blob) < 6 or blob[:4] != b"\x00\x00\x01\x00":
        return None
    try:
        count = struct.unpack("<H", blob[4:6])[0]
    except struct.error:
        return None
    if count <= 0 or 6 + count * 16 > len(blob):
        return None
    entries: list[tuple[int, bytes, bytes]] = []
    for index in range(count):
        start = 6 + index * 16
        entry = blob[start : start + 16]
        width, height = entry[0] or 256, entry[1] or 256
        try:
            size, offset = struct.unpack("<II", entry[8:16])
        except struct.error:
            return None
        if offset + size > len(blob):
            return None
        entries.append((width * height, entry, blob[offset : offset + size]))
    return entries


def _largest_first_ico(blob: bytes) -> bytes:
    """The ICO with its directory sorted largest frame first.

    Qt reads the first frame when no size is requested, and icon editors
    write the frames smallest first: the GUI would draw the 16x16 one.
    The data offsets are absolute and stay untouched.
    """
    entries = _ico_entries(blob)
    if entries is None:
        return blob
    ordered = sorted(entries, key=lambda item: item[0], reverse=True)
    directory = b"".join(entry for _area, entry, _frame in ordered)
    return blob[:6] + directory + blob[6 + 16 * len(ordered) :]


def best_ico_frame(blob: bytes) -> tuple[bytes, str]:
    """Best frame of an ICO: (bytes, suffix).

    The largest frame by area wins. A PNG frame comes out as an image of
    its own; a BMP frame keeps the ICO, with the directory sorted so Qt
    decodes the biggest one. An unreadable icon is returned as it came.
    """
    entries = _ico_entries(blob)
    if entries is None:
        return blob, ".ico"
    frame = max(entries, key=lambda item: item[0])[2]
    if frame[:8] == b"\x89PNG\r\n\x1a\n":
        return frame, ".png"
    return _largest_first_ico(blob), ".ico"


def _store(appid: str, kind: str, url: str) -> Path | None:
    """Download one URL into the kind's cache slot, keeping its suffix."""
    body, _error = _get(url, limit=URL_IMAGE_LIMIT)
    if not body:
        return None
    if body[:4] == b"\x00\x00\x01\x00":
        frame = ico_png_frame(body)
        if frame is None:
            return None
        body = frame
    if not image_suffix(body):
        # A challenge or error page can answer 200: keeping it would mark
        # the kind filled and the cache would never ask the provider again.
        log.warning("artwork: %s did not return an image", url)
        return None
    suffix = _stored_suffix(url, body)
    return replace_image(grid_path(appid, kind), body, suffix)


def replace_image(path: Path, body: bytes, suffix: str) -> Path | None:
    """Write an image in one stored file, dropping its other suffixes.

    Used by the cache rewrite and by the GUI's re-encoding pass. The new
    file lands before the other suffixes go, so the cache never points at
    a file that was not written.
    """
    dest = Path(path).with_suffix(suffix)
    try:
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(body)
    except Exception as e:
        log.warning("artwork: could not write %s: %s", dest, e)
        return None
    stem = dest.with_suffix("")
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
    """Official Steam URLs to try for one kind, best first.

    The icon is the client icon: a multi-size .ico (up to 256x256) whose
    PNG frame is the real one. A few apps only ship the 32x32 jpg, which
    is still the real icon (Steam itself draws it), so it comes right
    after the .ico and before any community submission.
    """
    hash_ = (info or {}).get("icon", "")
    if kind == "icon":
        urls = [COMMUNITY_CDN.format(appid=appid, name=f"{hash_}.ico")] if hash_ else []
        if hash_:
            urls.append(COMMUNITY_CDN.format(appid=appid, name=f"{hash_}.jpg"))
        return urls + [STEAM_CDN.format(appid=appid, name=name) for name in _OFFICIAL_FILES["icon"]]
    return [STEAM_CDN.format(appid=appid, name=name) for name in _OFFICIAL_FILES.get(kind, ())]


def _missing_kinds(gid: str, kinds, force: bool) -> list[str]:
    """Kinds to download: the missing ones, minus the ones the user cleared.

    A cleared kind stays out until Fetch Artwork forces the download; the
    other kinds keep filling as usual.
    """
    wanted = []
    for kind in kinds:
        if not force and (is_kind_cleared(gid, kind) or cached_path(gid, kind) is not None):
            continue
        wanted.append(kind)
    return wanted


def fetch_official(
    appid: str,
    kinds=FETCH_KINDS,
    info: dict | None = None,
    force: bool = False,
) -> dict[str, Path]:
    """Download the official Steam art of `appid` (no key needed).

    `info` is an already-resolved `steam_app()` record; it is looked up
    when omitted. With force, cached kinds are refreshed too.
    """
    gid = _art_key(appid)
    if not gid.isdigit():
        return {}
    if not force and is_cleared(gid):
        return {}
    wanted = _missing_kinds(gid, kinds, force)
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
                _write_manifest(gid, kind, "steam")
                if kind == "icon":
                    _mark_icon_chain(gid)
                break
    return out


def _sgdb_game_id(appid: str, api_key: str) -> str:
    """SteamGridDB game id of a Steam AppID ("" when the site has none)."""
    game = _get_json(GAME_URL.format(appid=appid), api_key)
    entries = game.get("data", []) if isinstance(game, dict) else []
    if isinstance(entries, dict):
        # /games/steam/{appid} returns a single object, not a list.
        entries = [entries]
    if not entries or not isinstance(entries[0], dict):
        return ""
    return str(entries[0].get("id") or "")


def _sgdb_thumbs(game_id: str, kind: str, api_key: str, safe: bool = False) -> list[dict]:
    """SteamGridDB entries for one kind, official ones first."""
    if kind == "icon":
        data = _get_json(ICONS_URL.format(game_id=game_id), api_key)
    elif kind == "banner":
        data = _get_json(HEROES_URL.format(game_id=game_id), api_key)
    else:
        data = _get_json(GRIDS_URL.format(game_id=game_id), api_key)
    rows = data.get("data", []) if isinstance(data, dict) else []
    rows = [row for row in rows if isinstance(row, dict) and _is_image(row)]
    if safe:
        rows = [row for row in rows if not row.get("nsfw")]
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
    kinds=FETCH_KINDS,
    force: bool = False,
) -> tuple[dict[str, Path], str]:
    """Download community art from SteamGridDB. (paths, error token)."""
    gid = _art_key(appid)
    if not (api_key or "").strip() or not gid.isdigit():
        return {}, "no-key"
    game_id = _sgdb_game_id(gid, api_key)
    if not game_id:
        return {}, "not-found"
    return fetch_sgdb_game(gid, game_id, api_key, kinds, force), ""


def fetch_sgdb_game(
    appid: str,
    game_id: str,
    api_key: str,
    kinds=FETCH_KINDS,
    force: bool = False,
) -> dict[str, Path]:
    """Download the SteamGridDB art of one game id into a game's cache.

    `appid` only names the cache slot: the game id may come from a Steam
    AppID lookup or from a name search.
    """
    gid = _art_key(appid)
    if not force and is_cleared(gid):
        return {}
    if force:
        unmark_cleared(gid)
    wanted = _missing_kinds(gid, kinds, force)
    out: dict[str, Path] = {}
    safe = _safe_downloads()
    for kind in wanted:
        for entry in _sgdb_thumbs(game_id, kind, api_key, safe):
            path = _store(gid, kind, str(entry["thumb"]))
            if path is not None:
                out[kind] = path
                _write_manifest(gid, kind, "sgdb")
                if kind == "icon":
                    _mark_icon_chain(gid)
                break
    return out


def _resolved_igdb_id(gid: str, igdb_id: str = "") -> str:
    """Stored/drafted IGDB id first, then the id a previous pick cached."""
    resolved = igdbmod.resolve(gid, igdb_id)
    if resolved:
        return resolved
    cached = stored_igdb_id(gid)
    return cached if cached.isdigit() else ""


def fetch_igdb(
    appid: str,
    kinds=FETCH_KINDS,
    force: bool = False,
    igdb_id: str = "",
) -> tuple[dict[str, Path], str]:
    """Download IGDB's cover and banner. (paths, error token).

    IGDB needs a game id: ``igdb_id`` is the dialog draft or a title
    lookup, the stored ``[metadata] igdb_id`` wins, then the cache
    remembers the resolved one. It has no square icon, so `icon` is
    always left to the other providers. Error tokens: "no-igdb-key",
    "no-id", "not-found", "no-art".
    """
    gid = _art_key(appid)
    if not force and is_cleared(gid):
        return {}, ""
    wanted = _missing_kinds(gid, [kind for kind in kinds if kind in IGDB_KINDS], force)
    if not wanted:
        return {}, ""
    resolved = _resolved_igdb_id(gid, igdb_id)
    if not resolved:
        return {}, "no-id"
    urls, error = igdbmod.art(gid, resolved)
    if error:
        return {}, error
    out: dict[str, Path] = {}
    for kind in wanted:
        url = urls.get(kind, "")
        if not url:
            continue
        path = _store(gid, kind, url)
        if path is not None:
            out[kind] = path
            _write_manifest(gid, kind, "igdb")
    if out:
        store_igdb_id(gid, resolved)
    return out, "" if out else "no-art"


def _resolved_vndb_id(gid: str, vndb_id: str = "") -> str:
    """Stored/drafted VNDB id first, then the id a previous pick cached."""
    resolved = vndbmod.resolve(gid, vndb_id)
    if resolved:
        return resolved
    return cfgmod.normalize_vndb_id(stored_vndb_id(gid))


def fetch_vndb(
    appid: str,
    kinds=FETCH_KINDS,
    force: bool = False,
    vndb_id: str = "",
) -> tuple[dict[str, Path], str]:
    """Download VNDB's cover and screenshot banner. (paths, error token).

    VNDB needs a visual novel id: ``vndb_id`` is the dialog draft or a
    title lookup, the stored ``[metadata] vndb_id`` wins, then the cache
    remembers the resolved one. It has no square icon, so `icon` is
    always left to the other providers. Error tokens: "no-vndb-id",
    "not-found", "no-art".
    """
    gid = _art_key(appid)
    if not force and is_cleared(gid):
        return {}, ""
    wanted = _missing_kinds(gid, [kind for kind in kinds if kind in VNDB_KINDS], force)
    if not wanted:
        return {}, ""
    resolved = _resolved_vndb_id(gid, vndb_id)
    if not resolved:
        return {}, "no-vndb-id"
    urls, error = vndbmod.art(resolved, safe=_safe_downloads())
    if error:
        return {}, error
    out: dict[str, Path] = {}
    for kind in wanted:
        url = urls.get(kind, "")
        if not url:
            continue
        path = _store(gid, kind, url)
        if path is not None:
            out[kind] = path
            _write_manifest(gid, kind, "vndb")
    if out:
        store_vndb_id(gid, resolved)
    return out, "" if out else "no-art"


# --------------------------------------------------------------------
# Chooser candidates (no download)


def _entry_note(entry: dict) -> str:
    """Small label under a SteamGridDB thumb: size and style."""
    parts: list[str] = []
    try:
        width = int(entry.get("width") or 0)
        height = int(entry.get("height") or 0)
    except (TypeError, ValueError):
        width = height = 0
    if width and height:
        parts.append(f"{width}x{height}")
    style = str(entry.get("style") or "").strip()
    if style:
        parts.append(style)
    return " / ".join(parts)


def _steam_label(kind: str, url: str) -> str:
    """Readable name of one official Steam asset."""
    name = url.rsplit("/", 1)[-1]
    if kind == "icon":
        if name.endswith(".ico"):
            return "Client Icon"
        if name != "header.jpg":
            return "Client Icon (32 px)"
    return _STEAM_LABELS.get(name, name)


def steam_options(appid: str, kinds=FETCH_KINDS, info: dict | None = None) -> dict[str, list[dict]]:
    """Official Steam candidates per kind, missing assets hidden.

    The first row of each kind is the automatic pick, the same file
    order `fetch_official` tries.
    """
    gid = _art_key(appid)
    if not gid.isdigit():
        return {}
    if info is None:
        info = steam_app(gid)
    icon_hash = str((info or {}).get("icon", "") or "")
    out: dict[str, list[dict]] = {}
    for kind in kinds:
        if kind not in FETCH_KINDS:
            continue
        rows: list[dict] = []
        for url in _official_candidates(gid, kind, info):
            if not _url_exists(url):
                continue
            thumb = url
            if kind == "icon" and url.endswith(".ico") and icon_hash:
                # Qt reads only the first ICO frame; the 32 px jpg of the
                # same hash previews the multi-size icon correctly.
                thumb = COMMUNITY_CDN.format(appid=gid, name=f"{icon_hash}.jpg")
            rows.append(
                {
                    "url": url,
                    "thumb": thumb,
                    "auto": not rows,
                    "label": _steam_label(kind, url),
                    "note": "",
                }
            )
        if rows:
            out[kind] = rows
    return out


def sgdb_game_options(
    game_id: str, api_key: str, kinds=FETCH_KINDS, safe: bool | None = None
) -> dict[str, list[dict]]:
    """SteamGridDB candidates per kind, sorted like the automatic pick."""
    safe = _safe_downloads() if safe is None else safe
    out: dict[str, list[dict]] = {}
    for kind in kinds:
        if kind not in FETCH_KINDS:
            continue
        entries = _sgdb_thumbs(game_id, kind, api_key, safe)[:GALLERY_LIMIT]
        rows = []
        for entry in entries:
            thumb = str(entry.get("thumb") or "")
            if not thumb:
                continue
            rows.append(
                {
                    "url": thumb,
                    "thumb": thumb,
                    "auto": not rows,
                    "label": "",
                    "note": _entry_note(entry),
                }
            )
        if rows:
            out[kind] = rows
    return out


def store_choice(appid: str, kind: str, url: str, provider: str) -> Path | None:
    """Download one chosen candidate into the kind's cache slot.

    The URL comes from our own provider payload, so only https is
    accepted; `_store` still sniffs the body before writing.
    """
    if kind not in FETCH_KINDS or provider not in PROVIDERS:
        return None
    if not str(url).startswith("https://"):
        return None
    gid = _art_key(appid)
    path = _store(gid, kind, url)
    if path is None:
        return None
    _write_manifest(gid, kind, provider)
    if kind == "icon" and provider == "sgdb":
        _mark_icon_chain(gid)
    return path


def _gallery_result(result: dict, provider: str, groups: dict) -> dict:
    """Fill a gallery result with one provider's groups, capped per kind."""
    groups = {kind: rows[:GALLERY_LIMIT] for kind, rows in groups.items() if rows}
    result["provider"] = provider
    result["groups"] = groups
    if not groups:
        result["error"] = result.get("error") or "no-art"
    return result


def _gallery_sgdb(result: dict, gid: str, api_key: str, kinds, names, game_id: str) -> dict:
    """SteamGridDB candidates after resolving the game id (no download)."""
    if not (api_key or "").strip():
        result["error"] = "no-key"
        return result
    game = str(game_id or "").strip() or stored_sgdb_id(gid)
    if not game and gid.isdigit():
        game = _sgdb_game_id(gid, api_key)
    if not game and names:
        game, _label, candidates = _resolve_sgdb_game(api_key, names)
        if not game:
            result["candidates"] = candidates
            result["error"] = "no-match" if candidates else "not-found"
            return result
    if not game:
        result["error"] = "not-found"
        return result
    result["game_id"] = game
    return _gallery_result(result, "sgdb", sgdb_game_options(game, api_key, kinds))


def _gallery_names(gid: str, names) -> tuple:
    """Title queries; a Steam AppID contributes its official name."""
    wanted = tuple(str(name).strip() for name in names if str(name or "").strip())
    if wanted:
        return wanted
    if gid.isdigit():
        info = steam_app(gid)
        label = str((info or {}).get("name", "") or "").strip()
        return (label,) if label else ()
    return ()


def _gallery_igdb(result: dict, gid: str, kinds, names, igdb_id: str, game_id: str) -> dict:
    """IGDB candidates after resolving its game id (no download)."""
    draft = str(game_id or "").strip() or igdb_id
    if not _resolved_igdb_id(gid, draft):
        names = _gallery_names(gid, names)
    resolved, candidates, error = _igdb_lookup(gid, draft, names)
    if candidates:
        result["candidates"] = candidates
        result["error"] = error
        return result
    if not resolved:
        result["error"] = error or "no-id"
        return result
    groups, error = igdbmod.art_options(gid, resolved)
    result["igdb_id"] = resolved
    if error:
        result["error"] = error
        return result
    return _gallery_result(result, "igdb", groups)


def _gallery_vndb(result: dict, gid: str, kinds, names, vndb_id: str, game_id: str) -> dict:
    """VNDB candidates after resolving its visual novel id (no download)."""
    draft = str(game_id or "").strip() or vndb_id
    if not _resolved_vndb_id(gid, draft):
        names = _gallery_names(gid, names)
    resolved, candidates, error = _vndb_lookup(gid, draft, names)
    if candidates:
        result["candidates"] = candidates
        result["error"] = error
        return result
    if not resolved:
        result["error"] = error or "no-vndb-id"
        return result
    groups, error = vndbmod.art_options(resolved, safe=_safe_downloads())
    result["vndb_id"] = resolved
    if error:
        result["error"] = error
        return result
    return _gallery_result(result, "vndb", groups)


def art_gallery(
    appid: str,
    provider: str = "steam",
    api_key: str = "",
    kinds=FETCH_KINDS,
    names=(),
    igdb_id: str = "",
    vndb_id: str = "",
    game_id: str = "",
) -> dict:
    """Candidate images for the chooser, with no download and no cache write.

    Returns {"provider": effective source, "groups": {kind: [item]},
    "igdb_id", "vndb_id", "game_id" (SteamGridDB), "candidates" (game
    identity search) and "error"}. Each item is {"url", "thumb", "auto",
    "label", "note"}; the first row of a kind is the automatic pick.

    A local game without an AppID, or a Steam AppID without official
    assets, falls to SteamGridDB like the fetch chain does. A chosen
    IGDB or VNDB source that cannot resolve reports its own error.
    """
    result = {
        "provider": "",
        "groups": {},
        "igdb_id": "",
        "vndb_id": "",
        "game_id": "",
        "candidates": [],
        "error": "",
    }
    gid = _art_key(appid)
    provider = provider if provider in PROVIDERS else "steam"
    wanted = tuple(kind for kind in kinds if kind in FETCH_KINDS)
    if not wanted:
        return result
    if provider == "steam":
        groups = steam_options(gid, wanted) if gid.isdigit() else {}
        if groups:
            return _gallery_result(result, "steam", groups)
        provider = "sgdb"
    if provider == "sgdb":
        return _gallery_sgdb(result, gid, api_key, wanted, tuple(names), game_id)
    if provider == "igdb":
        return _gallery_igdb(result, gid, wanted, tuple(names), igdb_id, game_id)
    return _gallery_vndb(result, gid, wanted, tuple(names), vndb_id, game_id)


# --------------------------------------------------------------------
# Name lookup (local games)


def normalize_name(text: str) -> str:
    """Name folded for comparison: case, accents and punctuation ignored."""
    folded = unicodedata.normalize("NFKD", str(text or ""))
    folded = "".join(char for char in folded if not unicodedata.combining(char))
    return " ".join("".join(char if char.isalnum() else " " for char in folded.casefold()).split())


def search_sgdb(name: str, api_key: str) -> list[dict]:
    """SteamGridDB games matching a name: [{"id", "name"}], best first."""
    term = urllib.parse.quote(str(name or "").strip())
    if not term or not (api_key or "").strip():
        return []
    data = _get_json(SEARCH_URL.format(term=term), api_key)
    rows = data.get("data", []) if isinstance(data, dict) else []
    out: list[dict] = []
    for row in rows if isinstance(rows, list) else []:
        if not isinstance(row, dict):
            continue
        game_id = row.get("id")
        label = str(row.get("name") or "").strip()
        if game_id is None or not label:
            continue
        out.append({"id": str(game_id), "name": html.unescape(label)})
    return out


def fetch_by_name(
    appid: str,
    names,
    api_key: str,
    kinds=FETCH_KINDS,
    force: bool = False,
) -> dict:
    """Download a local game's art by name, trying each name in order.

    An exact (normalized) name wins automatically. Otherwise the first
    name's candidates come back in `candidates` so the dialog can ask,
    and `game_id` stays empty. Returns {"art", "game_id", "name", "error",
    "candidates"}; error tokens: "no-key", "no-match", "not-found",
    "no-art".
    """
    gid = _art_key(appid)
    result = {"art": {}, "game_id": "", "name": "", "error": "", "candidates": []}
    names = [str(name).strip() for name in names if str(name or "").strip()]
    if not (api_key or "").strip():
        result["error"] = "no-key"
        return result
    if not force and is_cleared(gid):
        return result
    wanted = _missing_kinds(gid, kinds, force)
    if not wanted:
        result["game_id"] = stored_sgdb_id(gid)
        return result
    game_id = stored_sgdb_id(gid)
    label = ""
    if not game_id:
        if not names:
            result["error"] = "no-match"
            return result
        game_id, label, candidates = _resolve_sgdb_game(api_key, names)
        if not game_id:
            result["candidates"] = candidates
            result["error"] = "no-match" if candidates else "not-found"
            return result
    art = fetch_sgdb_game(gid, game_id, api_key, wanted, force)
    if not art:
        result["error"] = "no-art"
        return result
    result["art"] = art
    result["game_id"] = game_id
    result["name"] = label
    store_sgdb_id(gid, game_id, label)
    return result


def _empty_result() -> dict:
    """The shape `fetch_best` returns for every game kind."""
    return {
        "art": {},
        "provider": "",
        "error": "",
        "name": "",
        "valid": False,
        "game_id": "",
        "igdb_id": "",
        "vndb_id": "",
        "candidates": [],
    }


def _resolve_sgdb_game(api_key: str, names) -> tuple[str, str, list[dict]]:
    """(game_id, name, candidates) for the first exact name match.

    The candidates of the first name that found anything come back when
    no name matched exactly, so the dialog can ask.
    """
    candidates: list[dict] = []
    for name in names:
        rows = search_sgdb(name, api_key)
        exact = [row for row in rows if normalize_name(row["name"]) == normalize_name(name)]
        if exact:
            return exact[0]["id"], exact[0]["name"], []
        if rows and not candidates:
            candidates = [dict(row, provider="sgdb") for row in rows[:10]]
    return "", "", candidates


#: IGDB search labels end with the release year; it is not part of the title.
_IGDB_YEAR = re.compile(r"\s*\(\d{4}\)$")


def _igdb_title(label: str) -> str:
    """Search label without its trailing ``(YYYY)``."""
    return _IGDB_YEAR.sub("", str(label or ""))


def _resolve_igdb_game(names) -> tuple[str, str, list[dict]]:
    """(game_id, label, candidates) for the first exact IGDB title match."""
    candidates: list[dict] = []
    for name in names:
        rows = igdbmod.search(name)
        exact = [
            row for row in rows if normalize_name(_igdb_title(row["name"])) == normalize_name(name)
        ]
        if exact:
            return exact[0]["id"], exact[0]["name"], []
        if rows and not candidates:
            candidates = [dict(row, provider="igdb") for row in rows[:10]]
    return "", "", candidates


def _igdb_lookup(gid: str, igdb_id: str, names) -> tuple[str, list[dict], str]:
    """(game_id, candidates, error) for an IGDB art fetch.

    The stored ``[metadata] igdb_id`` and the dialog draft win, then the
    id a previous search remembered; without one, the title is searched
    and an exact match wins automatically. Error tokens: "no-id",
    "no-igdb-key", "no-match", "not-found".
    """
    resolved = _resolved_igdb_id(gid, igdb_id)
    if resolved:
        return resolved, [], ""
    names = [str(name).strip() for name in names if str(name or "").strip()]
    if not names:
        return "", [], "no-id"
    client_id, secret = igdbmod.credentials()
    if not (client_id and secret):
        return "", [], "no-igdb-key"
    game_id, _label, candidates = _resolve_igdb_game(names)
    if game_id:
        return game_id, [], ""
    return "", candidates, ("no-match" if candidates else "not-found")


def _vndb_title_match(row: dict, name: str) -> bool:
    """True when the title or the alternative title equals `name`."""
    wanted = normalize_name(name)
    titles = (row.get("title"), row.get("alt"))
    return any(normalize_name(title) == wanted for title in titles if title)


def _vndb_lookup(gid: str, vndb_id: str, names) -> tuple[str, list[dict], str]:
    """(visual novel id, candidates, error) for a VNDB art fetch.

    The stored ``[metadata] vndb_id`` and the dialog draft win, then the
    id a previous search remembered; without one, the title is searched
    and an exact match wins automatically. Error tokens: "no-vndb-id",
    "no-match", "not-found".
    """
    resolved = _resolved_vndb_id(gid, vndb_id)
    if resolved:
        return resolved, [], ""
    names = [str(name).strip() for name in names if str(name or "").strip()]
    if not names:
        return "", [], "no-vndb-id"
    candidates: list[dict] = []
    for name in names:
        rows = vndbmod.search(name)
        exact = [row for row in rows if _vndb_title_match(row, name)]
        if exact:
            return exact[0]["id"], [], ""
        if rows and not candidates:
            candidates = [dict(row, provider="vndb") for row in rows[:10]]
    return "", candidates, ("no-match" if candidates else "not-found")


#: Chosen title providers: (id lookup, art fetch, result key).
_PROVIDER_CHOICE = {
    "igdb": (_igdb_lookup, fetch_igdb, "igdb_id"),
    "vndb": (_vndb_lookup, fetch_vndb, "vndb_id"),
}


def fetch_best(
    appid: str,
    provider: str = "steam",
    api_key: str = "",
    kinds=FETCH_KINDS,
    force: bool = False,
    names=(),
    igdb_id: str = "",
    vndb_id: str = "",
) -> dict:
    """Download a game's art with the chosen provider first.

    Returns {"art": {kind: Path}, "provider": "steam"|"sgdb"|"igdb"|"vndb",
    "error": token, "name": Steam name or "", "valid": whether the AppID
    is a real Steam app, "game_id": resolved SteamGridDB id, "igdb_id":
    resolved IGDB id, "vndb_id": resolved VNDB id, "candidates": name
    matches when the user has to choose}. The first provider fills
    what it can; the others only cover the kinds still missing. Official
    Steam art never needs a key.

    A game without a Steam AppID is looked up by `names` on SteamGridDB;
    IGDB or VNDB join only when chosen (they resolve an id from the
    config, the dialog draft or a title search).
    """
    gid = _art_key(appid)
    if force:
        # Fetch Artwork is explicit: the user wants the art back, so every
        # marker that keeps the background fetch away goes, including the
        # kinds no provider downloads (`background` falls back to the
        # banner).
        unmark_cleared(gid)
    if not gid.isdigit():
        return _fetch_named(gid, names, api_key, kinds, force, provider, igdb_id, vndb_id)
    return _fetch_numeric(gid, provider, api_key, kinds, force, igdb_id, vndb_id)


def _fetch_named(
    gid: str,
    names,
    api_key: str,
    kinds,
    force: bool,
    provider: str = "",
    igdb_id: str = "",
    vndb_id: str = "",
) -> dict:
    """`fetch_best` for a game without a Steam AppID.

    IGDB and VNDB run only when chosen: each resolves a stored, drafted
    or searched id, and SteamGridDB keeps the name search for the kinds
    they cannot fill.
    """
    result = _empty_result()
    remaining = list(kinds)
    entry = _PROVIDER_CHOICE.get(provider)
    if entry is not None:
        lookup, fetch, id_key = entry
        draft = igdb_id if id_key == "igdb_id" else vndb_id
        resolved, candidates, error = lookup(gid, draft, names)
        if candidates:
            # The chosen provider needs a pick before its art exists; do
            # not mix in SteamGridDB until the pick comes back.
            result["candidates"] = candidates
            result["error"] = error
            return result
        if resolved:
            result[id_key] = resolved
            art, error = fetch(gid, remaining, force, resolved)
            result["art"].update(art)
            remaining = [kind for kind in remaining if kind not in art]
            if art:
                result["provider"] = provider
            if error and not art:
                result["error"] = error
        else:
            result["error"] = error
    if remaining:
        looked = fetch_by_name(gid, names, api_key, remaining, force)
    else:
        looked = _empty_result()
        looked["game_id"] = stored_sgdb_id(gid)
    result.update(
        art={**result["art"], **looked["art"]},
        game_id=looked["game_id"],
        name=looked["name"],
        candidates=result["candidates"] or looked["candidates"],
        error=result["error"] or looked["error"],
    )
    if looked["art"] and not result["provider"]:
        result["provider"] = "sgdb"
    return result


def _provider_numeric_lookup(
    result: dict, gid: str, provider: str, igdb_id: str, vndb_id: str
) -> tuple[str, bool]:
    """Resolve the chosen title provider for a Steam AppID.

    True means the dialog must ask: a title search found candidates.
    """
    lookup, _fetch, id_key = _PROVIDER_CHOICE[provider]
    draft = igdb_id if id_key == "igdb_id" else vndb_id
    # A Steam game has no stored provider id by default: its official
    # name is the one title the search can safely use.
    name = str(result.get("name", "") or "")
    resolved, candidates, error = lookup(gid, draft, (name,) if name else ())
    if candidates:
        result["candidates"] = candidates
        result["error"] = error
        return "", True
    if resolved:
        result[id_key] = resolved
    elif error:
        result["error"] = error
    return resolved, False


def _resolve_chosen_numeric(
    result: dict, gid: str, provider: str, igdb_id: str, vndb_id: str
) -> tuple[str, str, bool]:
    """(igdb_id, vndb_id, pending) for a chosen title provider."""
    if provider not in _PROVIDER_CHOICE:
        return igdb_id, vndb_id, False
    resolved, pending = _provider_numeric_lookup(result, gid, provider, igdb_id, vndb_id)
    if provider == "igdb":
        return (resolved or igdb_id), vndb_id, pending
    return igdb_id, (resolved or vndb_id), pending


def _fetch_numeric(
    gid: str,
    provider: str,
    api_key: str,
    kinds,
    force: bool,
    igdb_id: str = "",
    vndb_id: str = "",
) -> dict:
    """`fetch_best` for a real Steam AppID."""
    result = _empty_result()
    if "icon" in kinds:
        _drop_stale_sgdb_icon(gid)
    info = steam_app(gid)
    result["valid"] = info is not None
    result["name"] = (info or {}).get("name", "")
    provider = provider if provider in PROVIDERS else "steam"
    igdb_id, vndb_id, pending = _resolve_chosen_numeric(result, gid, provider, igdb_id, vndb_id)
    if pending:
        return result
    order = (provider,) + tuple(source for source in PROVIDERS if source != provider)
    missing = [kind for kind in kinds if kind in ART_KINDS]
    first = True
    for source in order:
        if not missing:
            break
        art, error = _fetch_from(
            source, gid, missing, info, api_key, force and first, igdb_id, vndb_id
        )
        first = False
        result["art"].update(art)
        missing = [item for item in missing if item not in art]
        if art and not result["provider"]:
            result["provider"] = source
        if error and not result["error"]:
            result["error"] = error
    if not result["art"] and not result["error"]:
        result["error"] = "no-art" if result["valid"] else "not-a-steam-app"
    return result


def _fetch_from(
    source: str,
    gid: str,
    kinds,
    info: dict | None,
    api_key: str,
    force: bool,
    igdb_id: str = "",
    vndb_id: str = "",
) -> tuple[dict[str, Path], str]:
    """One provider pass: (paths, error token)."""
    if source == "steam":
        return fetch_official(gid, kinds, info, force), ""
    if source == "igdb":
        return fetch_igdb(gid, kinds, force, igdb_id)
    if source == "vndb":
        return fetch_vndb(gid, kinds, force, vndb_id)
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
