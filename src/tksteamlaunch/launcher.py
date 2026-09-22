"""tksteamlaunch CLI: Steam -> tksteamlaunch %command% -> game.

Pipeline:
  resolve AppID -> load TOML -> nightlight disable -> pre hook
  -> build prefix (exe swap + mangohud + cachy/gamemode + gamescope,
     ludusavi wrap outermost) -> run game -> post hook
  -> nightlight restore -> log
"""
from __future__ import annotations

import argparse
import logging
import os
import shlex
import subprocess
import sys
from pathlib import Path

from . import config as cfgmod
from . import steam as steammod
from . import xdg
from .backends import gamemode as gm_backend
from .backends import ludusavi as lu_backend
from .backends import nightlight as nl_backend
from .backends import overlay as ov_backend
from .backends import prepost as pp_backend

log = logging.getLogger("tksteamlaunch")


def setup_logging(verbose: bool = False) -> Path:
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format="%(asctime)s %(name)s %(levelname)s: %(message)s",
    )
    try:
        d = xdg.app_state_dir()
        d.mkdir(parents=True, exist_ok=True)
        fh = logging.FileHandler(d / "launcher.log", encoding="utf-8")
        fh.setLevel(level)
        fh.setFormatter(logging.Formatter("%(asctime)s %(name)s %(levelname)s: %(message)s"))
        logging.getLogger().addHandler(fh)
        return d / "launcher.log"
    except Exception:  # noqa: BLE001
        return Path("launcher.log")


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


def build_final_command(cfg: cfgmod.GameConfig, game_cmd: list[str]) -> tuple[list[str], dict, list[str]]:
    warnings: list[str] = []
    custom = cfg.general.custom_executable.strip()
    cmd = swap_proton_executable(list(game_cmd), custom)
    if custom and game_cmd and custom not in cmd:
        warnings.append("custom_executable set but no 'run'/'--' marker found; keeping original command")

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
    cmd, w = lu_backend.wrap_command(
        cmd,
        name_override=cfg.ludusavi.name_override,
        enabled=cfg.ludusavi.enable,
        restore=cfg.ludusavi.restore,
        backup=cfg.ludusavi.backup,
        use_gui=cfg.ludusavi.use_gui,
    )
    warnings += w

    env = dict(cfg.env.vars)
    return cmd, env, warnings


def parse_args(argv: list[str]) -> argparse.Namespace:
    p = argparse.ArgumentParser(
        prog="tksteamlaunch",
        description="Minimal Steam launch wrapper. Use in Steam as: tksteamlaunch %command%",
    )
    p.add_argument("--appid", default="", help="Steam AppID (else STEAMAPPID env)")
    p.add_argument("--dry-run", action="store_true", help="print final command, do not run")
    p.add_argument("--verbose", action="store_true")
    p.add_argument("--version", action="store_true")
    p.add_argument("command", nargs=argparse.REMAINDER, help="game command (after -- or %%command%%)")
    return p.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(sys.argv[1:] if argv is None else argv)
    if args.version:
        from . import __version__

        print(__version__)
        return 0
    setup_logging(args.verbose)

    game_cmd = list(args.command)
    if game_cmd and game_cmd[0] == "--":
        game_cmd = game_cmd[1:]

    appid = steammod.resolve_appid(args.appid)
    if not appid:
        log.error("cannot resolve AppID (use --appid or STEAMAPPID env). game_cmd=%r", game_cmd)
        print("tksteamlaunch: cannot resolve AppID", file=sys.stderr)
        return 10

    cfg = cfgmod.load(appid)
    log.info("appid=%s config=%s game_cmd=%r", appid, cfgmod.game_file(appid), game_cmd)

    final_cmd, extra_env, warnings = build_final_command(cfg, game_cmd)
    for w in warnings:
        log.warning("%s", w)

    if args.dry_run:
        print(f"AppID: {appid}")
        print(f"Final: {shlex.join(final_cmd) if final_cmd else '(empty)'}")
        if extra_env:
            print(f"Env: {extra_env}")
        for w in warnings:
            print(f"warn: {w}")
        return 0

    if not final_cmd:
        log.error("empty game command and no custom_executable")
        return 11

    # --- pipeline with guaranteed nightlight restore ---
    nl_session = nl_backend.NightlightSession(
        cfg.nightlight.provider if cfg.nightlight.disable_during_game else "off"
    )
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
                return 12

        # run game (possibly inside `ludusavi wrap`; verified: wrap returns 0
        # even when the wrapped command fails, so the logged code may mask
        # game crashes while ludusavi is enabled)
        env = dict(os.environ)
        env.update({k: str(v) for k, v in extra_env.items()})
        log.info("exec: %s", shlex.join(final_cmd))
        try:
            proc = subprocess.run(final_cmd, env=env)
            game_rc = proc.returncode
        except FileNotFoundError:
            log.error("game executable not found: %r", final_cmd)
            return 13
        log.info("game exit=%s", game_rc)

        # post hook (never aborts, only logs)
        if cfg.pre_post.post_command.strip():
            pp_backend.run_hook(
                "post",
                cfg.pre_post.post_command,
                cfg.pre_post.post_args,
                timeout=cfg.pre_post.timeout,
                run_in_shell=cfg.pre_post.run_in_shell,
                extra_env=extra_env,
            )

        return int(game_rc)
    finally:
        try:
            nl_session.stop()
        except Exception as e:  # noqa: BLE001
            log.error("nightlight restore failed: %s", e)


if __name__ == "__main__":
    raise SystemExit(main())
