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
        '#!/bin/sh\nwhile [ "$1" != "--" ] && [ $# -gt 0 ]; do shift; done\n'
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
    (root / "appmanifest_7.acf").write_text('"AppState"\n{\n"appid" "7"\n"name" "Some Game"\n}\n')
    monkeypatch.setenv("STEAM_ROOT", str(tmp_path))
    _save("7")
    env = _env(xdg_env)
    env["STEAM_ROOT"] = str(tmp_path)
    r = _run(env, "--list")
    assert r.returncode == 0
    assert "Configured:" in r.stdout and "7" in r.stdout


def test_export_import_cli(xdg_env, tmp_path):
    _save("8")
    env = _env(xdg_env)
    dest = tmp_path / "b.tar.gz"
    r = _run(env, "--export", str(dest))
    assert r.returncode == 0 and dest.exists()
    r = _run(env, "--import", str(dest))
    assert r.returncode == 0 and "8" in r.stdout
    r = _run(env, "--import", str(tmp_path / "missing.tar.gz"))
    assert r.returncode == 16


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


def test_launch_notification_toggle(xdg_env, fake_bin, monkeypatch, tmp_path):
    log = tmp_path / "notify.log"
    fake_bin("notify-send", f'#!/bin/sh\necho "$@" >> "{log}"\n')
    monkeypatch.setenv("DISPLAY", ":0")
    _save("9", notifications={"notify_on_launch": True})
    env = _env(xdg_env)  # inherits fake PATH + DISPLAY
    assert _run(env, "--appid", "9", "/bin/true").returncode == 0
    assert "TKSteamLaunch" in log.read_text()
    log.unlink()
    _save("9", notifications={"notify_on_launch": False})
    assert _run(env, "--appid", "9", "/bin/true").returncode == 0
    assert not log.exists()


def test_session_end_notification(xdg_env, fake_bin, monkeypatch, tmp_path):
    log = tmp_path / "notify.log"
    fake_bin("notify-send", f'#!/bin/sh\necho "$@" >> "{log}"\n')
    monkeypatch.setenv("DISPLAY", ":0")
    _save("10", notifications={"notify_on_launch": True})
    env = _env(xdg_env)
    assert _run(env, "--appid", "10", "/bin/sleep", "0").returncode == 0
    out = log.read_text()
    assert "Finished 10" in out and "Played" in out


def test_validate_reports_issues(xdg_env, monkeypatch, tmp_path):
    from tksteamlaunch import launcher as L

    monkeypatch.setenv("PATH", str(tmp_path))
    cfg = C.GameConfig()
    cfg.general.appid = "30"
    cfg.general.custom_prefix = "nope-bin"
    cfg.gamemode.feral_gamemode = True
    C.save(cfg)
    issues = L.validate_game("30")
    assert any("nope-bin" in i for i in issues)
    assert any("gamemoderun" in i for i in issues)
    assert L.cmd_validate(["30"]) == 17
    C.game_file("30").write_text("[general\nbroken", encoding="utf-8")
    assert any("invalid TOML" in i for i in L.validate_game("30"))


def test_validate_cli_exit_code(xdg_env, monkeypatch, tmp_path):
    _save("32", gamemode={"feral_gamemode": True})
    monkeypatch.setenv("PATH", str(tmp_path))  # hide all helper binaries
    assert _run(_env(xdg_env), "--validate", "--appid", "32").returncode == 17


def test_validate_clean(xdg_env):
    from tksteamlaunch import launcher as L

    cfg = C.GameConfig()
    cfg.general.appid = "31"
    C.save(cfg)
    assert L.cmd_validate(["31"]) == 0


def test_global_log_carries_duration(xdg_env):
    from tksteamlaunch import xdg

    _save("11")
    env = _env(xdg_env)
    assert _run(env, "--appid", "11", "/bin/true").returncode == 0
    line = (xdg.app_state_dir() / "launcher.log").read_text()
    assert "appid=11" in line and " dur=" in line


def test_peel_edit_appid():
    from tksteamlaunch.launcher import peel_edit_appid

    assert peel_edit_appid(["588950"]) == ("588950", [])
    assert peel_edit_appid(["/bin/echo", "hi"]) == ("", ["/bin/echo", "hi"])
    assert peel_edit_appid([]) == ("", [])
    assert peel_edit_appid(["12", "34"]) == ("", ["12", "34"])


def test_menu_without_display_launches_directly(xdg_env, monkeypatch):
    _save("6", general={"show_menu": True})
    monkeypatch.delenv("DISPLAY", raising=False)
    monkeypatch.delenv("WAYLAND_DISPLAY", raising=False)
    r = _run(_env(xdg_env), "--appid", "6", "--menu", "--", "/bin/echo", "hi")
    assert r.returncode == 0
    r = _run(_env(xdg_env), "--appid", "6", "--", "/bin/echo", "hi")
    assert r.returncode == 0
    log = xdg_env["state"] / "tksteamlaunch" / "games" / "6.log"
    assert "launching directly" in log.read_text()


