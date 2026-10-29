"""Launcher CLI end-to-end (subprocess): exit codes, sentinel, --edit guard."""

import os
import subprocess
import sys
from pathlib import Path

from tkarcade import config as C

SRC = str(Path(__file__).resolve().parent.parent / "src")


def _run(env, *args):
    cmd = [sys.executable, "-m", "tkarcade.launcher", *args]
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
    cfg.general.environment = "native"
    for section, values in kw.items():
        target = getattr(cfg, section)
        for key, value in values.items():
            setattr(target, key, value)
    return C.save(cfg)


def test_dry_run(xdg_env):
    _save("1")
    r = _run(_env(xdg_env), "--appid", "1", "--dry-run", "--", "/bin/echo", "hi")
    assert r.returncode == 0
    assert "AppID: 1" in r.stdout and "/bin/echo hi" in r.stdout


def test_no_appid(xdg_env):
    r = _run(_env(xdg_env), "--", "/bin/echo", "hi")
    assert r.returncode == 10


def test_unset_environment_exits_18(xdg_env):
    cfg = C.GameConfig()
    cfg.general.appid = "39"
    C.save(cfg)
    r = _run(_env(xdg_env), "--appid", "39", "/bin/true")
    assert r.returncode == 18
    assert "environment not set" in r.stderr


def test_local_game_cannot_borrow_proton(xdg_env):
    cfg = C.GameConfig()
    cfg.general.appid = "local-nope"
    cfg.general.environment = "proton"
    C.save(cfg)
    r = _run(_env(xdg_env), "--appid", "local-nope", "/bin/true")
    assert r.returncode == 18
    assert "Steam AppID" in r.stderr


def test_validate_flags_unset_environment(xdg_env):
    from tkarcade import launcher as L

    cfg = C.GameConfig()
    cfg.general.appid = "38"
    C.save(cfg)
    assert any("environment not set" in i for i in L.validate_game("38"))


def test_wine_missing_binary_exit_14(xdg_env, tmp_path):
    cfg = C.GameConfig()
    cfg.general.appid = "local-wine"
    cfg.general.environment = "wine"
    cfg.general.custom_executable = "/games/doom.exe"
    C.save(cfg)
    env = _env(xdg_env)
    env["PATH"] = str(tmp_path / "empty")
    r = _run(env, "--appid", "local-wine")
    assert r.returncode == 14
    assert "wine binary not found" in r.stderr


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


def test_migrate_ids_cli(xdg_env):
    cfg = C.GameConfig()
    cfg.general.appid = "local-bad-hero---episode-1"
    cfg.general.name = "Bad Hero - Episode 1"
    C.save(cfg)
    env = _env(xdg_env)
    r = _run(env, "--migrate-ids")
    assert r.returncode == 0
    assert "local-bad-hero---episode-1 -> local-bad-hero-episode-1" in r.stdout
    assert "Steam shortcuts" in r.stderr
    assert C.game_file("local-bad-hero-episode-1").is_file()
    r = _run(env, "--migrate-ids")
    assert r.returncode == 0 and "No local AppID needs renaming." in r.stdout


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

    from tkarcade import xdg
    from tkarcade.launcher import setup_logging

    logdir = xdg.games_log_dir()
    logdir.mkdir(parents=True, exist_ok=True)
    (logdir / "8.log").write_bytes(b"x" * 1_100_000)
    setup_logging("8")
    # WARNING: pytest runs the root logger at WARNING, INFO would be filtered.
    logging.getLogger("tkarcade.test").warning("trigger rollover")
    assert (logdir / "8.log.1").exists()


def test_launch_notification_toggle(xdg_env, fake_bin, monkeypatch, tmp_path):
    log = tmp_path / "notify.log"
    fake_bin("notify-send", f'#!/bin/sh\necho "$@" >> "{log}"\n')
    monkeypatch.setenv("DISPLAY", ":0")
    _save("9", notifications={"notify_on_launch": True})
    env = _env(xdg_env)  # inherits fake PATH + DISPLAY
    env.pop("TKARCADE_NO_NOTIFY", None)  # opt out of suite silence
    assert _run(env, "--appid", "9", "/bin/true").returncode == 0
    assert "TKArcade" in log.read_text()
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
    env.pop("TKARCADE_NO_NOTIFY", None)  # opt out of suite silence
    assert _run(env, "--appid", "10", "/bin/sleep", "0").returncode == 0
    out = log.read_text()
    assert "Finished 10" in out and "Played" in out


