"""Steam helpers: resolve AppID, list installed games (vdf optional)."""

from __future__ import annotations

import os
import re
from pathlib import Path

_ICON_HASH_RE = re.compile(r"^[0-9a-f]{40}\.jpg$")


def resolve_appid(explicit: str = "") -> str:
    if explicit:
        return explicit.strip()
    for key in ("STEAMAPPID", "SteamAppId", "STEAM_APP_ID"):
        v = os.environ.get(key, "").strip()
        if v:
            return v
    # STEAM_COMPAT_DATA_PATH ends with <appid>
    compat = os.environ.get("STEAM_COMPAT_DATA_PATH", "").strip()
    if compat:
        cand = Path(compat).name
        if cand.isdigit():
            return cand
    return ""


def steam_roots() -> list[Path]:
    roots = [
        cand
        for cand in (
            Path.home() / ".steam/steam",
            Path.home() / ".local/share/Steam",
            Path.home() / ".var/app/com.valvesoftware.Steam/.local/share/Steam",
        )
        if cand.exists()
    ]
    env = os.environ.get("STEAM_ROOT", "").strip()
    if env and Path(env).exists():
        roots.append(Path(env))
    return roots


def loads_kv1(text: str) -> dict | None:
    """Parse Valve KV1 text with the vdf package when available."""
    try:
        import vdf  # type: ignore

        data = vdf.loads(text)
        return data if isinstance(data, dict) else None
    except Exception:
        return None


def _parse_libraryfolders_vdf(path: Path) -> list[Path]:
    """Parse libraryfolders.vdf without deps (KV1 subset). Returns library paths."""
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except Exception:
        return []
    data = loads_kv1(text)
    if data is not None:
        libs = data.get("libraryfolders", {})
        out = [Path(str(v["path"])) for v in libs.values() if isinstance(v, dict) and "path" in v]
        return [p for p in out if p.exists()]
    # fallback: crude "path" "..." extraction
    out = []
    for m in re.finditer(r'"path"\s+"([^"]+)"', text):
        p = Path(m.group(1))
        if p.exists():
            out.append(p)
    return out


def library_paths() -> list[Path]:
    paths: list[Path] = []
    for root in steam_roots():
        paths.append(root / "steamapps")
        lf = root / "steamapps/libraryfolders.vdf"
        if lf.exists():
            for lib in _parse_libraryfolders_vdf(lf):
                sap = lib / "steamapps"
                if sap.exists():
                    paths.append(sap)
    # dedupe
    seen: list[Path] = []
    for p in paths:
        if p not in seen:
            seen.append(p)
    return seen


def _parse_acf_name(path: Path) -> tuple[str, str]:
    """Return (appid, name) from appmanifest_<id>.acf without deps."""
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except Exception:
        return "", ""
    data = loads_kv1(text)
    if data is not None:
        app = data.get("AppState", {})
        if isinstance(app, dict):
            return str(app.get("appid", "")), str(app.get("name", ""))
        return "", ""
    m_id = re.search(r'"appid"\s+"(\d+)"', text)
    m_name = re.search(r'"name"\s+"([^"]+)"', text)
    return (m_id.group(1) if m_id else ""), (m_name.group(1) if m_name else "")


_GAMES_CACHE: dict[tuple[str, str], list[tuple[str, str]]] = {}


def _parse_acf_installdir(path: Path) -> str:
    """Return the installdir from appmanifest_<id>.acf ("" when unknown)."""
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except Exception:
        return ""
    data = loads_kv1(text)
    if data is not None:
        app = data.get("AppState", {})
        if isinstance(app, dict):
            return str(app.get("installdir", ""))
        return ""
    m = re.search(r'"installdir"\s+"([^"]+)"', text)
    return m.group(1) if m else ""


def _safe_appid(appid: str) -> str:
    """Steam AppIDs are digits; anything else cannot name a manifest."""
    return str(appid) if str(appid).isdigit() else ""


def install_dir(appid: str) -> Path | None:
    """Game install folder (steamapps/common/<installdir>), if present."""
    appid = _safe_appid(appid)
    if not appid:
        return None
    for lib in library_paths():
        if _parse_acf_name(lib / f"appmanifest_{appid}.acf")[0] != appid:
            continue
        name = _parse_acf_installdir(lib / f"appmanifest_{appid}.acf")
        if not name:
            continue
        cand = lib / "common" / name
        if cand.is_dir():
            return cand
    return None


def prefix_dir(appid: str) -> Path | None:
    """Proton prefix folder (steamapps/compatdata/<appid>), if ever created."""
    appid = _safe_appid(appid)
    if not appid:
        return None
    for lib in library_paths():
        cand = lib / "compatdata" / appid
        if cand.is_dir():
            return cand
    return None


