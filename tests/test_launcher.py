"""Launcher CLI end-to-end (subprocess): exit codes, sentinel, --edit guard."""

import os
import subprocess
import sys
from pathlib import Path

from tksteamlaunch import config as C

SRC = str(Path(__file__).resolve().parent.parent / "src")


def _run(env, *args):
    cmd = [sys.executable, "-m", "tksteamlaunch.launcher", *args]
    return subprocess.run(cmd, capture_output=True, text=True, env=env, timeout=60)


def _env(xdg_env):
    env = {
        **os.environ,
        "XDG_CONFIG_HOME": str(xdg_env["config"]),
        "XDG_STATE_HOME": str(xdg_env["state"]),
    }
    env["PYTHONPATH"] = SRC + os.pathsep + env.get("PYTHONPATH", "")
    return env


def _save(appid, **kw):
    cfg = C.GameConfig()
    cfg.general.appid = appid
    for section, values in kw.items():
        target = getattr(cfg, section)
        for key, value in values.items():
            setattr(target, key, value)
    return C.save(cfg)


def test_dry_run(xdg_env):
    r = _run(_env(xdg_env), "--appid", "1", "--dry-run", "--", "/bin/echo", "hi")
    assert r.returncode == 0
    assert "AppID: 1" in r.stdout and "/bin/echo hi" in r.stdout


def test_no_appid(xdg_env):
    r = _run(_env(xdg_env), "--", "/bin/echo", "hi")
    assert r.returncode == 10


def test_run_and_pre_hook_abort(xdg_env):
    _save("2", pre_post={"pre_command": "/bin/echo", "pre_args": ["ok"]})
    assert _run(_env(xdg_env), "--appid", "2", "/bin/echo", "hi").returncode == 0
    _save("2", pre_post={"pre_command": "/bin/false"})
    assert _run(_env(xdg_env), "--appid", "2", "/bin/echo", "hi").returncode == 12


def test_missing_prefix_exit_14(xdg_env):
    _save("3", general={"custom_prefix": "nope-missing-bin"})
    assert _run(_env(xdg_env), "--appid", "3", "/bin/echo", "hi").returncode == 14


def test_wrap_sentinel_recovers_exit_code(xdg_env, fake_bin):
    # fake_bin prepends to this process's PATH, inherited by the subprocess.
    fake_bin(
        "ludusavi",
        "#!/bin/sh\nwhile [ \"$1\" != \"--\" ] && [ $# -gt 0 ]; do shift; done\n"
        '[ "$1" = "--" ] && shift\n"$@"\nexit 0\n',
    )
    _save("4", ludusavi={"enable": True, "restore": True, "backup": False})
    env = _env(xdg_env)
    assert _run(env, "--appid", "4", "/bin/false").returncode == 1
    assert _run(env, "--appid", "4", "/bin/true").returncode == 0


def test_edit_without_display(xdg_env, monkeypatch):
    monkeypatch.delenv("DISPLAY", raising=False)
    monkeypatch.delenv("WAYLAND_DISPLAY", raising=False)
    r = _run(_env(xdg_env), "--appid", "5", "--edit", "--", "/bin/echo", "hi")
    assert r.returncode == 15


def test_list(xdg_env, monkeypatch, tmp_path):
    root = tmp_path / "steamapps"
    root.mkdir()
    (root / "appmanifest_7.acf").write_text(
        '"AppState"\n{\n"appid" "7"\n"name" "Some Game"\n}\n'
    )
    monkeypatch.setenv("STEAM_ROOT", str(tmp_path))
    _save("7")
    env = _env(xdg_env)
    env["STEAM_ROOT"] = str(tmp_path)
    r = _run(env, "--list")
    assert r.returncode == 0
    assert "Configured:" in r.stdout and "7" in r.stdout


def test_per_game_log_rotates(xdg_env):
    import logging

    from tksteamlaunch import xdg
    from tksteamlaunch.launcher import setup_logging

    logdir = xdg.games_log_dir()
    logdir.mkdir(parents=True, exist_ok=True)
    (logdir / "8.log").write_bytes(b"x" * 1_100_000)
    setup_logging("8")
    # WARNING: pytest runs the root logger at WARNING, INFO would be filtered.
    logging.getLogger("tksteamlaunch.test").warning("trigger rollover")
    assert (logdir / "8.log.1").exists()