def test_validate_reports_issues(xdg_env, monkeypatch, tmp_path):
    from tkarcade import launcher as L

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
    from tkarcade import launcher as L

    cfg = C.GameConfig()
    cfg.general.appid = "31"
    cfg.general.environment = "native"
    C.save(cfg)
    assert L.cmd_validate(["31"]) == 0


def test_validate_steam_runtime_is_a_note_not_an_issue(
    xdg_env, fake_bin, monkeypatch, tmp_path, capsys
):
    from tkarcade import launcher as L

    fake_bin("umu-run")
    cfg = C.GameConfig()
    cfg.general.appid = "local-srl"
    cfg.general.name = "Srl"
    cfg.general.environment = "native"
    cfg.general.custom_executable = fake_bin("game")
    cfg.runtime.steam_runtime = "sniper"
    C.save(cfg)
    # umu downloads a missing runtime on first launch: a note, never a 17.
    assert L.validate_game("local-srl") == []
    notes = L.validate_notes("local-srl")
    assert notes and "3.0 (sniper)" in notes[0] and "first launch" in notes[0]
    assert L.cmd_validate(["local-srl"]) == 0
    out = capsys.readouterr().out
    assert "(note)" in out and "all clear" in out
    # Without umu-run the launch would exit 14, so that one is an issue.
    monkeypatch.setenv("PATH", str(tmp_path / "empty"))
    assert any("umu-run" in issue for issue in L.validate_game("local-srl"))


def test_global_log_carries_duration(xdg_env):
    from tkarcade import xdg

    _save("11")
    env = _env(xdg_env)
    assert _run(env, "--appid", "11", "/bin/true").returncode == 0
    line = (xdg.app_state_dir() / "launcher.log").read_text()
    assert "appid=11" in line and " dur=" in line


def test_peel_display_appid():
    from tkarcade.launcher import peel_display_appid

    assert peel_display_appid(["588950"]) == ("588950", [])
    assert peel_display_appid(["/bin/echo", "hi"]) == ("", ["/bin/echo", "hi"])
    assert peel_display_appid([]) == ("", [])
    assert peel_display_appid(["12", "34"]) == ("", ["12", "34"])
    # A local id qualifies only when it names a configured game.
    assert peel_display_appid(["local-glxgears"], {"local-glxgears"}) == ("local-glxgears", [])
    assert peel_display_appid(["local-nope"], {"local-glxgears"}) == ("", ["local-nope"])
    assert peel_display_appid(["glxgears"], {"local-glxgears"}) == ("", ["glxgears"])


def test_menu_without_display_launches_directly(xdg_env, monkeypatch):
    _save("6", general={"show_menu": True})
    monkeypatch.delenv("DISPLAY", raising=False)
    monkeypatch.delenv("WAYLAND_DISPLAY", raising=False)
    r = _run(_env(xdg_env), "--appid", "6", "--menu", "--", "/bin/echo", "hi")
    assert r.returncode == 0
    r = _run(_env(xdg_env), "--appid", "6", "--", "/bin/echo", "hi")
    assert r.returncode == 0
    log = xdg_env["state"] / "tkarcade" / "games" / "6.log"
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
    log = xdg_env["state"] / "tkarcade" / "games" / "8.log"
    assert "no game command to run" in log.read_text()


def test_menu_flag_shows_editor_once_without_display(xdg_env, monkeypatch):
    _save("9", general={})
    monkeypatch.delenv("DISPLAY", raising=False)
    monkeypatch.delenv("WAYLAND_DISPLAY", raising=False)
    r = _run(_env(xdg_env), "--appid", "9", "--menu", "--", "/bin/echo", "hi")
    assert r.returncode == 0
    log = xdg_env["state"] / "tkarcade" / "games" / "9.log"
    assert log.read_text().count("launching directly") == 1


def test_menu_positional_appid_resolves_like_edit(xdg_env, monkeypatch):
    """`--menu <appid>` peels the positional AppID exactly like `--edit`."""
    monkeypatch.delenv("DISPLAY", raising=False)
    monkeypatch.delenv("WAYLAND_DISPLAY", raising=False)
    r = _run(_env(xdg_env), "--menu", "21")
    assert r.returncode == 0, r.stderr
    assert "cannot resolve AppID" not in r.stderr
    log = xdg_env["state"] / "tkarcade" / "games" / "21.log"
    assert "no game command to run" in log.read_text()


def test_clean_gui_env():
    from tkarcade.launcher import clean_gui_env

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
    _save("77", runtime={"fresh_prefix": True})
    assert _run(_env(xdg_env), "--appid", "77", "/bin/echo", "hi").returncode == 0
    assert not pfx.exists()
    assert C.load("77").runtime.fresh_prefix is False


