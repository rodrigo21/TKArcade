"""XDG Base Directory helpers (stdlib only)."""

from __future__ import annotations

import os
from pathlib import Path


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


def app_config_dir() -> Path:
    return config_home() / "tksteamlaunch"


def games_dir() -> Path:
    return app_config_dir() / "games"


def app_state_dir() -> Path:
    return state_home() / "tksteamlaunch"


def app_cache_dir() -> Path:
    return cache_home() / "tksteamlaunch"


def log_file() -> Path:
    return app_state_dir() / "launcher.log"


def games_log_dir() -> Path:
    return app_state_dir() / "games"


def game_log_file(appid: str) -> Path:
    return games_log_dir() / f"{appid}.log"


def defaults_file() -> Path:
    return app_config_dir() / "defaults.toml"


def preferences_file() -> Path:
    return app_config_dir() / "preferences.toml"
