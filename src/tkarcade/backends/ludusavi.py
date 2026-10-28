"""ludusavi integration (simple level: CLI delegation only).

Uses `ludusavi wrap` as the game invocation: it restores before launch and
backs up after exit. NOTE: `backup`/`restore` subcommands do NOT accept
`--infer` (only `wrap` does), and game names there are positional, so the
split approach cannot address games by Steam AppID. `wrap` supports both
`--infer steam` and `--name`, plus `--no-restore`/`--no-backup` for the
independent toggles.
"""

from __future__ import annotations

import json
import shutil
import subprocess

from ..steam import is_steam_id
from . import is_flatpak_path, which

# Fixed `sh -c` script used to recover the wrapped game's exit code
# (`wrap` itself returns 0 even when the game crashes). $0 carries the
# rc-file path, $@ the game command. List-based, no quoting needed.
_SH_EXIT_SENTINEL = '"$@"; echo $? > "$0"'


def find() -> tuple[str | None, str | None]:
    """Return (path, warning). Warning set for flatpak builds."""
    path = which("ludusavi")
    if not path:
        return None, "ludusavi not found in PATH"
    if is_flatpak_path(path) or "flatpak" in path:
        return path, "flatpak ludusavi may not see Proton prefixes; prefer standalone binary"
    return path, None


def effective_name(appid: str, name_override: str, game_name: str) -> str:
    """The game name `wrap` and the coverage check resolve saves by.

    The explicit override wins. A Steam id lets Ludusavi infer the game;
    a local game has none (its id is `local-*`), so its `[general]` name
    is the default. '' tells the caller to infer by Steam id.
    """
    override = (name_override or "").strip()
    if override:
        return override
    if is_steam_id(appid):
        return ""
    return (game_name or "").strip()


def _wrap_options(name_override: str, restore: bool, backup: bool, use_gui: bool) -> list[str]:
    """`ludusavi wrap` prefix with the name and restore/backup/gui flags."""
    opts = ["ludusavi", "wrap"]
    if (name_override or "").strip():
        opts += ["--name", name_override.strip()]
    else:
        opts += ["--infer", "steam"]
    if not restore:
        opts.append("--no-restore")
    if not backup:
        opts.append("--no-backup")
    if use_gui:
        opts.append("--gui")
    return opts


def _inner_command(game_cmd: list[str], rc_file: str) -> tuple[list[str], str]:
    """The game command, wrapped in `sh -c` when rc_file wants the exit code.

    Returns (command, warning); the warning is set when rc_file was asked
    but `sh` is missing, so the code stays masked by ludusavi wrap.
    """
    if not rc_file:
        return list(game_cmd), ""
    if shutil.which("sh"):
        return ["sh", "-c", _SH_EXIT_SENTINEL, rc_file, *game_cmd], ""
    return list(game_cmd), "sh not found, game exit code may be masked by ludusavi wrap"


def wrap_command(
    game_cmd: list[str],
    *,
    name_override: str = "",
    enabled: bool = False,
    restore: bool = True,
    backup: bool = True,
    use_gui: bool = True,
    rc_file: str = "",
) -> tuple[list[str], list[str]]:
    """Wrap game_cmd with `ludusavi wrap`.

    Returns (new_cmd, warnings). new_cmd == game_cmd unchanged when ludusavi
    is off (enabled=False, or neither restore nor backup). When enabled but
    the binary is missing, returns game_cmd + warning.

    When rc_file is given (and `sh` exists), the game runs inside
    `sh -c '"$@"; echo $? > rc_file'` so callers can recover the real game
    exit code that `wrap` otherwise masks with 0.
    """
    warnings: list[str] = []
    if not enabled or (not restore and not backup):
        return list(game_cmd), warnings
    path, warn = find()
    if warn:
        warnings.append(warn)
    if not path:
        return list(game_cmd), warnings
    # Bare name (PATH lookup at launch), consistent with the other
    # wrappers; `path` above is only used for the missing/flatpak checks.
    cmd = _wrap_options(name_override, restore, backup, use_gui)
    inner, inner_warn = _inner_command(game_cmd, rc_file)
    if inner_warn:
        warnings.append(inner_warn)
    cmd += ["--", *inner]
    return cmd, warnings


def _find_manifest_title(path: str, appid: str, name_override: str) -> tuple[str, str]:
    """Resolve a game's manifest title. Returns (title, failure detail)."""
    if (name_override or "").strip():
        find_cmd = [path, "find", "--api", "--", name_override.strip()]
    else:
        find_cmd = [path, "find", "--api", "--steam-id", str(appid)]
    try:
        found = subprocess.run(find_cmd, capture_output=True, text=True, timeout=120)
    except (OSError, subprocess.TimeoutExpired) as e:
        return "", f"ludusavi find failed: {e}"
    if found.returncode != 0:
        return "", ""
    try:
        games = json.loads(found.stdout or "{}").get("games", {})
    except ValueError:
        return "", ""
    return (next(iter(games)) if isinstance(games, dict) else ""), ""


def _preview_files(path: str, title: str) -> tuple[dict, str]:
    """The manifest's file map for a title. Returns (files, failure detail)."""
    try:
        preview = subprocess.run(
            [path, "backup", "--preview", "--api", title],
            capture_output=True,
            text=True,
            timeout=180,
        )
    except (OSError, subprocess.TimeoutExpired) as e:
        return {}, f"ludusavi preview failed: {e}"
    if preview.returncode != 0:
        return {}, "ludusavi preview failed"
    try:
        entry = json.loads(preview.stdout or "{}").get("games", {}).get(title, {})
    except ValueError:
        entry = {}
    files = entry.get("files", {}) if isinstance(entry, dict) else {}
    return (files if isinstance(files, dict) else {}), ""


def check_coverage(appid: str, name_override: str = "") -> tuple[str, str]:
    """Check manifest coverage for a game. Returns (status, detail).

    status is 'covered' (saves found), 'no-local-saves' (entry exists but
    nothing on disk), 'no-entry' (no manifest entry) or 'unavailable'.
    Resolves by Steam ID, or by exact title with a name override.
    """
    path, _warn = find()
    if not path:
        return "unavailable", "ludusavi not found in PATH"
    title, failed = _find_manifest_title(path, appid, name_override)
    if failed:
        return "unavailable", failed
    if not title:
        return "no-entry", "No manifest entry for this game"
    files, failed = _preview_files(path, title)
    if failed:
        return "unavailable", failed
    total = 0
    for info in files.values():
        size = info.get("bytes", 0) if isinstance(info, dict) else 0
        total += size if isinstance(size, int) else 0
    if not files:
        return "no-local-saves", f"Entry '{title}' exists, no saves on disk"
    return "covered", f"Entry '{title}': {len(files)} file(s), {total} bytes"
