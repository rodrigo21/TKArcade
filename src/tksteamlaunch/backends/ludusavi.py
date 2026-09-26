"""ludusavi integration (simple level: CLI delegation only).

Uses `ludusavi wrap` as the game invocation: it restores before launch and
backs up after exit. NOTE: `backup`/`restore` subcommands do NOT accept
`--infer` (only `wrap` does), and game names there are positional, so the
split approach cannot address games by Steam AppID. `wrap` supports both
`--infer steam` and `--name`, plus `--no-restore`/`--no-backup` for the
independent toggles.
"""

from __future__ import annotations

import shutil
import subprocess

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
    cmd = [path, "wrap"]
    if (name_override or "").strip():
        cmd += ["--name", name_override.strip()]
    else:
        cmd += ["--infer", "steam"]
    if not restore:
        cmd += ["--no-restore"]
    if not backup:
        cmd += ["--no-backup"]
    if use_gui:
        cmd += ["--gui"]
    inner = list(game_cmd)
    if rc_file and shutil.which("sh"):
        inner = ["sh", "-c", _SH_EXIT_SENTINEL, rc_file, *game_cmd]
    elif rc_file:
        warnings.append("sh not found, game exit code may be masked by ludusavi wrap")
    cmd += ["--", *inner]
    return cmd, warnings


def check_coverage(appid: str, name_override: str = "") -> tuple[str, str]:
    """Check manifest coverage for a game. Returns (status, detail).

    status is 'covered' (saves found), 'no-local-saves' (entry exists but
    nothing on disk), 'no-entry' (no manifest entry) or 'unavailable'.
    Resolves by Steam ID, or by exact title with a name override.
    """
    import json

    path, _warn = find()
    if not path:
        return "unavailable", "ludusavi not found in PATH"
    if (name_override or "").strip():
        find_cmd = [path, "find", "--api", "--", name_override.strip()]
    else:
        find_cmd = [path, "find", "--api", "--steam-id", str(appid)]
    try:
        found = subprocess.run(find_cmd, capture_output=True, text=True, timeout=120)
    except (OSError, subprocess.TimeoutExpired) as e:
        return "unavailable", f"ludusavi find failed: {e}"
    title = ""
    if found.returncode == 0:
        try:
            games = json.loads(found.stdout or "{}").get("games", {})
            title = next(iter(games)) if isinstance(games, dict) else ""
        except ValueError:
            title = ""
    if not title:
        return "no-entry", "No manifest entry for this game"
    try:
        preview = subprocess.run(
            [path, "backup", "--preview", "--api", title],
            capture_output=True,
            text=True,
            timeout=180,
        )
    except (OSError, subprocess.TimeoutExpired) as e:
        return "unavailable", f"ludusavi preview failed: {e}"
    if preview.returncode != 0:
        return "unavailable", "ludusavi preview failed"
    try:
        entry = json.loads(preview.stdout or "{}").get("games", {}).get(title, {})
    except ValueError:
        entry = {}
    files = entry.get("files", {}) if isinstance(entry, dict) else {}
    total = sum(info.get("bytes", 0) for info in files.values() if isinstance(info, dict))
    if not files:
        return "no-local-saves", f"Entry '{title}' exists, no saves on disk"
    return "covered", f"Entry '{title}': {len(files)} file(s), {total} bytes"
