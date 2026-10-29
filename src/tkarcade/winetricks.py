"""winetricks verbs for local Wine/umu prefixes (stdlib only).

The Steam path lives in ``proton.run_winetricks`` and goes through
protontricks; a local game has no AppID, so this runs the host
``winetricks`` against the game's prefix with ``WINE`` pointing at the
chosen runtime. The recorded state includes the prefix path, so moving
a game to another prefix reruns the verbs.

A Steam game whose ``[runtime] prefix`` moves the compatdata dir cannot
use protontricks either (it always targets Steam's own), so it takes the
same path: the game's Proton provides ``WINE`` and the prefix is the
custom container's ``pfx``.

The launcher calls this before the command is built, so a failure only
warns and never blocks the launch.
"""

from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
from pathlib import Path

from . import xdg

TIMEOUT = 1200

#: Environments whose prefix is Proton's: the Proton install supplies wine.
PROTON_RUNTIMES = ("umu", "proton")

# `list-all` costs ~2s and never changes while the binary sits there, so
# the parsed rows are cached per process, keyed by path plus mtime.
_CATALOG: tuple[tuple[str, int] | None, list[dict]] | None = None


def state_path(appid: str) -> Path:
    return xdg.app_state_dir() / "winetricks" / f"{appid}.json"


def _log_path(prefix: Path) -> Path | None:
    """winetricks.log of a WINEPREFIX or of a Steam compatdata container."""
    for candidate in (prefix / "winetricks.log", prefix / "pfx" / "winetricks.log"):
        try:
            if candidate.is_file():
                return candidate
        except OSError:
            continue
    return None


def installed_verbs(prefix: Path) -> list[str]:
    """Verbs recorded in ``winetricks.log``, in install order ([] when none).

    winetricks appends the whole verb list of a run on one line, so every
    line is tokenized. Options and the internal workaround entries are
    dropped: they are not verbs the user picked. Protontricks writes
    through winetricks, so the same reader covers Steam and local games;
    a compatdata directory is looked into through its ``pfx``.
    """
    path = _log_path(Path(prefix))
    if path is None:
        return []
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return []
    verbs: list[str] = []
    for line in text.splitlines():
        for token in line.split():
            if token.startswith("-") or token.startswith("w_workaround_wine_bug"):
                continue
            if token not in verbs:
                verbs.append(token)
    return verbs


def parse_catalog(text: str) -> list[dict]:
    """Rows of ``winetricks list-all``: verb, description and category.

    Sections are ``===== apps =====`` headers; each entry is the verb
    padded to a column and its description. Unparsable lines are skipped.
    """
    rows: list[dict] = []
    category = ""
    for line in str(text or "").splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        if stripped.startswith("=====") and stripped.endswith("====="):
            category = stripped.strip("= ").strip()
            continue
        parts = re.split(r"\s{2,}", stripped, maxsplit=1)
        word = parts[0].strip()
        if not word or " " in word:
            continue
        rows.append(
            {
                "verb": word,
                "description": parts[1].strip() if len(parts) > 1 else "",
                "category": category,
            }
        )
    return rows


def clear_catalog_cache() -> None:
    """Forget the parsed ``list-all`` rows (tests pick another binary)."""
    global _CATALOG
    _CATALOG = None


def catalog_ready() -> bool:
    """Whether :func:`list_all` answers without spawning winetricks."""
    exe = shutil.which("winetricks")
    if not exe:
        return True
    if _CATALOG is None:
        return False
    try:
        return _CATALOG[0] == (exe, Path(exe).stat().st_mtime_ns)
    except OSError:
        return False


def list_all() -> list[dict]:
    """``winetricks list-all`` parsed and cached per process ([] without it)."""
    global _CATALOG
    exe = shutil.which("winetricks")
    if not exe:
        return []
    try:
        key: tuple[str, int] | None = (exe, Path(exe).stat().st_mtime_ns)
    except OSError:
        key = None
    if _CATALOG is not None and _CATALOG[0] == key:
        return _CATALOG[1]
    try:
        proc = subprocess.run([exe, "list-all"], capture_output=True, text=True, timeout=60)
    except (OSError, subprocess.TimeoutExpired):
        return []
    if proc.returncode != 0:
        return []
    rows = parse_catalog(proc.stdout)
    _CATALOG = (key, rows)
    return rows


def _wine_for(proton: object) -> str:
    """The Proton install's wine binary ("" when absent)."""
    path = getattr(proton, "path", None)
    if not path:
        return ""
    candidate = Path(path) / "files" / "bin" / "wine"
    if candidate.is_file() and os.access(candidate, os.X_OK):
        return os.fspath(candidate)
    return ""


def _prepare(
    prefix: Path, environment: str, wine: str, proton: object
) -> tuple[str, str, list[str]]:
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
    if environment in PROTON_RUNTIMES:
        wine = _wine_for(proton)
        if not wine:
            return "", "", ["winetricks skipped: the selected Proton install has no files/bin/wine"]
    elif not wine:
        return "", "", ["winetricks skipped: wine binary not found"]
    return exe, wine, []


def run_local(
    appid: str,
    prefix: Path,
    environment: str,
    wine: str,
    proton: object,
    verbs: list[str],
) -> list[str]:
    """Run winetricks verbs in a local prefix. Returns warnings; never raises.

    ``wine`` is the resolved Wine binary for ``environment == "wine"``;
    ``proton`` is the chosen :class:`runtimes.ProtonInstall` for umu.
    A prefix that does not exist yet is skipped: umu needs its own
    runtime to create one, and winetricks would create an incompatible
    prefix with a bare wine binary.
    """
    verbs = [str(v).strip() for v in (verbs or []) if str(v).strip()]
    if not verbs:
        return []
    prefix = Path(prefix)
    exe, wine, warnings = _prepare(prefix, environment, wine, proton)
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


def local_gui(
    prefix: Path, environment: str, wine: str, proton: object
) -> tuple[list[str], dict[str, str], str]:
    """argv/env for ``winetricks --gui``, plus a message when it cannot run.

    ``prefix`` is a real WINEPREFIX (the compatdata ``pfx`` for Steam).
    A missing prefix, binary or wine refuses instead of opening a GUI
    that would build an incompatible prefix: the launch path skips the
    same cases, and umu needs its own runtime to create one.
    """
    exe = shutil.which("winetricks")
    if not exe:
        return [], {}, "Winetricks Was Not Found in PATH."
    prefix = Path(prefix)
    if not (prefix / "drive_c").is_dir():
        return [], {}, f"The Prefix Does Not Exist Yet: {prefix} — Launch the Game Once."
    if environment in PROTON_RUNTIMES:
        wine = _wine_for(proton)
        if not wine:
            return [], {}, "The Selected Proton Install Has No files/bin/wine."
    elif not wine:
        return [], {}, "No Wine Binary: Pick a Tool in the Runtime Tab."
    return [exe, "--gui"], {"WINEPREFIX": os.fspath(prefix), "WINE": wine}, ""
