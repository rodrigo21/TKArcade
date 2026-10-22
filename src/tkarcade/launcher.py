"""tkarcade CLI: Steam -> tkarcade %command% -> game.

Pipeline:
  resolve AppID -> load game snapshot (unconfigured games use the defaults
  template) -> nightlight disable -> pre hook -> build prefix (exe swap
  honoring game type + custom prefix + mangohud + cachy/gamemode +
  gamescope, ludusavi wrap outermost with exit-code recovery) -> run game
  -> post hook -> nightlight restore -> log (per-game <appid>.log plus a
  one-line global entry)
"""

from __future__ import annotations

import argparse
import datetime
import json
import logging
import logging.handlers
import os
import shlex
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path

from . import config as cfgmod
from . import proton as protonmod
from . import steam as steammod
from . import xdg
from .backends import audio as au_backend
from .backends import display as disp_backend
from .backends import gamemode as gm_backend
from .backends import ludusavi as lu_backend
from .backends import nightlight as nl_backend
from .backends import notify as notify_backend
from .backends import overlay as ov_backend
from .backends import prepost as pp_backend
from .backends import rtupscale as rtu_backend
from .backends import split_args
from .config import GameType

log = logging.getLogger("tkarcade")


class PrefixNotFoundError(ValueError):
    """Raised when custom_prefix names a binary missing from PATH."""


_GUI_ENV_KEYS = (
    "QT_QPA_PLATFORM",
    "QT_QPA_PLATFORMTHEME",
    "QT_STYLE_OVERRIDE",
    "XDG_CURRENT_DESKTOP",
    "DESKTOP_SESSION",
)


def _log_gui_env() -> None:
    """Log Qt/desktop env keys to help diagnose GUI theming issues."""
    try:
        shown = {k: os.environ.get(k, "") for k in _GUI_ENV_KEYS}
        ld = os.environ.get("LD_LIBRARY_PATH", "")
        if len(ld) > 200:
            ld = ld[:200] + "..."
        shown["LD_LIBRARY_PATH"] = ld
        log.info("gui env: %r", shown)
    except Exception:
        pass


def setup_logging(appid: str = "", verbose: bool = False) -> Path:
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format="%(asctime)s %(name)s %(levelname)s: %(message)s",
    )
    if not appid:
        return xdg.log_file()
    try:
        d = xdg.games_log_dir()
        d.mkdir(parents=True, exist_ok=True)
        target = d / f"{appid}.log"
        root = logging.getLogger()
        for h in root.handlers:
            name = getattr(h, "baseFilename", "")
            if name and os.path.abspath(name) == os.path.abspath(target):
                # Already attached (e.g. --edit/--menu calls this twice):
                # don't stack a second handler writing the same file.
                h.setLevel(level)
                return target
        fh = logging.handlers.RotatingFileHandler(
            target,
            maxBytes=1_000_000,
            backupCount=3,
            encoding="utf-8",
        )
        fh.setLevel(level)
        fh.setFormatter(logging.Formatter("%(asctime)s %(name)s %(levelname)s: %(message)s"))
        root.addHandler(fh)
        return target
    except Exception:
        return Path(f"{appid}.log")


def write_global_log(
    appid: str, exit_code: int, cmd: list[str], duration: float | None = None
) -> None:
    """Append a one-line summary to the global launcher.log."""
    try:
        path = xdg.log_file()
        path.parent.mkdir(parents=True, exist_ok=True)
        stamp = datetime.datetime.now().astimezone().isoformat(timespec="seconds")
        shown = shlex.join(cmd)
        if len(shown) > 300:
            shown = shown[:300] + "..."
        line = f"{stamp} appid={appid} exit={exit_code}"
        if duration is not None:
            line += f" dur={max(0, int(duration))}"
        line += f" cmd={shown}\n"
        with path.open("a", encoding="utf-8") as f:
            f.write(line)
    except Exception as e:
        log.error("cannot write global log: %s", e)


def local_run_cwd(appid: str, cfg: cfgmod.GameConfig) -> str | None:
    """Working directory for local games: the executable's own folder.

    A valid launch_cwd override wins. None means inherit (all Steam
    launches and path-less commands).
    """
    if steammod.is_steam_id(appid):
        return None
    override = (cfg.general.launch_cwd or "").strip()
    if override:
        if Path(override).is_dir():
            return override
        log.warning("launch_cwd is not a directory, ignoring: %r", override)
    exe = (cfg.general.custom_executable or "").strip()
    if exe and Path(exe).is_file():
        return str(Path(exe).parent) or None
    return None


def proton_log_dir(appid: str) -> Path:
    """Directory for PROTON_LOG output of one game (created at launch)."""
    safe = xdg.safe_stem((appid or "").strip())
    return xdg.games_log_dir() / safe / "proton"


#: A planted skip file suppresses the pre-launch menu once (Play button,
#: tray and context menu launch straight through Steam).
MENU_SKIP_TTL = 300


def menu_skip_path(appid: str) -> Path:
    """Sentinel file consumed by the next launch of this game."""
    return xdg.app_state_dir() / f"skip-menu-{xdg.safe_stem(appid)}.once"


def plant_menu_skip(appid: str) -> None:
    """Ask the next launch to skip the pre-launch menu (best effort)."""
    try:
        path = menu_skip_path(appid)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("1", encoding="utf-8")
    except OSError as e:
        log.warning("cannot plant menu skip: %s", e)


def consume_menu_skip(appid: str) -> bool:
    """Use up a planted menu skip; False when absent or stale."""
    path = menu_skip_path(appid)
    try:
        fresh = time.time() - path.stat().st_mtime < MENU_SKIP_TTL
    except OSError:
        return False
    try:
        path.unlink(missing_ok=True)
    except OSError:
        pass
    return fresh