def test_validate_dangling_profile(xdg_env):
    from tkarcade import config as C
    from tkarcade import launcher as L

    cfg = C.GameConfig()
    cfg.general.appid = "33"
    cfg.general.active_profile = "gone"
    cfg.general.environment = "native"
    C.save(cfg)
    issues = L.validate_game("33")
    assert any("gone" in i and "live config" in i for i in issues)
    C.save_profile("33", "ok", cfg)
    cfg.general.active_profile = "ok"
    C.save(cfg)
    assert L.validate_game("33") == []


def test_validate_bad_display_mode(xdg_env):
    from tkarcade import config as C
    from tkarcade import launcher as L

    cfg = C.GameConfig()
    cfg.general.appid = "34"
    cfg.display.mode = "bogus"
    C.save(cfg)
    assert any("display mode" in i for i in L.validate_game("34"))
    cfg.display.mode = "1920x1080@60"
    C.save(cfg)
    assert not any("display mode" in i for i in L.validate_game("34"))


def test_validate_newer_config_version(xdg_env):
    from tkarcade import config as C
    from tkarcade import launcher as L

    cfg = C.GameConfig()
    cfg.general.appid = "35"
    C.save(cfg)
    C.game_file("35").write_text(
        C.game_file("35").read_text().replace("config_version = 1", "config_version = 99"),
        encoding="utf-8",
    )
    issues = L.validate_game("35")
    assert any("newer" in i for i in issues)


def test_launcher_gui_dispatch(xdg_env, monkeypatch):
    import sys

    from tkarcade import launcher as L

    calls = []
    monkeypatch.setattr("tkarcade.gui.kirigami_app.main", lambda *a: calls.append("gui") or 0)
    monkeypatch.setenv("DISPLAY", ":0")
    monkeypatch.delenv("WAYLAND_DISPLAY", raising=False)
    monkeypatch.setattr(sys, "argv", ["tkarcade"])
    assert L.main([]) == 0
    assert L.main(["--gui"]) == 0
    assert calls == ["gui", "gui"]
    monkeypatch.delenv("DISPLAY")
    assert L.main(["--gui"]) == 15  # no display
    assert L.main(["--cli"]) == 10  # never GUI: classic no-AppID error


def test_validate_checks_effective_profile_content(xdg_env):
    from tkarcade import config as C
    from tkarcade import launcher as L

    cfg = C.GameConfig()
    cfg.general.appid = "36"
    cfg.general.active_profile = "p1"
    C.save(cfg)
    prof = C.GameConfig()
    prof.general.appid = "36"
    prof.pre_post.pre_command = "/definitely/not/here.sh"
    C.save_profile("36", "p1", prof)
    issues = L.validate_game("36")
    assert any("not/here" in i for i in issues)


def test_menu_skip_plant_consume_expire(xdg_env, tmp_path):
    import os
    import time

    from tkarcade import launcher as L

    assert L.consume_menu_skip("40") is False
    L.plant_menu_skip("40")
    assert L.consume_menu_skip("40") is True
    assert L.consume_menu_skip("40") is False  # one-shot
    L.plant_menu_skip("41")
    path = L.menu_skip_path("41")
    old = time.time() - L.MENU_SKIP_TTL - 10
    os.utime(path, (old, old))
    assert L.consume_menu_skip("41") is False
    assert not path.exists()
    assert "../" not in str(L.menu_skip_path("../../evil"))


def test_validate_flags_missing_custom_executable(xdg_env):
    from tkarcade import launcher as L

    cfg = C.GameConfig()
    cfg.general.appid = "local-doom"
    cfg.general.custom_executable = "/nonexistent/doom"
    cfg.general.environment = "native"
    C.save(cfg)
    assert L.validate_game("local-doom") == [
        "local-doom: custom_executable not found: /nonexistent/doom"
    ]


def test_local_run_cwd(xdg_env, tmp_path):
    from tkarcade import launcher as L

    cfg = C.GameConfig()
    exe = tmp_path / "doom"
    exe.write_text("#!/bin/sh\n")
    cfg.general.custom_executable = str(exe)
    assert L.local_run_cwd("local-doom", cfg) == str(tmp_path)
    cfg.general.custom_executable = "/nonexistent/doom"
    assert L.local_run_cwd("local-doom", cfg) is None
    assert L.local_run_cwd("213", cfg) is None


