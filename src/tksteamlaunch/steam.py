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
    roots: list[Path] = []
    for cand in (
        Path.home() / ".steam/steam",
        Path.home() / ".local/share/Steam",
        Path.home() / ".var/app/com.valvesoftware.Steam/.local/share/Steam",
    ):
        if cand.exists():
            roots.append(cand)
    env = os.environ.get("STEAM_ROOT", "").strip()
    if env and Path(env).exists():
        roots.append(Path(env))
    return roots


def _parse_libraryfolders_vdf(path: Path) -> list[Path]:
    """Parse libraryfolders.vdf without deps (KV1 subset). Returns library paths."""
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except Exception:  # noqa: BLE001
        return []
    # try vdf lib first
    try:
        import vdf  # type: ignore

        data = vdf.loads(text)
        libs = data.get("libraryfolders", {})
        out = []
        for _k, v in libs.items():
            if isinstance(v, dict) and "path" in v:
                out.append(Path(str(v["path"])))
        return [p for p in out if p.exists()]
    except Exception:  # noqa: BLE001
        pass
    # fallback: crude "path" "..." extraction
    import re

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
    import re

    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except Exception:  # noqa: BLE001
        return "", ""
    try:
        import vdf  # type: ignore

        data = vdf.loads(text)
        app = data.get("AppState", {})
        return str(app.get("appid", "")), str(app.get("name", ""))
    except Exception:  # noqa: BLE001
        pass
    m_id = re.search(r'"appid"\s+"(\d+)"', text)
    m_name = re.search(r'"name"\s+"([^"]+)"', text)
    return (m_id.group(1) if m_id else ""), (m_name.group(1) if m_name else "")


def list_games() -> list[tuple[str, str]]:
    """Return sorted [(appid, name)]."""
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
        except Exception:  # noqa: BLE001
            continue
    return sorted(games.items(), key=lambda kv: kv[1].lower())


def find_game_icon(appid: str) -> Path | None:
    """Return Steam artwork for a game, to use as a list icon.

    Modern clients cache per-game art under
    appcache/librarycache/<appid>/ (client icon as <sha1>.jpg, logo.png,
    header.jpg, ...). Older clients used flat <appid>_icon.jpg files;
    both layouts are tried.
    """
    for root in steam_roots():
        cache = root / "appcache" / "librarycache"
        d = cache / str(appid)
        try:
            if d.is_dir():
                hashed = sorted(
                    p for p in d.iterdir()
                    if p.is_file() and _ICON_HASH_RE.match(p.name)
                )
                if hashed:
                    return hashed[0]
                for name in ("logo.png", "header.jpg", "library_600x900.jpg"):
                    cand = d / name
                    if cand.is_file():
                        return cand
        except Exception:  # noqa: BLE001
            continue
    for root in steam_roots():
        cache = root / "appcache" / "librarycache"
        for suffix in (f"{appid}_icon.jpg", f"{appid}_logo.png"):
            cand = cache / suffix
            try:
                if cand.is_file():
                    return cand
            except Exception:  # noqa: BLE001
                continue
    return None
