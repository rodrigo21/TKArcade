"""SteamTinkerLaunch config importer (stdlib only, read-only on STL files).

Reads STL per-game files (~/.config/steamtinkerlaunch/gamecfgs/id/<aid>.conf)
which are shell-style VAR="value" files, and maps the subset common to
both programs onto a GameConfig. Anything else is reported, never guessed.
"""

from __future__ import annotations

import os
import re
import shlex
from pathlib import Path

from . import config as cfgmod

PROFILE_NAME = "steamtinkerlaunch"

_ASSIGN_RE = re.compile(r"^([A-Za-z_][A-Za-z0-9_]*)=(.*)$")

# STL vars exported as environment (allowlist; the rest are STL internals).
_ENV_PREFIXES = (
    "PROTON_",
    "WINE_",
    "DXVK_",
    "VKD3D_",
    "MANGOHUD",
    "SDL_",
    "RADV_",
    "MESA_",
    "DRI_",
    "__GL",
    "__NV",
    "HOST_LC_ALL",
)

_KNOWN_WINEDEBUG = {"", "-all", "+err", "+warn", "+warn,+err"}
_UNSET = {"", "none"}

# Boolean-ish flags where "0"/"none" means off (same as absent).
# Anything else (notably numeric scales like FSR_STRENGTH, where 0 means
# maximum sharpness) is never pruned.
_PRUNABLE_OFF = {
    "DXVK_HUD",
    "DXVK_LOG_LEVEL",
    "DXVK_FPSLIMIT",
    "DXVK_ASYNC",
    "PROTON_DUMP_DEBUG_COMMANDS",
    "PROTON_USE_WINED3D",
    "PROTON_NO_D3D12",
    "PROTON_NO_D3D11",
    "PROTON_NO_D3D10",
    "PROTON_NO_D3D9",
    "PROTON_NO_ESYNC",
    "PROTON_NO_FSYNC",
    "PROTON_ENABLE_NVAPI",
    "PROTON_HIDE_NVIDIA_GPU",
    "PROTON_FORCE_LARGE_ADDRESS_AWARE",
    "PROTON_HEAP_DELAY_FREE",
    "WINE_FULLSCREEN_FSR",
    "WINE_FULLSCREEN_INTEGER_SCALING",
    "DXVK_HDR",
    "PROTON_LOCAL_SHADER_CACHE",
    "PROTON_MEDIA_FORCE_GST",
}
_PRUNE_VALUES = {"0", "none"}


def stl_config_dir() -> Path:
    base = os.environ.get("XDG_CONFIG_HOME", "").strip() or str(Path.home() / ".config")
    return Path(base) / "steamtinkerlaunch"


def list_stl_appids() -> list[str]:
    """AppIDs with an STL per-game config file (numeric names only)."""
    d = stl_config_dir() / "gamecfgs" / "id"
    try:
        names = [p.stem for p in d.iterdir() if p.is_file()]
    except Exception:
        return []
    return sorted({n for n in names if n.isdigit()})


def parse_stl_conf(path: str | Path) -> dict[str, str]:
    """Parse shell-style VAR="value" lines; comments and junk skipped."""
    try:
        text = Path(path).read_text(encoding="utf-8", errors="replace")
    except Exception:
        return {}
    out: dict[str, str] = {}
    for raw in text.splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        match = _ASSIGN_RE.match(line)
        if not match:
            continue
        key, val = match.group(1), match.group(2).strip()
        if len(val) >= 2 and val[0] == val[-1] and val[0] in "\"'":
            try:
                val = shlex.split(val, posix=True)[0]
            except (ValueError, IndexError):
                val = val[1:-1]
        out[key] = val
    return out


def _is_set(value: str) -> bool:
    return value.strip().lower() not in _UNSET


def _exists_on_disk(command: str) -> bool:
    """True for existing paths and PATH binaries (no false missing alarms)."""
    import os
    import shutil

    text = (command or "").strip()
    if not text:
        return True
    try:
        first = shlex.split(text, posix=True)[0]
    except (ValueError, IndexError):
        first = text.split(maxsplit=1)[0]
    if not first:
        return True
    return os.path.exists(os.path.expanduser(first)) or shutil.which(first) is not None


# STL vars whose value "1" flips a GameConfig flag (section, attribute).
_TOGGLES = (
    ("USEGAMEMODERUN", "gamemode", "feral_gamemode"),
    ("USEMANGOHUD", "mangohud", "enable"),
    ("PROTON_LOG", "debug", "proton_log"),
)

#: STL-only settings with no TKArcade equivalent (counted for the report).
_NO_EQUIVALENT = ("USEPROTON", "REDIRCOMPDATA", "USESLR")