def test_edit_positional_appid_without_display(xdg_env, monkeypatch):
    monkeypatch.delenv("DISPLAY", raising=False)
    monkeypatch.delenv("WAYLAND_DISPLAY", raising=False)
    r = _run(_env(xdg_env), "--edit", "7")
    assert r.returncode == 15


def test_empty_command_skipped(xdg_env):
    _save("8", mangohud={"enable": True})
    r = _run(_env(xdg_env), "--appid", "8")
    assert r.returncode == 0
    log = xdg_env["state"] / "tksteamlaunch" / "games" / "8.log"
    assert "no game command to run" in log.read_text()


def test_menu_flag_shows_editor_once_without_display(xdg_env, monkeypatch):
    _save("9", general={})
    monkeypatch.delenv("DISPLAY", raising=False)
    monkeypatch.delenv("WAYLAND_DISPLAY", raising=False)
    r = _run(_env(xdg_env), "--appid", "9", "--menu", "--", "/bin/echo", "hi")
    assert r.returncode == 0
    log = xdg_env["state"] / "tksteamlaunch" / "games" / "9.log"
    assert log.read_text().count("launching directly") == 1


def test_clean_gui_env():
    from tksteamlaunch.launcher import clean_gui_env

    env = {
        "LD_LIBRARY_PATH": "/opt/intel/lib:/home/u/.local/share/Steam/ubuntu12_32/steam-runtime/pinned_libs_64:/usr/lib",
        "DISPLAY": ":0",
    }
    out = clean_gui_env(env)
    assert out["LD_LIBRARY_PATH"] == "/opt/intel/lib:/usr/lib"
    assert out["DISPLAY"] == ":0"
    assert env["LD_LIBRARY_PATH"].startswith("/opt/intel")  # input untouched
    assert clean_gui_env({}) == {}
    only_steam = {"LD_LIBRARY_PATH": "/a/steam-runtime/b"}
    assert "LD_LIBRARY_PATH" not in clean_gui_env(only_steam)


def test_edit_child_headless(xdg_env, monkeypatch):
    monkeypatch.delenv("DISPLAY", raising=False)
    monkeypatch.delenv("WAYLAND_DISPLAY", raising=False)
    r = _run(_env(xdg_env), "-m", "tksteamlaunch.gui.edit", "--appid", "1")
    assert r.returncode == 2


def test_editor_menu_parsing(monkeypatch):
    import subprocess as sp

    from tksteamlaunch import launcher as L

    seen = {}

    def fake_run(cmd, **kw):
        seen["cmd"] = cmd
        seen["env"] = kw.get("env", {})

        class P:
            returncode = 0
            stdout = '{"outcome": "launch", "appid": "42"}\n'
            stderr = ""

        return P()

    monkeypatch.setattr(sp, "run", fake_run)
    assert L.run_editor_menu("42") == ("launch", "42")
    assert "-m" in seen["cmd"] and "tksteamlaunch.gui.edit" in seen["cmd"]
    assert "LD_LIBRARY_PATH" not in seen["env"] or "steam-runtime" not in seen["env"].get(
        "LD_LIBRARY_PATH", ""
    )


def test_editor_menu_crash_means_cancelled(monkeypatch):
    import subprocess as sp

    from tksteamlaunch import launcher as L

    class P:
        returncode = 1
        stdout = ""
        stderr = "boom"

    monkeypatch.setattr(sp, "run", lambda *a, **k: P())
    assert L.run_editor_menu("42") == ("cancelled", "42")


def test_editor_menu_bad_output_cancelled(monkeypatch):
    import subprocess as sp

    from tksteamlaunch import launcher as L

    class P:
        returncode = 0
        stdout = "not json\n"
        stderr = ""

    monkeypatch.setattr(sp, "run", lambda *a, **k: P())
    assert L.run_editor_menu("42") == ("cancelled", "42")


def test_editor_menu_spawn_fallback_headless(monkeypatch):
    from tksteamlaunch import launcher as L

    def boom(*a, **k):
        raise OSError("noexec")

    monkeypatch.setattr("subprocess.run", boom)
    monkeypatch.delenv("DISPLAY", raising=False)
    monkeypatch.delenv("WAYLAND_DISPLAY", raising=False)
    assert L.run_editor_menu("42") == ("unavailable", "42")


def test_help_documents_exit_codes(xdg_env):
    r = _run(_env(xdg_env), "--help")
    assert r.returncode == 0
    assert "exit codes" in r.stdout and "  10  AppID not resolved" in r.stdout


def test_help_exit_codes_format(xdg_env):
    r = _run(_env(xdg_env), "--help")
    assert r.returncode == 0
    assert "\n  10  AppID not resolved\n" in r.stdout
    assert "\n  17  validation issues found\n" in r.stdout


def test_fresh_prefix_disarms_after_wipe(xdg_env, monkeypatch, tmp_path):
    pfx = tmp_path / "compatdata" / "77"
    (pfx / "pfx").mkdir(parents=True)
    monkeypatch.setenv("STEAM_COMPAT_DATA_PATH", str(pfx))
    _save("77", proton={"fresh_prefix": True})
    assert _run(_env(xdg_env), "--appid", "77", "/bin/echo", "hi").returncode == 0
    assert not pfx.exists()
    assert C.load("77").proton.fresh_prefix is False
