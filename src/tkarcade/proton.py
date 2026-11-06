"""Proton version lookup (best effort).

Reads the per-game compat tool from Steam's config.vdf and its `version`
file from the tool install dir. Anything missing -> None (callers omit).
"""

from __future__ import annotations

from pathlib import Path

from . import steam as steammod
from . import xdg


def compat_tool_name(appid: str) -> str | None:
    """Return the compat tool name for a game (e.g. 'proton_9'), if mapped."""
    numeric = steammod.steam_appid(appid)
    if not numeric:
        return None
    for root in steammod.steam_roots():
        name = _tool_mapping(root / "config" / "config.vdf").get(numeric, "")
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
    if data is None:
        return {}
    try:
        section = data["InstallConfigStore"]["Software"]["Valve"]["Steam"]["CompatToolMapping"]
    except (KeyError, TypeError, AttributeError):
        return {}
    if not isinstance(section, dict):
        return {}
    return {
        str(a): str(e.get("name", "")).strip()
        for a, e in section.items()
        if isinstance(e, dict) and str(e.get("name", "")).strip()
    }


def default_compat_tool() -> str | None:
    """Steam's default compat tool (the ``CompatToolMapping`` "0" entry)."""
    for root in steammod.steam_roots():
        name = _tool_mapping(root / "config" / "config.vdf").get("0", "")
        if name:
            return name
    return None


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

    A game without its own mapping runs Steam's default tool, so that entry
    answers instead of a bare "Proton". Same rule everywhere (dialog,
    notifications) so both agree even when only the tool mapping exists
    without a readable version file.
    """
    tool = compat_tool_name(appid) or default_compat_tool()
    if not tool:
        return "Proton"
    version = tool_version(tool)
    return f"{tool} ({version})" if version else tool


def is_steam_runtime_tool(tool: str) -> bool:
    """True for Steam Linux Runtime compat tools (native games)."""
    low = (tool or "").strip().lower()
    return low.startswith("steamlinuxruntime") or low.startswith("steam-runtime")


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


def list_compat_tools() -> list[str]:
    """Installed Proton builds: compatibilitytools.d entries plus Steam's.

    Sorted, deduplicated tool directory names, each holding the `proton`
    launcher Steam invokes. Steam's anti-cheat runtime tools ship no
    launcher and are not usable compat tools.
    """
    found: set[str] = set()
    for root in steammod.steam_roots():
        for base in (root / "compatibilitytools.d", root / "steamapps" / "common"):
            try:
                entries = list(base.iterdir())
            except OSError:
                continue
            for entry in entries:
                try:
                    if not entry.is_dir():
                        continue
                    has_launcher = (entry / "proton").is_file()
                except OSError:
                    continue
                if has_launcher:
                    found.add(entry.name)
    return sorted(found)


def prepare_fresh_prefix(appid: str, prefix: str = "") -> tuple[bool, list[str]]:
    """Delete this game's own Proton prefix so Steam recreates it.

    `prefix` is the configured [runtime] prefix; without it the
    STEAM_COMPAT_DATA_PATH Steam exported is used. Only a
    compatdata/<appid> folder for this very AppID is wiped; a symlink is
    refused, since deleting through it could hit a shared target.
    Returns (ok, warnings). ok is False when the target is missing,
    refused or the deletion failed (keep retrying those); callers disarm
    one-shot toggles when ok is True.
    Saves inside the prefix are destroyed; cloud/manual backups survive.
    """
    import os
    import shutil

    compat = (prefix or os.environ.get("STEAM_COMPAT_DATA_PATH", "")).strip()
    if not compat:
        return False, ["fresh_prefix set but STEAM_COMPAT_DATA_PATH is missing; skipped"]
    target = Path(compat)
    numeric = steammod.steam_appid(appid)
    if not numeric or target.name != numeric or "compatdata" not in target.parts:
        return False, [
            f"fresh_prefix refused: {compat} is not this game's compatdata/<appid> prefix; skipped"
        ]
    if target.is_symlink():
        return False, [f"fresh_prefix refused: {compat} is a symlink; remove it manually"]
    try:
        if target.is_dir():
            shutil.rmtree(target)
            return True, []
        return True, [f"prefix not found, nothing to delete: {compat}"]
    except Exception as e:
        return False, [f"could not delete prefix {compat}: {e}"]


def winetricks_state_path(appid: str) -> Path:
    """Where run_winetricks records the verbs it already installed."""
    return xdg.app_state_dir() / "winetricks" / f"{xdg.safe_stem(appid)}.json"


def clear_winetricks_state(appid: str) -> None:
    """Forget the recorded verbs, so the next launch installs them again.

    A wiped prefix (fresh_prefix) lost the verbs with it: keeping the
    record would skip protontricks and leave the new prefix bare.
    """
    try:
        winetricks_state_path(appid).unlink(missing_ok=True)
    except OSError:
        pass


def run_winetricks(appid: str, verbs: list[str]) -> list[str]:
    """Install winetricks verbs via protontricks (unattended). Skips when
    the recorded verb set already ran. Returns warnings; never raises."""
    import json
    import shutil
    import subprocess

    verbs = [v for v in (verbs or []) if str(v).strip()]
    if not verbs:
        return []
    numeric = steammod.steam_appid(appid)
    if not numeric:
        return [f"winetricks skipped: non-Steam AppID {appid!r}"]
    exe = shutil.which("protontricks")
    if not exe:
        return ["winetricks skipped: protontricks not found in PATH"]

    state = winetricks_state_path(appid)
    try:
        recorded = json.loads(state.read_text(encoding="utf-8")).get("verbs")
        if recorded == sorted(verbs):
            return []
    except Exception:
        pass
    try:
        proc = subprocess.run(
            [exe, numeric, "-q", *verbs],
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


def gui_command(appid: str) -> tuple[list[str], str]:
    """argv for ``protontricks --gui``, plus a message when it cannot run.

    The GUI installs into the game's own compatdata prefix, which is why
    a game with a custom ``[runtime] prefix`` cannot use it: protontricks
    would target a prefix the launcher does not use.
    """
    import shutil

    numeric = steammod.steam_appid(appid)
    if not numeric:
        return [], f"Protontricks Needs a Steam AppID ({appid!r})."
    exe = shutil.which("protontricks")
    if not exe:
        return [], "Protontricks Was Not Found in PATH."
    return [exe, "--gui", numeric], ""


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