def _roots_key() -> tuple[str, str]:
    return (os.environ.get("HOME", ""), os.environ.get("STEAM_ROOT", ""))


def list_games() -> list[tuple[str, str]]:
    """Return sorted [(appid, name)]. Cached per process (keyed by env)."""
    key = _roots_key()
    hit = _GAMES_CACHE.get(key)
    if hit is not None:
        return hit
    games: dict[str, str] = {}
    for lib in library_paths():
        try:
            for acf in lib.glob("appmanifest_*.acf"):
                appid, name = _parse_acf_name(acf)
                if not appid:
                    # derive from filename
                    stem = acf.stem.replace("appmanifest_", "")
                    if stem.isdigit():
                        appid = stem
                if appid and appid not in games:
                    games[appid] = name or appid
        except Exception:
            continue
    result = sorted(games.items(), key=lambda kv: kv[1].lower())
    _GAMES_CACHE[key] = result
    return result


def clear_games_cache() -> None:
    """Drop the list_games cache (e.g. the main-window Reload button)."""
    _GAMES_CACHE.clear()


def find_game_icon(appid: str, landscape: bool = False) -> Path | None:
    """Return Steam artwork for a game, to use as a list icon.

    Modern clients cache per-game art under
    appcache/librarycache/<appid>/ (client icon as <sha1>.jpg, logo.png,
    header.jpg, ...). Older clients used flat <appid>_icon.jpg files;
    both layouts are tried. With landscape=True, wide art wins (better
    for headers and menu icons).
    """
    ordered = ("header.jpg", "logo.png", "library_600x900.jpg") if landscape else ()
    for root in steam_roots():
        cache = root / "appcache" / "librarycache"
        try:
            d = cache / str(appid)
            if d.is_dir():
                hashed = sorted(
                    p for p in d.iterdir() if p.is_file() and _ICON_HASH_RE.match(p.name)
                )
                names = (
                    list(ordered)
                    + [p.name for p in hashed if p.name not in ordered]
                    + ["logo.png", "header.jpg", "library_600x900.jpg"]
                )
                for name in dict.fromkeys(names):
                    cand = d / name
                    if cand.is_file():
                        return cand
            for suffix in (f"{appid}_icon.jpg", f"{appid}_logo.png"):
                cand = cache / suffix
                if cand.is_file():
                    return cand
        except Exception:
            continue
    return None


def launch_options_status(appid: str) -> tuple[str, str]:
    """Check Steam launch options for tksteamlaunch. Read-only.

    Returns (status, detail) with status 'ok' (options contain
    tksteamlaunch), 'missing' (options found without it) or 'unknown'
    (no Steam userdata found).
    """
    found_any = False
    for root in steam_roots():
        userdir = root / "userdata"
        try:
            profiles = [p for p in userdir.iterdir() if p.is_dir()]
        except Exception:
            continue
        for profile in profiles:
            localconfig = profile / "config" / "localconfig.vdf"
            try:
                text = localconfig.read_text(encoding="utf-8", errors="replace")
            except Exception:
                continue
            found_any = True
            options = _launch_options_from_text(text, appid)
            if options is not None and "tksteamlaunch" in options.lower():
                return "ok", f"Steam launch options: {options}"
    if found_any:
        return "missing", "Steam launch options lack tksteamlaunch (add: tksteamlaunch %command%)"
    return "unknown", "Steam userdata not found"


def _launch_options_from_text(text: str, appid: str) -> str | None:
    data = loads_kv1(text)
    if data is not None:
        try:
            steam = data["UserLocalConfigStore"]["Software"]["Valve"]["Steam"]
            apps = steam.get("Apps", steam.get("apps", {}))
            entry = apps.get(str(appid), {})
            if isinstance(entry, dict) and "LaunchOptions" in entry:
                return str(entry["LaunchOptions"])
            return None
        except (KeyError, TypeError, AttributeError):
            pass
    match = re.search(
        r'"Apps"\s*\{(?P<apps>.*)\}\s*\}\s*\}\s*\}\s*\}$',
        text,
        re.DOTALL | re.IGNORECASE,
    )
    region = match.group("apps") if match else text
    # One nesting level tolerated (e.g. a "cloud" {...} block sits
    # between the AppID and its LaunchOptions in real files).
    match = re.search(
        r'"' + re.escape(str(appid)) + r'"\s*\{(?:[^{}]|\{[^{}]*\})*?"LaunchOptions"\s+"([^"]*)"',
        region,
        re.DOTALL,
    )
    return match.group(1) if match else None
