"""Game artwork: official Steam assets first, then SteamGridDB, then IGDB.

Official art comes from Steam's public CDN and needs no key at all: the
library capsule (portrait), the library hero (wide) and the client icon
(the square one Steam itself shows). SteamGridDB is the community
fallback and needs a key; IGDB is the other community source, needs a
Twitch application and only serves a game whose ``[metadata] igdb_id``
is known (so it has no name lookup and no icon). A game can point at any
Steam AppID's art (`[artwork] artwork_appid`), installed or not. A local
game without one is looked up by name and the chosen SteamGridDB game id
is remembered.

Downloaded files live in our own cache and never touch Steam's files;
the per-kind provider is recorded next to them so the dialog can say
where a given image came from.
"""

from __future__ import annotations

import html
import json
import logging
import struct
import unicodedata
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

from . import exeicon as exeiconmod
from . import igdb as igdbmod
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
PROVIDERS = ("steam", "sgdb", "igdb")

#: Kinds IGDB can fill: it has no square icon, so `icon` stays with the
#: other providers.
IGDB_KINDS = ("cover", "banner")

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

#: Sidecar key: the SteamGridDB entry a name lookup resolved and the user
#: chose. Kept across Clear so Fetch restores the same game's art.
SGDB_KEY = "sgdb"

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
_CACHE_SUFFIXES = (".png", ".jpg", ".jpeg", ".webp", ".ico")

#: Sidecar key: the user removed this AppID's art, the background fetch
#: must not fill it back until Fetch Artwork is pressed.
CLEARED_KEY = "cleared"

#: Sidecar key: the local executable an icon was extracted from, with its
#: stat, so a changed executable is re-extracted and an unchanged one is not.
EXE_ICON_KEY = "exe_icon"

#: Largest image a pasted URL may deliver; anything bigger is refused
#: before it reaches the disk.
URL_IMAGE_LIMIT = 20 * 1024 * 1024


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


def exe_icon_path(appid: str) -> Path:
    """Cache path of the icon extracted from a local game's executable.

    Deliberately not `<key>-icon.*`: that name belongs to downloaded
    client icons, and Clear must not delete a file the game ships.
    """
    base = xdg.app_cache_dir() / "grids"
    return base / f"{xdg.safe_stem(_cache_key(appid))}-exe.ico"


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


def _write_manifest(appid: str, kind: str, provider: str) -> None:
    data = read_manifest(appid)
    data[kind] = {"provider": provider}
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
    is the way back. A name lookup's SGDB entry survives the Clear, so the
    next Fetch restores the same game's art.
    """
    path = manifest_path(appid)
    data = read_manifest(appid)
    kept = {key: value for key, value in data.items() if key == SGDB_KEY}
    kept[CLEARED_KEY] = True
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(kept, indent=2), encoding="utf-8")
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


def provider_for(appid: str, kind: str) -> str:
    """Recorded provider of one kind ("steam", "sgdb") or ""."""
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
    path = manifest_path(appid)
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(data, indent=2, sort_keys=True), encoding="utf-8")
    except Exception as e:
        log.debug("artwork sgdb id write failed: %s", e)


def _mark_icon_chain(appid: str) -> None:
    """Record that this cache's icon came from the current chain."""
    data = read_manifest(appid)
    data[ICON_CHAIN_KEY] = ICON_CHAIN
    path = manifest_path(appid)
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(data, indent=2, sort_keys=True), encoding="utf-8")
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
    manifest = manifest_path(gid)
    try:
        if data:
            manifest.write_text(json.dumps(data, indent=2, sort_keys=True), encoding="utf-8")
        else:
            manifest.unlink(missing_ok=True)
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
    for suffix in (".png", ".jpg", ".jpeg", ".webp"):
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
    for other in (".png", ".jpg", ".jpeg", ".webp"):
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
        if not origin.is_file() or origin.suffix.lower() not in (
            ".png",
            ".jpg",
            ".jpeg",
            ".webp",
        ):
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
    return ""


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
    """Download one image from a pasted URL: (bytes, error token)."""
    body, error = _get(url)
    if body is None:
        return None, error or "network"
    if len(body) > limit:
        return None, "too-large"
    if not image_suffix(body):
        return None, "not-image"
    return body, ""


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
    candidates.append(base / f"{key}-exe.ico")
    candidates.append(base / f"{key}.json")
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
    own_manual = _safe_manual(str(appid), kind)
    if own_manual is not None:
        return own_manual, "manual"
    source_appid = str(source_appid or "").strip()
    if source_appid and source_appid != str(appid):
        path, source = _local_art(source_appid, kind)
        if path is not None:
            return path, "appid-" + source
    return _local_art(str(appid), kind, exe)


def _safe_manual(gid: str, kind: str) -> Path | None:
    """A game's manual slot, or None when the cache is unreadable."""
    try:
        return manual_path(gid, kind)
    except Exception:
        return None


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