def test_local_dry_run_uses_custom_executable(xdg_env, tmp_path, capsys):
    from tkarcade import launcher as L

    exe = tmp_path / "doom"
    exe.write_text("#!/bin/sh\n")
    cfg = C.GameConfig()
    cfg.general.appid = "local-doom"
    cfg.general.name = "Doom"
    cfg.general.custom_executable = str(exe)
    cfg.general.environment = "native"
    C.save(cfg)
    assert L.main(["--appid", "local-doom", "--dry-run"]) == 0
    out = capsys.readouterr().out
    assert "AppID: local-doom" in out
    assert str(exe) in out


def test_setup_logging_no_duplicate_handler(xdg_env):
    import logging

    from tkarcade.launcher import setup_logging

    setup_logging("30")
    setup_logging("30")
    targets = [
        getattr(h, "baseFilename", "")
        for h in logging.getLogger().handlers
        if getattr(h, "baseFilename", "").endswith("30.log")
    ]
    assert len(targets) == 1


def test_dry_run_loads_config_once(xdg_env, monkeypatch):
    from tkarcade import launcher as L

    _save("31")
    calls = []
    real = C.load_effective

    def counting(appid):
        calls.append(appid)
        return real(appid)

    monkeypatch.setattr(L.cfgmod, "load_effective", counting)
    assert L.main(["--appid", "31", "--dry-run", "--", "/bin/true"]) == 0
    assert calls == ["31"]


def test_nonexecutable_exit_13(xdg_env, tmp_path):
    exe = tmp_path / "noexec"
    exe.write_text("#!/bin/sh\necho hi\n")  # deliberately left non-executable
    _save("32")
    assert _run(_env(xdg_env), "--appid", "32", str(exe)).returncode == 13


# --- run_editor_menu: the child protocol (in-process, no Qt) ---------------


def _fake_child(monkeypatch, *, returncode=0, stdout="", stderr="", boom=None):
    """Stub subprocess.run; returns the list the launcher called with."""
    from tkarcade import launcher as L

    calls = []

    def fake_run(cmd, **kwargs):
        calls.append((cmd, kwargs))
        if boom is not None:
            raise boom
        return subprocess.CompletedProcess(cmd, returncode, stdout=stdout, stderr=stderr)

    monkeypatch.setattr(L.subprocess, "run", fake_run)
    return calls


def test_editor_menu_parses_the_child_outcome(monkeypatch):
    from tkarcade import launcher as L

    calls = _fake_child(monkeypatch, stdout='{"outcome": "saved", "appid": "7"}\n')
    assert L.run_editor_menu("7") == ("saved", "7")
    cmd, kwargs = calls[0]
    assert cmd[1:] == ["-m", "tkarcade.gui.edit", "--appid", "7", "--can-launch"]
    assert kwargs["capture_output"] is True


def test_editor_menu_passes_the_pick_menu_and_env(monkeypatch):
    from tkarcade import launcher as L

    calls = _fake_child(monkeypatch, stdout='{"outcome": "launch", "appid": "42"}')
    monkeypatch.setenv(
        "LD_LIBRARY_PATH",
        "/opt/x:/home/u/.local/share/Steam/ubuntu12_32/steam-runtime/pinned",
    )
    assert L.run_editor_menu("", for_menu=True, can_launch=False) == ("launch", "42")
    cmd, kwargs = calls[0]
    assert cmd[1:] == [
        "-m",
        "tkarcade.gui.edit",
        "--pick",
        "--no-can-launch",
        "--menu",
    ]
    assert "Steam" not in kwargs["env"].get("LD_LIBRARY_PATH", "")


def test_edit_targets_a_positional_local_game(xdg_env, monkeypatch):
    """`--edit local-glxgears` opens that game, not the picker."""
    from tkarcade import launcher as L

    _save(
        "local-glxgears",
        general={"name": "glxgears", "custom_executable": "/usr/bin/glxgears"},
    )
    calls = _fake_child(monkeypatch, stdout='{"outcome": "cancelled", "appid": "local-glxgears"}')
    assert L.main(["--edit", "local-glxgears"]) == 0
    cmd, _ = calls[0]
    assert cmd[1:] == ["-m", "tkarcade.gui.edit", "--appid", "local-glxgears", "--can-launch"]


def test_menu_targets_a_positional_local_game(xdg_env, monkeypatch):
    from tkarcade import launcher as L

    _save(
        "local-glxgears",
        general={"name": "glxgears", "custom_executable": "/usr/bin/glxgears"},
    )
    calls = _fake_child(monkeypatch, stdout='{"outcome": "cancelled", "appid": "local-glxgears"}')
    assert L.main(["--menu", "local-glxgears"]) == 0
    cmd, _ = calls[0]
    assert cmd[1:] == [
        "-m",
        "tkarcade.gui.edit",
        "--appid",
        "local-glxgears",
        "--can-launch",
        "--menu",
    ]