def swap_proton_executable(game_cmd: list[str], custom: str) -> list[str]:
    """Swap exe inside Proton prefix. Keeps 'proton run' wrapper.

    - if 'run' token found (proton run <exe>), replace next token
    - elif '--' found, replace token after '--'
    - elif empty game_cmd, return [custom]
    - else return game_cmd unchanged + warning handled by caller
    """
    custom = (custom or "").strip()
    if not custom:
        return game_cmd
    if not game_cmd:
        return [custom]
    out = list(game_cmd)
    if "run" in out:
        i = out.index("run")
        if i + 1 < len(out):
            out[i + 1] = custom
            return out
    if "--" in out:
        i = out.index("--")
        if i + 1 < len(out):
            out[i + 1] = custom
            return out
    return out


def detect_game_type(game_cmd: list[str], explicit: str = "auto") -> str:
    """Return 'proton' or 'native'. Explicit setting wins; auto sniffs."""
    req = (explicit or "auto").strip().lower()
    match req:
        case GameType.PROTON | GameType.NATIVE:
            return str(req)
    if os.environ.get("STEAM_COMPAT_DATA_PATH", "").strip():
        return str(GameType.PROTON)
    if any("proton" in t.lower() for t in game_cmd):
        return str(GameType.PROTON)
    return str(GameType.NATIVE)


def swap_native_executable(game_cmd: list[str], custom: str) -> list[str]:
    """Replace argv[0], keeping arguments. Used for native Linux games."""
    custom = (custom or "").strip()
    if not custom:
        return game_cmd
    if not game_cmd:
        return [custom]
    return [custom, *game_cmd[1:]]


def _game_argv(
    cfg: cfgmod.GameConfig, game_cmd: list[str], game_type: str
) -> tuple[list[str], list[str]]:
    """Game argv: custom executable swapped in, plus configured launch args."""
    warnings: list[str] = []
    custom = cfg.general.custom_executable.strip()
    if game_type == "native":
        cmd = swap_native_executable(list(game_cmd), custom)
    else:
        cmd = swap_proton_executable(list(game_cmd), custom)
        if custom and game_cmd and custom not in cmd:
            warnings.append(
                "custom_executable set but no 'run'/'--' marker found; keeping original command"
            )
    extra_args = (cfg.general.launch_args or "").strip()
    if extra_args:
        # split_args never raises: unbalanced quotes fall back to plain
        # whitespace splitting, so a config typo cannot abort the launch.
        cmd = [*cmd, *split_args(extra_args)]
    return cmd, warnings


def _apply_custom_prefix(cmd: list[str], prefix: str) -> list[str]:
    """Wrap the command with the custom prefix, or abort loudly.

    Innermost wrapper: it holds the executable directly (e.g. zink-run),
    inside mangohud/gamemode/gamescope/wrap. Unlike the others this one
    cannot be skipped.
    """
    if not prefix:
        return cmd
    parts = split_args(prefix)
    if parts and not shutil.which(parts[0]):
        raise PrefixNotFoundError(f"custom_prefix binary not found in PATH: {parts[0]!r}")
    return parts + cmd


def _apply_fps_cap(cmd: list[str], cfg: cfgmod.GameConfig) -> tuple[list[str], list[str]]:
    """Cap FPS through libstrangle when MangoHud (which caps itself) is off."""
    fps = max(0, int(cfg.mangohud.fps_limit or 0))
    if fps <= 0 or cfg.mangohud.enable:
        return cmd, []
    if shutil.which("strangle"):
        return ["strangle", str(fps), *cmd], ["MangoHud disabled: FPS capped via libstrangle"]
    return cmd, ["fps_limit set but MangoHud is disabled; ignoring"]


def _apply_idle_inhibit(cmd: list[str], cfg: cfgmod.GameConfig) -> tuple[list[str], list[str]]:
    """Wrap with systemd-inhibit (idle only: logind grants no sleep lock)."""
    if not cfg.session.inhibit_idle:
        return cmd, []
    if not shutil.which("systemd-inhibit"):
        return cmd, ["systemd-inhibit not found, skipping idle inhibitor"]
    why = cfg.general.appid.strip() or "game"
    wrapped = ["systemd-inhibit", "--what=idle", "--who=TKArcade", f"--why={why}", "--", *cmd]
    return wrapped, []


def _apply_wrappers(
    cmd: list[str], cfg: cfgmod.GameConfig, wrap_rc_file: str
) -> tuple[list[str], list[str]]:
    """Layer the enabled wrappers inner (mangohud) to outer (ludusavi)."""
    warnings: list[str] = []
    cmd, w = ov_backend.apply_mangohud(cmd, cfg.mangohud.enable, cfg.mangohud.args)
    warnings += w
    cmd, w = rtu_backend.apply(cmd, cfg.rtupscale.enable, cfg.rtupscale.args)
    warnings += w
    cmd, w = gm_backend.prefix(
        cmd, cfg.gamemode.feral_gamemode, cfg.gamemode.cachyos_game_performance
    )
    warnings += w
    cmd, w = ov_backend.apply_gamescope(cmd, cfg.gamescope.enable, cfg.gamescope.args)
    warnings += w
    cmd, w = _apply_idle_inhibit(cmd, cfg)
    warnings += w
    # ludusavi wrap outermost: restore runs before everything, backup --gui
    # after the whole stack (e.g. gamescope) exits so dialogs stay visible.
    # wrap_rc_file recovers the real game exit code that wrap masks with 0.
    cmd, w = lu_backend.wrap_command(
        cmd,
        name_override=cfg.ludusavi.name_override,
        enabled=cfg.ludusavi.enable,
        restore=cfg.ludusavi.restore,
        backup=cfg.ludusavi.backup,
        use_gui=cfg.ludusavi.use_gui,
        rc_file=wrap_rc_file,
    )
    warnings += w
    return cmd, warnings


