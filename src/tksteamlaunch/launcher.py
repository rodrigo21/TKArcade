"""tksteamlaunch CLI: Steam -> tksteamlaunch %command% -> game.

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
from .backends import gamemode as gm_backend
from .backends import ludusavi as lu_backend
from .backends import nightlight as nl_backend
from .backends import notify as notify_backend
from .backends import overlay as ov_backend
from .backends import prepost as pp_backend
from .backends import split_args
from .config import GameType

log = logging.getLogger("tksteamlaunch")


class PrefixNotFoundError(ValueError):
    """Raised when custom_prefix names a binary missing from PATH."""


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
        fh = logging.handlers.RotatingFileHandler(
            d / f"{appid}.log",
            maxBytes=1_000_000,
            backupCount=3,
            encoding="utf-8",
        )
        fh.setLevel(level)
        fh.setFormatter(logging.Formatter("%(asctime)s %(name)s %(levelname)s: %(message)s"))
        logging.getLogger().addHandler(fh)
        return d / f"{appid}.log"
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


def build_final_command(
    cfg: cfgmod.GameConfig,
    game_cmd: list[str],
    wrap_rc_file: str = "",
) -> tuple[list[str], dict, list[str]]:
    warnings: list[str] = []
    custom = cfg.general.custom_executable.strip()
    game_type = detect_game_type(game_cmd, cfg.general.game_type)
    if game_type == "native":
        cmd = swap_native_executable(list(game_cmd), custom)
    else:
        cmd = swap_proton_executable(list(game_cmd), custom)
        if custom and game_cmd and custom not in cmd:
            warnings.append(
                "custom_executable set but no 'run'/'--' marker found; keeping original command"
            )

    # innermost: custom prefix wraps the executable directly
    # (e.g. zink-run), inside mangohud/gamemode/gamescope/wrap.
    # Unlike the other wrappers this one cannot be skipped: abort loudly.
    prefix = cfg.general.custom_prefix.strip()
    if prefix:
        parts = split_args(prefix)
        if parts and not shutil.which(parts[0]):
            raise PrefixNotFoundError(f"custom_prefix binary not found in PATH: {parts[0]!r}")
        cmd = parts + cmd

    # inner -> outer: mangohud, gamemode/cachy, gamescope outermost
    cmd, w = ov_backend.apply_mangohud(cmd, cfg.mangohud.enable, cfg.mangohud.args)
    warnings += w
    cmd, w = gm_backend.prefix(
        cmd, cfg.gamemode.feral_gamemode, cfg.gamemode.cachyos_game_performance
    )
    warnings += w
    cmd, w = ov_backend.apply_gamescope(cmd, cfg.gamescope.enable, cfg.gamescope.args)
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

    env = dict(cfg.env.vars)
    mh_env, w = ov_backend.mangohud_env(cfg.mangohud.config_file)
    warnings += w
    env.update(mh_env)
    return cmd, env, warnings


def _new_wrap_rc_file(appid: str) -> str:
    """Reserve a sentinel path where the wrap shim writes the game exit code."""
    d = xdg.app_state_dir()
    d.mkdir(parents=True, exist_ok=True)
    fd, path = tempfile.mkstemp(prefix=f"tksteamlaunch-{appid}-", suffix=".rc", dir=str(d))
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


def notify_launch(appid: str, cfg: cfgmod.GameConfig, game_cmd: list[str]) -> tuple[str, str]:
    """Send the transient game-start summary. Returns (name, icon) for reuse."""
    game_type = detect_game_type(game_cmd, cfg.general.game_type)
    wrappers = []
    if cfg.gamemode.feral_gamemode:
        wrappers.append("GameMode")
    if cfg.gamemode.cachyos_game_performance:
        wrappers.append("CachyOS")
    if cfg.gamescope.enable:
        wrappers.append("Gamescope")
    if cfg.mangohud.enable:
        wrappers.append("MangoHud")
    if cfg.ludusavi.enable and (cfg.ludusavi.restore or cfg.ludusavi.backup):
        wrappers.append("Ludusavi")
    if cfg.nightlight.disable_during_game:
        wrappers.append("Night Light")
    names = {a: n for a, n in steammod.list_games()}
    proton_version = protonmod.proton_version_for(appid) if game_type != "native" else None
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
        proton_version=proton_version,
        runtime=runtime,
    )
    notify_backend.send(title, body, icon=icon, expire_ms=5000)
    return name, icon


def validate_game(appid: str) -> list[str]:
    """Check one game's config and helper binaries. Returns issue strings."""
    import tomllib

    issues: list[str] = []
    path = cfgmod.game_file(appid)
    if path.exists():
        try:
            with path.open("rb") as f:
                tomllib.load(f)
        except (OSError, tomllib.TOMLDecodeError) as e:
            return [f"{appid}: invalid TOML ({e}); built-in defaults apply"]
    cfg = cfgmod.load(appid)

    def check_exe(label: str, command: str) -> None:
        parts = split_args(command)
        if not parts:
            return
        first = parts[0]
        if not shutil.which(first) and not Path(first).is_file():
            issues.append(f"{appid}: {label} not found: {first}")

    check_exe("pre_command", cfg.pre_post.pre_command)
    check_exe("post_command", cfg.pre_post.post_command)
    check_exe("custom_prefix", cfg.general.custom_prefix)
    if cfg.gamemode.feral_gamemode and not shutil.which("gamemoderun"):
        issues.append(f"{appid}: gamemoderun not found (Feral GameMode on)")
    if cfg.gamemode.cachyos_game_performance and not shutil.which("game-performance"):
        issues.append(f"{appid}: game-performance not found (CachyOS tweak on)")
    if cfg.gamescope.enable and not shutil.which("gamescope"):
        issues.append(f"{appid}: gamescope not found (enabled)")
    if cfg.mangohud.enable and not shutil.which("mangohud"):
        issues.append(f"{appid}: mangohud not found (enabled)")
    if (
        cfg.mangohud.config_file
        and ov_backend.mangohud_config_path(cfg.mangohud.config_file) is None
    ):
        issues.append(f"{appid}: MangoHud config not found: {cfg.mangohud.config_file}")
    if cfg.ludusavi.enable and not lu_backend.find()[0]:
        issues.append(f"{appid}: ludusavi not found (enabled)")
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
        prog="tksteamlaunch",
        description="Minimal Steam launch wrapper. Use in Steam as: tksteamlaunch %command%",
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
        "(needs a display; launches directly without one)",
    )
    p.add_argument("--verbose", action="store_true")
    p.add_argument("--version", action="store_true")
    p.add_argument(
        "command", nargs=argparse.REMAINDER, help="game command (after -- or %%command%%)"
    )
    return p.parse_args(argv)


