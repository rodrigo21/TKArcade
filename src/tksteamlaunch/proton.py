"""Proton version lookup (best effort, no deps).

Reads the per-game compat tool from Steam's config.vdf and its `version`
file from the tool install dir. Anything missing -> None (callers omit).
"""

from __future__ import annotations

import re
from pathlib import Path

from . import steam as steammod


def compat_tool_name(appid: str) -> str | None:
    """Return the compat tool name for a game (e.g. 'proton_9'), if mapped."""
    for root in steammod.steam_roots():
        name = _tool_mapping(root / "config" / "config.vdf").get(str(appid), "")
        if name:
            return name
    return None


_TOOL_CACHE: dict[str, tuple[float, dict[str, str]]] = {}


def _tool_mapping(config_vdf: Path) -> dict[str, str]:
    """appid -> compat tool name, cached by file mtime."""
    try:
        mtime = config_vdf.stat().st_mtime
    except OSError:
        return {}
    key = str(config_vdf)
    hit = _TOOL_CACHE.get(key)
    if hit is not None and hit[0] == mtime:
        return hit[1]
    try:
        text = config_vdf.read_text(encoding="utf-8", errors="replace")
    except Exception:
        return {}
    mapping = _parse_tool_mapping(text)
    _TOOL_CACHE[key] = (mtime, mapping)
    return mapping


def clear_tool_cache() -> None:
    """Drop the compat-tool cache (tests, Steam root switches)."""
    _TOOL_CACHE.clear()


def _parse_tool_mapping(text: str) -> dict[str, str]:
    """Parse the whole CompatToolMapping section: {appid: tool name}."""
    data = steammod.loads_kv1(text)
    if data is not None:
        try:
            section = data["InstallConfigStore"]["Software"]["Valve"]["Steam"]["CompatToolMapping"]
            if isinstance(section, dict):
                return {
                    str(a): str(e.get("name", "")).strip()
                    for a, e in section.items()
                    if isinstance(e, dict) and str(e.get("name", "")).strip()
                }
        except (KeyError, TypeError, AttributeError):
            pass
    # stdlib fallback: every "appid" { "name" "tool" } pair in the section.
    region = text.find("CompatToolMapping")
    if region < 0:
        return {}
    out: dict[str, str] = {}
    for match in re.finditer(r'"(\d+)"\s*\{\s*"name"\s+"([^"]+)"', text[region:]):
        if match.group(2).strip():
            out.setdefault(match.group(1), match.group(2).strip())
    return out


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
                    line = cand.read_text(encoding="utf-8", errors="replace").splitlines()
                    if line and line[0].strip():
                        return line[0].strip()[:40]
            except Exception:
                continue
    return None


def tool_display(appid: str) -> str:
    """Display string for the Proton tool: 'tool (version)', 'tool', or 'Proton'.
    Same rule everywhere (dialog, notifications) so both agree even when
    only the tool mapping exists without a readable version file.
    """
    tool = compat_tool_name(appid)
    if not tool:
        return "Proton"
    version = tool_version(tool)
    return f"{tool} ({version})" if version else tool


def flavor(tool: str) -> str:
    """Classify a compat tool: 'cachyos', 'ge', 'dw' or 'valve' (default)."""
    low = (tool or "").lower()
    if "cachyos" in low:
        return "cachyos"
    if "dwproton" in low or "dw-proton" in low or low.startswith("dw-"):
        return "dw"
    if "ge-proton" in low or low == "ge" or low.startswith("ge-"):
        return "ge"
    return "valve"


def prepare_fresh_prefix() -> tuple[bool, list[str]]:
    """Delete the Proton prefix so Steam recreates it on launch.

    Returns (ok, warnings). ok is False only when deletion failed or
    STEAM_COMPAT_DATA_PATH is missing (keep retrying those); callers
    should disarm one-shot toggles when ok is True.
    Saves inside the prefix are destroyed; cloud/manual backups survive.
    """
    import os
    import shutil

    compat = os.environ.get("STEAM_COMPAT_DATA_PATH", "").strip()
    if not compat:
        return False, ["fresh_prefix set but STEAM_COMPAT_DATA_PATH is missing; skipped"]
    target = Path(compat)
    try:
        if target.is_dir() and not target.is_symlink():
            shutil.rmtree(target)
            return True, []
        return True, [f"prefix not found, nothing to delete: {compat}"]
    except Exception as e:
        return False, [f"could not delete prefix {compat}: {e}"]


def run_winetricks(appid: str, verbs: list[str]) -> list[str]:
    """Install winetricks verbs via protontricks (unattended). Skips when
    the recorded verb set already ran. Returns warnings; never raises."""
    import json
    import shutil
    import subprocess

    verbs = [v for v in (verbs or []) if str(v).strip()]
    if not verbs:
        return []
    if not str(appid).isdigit():
        return [f"winetricks skipped: non-Steam AppID {appid!r}"]
    exe = shutil.which("protontricks")
    if not exe:
        return ["winetricks skipped: protontricks not found in PATH"]
    from . import xdg

    state = xdg.app_state_dir() / "winetricks" / f"{appid}.json"
    try:
        recorded = json.loads(state.read_text(encoding="utf-8")).get("verbs")
        if recorded == sorted(verbs):
            return []
    except Exception:
        pass
    try:
        proc = subprocess.run(
            [exe, str(appid), "-q", *verbs],
            capture_output=True,
            text=True,
            timeout=1200,
        )
    except (OSError, subprocess.TimeoutExpired) as e:
        return [f"winetricks failed: {e}"]
    if proc.returncode != 0:
        tail = (proc.stderr or proc.stdout or "").strip().splitlines()[-3:]
        return [f"winetricks exit {proc.returncode}: {'; '.join(tail)}"[:300]]
    try:
        state.parent.mkdir(parents=True, exist_ok=True)
        state.write_text(json.dumps({"verbs": sorted(verbs)}), encoding="utf-8")
    except Exception as e:
        return [f"winetricks ran, state not recorded: {e}"]
    return []


def native_runtime(game_cmd: list[str]) -> str | None:
    """Sniff the Steam Linux Runtime flavor from a native game command.

    Steam wraps SLR games like .../SteamLinuxRuntime_soldier/... so the
    codename (soldier/sniper/scout) is visible in argv. Only matches when
    a runtime marker is present to avoid false positives from game paths.
    """
    for token in game_cmd:
        low = token.lower()
        if "steamlinuxruntime" in low or "steam-runtime" in low or "pressure-vessel" in low:
            for name in ("soldier", "sniper", "scout"):
                if name in low:
                    return name
            return "steam-runtime"
    return None