def _force_xwayland(env: dict) -> list[str]:
    """Force XWayland for rt-upscaler (it only handles X11/XWayland windows)."""
    was_wayland = env.get("PROTON_ENABLE_WAYLAND", "").strip() == "1"
    env["PROTON_ENABLE_WAYLAND"] = "0"
    if was_wayland:
        return ["rt-upscaler needs XWayland: overriding PROTON_ENABLE_WAYLAND=1 with 0"]
    return []


def _debug_env(env: dict, cfg: cfgmod.GameConfig) -> None:
    """PROTON_LOG / PROTON_LOG_DIR / WINEDEBUG toggles."""
    if cfg.debug.proton_log:
        env["PROTON_LOG"] = "1"
        env["PROTON_LOG_DIR"] = os.fspath(proton_log_dir(cfg.general.appid))
    winedebug = cfg.debug.winedebug.strip()
    if winedebug:
        env["WINEDEBUG"] = winedebug


def _build_env(cfg: cfgmod.GameConfig, game_type: str) -> tuple[dict, list[str]]:
    """Environment for the game: config vars, wrapper bits, debug toggles."""
    warnings: list[str] = []
    env = dict(cfg.env.vars)
    mh_env, w = ov_backend.mangohud_env(cfg.mangohud.config_file)
    warnings += w
    env.update(mh_env)
    if cfg.rtupscale.enable:
        warnings += _force_xwayland(env)
    _debug_env(env, cfg)
    prefix = cfg.proton.wine_prefix.strip()
    if prefix and game_type == "proton" and "STEAM_COMPAT_DATA_PATH" not in env:
        env["STEAM_COMPAT_DATA_PATH"] = prefix
    fps = max(0, int(cfg.mangohud.fps_limit or 0))
    if cfg.mangohud.enable and fps > 0:
        prior = env.get("MANGOHUD_CONFIG", "").strip()
        env["MANGOHUD_CONFIG"] = f"{prior},fps_limit={fps}" if prior else f"fps_limit={fps}"
    return env, warnings


def build_final_command(
    cfg: cfgmod.GameConfig,
    game_cmd: list[str],
    wrap_rc_file: str = "",
) -> tuple[list[str], dict, list[str]]:
    """Assemble the launch argv and extra environment for one game."""
    game_type = detect_game_type(game_cmd, cfg.general.game_type)
    cmd, warnings = _game_argv(cfg, game_cmd, game_type)
    cmd = _apply_custom_prefix(cmd, cfg.general.custom_prefix.strip())
    cmd, w = _apply_fps_cap(cmd, cfg)
    warnings += w
    cmd, w = _apply_wrappers(cmd, cfg, wrap_rc_file)
    warnings += w
    env, w = _build_env(cfg, game_type)
    warnings += w
    return cmd, env, warnings


def _new_wrap_rc_file(appid: str) -> str:
    """Reserve a sentinel path where the wrap shim writes the game exit code."""
    d = xdg.app_state_dir()
    d.mkdir(parents=True, exist_ok=True)
    fd, path = tempfile.mkstemp(prefix=f"tkarcade-{appid}-", suffix=".rc", dir=str(d))
    os.close(fd)
    return path


def _remove_wrap_rc_file(path: str) -> None:
    if path:
        try:
            Path(path).unlink(missing_ok=True)
        except Exception:
            pass


def _read_wrap_rc_file(path: str, fallback: int) -> int:
    """Read the game exit code captured by the wrap shim, else fallback."""
    try:
        code = int(Path(path).read_text(encoding="utf-8").strip().split()[0])
        if 0 <= code <= 255:
            return code
        log.warning("wrap exit-code file out of range: %r", code)
    except Exception as e:
        log.warning("could not read wrap exit-code file, using wrap code: %s", e)
    return fallback


def active_wrappers(cfg: cfgmod.GameConfig) -> list[str]:
    """Enabled wrappers/add-ons, innermost first, for summaries and menus."""
    rules = (
        ("GameMode", cfg.gamemode.feral_gamemode),
        ("game-performance", cfg.gamemode.cachyos_game_performance),
        ("Gamescope", cfg.gamescope.enable),
        ("MangoHud", cfg.mangohud.enable),
        ("RT Upscaler", cfg.rtupscale.enable),
        ("Ludusavi", cfg.ludusavi.enable and (cfg.ludusavi.restore or cfg.ludusavi.backup)),
        ("Night Light", cfg.nightlight.disable_during_game),
        ("Idle Inhibit", cfg.session.inhibit_idle),
        ("Fresh Prefix", cfg.proton.fresh_prefix),
    )
    return [label for label, enabled in rules if enabled]


def notify_launch(appid: str, cfg: cfgmod.GameConfig, game_cmd: list[str]) -> tuple[str, str]:
    """Send the transient game-start summary. Returns (name, icon) for reuse."""
    game_type = detect_game_type(game_cmd, cfg.general.game_type)
    wrappers = active_wrappers(cfg)
    names = {a: n for a, n in steammod.list_games()}
    names.update(steammod.local_names())
    proton_display = protonmod.tool_display(appid) if game_type != "native" else ""
    runtime = protonmod.native_runtime(game_cmd) if game_type == "native" else None
    icon_path = steammod.find_game_icon(appid)
    icon = str(icon_path) if icon_path else ""
    name = names.get(appid, appid)
    title, body = notify_backend.launch_summary(
        appid=appid,
        name=names.get(appid, ""),
        game_type=game_type,
        wrappers=wrappers,
        custom_executable=cfg.general.custom_executable,
        proton_display=proton_display,
        runtime=runtime,
        proton_log=cfg.debug.proton_log,
    )
    notify_backend.send(title, body, icon=icon, expire_ms=5000)
    return name, icon