def peel_edit_appid(game_cmd: list[str]) -> tuple[str, list[str]]:
    """Split a lone all-digit positional off an --edit command line.

    Returns (appid, remaining_cmd). Only a single bare token qualifies,
    so real game commands are never affected.
    """
    if len(game_cmd) == 1 and game_cmd[0].isdigit():
        return game_cmd[0], []
    return "", list(game_cmd)


def pick_game_appid() -> str:
    """Show a game picker dialog. Returns the AppID or '' when cancelled.

    Callers must ensure PySide6 and a display exist (use run_editor,
    which reports 'unavailable' otherwise).
    """
    from PySide6.QtWidgets import QApplication, QInputDialog

    app = QApplication.instance() or QApplication(sys.argv)  # noqa: F841
    names = {a: n for a, n in steammod.list_games()}
    configured = set(cfgmod.list_appids())
    entries = [(a, names.get(a, a)) for a in configured]
    entries += [(a, n) for a, n in names.items() if a not in configured]
    if not entries:
        return ""
    labels = [f"{n} [{a}]" for a, n in entries]
    choice, ok = QInputDialog.getItem(None, "Edit Game", "Game:", labels, 0, False)
    if not ok or not choice:
        return ""
    for appid, _name in entries:
        if choice.endswith(f"[{appid}]"):
            return appid
    return ""


def _ensure_qapp(tool: str) -> bool:
    """Lazy Qt import + display check. False means 'unavailable'."""
    try:
        from PySide6.QtWidgets import QApplication  # noqa: F401
    except ImportError:
        print(f"tksteamlaunch: {tool} needs PySide6 installed", file=sys.stderr)
        return False
    if not os.environ.get("DISPLAY") and not os.environ.get("WAYLAND_DISPLAY"):
        print(f"tksteamlaunch: {tool} needs a display", file=sys.stderr)
        return False
    return True