def exe_icon(appid: str, exe: str = "") -> Path | None:
    """The icon embedded in a local game's executable, extracted once.

    The `.ico` copy is reused while the executable's path, size and mtime
    stay the same, so a refresh only stats the file.
    """
    source = str(exe or "").strip()
    if not source:
        return None
    try:
        exe_path = Path(source).expanduser()
        stat = exe_path.stat()
    except OSError:
        return None
    dest = exe_icon_path(appid)
    known = read_manifest(appid).get(EXE_ICON_KEY)
    if (
        isinstance(known, dict)
        and dest.is_file()
        and known.get("path") == str(exe_path)
        and known.get("mtime_ns") == stat.st_mtime_ns
        and known.get("size") == stat.st_size
    ):
        return dest
    icon = exeiconmod.icon_bytes(exe_path)
    if icon is None:
        return None
    try:
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(icon)
        data = read_manifest(appid)
        data[EXE_ICON_KEY] = {
            "path": str(exe_path),
            "mtime_ns": stat.st_mtime_ns,
            "size": stat.st_size,
        }
        manifest_path(appid).write_text(
            json.dumps(data, indent=2, sort_keys=True), encoding="utf-8"
        )
    except Exception as e:
        log.debug("artwork exe icon write failed: %s", e)
        return None
    return dest


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


def _sgdb_thumbs(game_id: str, kind: str, api_key: str) -> list[dict]:
    """SteamGridDB entries for one kind, official ones first."""
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
    wanted = [kind for kind in kinds if force or cached_path(gid, kind) is None]
    out: dict[str, Path] = {}
    for kind in wanted:
        for entry in _sgdb_thumbs(game_id, kind, api_key):
            path = _store(gid, kind, str(entry["thumb"]))
            if path is not None:
                out[kind] = path
                _write_manifest(gid, kind, "sgdb")
                if kind == "icon":
                    _mark_icon_chain(gid)
                break
    return out


def fetch_igdb(
    appid: str,
    kinds=FETCH_KINDS,
    force: bool = False,
) -> tuple[dict[str, Path], str]:
    """Download IGDB's cover and banner. (paths, error token).

    IGDB needs the ``[metadata] igdb_id`` the metadata download saves;
    without it nothing is fetched. It has no square icon, so `icon` is
    always left to the other providers. Error tokens: "no-igdb-key",
    "no-id", "not-found", "no-art".
    """
    gid = _art_key(appid)
    if not force and is_cleared(gid):
        return {}, ""
    wanted = [
        kind for kind in kinds if kind in IGDB_KINDS and (force or cached_path(gid, kind) is None)
    ]
    if not wanted:
        return {}, ""
    urls, error = igdbmod.art(gid)
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
    return out, "" if out else "no-art"


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
    wanted = [kind for kind in kinds if force or cached_path(gid, kind) is None]
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
            candidates = rows[:10]
    return "", "", candidates


def fetch_best(
    appid: str,
    provider: str = "steam",
    api_key: str = "",
    kinds=FETCH_KINDS,
    force: bool = False,
    names=(),
) -> dict:
    """Download a game's art with the chosen provider first.

    Returns {"art": {kind: Path}, "provider": "steam"|"sgdb"|"igdb",
    "error": token, "name": Steam name or "", "valid": whether the AppID
    is a real Steam app, "game_id": resolved SteamGridDB id, "candidates":
    name matches when the user has to choose}. The first provider fills
    what it can; the others only cover the kinds still missing. Official
    Steam art never needs a key.

    A game without a Steam AppID is looked up by `names` on SteamGridDB;
    IGDB joins only when it is the chosen provider (it needs a stored
    igdb_id and has no name search).
    """
    gid = _art_key(appid)
    if force:
        # Fetch Artwork is explicit: the user wants the art back, so the
        # marker that keeps the background fetch away goes.
        _unmark_cleared(gid)
    if not gid.isdigit():
        return _fetch_named(gid, names, api_key, kinds, force, provider)
    return _fetch_numeric(gid, provider, api_key, kinds, force)


def _fetch_named(
    gid: str,
    names,
    api_key: str,
    kinds,
    force: bool,
    provider: str = "",
) -> dict:
    """`fetch_best` for a game without a Steam AppID.

    IGDB runs only when it is the chosen provider: it needs a stored
    igdb_id and has no name lookup, so SteamGridDB keeps the name search
    and fills whatever IGDB did not.
    """
    result = _empty_result()
    remaining = list(kinds)
    if provider == "igdb":
        art, error = fetch_igdb(gid, remaining, force)
        result["art"].update(art)
        remaining = [kind for kind in remaining if kind not in art]
        if art:
            result["provider"] = "igdb"
        if error and not art:
            result["error"] = error
    looked = fetch_by_name(gid, names, api_key, remaining, force)
    result.update(
        art={**result["art"], **looked["art"]},
        game_id=looked["game_id"],
        name=looked["name"],
        candidates=looked["candidates"],
        error=result["error"] or looked["error"],
    )
    if looked["art"] and not result["provider"]:
        result["provider"] = "sgdb"
    return result


def _fetch_numeric(gid: str, provider: str, api_key: str, kinds, force: bool) -> dict:
    """`fetch_best` for a real Steam AppID."""
    result = _empty_result()
    if "icon" in kinds:
        _drop_stale_sgdb_icon(gid)
    info = steam_app(gid)
    result["valid"] = info is not None
    result["name"] = (info or {}).get("name", "")
    if provider not in PROVIDERS:
        provider = "steam"
    order = (provider,) + tuple(source for source in PROVIDERS if source != provider)
    missing = [kind for kind in kinds if kind in ART_KINDS]
    first = True
    for source in order:
        if not missing:
            break
        art, error = _fetch_from(source, gid, missing, info, api_key, force and first)
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
) -> tuple[dict[str, Path], str]:
    """One provider pass: (paths, error token)."""
    if source == "steam":
        return fetch_official(gid, kinds, info, force), ""
    if source == "igdb":
        return fetch_igdb(gid, kinds, force)
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