def _config_prefix_issues(appid: str) -> list[str]:
    """Raw-TOML read and load problems ([] when the config is fine)."""
    import tomllib

    path = cfgmod.game_file(appid)
    if path.exists():
        try:
            with path.open("rb") as f:
                tomllib.load(f)
        except (OSError, tomllib.TOMLDecodeError) as e:
            return [f"{appid}: invalid TOML ({e}); built-in defaults apply"]
    try:
        cfgmod.load(appid)
    except cfgmod.ConfigVersionError as e:
        return [f"{appid}: config needs a newer TKArcade ({e})"]
    return []


def _profile_issues(appid: str, cfg: cfgmod.GameConfig) -> list[str]:
    """Selected-profile problems: missing file or unreadable TOML."""
    sel = cfg.general.active_profile
    if not sel:
        return []
    prof_path = cfgmod.profile_file(appid, sel)
    if not prof_path.exists():
        return [f"{appid}: selected profile {sel!r} is missing; live config applies"]
    if cfgmod.toml_error(prof_path) is not None:
        return [f"{appid}: selected profile {sel!r} is unreadable; live config applies"]
    return []


def _missing_exe(appid: str, label: str, command: str) -> str | None:
    """The "not found" issue for a hook/prefix command, or None when it resolves."""
    parts = split_args(command)
    if not parts:
        return None
    first = parts[0]
    if shutil.which(first) or Path(first).is_file():
        return None
    return f"{appid}: {label} not found: {first}"


def _exe_issues(appid: str, eff: cfgmod.GameConfig) -> list[str]:
    """Hook, custom prefix and custom executable binaries that are missing."""
    issues = [
        issue
        for issue in (
            _missing_exe(appid, "pre_command", eff.pre_post.pre_command),
            _missing_exe(appid, "post_command", eff.pre_post.post_command),
            _missing_exe(appid, "custom_prefix", eff.general.custom_prefix),
        )
        if issue
    ]
    custom = eff.general.custom_executable.strip()
    if custom and not shutil.which(custom) and not Path(custom).is_file():
        issues.append(f"{appid}: custom_executable not found: {custom}")
    return issues


def _display_issue(appid: str, eff: cfgmod.GameConfig) -> str | None:
    """Invalid display mode string, or None when it is absent/parsable."""
    mode = eff.display.mode.strip()
    if mode and disp_backend.parse_mode(mode) is None:
        return f"{appid}: invalid display mode {mode!r}; use WIDTHxHEIGHT[@RATE]"
    return None


def _mangohud_config_issue(appid: str, path: str) -> str | None:
    """Missing MangoHud config file, or None when it is absent/found."""
    if path and ov_backend.mangohud_config_path(path) is None:
        return f"{appid}: MangoHud config not found: {path}"
    return None


def _tool_issues(appid: str, eff: cfgmod.GameConfig) -> list[str]:
    """Enabled wrappers whose binary (or MangoHud config) is missing."""
    issues: list[str] = []
    checks = (
        (eff.gamemode.feral_gamemode, "gamemoderun", "gamemoderun not found (Feral GameMode on)"),
        (
            eff.gamemode.cachyos_game_performance,
            "game-performance",
            "game-performance not found (CachyOS tweak on)",
        ),
        (eff.gamescope.enable, "gamescope", "gamescope not found (enabled)"),
        (eff.mangohud.enable, "mangohud", "mangohud not found (enabled)"),
    )
    for enabled, tool, note in checks:
        if enabled and not shutil.which(tool):
            issues.append(f"{appid}: {note}")
    mh_issue = _mangohud_config_issue(appid, eff.mangohud.config_file)
    if mh_issue:
        issues.append(mh_issue)
    if eff.ludusavi.enable and not lu_backend.find()[0]:
        issues.append(f"{appid}: ludusavi not found (enabled)")
    return issues


def validate_game(appid: str) -> list[str]:
    """Check one game's config and helper binaries. Returns issue strings."""
    prefix = _config_prefix_issues(appid)
    if prefix:
        return prefix
    cfg = cfgmod.load(appid)
    eff = cfgmod.load_effective(appid)  # what would actually launch
    issues = _profile_issues(appid, cfg)
    issues += _exe_issues(appid, eff)
    display_issue = _display_issue(appid, eff)
    if display_issue:
        issues.append(display_issue)
    issues += _tool_issues(appid, eff)
    return issues


def cmd_validate(appids: list[str]) -> int:
    """Print a validation report. Returns 0 when clean, else 17."""
    if not steammod.steam_roots():
        print("global: no Steam installation found")
    problems = 0
    for appid in appids:
        for issue in validate_game(appid):
            print(issue)
            problems += 1
    if problems:
        print(f"{problems} issue(s) found")
        return 17
    print("all clear")
    return 0