def run_editor_menu(appid: str, for_menu: bool = False) -> tuple[str, str]:
    """Open the game settings dialog. Returns (outcome, appid).

    An empty appid opens a game picker first. Outcomes: 'launch',
    'saved', 'cancelled' or 'unavailable'. Qt is imported lazily so
    the plain CLI stays stdlib-only.
    """
    tool = "--menu" if for_menu else "--edit"
    if not _ensure_qapp(tool):
        return "unavailable", appid
    from PySide6.QtWidgets import QApplication, QDialog

    from .gui.game_dialog import GameDialog

    # Reference kept alive: the dialog needs a living QApplication during exec.
    app = QApplication.instance() or QApplication(sys.argv)  # noqa: F841
    if not appid:
        appid = pick_game_appid()
        if not appid:
            return "cancelled", ""
    names = {a: n for a, n in steammod.list_games()}
    dlg = GameDialog(None, appid, names.get(appid, ""), launch_mode=True)
    result = dlg.exec()
    if int(result) != int(QDialog.DialogCode.Accepted):
        return "cancelled", appid
    return ("launch" if dlg.launch_requested else "saved"), appid


def run_editor(appid: str) -> str:
    """Open the game settings dialog. Returns 'launch', 'saved' or 'cancelled'.

    An empty appid opens a game picker first ('cancelled' when dismissed).

    'unavailable' when PySide6 or a display is missing (exit 15). Qt is
    imported lazily so the plain CLI stays stdlib-only.
    """
    outcome, _appid = run_editor_menu(appid)
    return outcome


