"""XDG Base Directory helpers (stdlib only)."""

from __future__ import annotations

import os
import re
from pathlib import Path


def safe_stem(name: str) -> str:
    """Filesystem-safe stem: crafted AppIDs cannot escape their dir."""
    return re.sub(r"[^A-Za-z0-9._-]", "_", name).strip("._") or "unknown"


def _env_home(name: str, default: str) -> Path:
    val = os.environ.get(name)
    if val:
        return Path(val)
    return Path.home() / default


def config_home() -> Path:
    return _env_home("XDG_CONFIG_HOME", ".config")


def cache_home() -> Path:
    return _env_home("XDG_CACHE_HOME", ".cache")


def state_home() -> Path:
    return _env_home("XDG_STATE_HOME", ".local/state")


def data_home() -> Path:
    return _env_home("XDG_DATA_HOME", ".local/share")


def app_config_dir() -> Path:
    return config_home() / "tkarcade"


def games_dir() -> Path:
    return app_config_dir() / "games"


def app_state_dir() -> Path:
    return state_home() / "tkarcade"


def app_cache_dir() -> Path:
    return cache_home() / "tkarcade"


def log_file() -> Path:
    return app_state_dir() / "launcher.log"


def games_log_dir() -> Path:
    return app_state_dir() / "games"


def game_log_file(appid: str) -> Path:
    return games_log_dir() / f"{safe_stem(appid)}.log"


def defaults_file() -> Path:
    return app_config_dir() / "defaults.toml"


def default_prefix_base() -> Path:
    """Built-in base directory for game prefixes (preferences may override)."""
    return data_home() / "tkarcade" / "prefixes"


def is_wine_prefix(path: Path) -> bool:
    """True when the directory looks like a Windows prefix Wine can reuse."""
    return (path / "drive_c").is_dir() and (path / "system.reg").is_file()


def iter_prefixes(base: str = "") -> list[Path]:
    """Existing Wine prefixes under the base, sorted by name (never raises)."""
    root = Path(base.strip()).expanduser() if base.strip() else default_prefix_base()
    try:
        entries = list(root.iterdir())
    except OSError:
        return []
    found: list[Path] = []
    for entry in entries:
        try:
            if entry.is_dir() and is_wine_prefix(entry):
                found.append(entry)
        except OSError:
            continue
    return sorted(found, key=lambda p: p.name.lower())


def preferences_file() -> Path:
    return app_config_dir() / "preferences.toml"