def parse_args(argv: list[str]) -> argparse.Namespace:
    p = argparse.ArgumentParser(
        prog="tkarcade",
        description="Minimal Steam launch wrapper. Use in Steam as: tkarcade %command%",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="exit codes:\n"
        "  0   ok: game ran (its own code), or menu/editor exited\n"
        "      without launching\n"
        "  10  AppID not resolved\n"
        "  11  empty game command\n"
        "  12  pre-launch hook failed\n"
        "  13  game executable not found\n"
        "  14  custom prefix binary not found\n"
        "  15  display needed but missing\n"
        "  16  export/import failed\n"
        "  17  validation issues found",
    )
    p.add_argument("--appid", default="", help="Steam AppID (else STEAMAPPID env)")
    p.add_argument("--dry-run", action="store_true", help="print final command, do not run")
    p.add_argument("--list", action="store_true", help="list configured/detected games and exit")
    p.add_argument(
        "--validate",
        action="store_true",
        help="check configs and helper binaries, exit 17 on issues",
    )
    p.add_argument(
        "--export", default="", metavar="FILE", help="export configs to a tar.gz and exit"
    )
    p.add_argument(
        "--import",
        dest="import_file",
        default="",
        metavar="FILE",
        help="import configs from a tar.gz and exit",
    )
    p.add_argument(
        "--edit",
        action="store_true",
        help="open the game settings dialog (needs a display); "
        "takes an optional positional AppID, otherwise shows a game picker",
    )
    p.add_argument(
        "--menu",
        action="store_true",
        help="show the pre-launch menu before starting the game "
        "(needs a display; launches directly without one); "
        "takes an optional positional AppID like --edit",
    )
    p.add_argument("--verbose", action="store_true", help="debug logging to the per-game log")
    p.add_argument("--version", action="store_true", help="print the version and exit")
    mode = p.add_mutually_exclusive_group()
    mode.add_argument("--gui", action="store_true", help="open the settings GUI and exit")
    mode.add_argument(
        "--cli",
        action="store_true",
        help="never open the GUI, even without a command (for scripts)",
    )
    p.add_argument(
        "command", nargs=argparse.REMAINDER, help="game command (after -- or %%command%%)"
    )
    return p.parse_args(argv)


def _has_display() -> bool:
    """True when a display server looks reachable for GUI work."""
    return bool(os.environ.get("DISPLAY") or os.environ.get("WAYLAND_DISPLAY"))


def _has_cli_action(args: argparse.Namespace) -> bool:
    """True when flags already determine non-GUI behavior."""
    return bool(
        args.list
        or args.validate
        or args.export
        or args.import_file
        or args.version
        or args.dry_run
        or args.edit
        or args.menu
    )


def _run_gui() -> int:
    try:
        from .gui.kirigami_app import main as gui_main
    except ImportError:
        print("tkarcade: GUI needs PySide6 installed", file=sys.stderr)
        return 15
    return gui_main()


def peel_display_appid(game_cmd: list[str], known: set[str] | None = None) -> tuple[str, list[str]]:
    """Split a lone positional AppID off an --edit/--menu command line.

    Returns (appid, remaining_cmd). A single bare token qualifies when it
    is all digits (a Steam AppID) or names a configured game (a local id
    like ``local-<slug>``, passed in ``known``); anything else stays a game
    command, so real commands are never affected.
    """
    if len(game_cmd) == 1 and (game_cmd[0].isdigit() or game_cmd[0] in (known or ())):
        return game_cmd[0], []
    return "", list(game_cmd)


# Path fragments that, when present in LD_LIBRARY_PATH entries, mark them
# as Steam-runtime pollution which breaks Qt theme plugin loading
# (Breeze falls back to Fusion). Filtered out for GUI child processes.
_STEAM_LIB_MARKERS = ("steam-runtime", "ubuntu12_32", ".local/share/Steam")


def clean_gui_env(env: dict[str, str]) -> dict[str, str]:
    """Copy env minus Steam-runtime library paths (pure, testable)."""
    env = dict(env)
    ld = env.get("LD_LIBRARY_PATH", "")
    if ld:
        kept = [p for p in ld.split(":") if p and not any(m in p for m in _STEAM_LIB_MARKERS)]
        if kept:
            env["LD_LIBRARY_PATH"] = ":".join(kept)
        else:
            env.pop("LD_LIBRARY_PATH", None)
    return env


def _editor_cmd(appid: str, for_menu: bool, can_launch: bool) -> list[str]:
    """Command line for the child settings editor (or pre-launch menu)."""
    cmd = [sys.executable, "-m", "tkarcade.gui.edit"]
    if (appid or "").strip():
        cmd += ["--appid", appid.strip()]
    else:
        cmd += ["--pick"]
    cmd += ["--can-launch" if can_launch else "--no-can-launch"]
    if for_menu:
        cmd.append("--menu")
    return cmd


def _parse_editor_output(stdout: str, appid: str) -> tuple[str, str] | None:
    """Parse the child's JSON line; None means the launch is cancelled."""
    try:
        data = json.loads(stdout.strip().splitlines()[-1])
        outcome = str(data.get("outcome", "cancelled"))
        picked = str(data.get("appid", "") or appid)
    except (ValueError, IndexError, AttributeError) as e:
        log.error("settings editor sent bad output (%s); launch cancelled", e)
        return None
    if outcome not in ("launch", "saved", "cancelled"):
        log.error("settings editor sent bad outcome %r; launch cancelled", outcome)
        return None
    return outcome, picked


def run_editor_menu(appid: str, for_menu: bool = False, can_launch: bool = True) -> tuple[str, str]:
    """Open the settings editor (or the pre-launch menu) in a child process.

    Returns (outcome, appid). Outcomes: 'launch', 'saved', 'cancelled' or
    'unavailable' (no PySide6/display, or the child could not be spawned).
    A child crash is treated as 'cancelled': never launch on unknown user
    intent. The child is `python -m tkarcade.gui.edit`, which prints the
    single JSON line read here (see that module for the protocol); it runs
    with a sanitized environment (clean_gui_env) because Steam's
    LD_LIBRARY_PATH breaks Qt theme plugin loading.
    """
    cmd = _editor_cmd(appid, for_menu, can_launch)
    try:
        proc = subprocess.run(
            cmd, env=clean_gui_env(dict(os.environ)), capture_output=True, text=True
        )
    except OSError as e:
        log.warning("settings editor subprocess failed to spawn (%s)", e)
        return "unavailable", appid
    for line in proc.stderr.strip().splitlines():
        log.debug("editor child stderr: %s", line)
    if proc.returncode == 2:
        return "unavailable", appid
    if proc.returncode != 0:
        log.error("settings editor crashed (exit %s); launch cancelled", proc.returncode)
        return "cancelled", appid
    parsed = _parse_editor_output(proc.stdout, appid)
    if parsed is None:
        return "cancelled", appid
    return parsed


