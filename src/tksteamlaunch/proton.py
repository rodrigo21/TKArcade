"""Proton version lookup (best effort, no deps).

Reads the per-game compat tool from Steam's config.vdf and its `version`
file from the tool install dir. Anything missing -> None (callers omit).
"""
from __future__ import annotations

import logging
import re

from . import steam as steammod

log = logging.getLogger("tksteamlaunch.proton")


def compat_tool_name(appid: str) -> str | None:
    """Return the compat tool name for a game (e.g. 'proton_9'), if mapped."""
    for root in steammod.steam_roots():
        config_vdf = root / "config" / "config.vdf"
        try:
            text = config_vdf.read_text(encoding="utf-8", errors="replace")
        except Exception:
            continue
        name = _tool_from_vdf(text, appid)
        if name:
            return name
    return None


def _tool_from_vdf(text: str, appid: str) -> str | None:
    try:
        import vdf  # type: ignore

        mapping = (
            vdf.loads(text)
            .get("InstallConfigStore", {})
            .get("Software", {})
            .get("Valve", {})
            .get("Steam", {})
            .get("CompatToolMapping", {})
        )
        entry = mapping.get(str(appid), {})
        name = str(entry.get("name", "")).strip()
        return name or None
    except Exception:
        pass
    # stdlib fallback: find the appid block inside CompatToolMapping.
    region = text.find("CompatToolMapping")
    if region < 0:
        return None
    match = re.search(
        r'"' + re.escape(str(appid)) + r'"\s*\{\s*"name"\s+"([^"]+)"',
        text[region : region + 20000],
    )
    return match.group(1).strip() or None if match else None


def tool_version(tool: str) -> str | None:
    """Return the first line of a compat tool's `version` file, if found."""
    tool = (tool or "").strip()
    if not tool:
        return None
    for root in steammod.steam_roots():
        for cand in (
            root / "compatibilitytools.d" / tool / "version",
            root / "steamapps" / "common" / tool / "version",
        ):
            try:
                if cand.is_file():
                    line = cand.read_text(
                        encoding="utf-8", errors="replace"
                    ).splitlines()
                    if line and line[0].strip():
                        return line[0].strip()[:40]
            except Exception:
                continue
    return None


def proton_version_for(appid: str) -> str | None:
    """Return the Proton version string for a game, or None when unknown."""
    tool = compat_tool_name(appid)
    if not tool:
        return None
    return tool_version(tool)


def native_runtime(game_cmd: list[str]) -> str | None:
    """Sniff the Steam Linux Runtime flavor from a native game command.

    Steam wraps SLR games like .../SteamLinuxRuntime_soldier/... so the
    codename (soldier/sniper/scout) is visible in argv. Only matches when
    a runtime marker is present to avoid false positives from game paths.
    """
    for token in game_cmd:
        low = token.lower()
        if (
            "steamlinuxruntime" in low
            or "steam-runtime" in low
            or "pressure-vessel" in low
        ):
            for name in ("soldier", "sniper", "scout"):
                if name in low:
                    return name
            return "steam-runtime"
    return None
