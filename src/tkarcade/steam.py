"""Steam helpers: resolve AppID, list installed games, read Steam VDF files."""

from __future__ import annotations

import os
import re
from pathlib import Path

_ICON_HASH_RE = re.compile(r"^[0-9a-f]{40}\.jpg$")
_STEAM_PREFIX = "steam-"


def origin(appid: str) -> str:
    """Game origin from the ID prefix: ``steam`` or ``local``.

    Bare digits are the legacy Steam form; new IDs are always
    ``steam-<appid>`` or ``local-<slug>``.
    """
    return "steam" if str(appid or "").strip().removeprefix(_STEAM_PREFIX).isdigit() else "local"


def steam_appid(appid: str) -> str:
    """Numeric Steam AppID behind a game ID ('' when not a Steam game)."""
    value = str(appid or "").strip()
    return value.removeprefix(_STEAM_PREFIX) if origin(value) == "steam" else ""


def is_steam_id(appid: str) -> bool:
    """True for Steam-origin IDs (canonical or legacy bare digits)."""
    return origin(appid) == "steam"


def canonical_id(appid: str) -> str:
    """Canonicalize an input ID: bare digits become ``steam-<n>``."""
    value = str(appid or "").strip()
    return f"{_STEAM_PREFIX}{value}" if value.isdigit() else value


def canonical_new_id(raw: str) -> str:
    """Canonical ID for a new target: a bare name is a local game."""
    from . import config as cfgmod

    value = str(raw or "").strip()
    if value.isdigit() or value.startswith(_STEAM_PREFIX):
        return canonical_id(value)
    if value.startswith("local-"):
        return value
    return f"local-{cfgmod.local_slug(value) or cfgmod.local_name_hash(value)}"


def resolve_appid(explicit: str = "") -> str:
    if explicit:
        return canonical_id(explicit)
    for key in ("STEAMAPPID", "SteamAppId", "STEAM_APP_ID"):
        v = os.environ.get(key, "").strip()
        if v:
            return canonical_id(v)
    # STEAM_COMPAT_DATA_PATH ends with <appid>
    compat = os.environ.get("STEAM_COMPAT_DATA_PATH", "").strip()
    if compat:
        cand = Path(compat).name
        if cand.isdigit():
            return canonical_id(cand)
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
    """Parse Valve KV1 text (None when it cannot be parsed)."""
    try:
        import vdf  # type: ignore

        data = vdf.loads(text)
        return data if isinstance(data, dict) else None
    except Exception:
        return None


def _vdf_library_section(data: dict) -> dict:
    """The libraries dict, whichever root key the file uses."""
    for root_key in ("libraryfolders", "LibraryFolders"):
        section = data.get(root_key)
        if isinstance(section, dict):
            return section
    return {}


def _section_paths(libs: dict) -> list[Path]:
    """Existing paths in a parsed section (dicts, or legacy bare strings)."""
    out = []
    for v in libs.values():
        if isinstance(v, dict) and "path" in v:
            out.append(Path(str(v["path"])))
        elif isinstance(v, str) and v.strip():
            # Legacy layout stores libraries as bare strings
            # ("1" "/mnt/steam") instead of {"path": ...} dicts.
            out.append(Path(v.strip()))
    return [p for p in out if p.exists()]


def _parse_libraryfolders_vdf(path: Path) -> list[Path]:
    """Parse libraryfolders.vdf (KV1). Returns library paths."""
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except Exception:
        return []
    data = loads_kv1(text)
    if data is None:
        return []
    return _section_paths(_vdf_library_section(data))


def library_paths() -> list[Path]:
    key = _roots_key()
    hit = _LIBRARY_PATHS_CACHE.get(key)
    if hit is not None:
        return hit
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
    _LIBRARY_PATHS_CACHE[key] = seen
    return seen


def _parse_acf_name(path: Path) -> tuple[str, str]:
    """Return (appid, name) from appmanifest_<id>.acf."""
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except Exception:
        return "", ""
    data = loads_kv1(text)
    if data is None:
        return "", ""
    app = data.get("AppState", {})
    if isinstance(app, dict):
        return str(app.get("appid", "")), str(app.get("name", ""))
    return "", ""