def launch_local_detached(appid: str) -> None:
    """Spawn `tkarcade --appid ...` detached for a local game.

    Shared Play path for every toolkit: logs, history and the one-shot
    menu skip apply; only the Steam client handoff is missing.
    Raises OSError when the spawn itself fails.
    """
    plant_menu_skip(appid)
    runner = shutil.which("tkarcade") or sys.argv[0]
    subprocess.Popen(
        [runner, "--appid", appid],
        start_new_session=True,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )


def _cmd_version() -> int:
    from . import __version__

    print(__version__)
    return 0


def _cmd_list() -> int:
    """Print configured games, then detected-but-unconfigured ones."""
    names = dict(steammod.list_games())
    names.update(steammod.local_names())
    configured = cfgmod.list_appids()
    print("Configured:")
    for appid in configured:
        print(f"  {appid}\t{names.get(appid, '')}".rstrip())
    extra = [(a, n) for a, n in names.items() if a not in set(configured)]
    if extra:
        print("Detected (not configured):")
        for appid, name in extra:
            print(f"  {appid}\t{name}")
    return 0


def _cmd_export(dest: str) -> int:
    try:
        path = cfgmod.export_configs(dest)
    except (OSError, ValueError) as e:
        print(f"tkarcade: export failed: {e}", file=sys.stderr)
        return 16
    print(f"Exported to {path}")
    return 0


def _cmd_import(src: str) -> int:
    try:
        imported = cfgmod.import_configs(src)
    except (OSError, ValueError) as e:
        print(f"tkarcade: import failed: {e}", file=sys.stderr)
        return 16
    print(f"Imported {len(imported)} game(s): {', '.join(imported)}")
    return 0


def _run_cli_action(args: argparse.Namespace) -> int | None:
    """Non-launch subcommands. None when the launch path should continue."""
    if args.version:
        return _cmd_version()
    if args.list:
        return _cmd_list()
    if args.validate:
        appids = [args.appid] if args.appid else cfgmod.list_appids()
        return cmd_validate(appids)
    if args.export:
        return _cmd_export(args.export)
    if args.import_file:
        return _cmd_import(args.import_file)
    return None


def _strip_double_dash(command: list[str]) -> list[str]:
    """Drop the leading ``--`` Steam puts in front of %command%."""
    if command and command[0] == "--":
        return command[1:]
    return command


def _peel_lone_appid(args: argparse.Namespace, game_cmd: list[str]) -> list[str]:
    """Turn a lone `--edit/--menu` positional naming a game into the AppID."""
    if not ((args.edit or args.menu) and not args.appid):
        return game_cmd
    # --edit/--menu 588950 or local-glxgears: a lone positional naming a game
    # (Steam digits, or a configured id such as local-<slug>) is the AppID,
    # not a command. Ids are matched by existence, so a real command is never
    # mistaken for a game.
    peeled, rest = peel_display_appid(game_cmd, set(cfgmod.list_appids()))
    if peeled:
        args.appid = peeled
    return rest


def _launch_requested(args: argparse.Namespace, game_cmd: list[str]) -> bool:
    """True when the invocation asks for a CLI action or a game launch."""
    return args.cli or bool(game_cmd) or bool(args.appid) or _has_cli_action(args)


def _gui_fallback(args: argparse.Namespace, game_cmd: list[str]) -> int | None:
    """Open the settings GUI when there is nothing else to do (None: continue)."""
    if not args.gui and _launch_requested(args, game_cmd):
        return None
    # No launch to perform and no AppID given: open the settings GUI instead
    # of erroring out (bare invocation used to exit 11/10). A lone --verbose
    # still lands here; verbosity only affects per-game log files, of which a
    # bare invocation has none.
    if _has_display():
        return _run_gui()
    if args.gui:
        print("tkarcade: --gui needs a display", file=sys.stderr)
        return 15
    # Headless and bare: fall through to the classic errors below.
    return None


def _load_target(
    args: argparse.Namespace, game_cmd: list[str]
) -> tuple[int | None, str, cfgmod.GameConfig | None]:
    """Resolve the AppID, set up logging and load the effective config."""
    appid = steammod.resolve_appid(args.appid)
    if not appid and not args.edit:
        setup_logging("", args.verbose)
        log.error("cannot resolve AppID (use --appid or STEAMAPPID env). game_cmd=%r", game_cmd)
        print("tkarcade: cannot resolve AppID", file=sys.stderr)
        return 10, "", None
    setup_logging(appid, args.verbose)
    cfg = cfgmod.load_effective(appid)
    log.info("appid=%s config=%s game_cmd=%r", appid, cfgmod.game_file(appid), game_cmd)
    _log_gui_env()
    return None, appid, cfg


def _explicit_editor(
    args: argparse.Namespace, appid: str, cfg: cfgmod.GameConfig, game_cmd: list[str]
) -> tuple[int | None, str, cfgmod.GameConfig]:
    """Run the requested --edit/--menu editor. Returns (exit code, appid, cfg)."""
    outcome, appid = run_editor_menu(
        appid,
        for_menu=args.menu and not args.edit,
        can_launch=bool(game_cmd or cfg.general.custom_executable.strip()),
    )
    if outcome == "unavailable":
        if args.edit and not args.menu:
            log.error("--edit unavailable (needs PySide6 and a display)")
            return 15, appid, cfg
        log.warning("--menu unavailable (needs PySide6 and a display); launching directly")
    elif outcome == "cancelled":
        log.info("launch cancelled in editor")
        return 0, appid, cfg
    elif outcome == "saved" and args.edit and not args.menu:
        log.info("config saved in editor, launch skipped")
        return 0, appid, cfg
    # "launch", or "saved" from the pre-launch menu: (re)load the config and
    # continue into the pipeline.
    if not appid:
        log.error("cannot resolve AppID (use --appid or STEAMAPPID env)")
        print("tkarcade: cannot resolve AppID", file=sys.stderr)
        return 10, appid, cfg
    setup_logging(appid, args.verbose)
    return None, appid, cfgmod.load_effective(appid)