def main(argv: list[str] | None = None) -> int:
    args = parse_args(sys.argv[1:] if argv is None else argv)
    if args.version:
        from . import __version__

        print(__version__)
        return 0
    if args.list:
        names = dict(steammod.list_games())
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
    if args.validate:
        appids = [args.appid] if args.appid else cfgmod.list_appids()
        return cmd_validate(appids)
    if args.export:
        try:
            path = cfgmod.export_configs(args.export)
        except (OSError, ValueError) as e:
            print(f"tksteamlaunch: export failed: {e}", file=sys.stderr)
            return 16
        print(f"Exported to {path}")
        return 0
    if args.import_file:
        try:
            imported = cfgmod.import_configs(args.import_file)
        except (OSError, ValueError) as e:
            print(f"tksteamlaunch: import failed: {e}", file=sys.stderr)
            return 16
        print(f"Imported {len(imported)} game(s): {', '.join(imported)}")
        return 0

    game_cmd = list(args.command)
    if game_cmd and game_cmd[0] == "--":
        game_cmd = game_cmd[1:]

    if args.edit and not args.appid:
        # --edit 588950: a lone all-digit token is the AppID, not a command.
        peeled, game_cmd = peel_edit_appid(game_cmd)
        if peeled:
            args.appid = peeled

    appid = steammod.resolve_appid(args.appid)
    if not appid and not args.edit:
        setup_logging("", args.verbose)
        log.error("cannot resolve AppID (use --appid or STEAMAPPID env). game_cmd=%r", game_cmd)
        print("tksteamlaunch: cannot resolve AppID", file=sys.stderr)
        return 10
    setup_logging(appid, args.verbose)

    if args.edit or args.menu:
        outcome, appid = run_editor_menu(appid, for_menu=args.menu and not args.edit)
        if outcome == "unavailable":
            if args.edit and not args.menu:
                log.error("--edit unavailable (needs PySide6 and a display)")
                return 15
            log.warning("--menu unavailable (needs PySide6 and a display); launching directly")
        elif outcome == "cancelled":
            log.info("launch cancelled in editor")
            return 0
        elif outcome == "saved" and args.edit and not args.menu:
            log.info("config saved in editor, launch skipped")
            return 0
        # "launch", or "saved" from the pre-launch menu: (re)load config below
        # and continue into the pipeline.
        if not appid:
            log.error("cannot resolve AppID (use --appid or STEAMAPPID env)")
            print("tksteamlaunch: cannot resolve AppID", file=sys.stderr)
            return 10
        setup_logging(appid, args.verbose)

    cfg = cfgmod.load(appid)
    log.info("appid=%s config=%s game_cmd=%r", appid, cfgmod.game_file(appid), game_cmd)

    if (args.menu or cfg.general.show_menu) and not args.edit:
        outcome, picked = run_editor_menu(appid, for_menu=True)
        if outcome == "unavailable":
            log.warning("--menu unavailable (needs PySide6 and a display); launching directly")
        elif outcome == "cancelled":
            log.info("launch cancelled in pre-launch menu")
            return 0
        else:
            # "launch" or "saved": reload the freshly saved config and continue.
            appid = picked or appid
            cfg = cfgmod.load(appid)

    # Sentinel file so the real game exit code survives `ludusavi wrap`
    # (which returns 0 even when the game crashes). Empty = wrap off.
    wrap_active = bool(cfg.ludusavi.enable and (cfg.ludusavi.restore or cfg.ludusavi.backup))
    rc_file = _new_wrap_rc_file(appid) if wrap_active else ""

    try:
        final_cmd, extra_env, warnings = build_final_command(cfg, game_cmd, wrap_rc_file=rc_file)
    except PrefixNotFoundError as e:
        log.error("%s", e)
        print(f"tksteamlaunch: {e}", file=sys.stderr)
        notify_backend.send("TKSteamLaunch: cannot launch", str(e), "critical")
        write_global_log(appid, 14, game_cmd)
        _remove_wrap_rc_file(rc_file)
        return 14
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

    # --- pipeline with guaranteed nightlight restore ---
    with nl_backend.NightlightSession(
        cfg.nightlight.provider if cfg.nightlight.disable_during_game else "off"
    ) as nl_session:
        if cfg.nightlight.disable_during_game:
            for w in nl_session.start():
                log.warning("nightlight: %s", w)
        try:
            # pre hook (abort game on failure, unless skipped)
            if cfg.pre_post.pre_command.strip():
                rc = pp_backend.run_hook(
                    "pre",
                    cfg.pre_post.pre_command,
                    cfg.pre_post.pre_args,
                    timeout=cfg.pre_post.timeout,
                    run_in_shell=cfg.pre_post.run_in_shell,
                    extra_env=extra_env,
                )
                if rc not in (-1, 0):
                    log.error("pre hook failed (rc=%s), aborting game launch", rc)
                    notify_backend.send(
                        "TKSteamLaunch: pre-launch hook failed",
                        f"App {appid}, exit {rc}; launch aborted",
                        "critical",
                    )
                    write_global_log(appid, 12, final_cmd)
                    return 12

            # run game (possibly inside `ludusavi wrap`; the sh shim writes the
            # real game exit code to rc_file, recovered below)
            session_info: tuple[str, str] | None = None
            if cfg.notifications.notify_on_launch:
                session_info = notify_launch(appid, cfg, game_cmd)
            env = dict(os.environ)
            env.update({k: str(v) for k, v in extra_env.items()})
            log.info("exec: %s", shlex.join(final_cmd))
            start = time.monotonic()
            try:
                proc = subprocess.run(final_cmd, env=env)
                game_rc = proc.returncode
                if rc_file:
                    game_rc = _read_wrap_rc_file(rc_file, game_rc)
            except FileNotFoundError:
                log.error("game executable not found: %r", final_cmd)
                notify_backend.send(
                    "TKSteamLaunch: game executable not found",
                    shlex.join(final_cmd)[:200],
                    "critical",
                )
                write_global_log(appid, 13, final_cmd)
                return 13
            log.info("game exit=%s", game_rc)

            # post hook (never aborts, only logs)
            if cfg.pre_post.post_command.strip():
                post_rc = pp_backend.run_hook(
                    "post",
                    cfg.pre_post.post_command,
                    cfg.pre_post.post_args,
                    timeout=cfg.pre_post.timeout,
                    run_in_shell=cfg.pre_post.run_in_shell,
                    extra_env=extra_env,
                )
                if post_rc not in (-1, 0):
                    notify_backend.send(
                        "TKSteamLaunch: post-exit hook failed",
                        f"App {appid}, exit {post_rc}",
                    )

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


if __name__ == "__main__":
    raise SystemExit(main())