def _map_switches(get, cfg: cfgmod.GameConfig, report: list[str]) -> None:
    """Flag toggles, plus USEGAMESCOPE (enable + its argument list)."""
    for key, section, attr in _TOGGLES:
        if get(key) == "1":
            setattr(getattr(cfg, section), attr, True)
    if get("USEGAMESCOPE") != "1":
        return
    cfg.gamescope.enable = True
    try:
        args = [t for t in shlex.split(get("GAMESCOPE_ARGS")) if t != "--"]
    except ValueError:
        args = []
        report.append("GAMESCOPE_ARGS had unbalanced quotes; dropped")
    cfg.gamescope.args = " ".join(args)


def _map_custom_command(get, cfg: cfgmod.GameConfig, report: list[str]) -> None:
    """CUSTOMCMD becomes the pre-launch hook, or the exe in "only" mode."""
    customcmd, customargs = get("CUSTOMCMD"), get("CUSTOMCMD_ARGS")
    if get("USECUSTOMCMD") != "1" or not _is_set(customcmd):
        return
    if get("ONLY_CUSTOMCMD") == "1":
        cfg.general.custom_executable = customcmd
        return
    cfg.pre_post.pre_command = customcmd
    try:
        cfg.pre_post.pre_args = shlex.split(customargs)
    except ValueError:
        report.append("CUSTOMCMD_ARGS had unbalanced quotes; dropped")
    report.append("CUSTOMCMD runs alongside the game here (STL fork/inject modes unsupported)")


def _map_hooks(get, cfg: cfgmod.GameConfig, report: list[str]) -> None:
    """USERSTART / USERSTOP override the pre / post hooks."""
    if _is_set(get("USERSTART")):
        if cfg.pre_post.pre_command:
            report.append(f"USERSTART {get('USERSTART')!r} replaced CUSTOMCMD as pre-launch hook")
        cfg.pre_post.pre_command = get("USERSTART")
        cfg.pre_post.pre_args = []
    if _is_set(get("USERSTOP")):
        cfg.pre_post.post_command = get("USERSTOP")
        cfg.pre_post.post_args = []


def _map_proton(get, cfg: cfgmod.GameConfig, report: list[str]) -> None:
    """Winetricks verbs and the Wine debug selector."""
    verbs = (get("WINETRICKSPAKS") or "").split()
    cfg.proton.winetricks_verbs = [v for v in verbs if v.lower() not in _UNSET]
    winedebug = get("STLWINEDEBUG")
    if winedebug and winedebug not in _KNOWN_WINEDEBUG:
        report.append(f"STLWINEDEBUG {winedebug!r} has no equivalent selector; left Off")
    elif winedebug:
        cfg.debug.winedebug = winedebug


def _env_skip(key: str, value: str) -> str:
    """Why an STL var is not imported as an env var: "" / "off" / "path"."""
    if not value or key == "PROTON_LOG" or not key.startswith(_ENV_PREFIXES):
        return "off"
    if "STLCFGDIR" in value:
        return "path"
    if key in _PRUNABLE_OFF and value.strip().lower() in _PRUNE_VALUES:
        return "off"
    return ""


def _collect_env(stl: dict[str, str], cfg: cfgmod.GameConfig, report: list[str]) -> None:
    """Import STL vars straight onto env vars, minus placeholders and offs."""
    skipped_paths = 0
    pruned_off = 0
    for key, value in stl.items():
        skip = _env_skip(key, value)
        if skip == "path":
            skipped_paths += 1
        elif skip == "off":
            pruned_off += 1
        elif not skip:
            cfg.env.vars[key] = value
    if skipped_paths:
        report.append(f"{skipped_paths} env-style value(s) referenced STL paths; skipped")
    if pruned_off:
        report.append(f"{pruned_off} default-off value(s) dropped (same as unset)")


def _audit_hook_paths(cfg: cfgmod.GameConfig, report: list[str]) -> None:
    """Warn about hook / executable paths that are missing on disk."""
    for label, path in (
        ("pre-launch hook", cfg.pre_post.pre_command),
        ("post-exit hook", cfg.pre_post.post_command),
        ("custom executable", cfg.general.custom_executable),
    ):
        if path and not _exists_on_disk(path):
            report.append(f"{label} not found on disk: {path}")


def _note_ignored(get, report: list[str]) -> None:
    """Count STL-only settings with no equivalent, as one report line."""
    ignored = sum(1 for key in _NO_EQUIVALENT if _is_set(get(key)))
    if ignored:
        report.append(f"{ignored} STL-only setting(s) have no equivalent")


def map_to_gameconfig(appid: str, stl: dict[str, str]) -> tuple[cfgmod.GameConfig, list[str]]:
    """Map STL vars onto a GameConfig. Returns (config, report notes)."""
    cfg = cfgmod.GameConfig()
    cfg.general.appid = appid
    report: list[str] = []

    def get(key: str) -> str:
        return stl.get(key, "")

    _map_switches(get, cfg, report)
    _map_custom_command(get, cfg, report)
    _map_hooks(get, cfg, report)
    _map_proton(get, cfg, report)
    _collect_env(stl, cfg, report)
    _audit_hook_paths(cfg, report)
    _note_ignored(get, report)

    cfg.notes.text = f"Imported from SteamTinkerLaunch config for AppID {appid}."
    return cfg, report