def _config_menu(
    appid: str, cfg: cfgmod.GameConfig, game_cmd: list[str]
) -> tuple[int | None, str, cfgmod.GameConfig]:
    """Config-triggered pre-launch menu. Returns (exit code, appid, cfg)."""
    outcome, picked = run_editor_menu(
        appid,
        for_menu=True,
        can_launch=bool(game_cmd or cfg.general.custom_executable.strip()),
    )
    if outcome == "unavailable":
        log.warning("--menu unavailable (needs PySide6 and a display); launching directly")
        return None, appid, cfg
    if outcome == "cancelled":
        log.info("launch cancelled in pre-launch menu")
        return 0, appid, cfg
    # "launch" or "saved": reload the freshly saved config and continue.
    appid = picked or appid
    return None, appid, cfgmod.load_effective(appid)


def _maybe_run_menus(
    args: argparse.Namespace, appid: str, cfg: cfgmod.GameConfig, game_cmd: list[str]
) -> tuple[int | None, str, cfgmod.GameConfig]:
    """The explicit --edit/--menu editor, then the config-triggered menu.

    --edit/--menu always skip the config-triggered menu (that is what used
    to be the `menu_shown` flag), so the check is simply "neither asked".
    """
    if args.edit or args.menu:
        return _explicit_editor(args, appid, cfg, game_cmd)
    if cfg.general.show_menu and not consume_menu_skip(appid):
        return _config_menu(appid, cfg, game_cmd)
    return None, appid, cfg


def _disarm_fresh_prefix(appid: str, cfg: cfgmod.GameConfig) -> None:
    """Wipe the broken prefix once, then disarm the one-shot toggle."""
    wiped_ok, fresh_warnings = protonmod.prepare_fresh_prefix()
    for w in fresh_warnings:
        log.warning("fresh_prefix: %s", w)
    if not wiped_ok:
        return
    cfg.proton.fresh_prefix = False
    try:
        cfgmod.save(cfg)
        log.info("fresh_prefix disarmed after wipe")
    except Exception as e:
        log.warning("could not disarm fresh_prefix: %s", e)


def _prepare_launch(appid: str, cfg: cfgmod.GameConfig) -> None:
    """One-shot prefix wipe and winetricks, before the command is built."""
    # Before ludusavi wrap: wipe the broken prefix, Steam recreates it, then
    # restore brings the saves back into it. One-shot: disarm the toggle
    # afterwards so later launches (and winetricks state) stay consistent.
    if cfg.proton.fresh_prefix:
        _disarm_fresh_prefix(appid, cfg)
    if cfg.proton.winetricks_verbs:
        for w in protonmod.run_winetricks(appid, cfg.proton.winetricks_verbs):
            log.warning("winetricks: %s", w)


def _final_command(
    appid: str, cfg: cfgmod.GameConfig, game_cmd: list[str], rc_file: str
) -> tuple[int, list[str], dict, list[str]]:
    """Build the launch argv/env. A non-zero code means "return it as-is"."""
    try:
        final_cmd, extra_env, warnings = build_final_command(cfg, game_cmd, wrap_rc_file=rc_file)
    except PrefixNotFoundError as e:
        log.error("%s", e)
        print(f"tkarcade: {e}", file=sys.stderr)
        notify_backend.send("TKArcade: cannot launch", str(e), "critical")
        write_global_log(appid, 14, game_cmd)
        _remove_wrap_rc_file(rc_file)
        return 14, [], {}, []
    return 0, final_cmd, extra_env, warnings


def _pre_hook(
    appid: str, cfg: cfgmod.GameConfig, extra_env: dict, final_cmd: list[str]
) -> int | None:
    """Run the pre-launch hook. Returns exit 12 when it fails and aborts."""
    if not cfg.pre_post.pre_command.strip():
        return None
    rc = pp_backend.run_hook(
        "pre",
        cfg.pre_post.pre_command,
        cfg.pre_post.pre_args,
        timeout=cfg.pre_post.timeout,
        run_in_shell=cfg.pre_post.run_in_shell,
        extra_env=extra_env,
    )
    if rc in (-1, 0):
        return None
    log.error("pre hook failed (rc=%s), aborting game launch", rc)
    notify_backend.send(
        "TKArcade: pre-launch hook failed",
        f"App {appid}, exit {rc}; launch aborted",
        "critical",
    )
    write_global_log(appid, 12, final_cmd)
    return 12


def _post_hook(appid: str, cfg: cfgmod.GameConfig, extra_env: dict) -> None:
    """Run the post-exit hook (never aborts, only notifies)."""
    if not cfg.pre_post.post_command.strip():
        return
    post_rc = pp_backend.run_hook(
        "post",
        cfg.pre_post.post_command,
        cfg.pre_post.post_args,
        timeout=cfg.pre_post.timeout,
        run_in_shell=cfg.pre_post.run_in_shell,
        extra_env=extra_env,
    )
    if post_rc not in (-1, 0):
        notify_backend.send("TKArcade: post-exit hook failed", f"App {appid}, exit {post_rc}")


def _ensure_proton_log_dir(appid: str, cfg: cfgmod.GameConfig) -> None:
    """Create the per-game Proton log directory when logging is on."""
    if not cfg.debug.proton_log:
        return
    try:
        proton_log_dir(appid).mkdir(parents=True, exist_ok=True)
    except Exception as e:
        log.warning("cannot create proton log dir: %s", e)


