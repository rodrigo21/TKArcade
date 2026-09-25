"""Curated environment variable presets for games (stdlib only)."""

from __future__ import annotations

ENV_PRESETS: dict[str, dict[str, str]] = {
    "FSR Upscaling (Wine/Proton)": {
        "WINE_FULLSCREEN_FSR": "1",
    },
    "Faster Shaders (RADV)": {
        "RADV_PERFTEST": "gpl",
    },
    "Prefer Wayland (SDL)": {
        "SDL_VIDEODRIVER": "wayland",
    },
}


def apply_preset(vars: dict[str, str], name: str) -> list[str]:
    """Merge preset entries missing from vars. Returns added key names."""
    added = []
    for key, value in ENV_PRESETS.get(name, {}).items():
        if key not in vars:
            vars[key] = value
            added.append(key)
    return added