def test_editor_menu_crash_is_cancelled(monkeypatch):
    from tkarcade import launcher as L

    _fake_child(monkeypatch, returncode=1, stderr="Traceback (most recent call last):")
    assert L.run_editor_menu("7") == ("cancelled", "7")


def test_editor_menu_bad_output_is_cancelled(monkeypatch):
    from tkarcade import launcher as L

    _fake_child(monkeypatch, stdout="not json at all")
    assert L.run_editor_menu("7") == ("cancelled", "7")


def test_editor_menu_bad_outcome_is_cancelled(monkeypatch):
    from tkarcade import launcher as L

    _fake_child(monkeypatch, stdout='{"outcome": "explode", "appid": "7"}')
    assert L.run_editor_menu("7") == ("cancelled", "7")


def test_editor_menu_exit_two_is_unavailable(monkeypatch):
    from tkarcade import launcher as L

    _fake_child(monkeypatch, returncode=2, stderr="tkarcade: --edit needs a display")
    assert L.run_editor_menu("7") == ("unavailable", "7")


def test_editor_menu_spawn_failure_is_unavailable(monkeypatch):
    from tkarcade import launcher as L

    _fake_child(monkeypatch, boom=OSError("no such file"))
    assert L.run_editor_menu("7") == ("unavailable", "7")


def _wait_for(path, timeout=30.0):
    import time

    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if path.exists():
            return True
        time.sleep(0.05)
    return path.exists()


def test_running_record_covers_the_game(xdg_env):
    """The launcher records itself while the game runs, then clears it."""
    from tkarcade import running

    _save("rec1")
    record = running.record_path("rec1")
    script = (
        "import json, os, sys\n"
        f"d = json.load(open({str(record)!r}))\n"
        "sys.exit(0 if d['pid'] == os.getppid() and d['appid'] == 'rec1' else 3)\n"
    )
    r = _run(_env(xdg_env), "--appid", "rec1", sys.executable, "-c", script)
    assert r.returncode == 0, r.stderr
    assert not record.exists()


def test_terminate_stops_the_game_and_clears_the_record(xdg_env, tmp_path):
    """SIGTERM to the launcher stops the game, then the launcher exits."""
    import signal
    import time

    from tkarcade import running

    _save("rec2")
    marker = tmp_path / "game.pid"
    game = f"import os, time\nopen({str(marker)!r}, 'w').write(str(os.getpid()))\ntime.sleep(120)\n"
    proc = subprocess.Popen(
        [sys.executable, "-m", "tkarcade.launcher", "--appid", "rec2", sys.executable, "-c", game],
        env=_env(xdg_env),
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        # Like the GUI's launch: the launcher owns its own session, so
        # the signal forwarding cannot reach this test process.
        start_new_session=True,
    )
    record = running.record_path("rec2")
    try:
        assert _wait_for(record), "no running record"
        assert _wait_for(marker), "game never started"
        game_pid = int(marker.read_text())
        os.kill(proc.pid, signal.SIGTERM)
        assert proc.wait(timeout=30) is not None
    finally:
        if proc.poll() is None:
            proc.kill()
            proc.wait(timeout=10)
    assert proc.returncode != -signal.SIGTERM  # exited on its own path
    assert not record.exists()
    deadline = time.monotonic() + 10
    while running.process_start_time(game_pid) is not None and time.monotonic() < deadline:
        time.sleep(0.02)
    assert running.process_start_time(game_pid) is None


def test_block_internet_wraps_the_game(monkeypatch):
    from tkarcade.backends import network
    from tkarcade.launcher import active_wrappers, build_final_command

    monkeypatch.setattr(network, "available", lambda: True)
    cfg = C.GameConfig()
    cfg.general.environment = "native"
    cfg.general.appid = "77"
    cfg.network.block_internet = True
    cmd, _env, warnings = build_final_command(cfg, ["/bin/true"])
    assert not warnings
    assert cmd == ["unshare", "-Urn", "--", "/bin/true"]
    assert "Block Internet" in active_wrappers(cfg)


def test_block_internet_unavailable_exits_14(xdg_env, monkeypatch):
    from tkarcade.backends import network
    from tkarcade.launcher import _final_command

    monkeypatch.setattr(network, "available", lambda: False)
    cfg = C.GameConfig()
    cfg.general.appid = "78"
    cfg.general.environment = "native"
    cfg.network.block_internet = True
    rc, cmd, _env, _warnings = _final_command("78", cfg, ["/bin/true"], "")
    assert rc == 14
    assert cmd == []