_GAMES_CACHE: dict[tuple[str, str], list[tuple[str, str]]] = {}
_LIBRARY_PATHS_CACHE: dict[tuple[str, str], list[Path]] = {}
_LAUNCH_OPTIONS_CACHE: dict[tuple[str, int, int], tuple[str, str]] = {}


def _parse_acf_installdir(path: Path) -> str:
    """Return the installdir from appmanifest_<id>.acf ("" when unknown)."""
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except Exception:
        return ""
    data = loads_kv1(text)
    if data is None:
        return ""
    app = data.get("AppState", {})
    if isinstance(app, dict):
        return str(app.get("installdir", ""))
    return ""


def local_names() -> dict[str, str]:
    """Display names of configured local (non-Steam) games (id -> name)."""
    from . import config as cfgmod

    names: dict[str, str] = {}
    for appid in cfgmod.list_appids():
        if is_steam_id(appid):
            continue
        try:
            name = cfgmod.load(appid).general.name.strip()
        except Exception:
            name = ""
        names[appid] = name or appid
    return names


def _safe_appid(appid: str) -> str:
    """Numeric AppID for Steam-owned files; '' for a non-Steam game."""
    return steam_appid(appid)


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


def unconfigured_games(configured: set[str]) -> list[tuple[str, str]]:
    """Steam games without a saved config (sorted by name)."""
    have = set(configured)
    return [(a, n) for a, n in list_games() if a not in have]


def shader_dir(appid: str) -> Path | None:
    """Precompiled shader cache dir (steamapps/shadercache/<appid>), if any."""
    appid = _safe_appid(appid)
    if not appid:
        return None
    for lib in library_paths():
        cand = lib / "shadercache" / appid
        if cand.is_dir():
            return cand
    return None


def dir_size(path: Path) -> int:
    """Recursive byte size, best effort (unreadable entries skipped).

    Iterative walk: constant memory even for huge shader trees (rglob
    would materialize the whole listing first).
    """
    total = 0
    stack = [path]
    while stack:
        current = stack.pop()
        try:
            with os.scandir(current) as it:
                entries = list(it)
        except OSError:
            continue
        for entry in entries:
            try:
                if entry.is_symlink():
                    continue
                if entry.is_dir(follow_symlinks=False):
                    stack.append(Path(entry.path))
                elif entry.is_file(follow_symlinks=False):
                    total += entry.stat(follow_symlinks=False).st_size
            except OSError:
                continue
    return total


def format_size(num: float) -> str:
    """Format bytes compactly: 512 B, 1.2 MB, 3.0 GB."""
    size = max(0, float(num))
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if size < 1024 or unit == "TB":
            return f"{size:.0f} {unit}" if unit == "B" else f"{size:.1f} {unit}"
        size /= 1024
    return f"{size:.1f} TB"  # unreachable, keeps types happy


def _roots_key() -> tuple[str, str]:
    return (os.environ.get("HOME", ""), os.environ.get("STEAM_ROOT", ""))


def list_games() -> list[tuple[str, str]]:
    """Return sorted [(game_id, name)] for installed Steam apps."""
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
                if appid:
                    games.setdefault(canonical_id(appid), name or appid)
        except Exception:
            continue
    result = sorted(games.items(), key=lambda kv: kv[1].lower())
    _GAMES_CACHE[key] = result
    return result


def clear_games_cache() -> None:
    """Drop the caches a Reload must refresh (games, libraries, options)."""
    _GAMES_CACHE.clear()
    _LIBRARY_PATHS_CACHE.clear()
    _LAUNCH_OPTIONS_CACHE.clear()


def _preferred_names(landscape: bool, portrait: bool) -> tuple[str, ...]:
    """Steam cache file names to try first, by shape (empty = icon first)."""
    if landscape:
        return ("header.jpg", "logo.png", "library_600x900.jpg")
    if portrait:
        return ("library_600x900.jpg", "header.jpg", "logo.png")
    return ()


