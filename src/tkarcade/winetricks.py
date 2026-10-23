"""winetricks verbs for local Wine/umu prefixes (stdlib only).

The Steam path lives in ``proton.run_winetricks`` and goes through
protontricks; a local game has no AppID, so this runs the host
``winetricks`` against the game's prefix with ``WINE`` pointing at the
chosen runtime. The recorded state includes the prefix path, so moving
a game to another prefix reruns the verbs.

The launcher calls this before the command is built, so a failure only
warns and never blocks the launch.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
from pathlib import Path

from . import xdg

TIMEOUT = 1200


def state_path(appid: str) -> Path:
    return xdg.app_state_dir() / "winetricks" / f"{appid}.json"


def _wine_for(proton: object) -> str:
    """The Proton install's wine binary ("" when absent)."""
    path = getattr(proton, "path", None)
    if not path:
        return ""
    candidate = Path(path) / "files" / "bin" / "wine"
    if candidate.is_file() and os.access(candidate, os.X_OK):
        return os.fspath(candidate)
    return ""


def _prepare(prefix: Path, game_type: str, wine: str, proton: object) -> tuple[str, str, list[str]]:
    """Resolve (winetricks, wine, warnings) for one prefix."""
    exe = shutil.which("winetricks")
    if not exe:
        return "", "", ["winetricks skipped: winetricks not found in PATH"]
    if not (prefix / "drive_c").is_dir():
        return (
            "",
            "",
            [
                f"winetricks skipped: {prefix} does not exist yet; "
                "launch the game once to create the prefix"
            ],
        )
    if game_type == "umu":
        wine = _wine_for(proton)
        if not wine:
            return "", "", ["winetricks skipped: the selected Proton install has no files/bin/wine"]
    elif not wine:
        return "", "", ["winetricks skipped: wine binary not found"]
    return exe, wine, []


def run_local(
    appid: str,
    prefix: Path,
    game_type: str,
    wine: str,
    proton: object,
    verbs: list[str],
) -> list[str]:
    """Run winetricks verbs in a local prefix. Returns warnings; never raises.

    ``wine`` is the resolved Wine binary for ``game_type == "wine"``;
    ``proton`` is the chosen :class:`runtimes.ProtonInstall` for umu.
    A prefix that does not exist yet is skipped: umu needs its own
    runtime to create one, and winetricks would create an incompatible
    prefix with a bare wine binary.
    """
    verbs = [str(v).strip() for v in (verbs or []) if str(v).strip()]
    if not verbs:
        return []
    prefix = Path(prefix)
    exe, wine, warnings = _prepare(prefix, game_type, wine, proton)
    if warnings:
        return warnings

    recorded = {"prefix": os.fspath(prefix), "verbs": sorted(verbs)}
    state = state_path(appid)
    try:
        if json.loads(state.read_text(encoding="utf-8")) == recorded:
            return []
    except Exception:
        pass

    env = dict(os.environ)
    env["WINEPREFIX"] = os.fspath(prefix)
    env["WINE"] = wine
    try:
        proc = subprocess.run(
            [exe, "-q", *verbs],
            capture_output=True,
            text=True,
            timeout=TIMEOUT,
            env=env,
        )
    except (OSError, subprocess.TimeoutExpired) as e:
        return [f"winetricks failed: {e}"]
    if proc.returncode != 0:
        tail = (proc.stderr or proc.stdout or "").strip().splitlines()[-3:]
        return [f"winetricks exit {proc.returncode}: {'; '.join(tail)}"[:300]]
    try:
        state.parent.mkdir(parents=True, exist_ok=True)
        state.write_text(json.dumps(recorded), encoding="utf-8")
    except Exception as e:
        return [f"winetricks ran, state not recorded: {e}"]
    return []