def _run_game_process(
    appid: str, cfg: cfgmod.GameConfig, final_cmd: list[str], extra_env: dict, rc_file: str
) -> tuple[bool, int]:
    """Run the game. Returns (failed to start, exit code).

    The game may run inside `ludusavi wrap`; the sh shim writes the real
    exit code to rc_file, recovered here.
    """
    env = dict(os.environ)
    env.update({k: str(v) for k, v in extra_env.items()})
    log.info("exec: %s", shlex.join(final_cmd))
    run_cwd = local_run_cwd(appid, cfg)
    if run_cwd:
        log.info("cwd: %s", run_cwd)
    try:
        proc = subprocess.run(final_cmd, env=env, cwd=run_cwd)
    except OSError as e:
        # FileNotFoundError: missing binary. PermissionError/ETXTBSY and
        # friends: present but not runnable. Same contract exit (13) either
        # way, with a global log line and a notification.
        if isinstance(e, FileNotFoundError):
            log.error("game executable not found: %r", final_cmd)
        else:
            log.error("cannot execute game %r: %s", final_cmd, e)
        notify_backend.send(
            "TKArcade: cannot start game",
            f"{shlex.join(final_cmd)[:200]} ({e})",
            "critical",
        )
        write_global_log(appid, 13, final_cmd)
        return True, 13
    game_rc = _read_wrap_rc_file(rc_file, proc.returncode) if rc_file else proc.returncode
    log.info("game exit=%s", game_rc)
    return False, game_rc


def _game_body(
    appid: str,
    cfg: cfgmod.GameConfig,
    game_cmd: list[str],
    final_cmd: list[str],
    extra_env: dict,
    rc_file: str,
) -> int:
    """pre hook -> game -> post hook, plus logging and notifications."""
    try:
        abort = _pre_hook(appid, cfg, extra_env, final_cmd)
        if abort is not None:
            return abort
        session_info = None
        if cfg.notifications.notify_on_launch:
            session_info = notify_launch(appid, cfg, game_cmd)
        _ensure_proton_log_dir(appid, cfg)
        start = time.monotonic()
        failed, game_rc = _run_game_process(appid, cfg, final_cmd, extra_env, rc_file)
        if failed:
            return game_rc
        _post_hook(appid, cfg, extra_env)
        write_global_log(appid, int(game_rc), final_cmd, time.monotonic() - start)
        if session_info is not None:
            name, icon = session_info
            notify_backend.send(
                f"Finished {name}",
                f"Played {notify_backend.format_duration(time.monotonic() - start)}",
                icon=icon,
                expire_ms=5000,
            )
        return int(game_rc)
    finally:
        _remove_wrap_rc_file(rc_file)


def _run_game(
    appid: str,
    cfg: cfgmod.GameConfig,
    game_cmd: list[str],
    final_cmd: list[str],
    extra_env: dict,
    rc_file: str,
) -> int:
    """Run the pipeline with display/audio/nightlight restore guaranteed."""
    # NB: the sessions' __enter__ already called start(); never call it again
    # (a second call used to orphan a holder process).
    with (
        disp_backend.DisplaySession(
            cfg.display.provider, cfg.display.output, cfg.display.mode, cfg.display.dip_seconds
        ),
        au_backend.AudioSession(cfg.audio.sink),
        nl_backend.NightlightSession(
            cfg.nightlight.provider if cfg.nightlight.disable_during_game else "off"
        ),
    ):
        return _game_body(appid, cfg, game_cmd, final_cmd, extra_env, rc_file)


def _launch_pipeline(
    appid: str, cfg: cfgmod.GameConfig, game_cmd: list[str], args: argparse.Namespace
) -> int:
    """Build the final command, honour --dry-run, then run the pipeline."""
    # Sentinel file so the real game exit code survives `ludusavi wrap`
    # (which returns 0 even when the game crashes). Empty = wrap off.
    wrap_active = bool(cfg.ludusavi.enable and (cfg.ludusavi.restore or cfg.ludusavi.backup))
    rc_file = _new_wrap_rc_file(appid) if wrap_active else ""
    rc, final_cmd, extra_env, warnings = _final_command(appid, cfg, game_cmd, rc_file)
    if rc:
        return rc
    for w in warnings:
        log.warning("%s", w)
    if args.dry_run:
        print(f"AppID: {appid}")
        print(f"Final: {shlex.join(final_cmd) if final_cmd else '(empty)'}")
        if extra_env:
            print(f"Env: {extra_env}")
        for w in warnings:
            print(f"warn: {w}")
        _remove_wrap_rc_file(rc_file)
        return 0
    if not final_cmd:
        log.error("empty game command and no custom_executable")
        _remove_wrap_rc_file(rc_file)
        return 11
    return _run_game(appid, cfg, game_cmd, final_cmd, extra_env, rc_file)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(sys.argv[1:] if argv is None else argv)
    action = _run_cli_action(args)
    if action is not None:
        return action

    game_cmd = _peel_lone_appid(args, _strip_double_dash(list(args.command)))

    gui_rc = _gui_fallback(args, game_cmd)
    if gui_rc is not None:
        return gui_rc

    rc, appid, cfg = _load_target(args, game_cmd)
    if rc is not None:
        return rc
    rc, appid, cfg = _maybe_run_menus(args, appid, cfg, game_cmd)
    if rc is not None:
        return rc

    if not game_cmd and not cfg.general.custom_executable.strip():
        # e.g. bare `--edit <appid>` in a terminal: the editor may request
        # a launch, but there is no game command to run. Skipping here
        # beats executing a bare prefix stack (exit 1 from mangohud & co).
        log.info("no game command to run; launch skipped")
        return 0

    _prepare_launch(appid, cfg)
    return _launch_pipeline(appid, cfg, game_cmd, args)


if __name__ == "__main__":
    raise SystemExit(main())