def find_game_icon(appid: str, landscape: bool = False, portrait: bool = False) -> Path | None:
    """Return Steam artwork for a game, to use as a list icon.

    Modern clients cache per-game art under
    appcache/librarycache/<appid>/ (client icon as <sha1>.jpg, logo.png,
    header.jpg, ...). Older clients used flat <appid>_icon.jpg files;
    both layouts are tried. With landscape=True, wide art wins (better
    for headers and menu icons); with portrait=True, the 600x900 cover
    wins instead.
    """
    ordered = _preferred_names(landscape, portrait)
    numeric = steam_appid(appid)
    if not numeric:
        return None
    for root in steam_roots():
        cache = root / "appcache" / "librarycache"
        try:
            d = cache / numeric
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
            for suffix in (f"{numeric}_icon.jpg", f"{numeric}_logo.png"):
                cand = cache / suffix
                if cand.is_file():
                    return cand
        except Exception:
            continue
    return None


def launch_options_status(appid: str) -> tuple[str, str]:
    """Check Steam launch options for tkarcade. Read-only.

    Returns (status, options) with status 'ok' (options contain
    tkarcade), 'missing' (options found without it) or 'unknown'
    (no Steam userdata found). `options` is the raw LaunchOptions
    string for 'ok' and '' otherwise: the caller words the message.
    """
    found_any = False
    numeric = steam_appid(appid)
    for root in steam_roots():
        userdir = root / "userdata"
        try:
            profiles = [p for p in userdir.iterdir() if p.is_dir()]
        except Exception:
            continue
        for profile in profiles:
            localconfig = profile / "config" / "localconfig.vdf"
            try:
                st = localconfig.stat()
            except OSError:
                continue
            key = (str(localconfig), st.st_mtime_ns, st.st_size, numeric)
            cached = _LAUNCH_OPTIONS_CACHE.get(key)
            if cached is None:
                try:
                    text = localconfig.read_text(encoding="utf-8", errors="replace")
                except Exception:
                    continue
                options = _launch_options_from_text(text, appid)
                ok = options is not None and "tkarcade" in options.lower()
                cached = ("ok", options) if ok else ("missing", "")
                _LAUNCH_OPTIONS_CACHE[key] = cached
            found_any = True
            if cached[0] == "ok":
                return cached
    if found_any:
        return "missing", ""
    return "unknown", ""


def _shortcuts_entries(path: Path) -> list[dict]:
    try:
        import vdf  # type: ignore

        with path.open("rb") as handle:
            data = vdf.binary_load(handle)
    except Exception:
        return []
    if not isinstance(data, dict):
        return []
    entries = data.get("shortcuts", {})
    if not isinstance(entries, dict):
        return []
    return [e for e in entries.values() if isinstance(e, dict)]


def _clean_exe(value: object) -> str:
    exe = str(value or "").strip()
    if exe.startswith('"'):
        end = exe.find('"', 1)
        exe = exe[1:end] if end > 0 else exe[1:]
    return exe.strip()


def shortcut_exe(appid: str) -> str:
    """Executable behind a numeric Steam shortcut ID ('' when unknown).

    Reads Steam's ``shortcuts.vdf`` for every profile, read-only. The
    launcher uses it to map a non-Steam shortcut to its local config.
    """
    numeric = steam_appid(appid)
    if not numeric:
        return ""
    wanted = int(numeric)
    for root in steam_roots():
        userdir = root / "userdata"
        try:
            profiles = [p for p in userdir.iterdir() if p.is_dir()]
        except Exception:
            continue
        for profile in profiles:
            for entry in _shortcuts_entries(profile / "config" / "shortcuts.vdf"):
                value = entry.get("appid")
                # vdf reads the field as signed int32; Steam writes it unsigned.
                if isinstance(value, int) and (value & 0xFFFFFFFF) == wanted:
                    return _clean_exe(entry.get("Exe"))
    return ""


def _launch_options_from_text(text: str, appid: str) -> str | None:
    appid = steam_appid(appid)
    if not appid:
        return None
    data = loads_kv1(text)
    if data is None:
        return None
    try:
        steam = data["UserLocalConfigStore"]["Software"]["Valve"]["Steam"]
        apps = steam.get("Apps", steam.get("apps", {}))
        entry = apps.get(appid, {})
    except (KeyError, TypeError, AttributeError):
        return None
    if isinstance(entry, dict) and "LaunchOptions" in entry:
        return str(entry["LaunchOptions"])
    return None
