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
    cfg.runtime.type = "native"
    for section, values in kw.items():
        target = getattr(cfg, section)
        for key, value in values.items():
            setattr(target, key, value)
    return C.save(cfg)


def test_dry_run(xdg_env):
    _save("1")
    r = _run(_env(xdg_env), "--game-id", "steam-1", "--dry-run", "--", "/bin/echo", "hi")
    assert r.returncode == 0
    assert "Game ID: steam-1" in r.stdout and "/bin/echo hi" in r.stdout
    # --appid stays as the alias until the 1.0 cleanup.
    r = _run(_env(xdg_env), "--appid", "1", "--dry-run", "--", "/bin/echo", "hi")
    assert r.returncode == 0
    assert "Game ID: steam-1" in r.stdout


def test_no_appid(xdg_env):
    r = _run(_env(xdg_env), "--", "/bin/echo", "hi")
    assert r.returncode == 10


def test_unset_environment_exits_18(xdg_env):
    cfg = C.GameConfig()
    cfg.general.appid = "local-unset"
    C.save(cfg)
    r = _run(_env(xdg_env), "--appid", "local-unset", "/bin/true")
    assert r.returncode == 18
    assert "runtime not set" in r.stderr


def test_infer_runtime_from_command():
    from tkarcade.launcher import effective_runtime, infer_runtime

    proton = [
        "/home/u/.steam/steamapps/common/Proton - Experimental/proton",
        "waitforexitandrun",
        "/game.exe",
    ]
    assert infer_runtime("39", proton) == "proton"
    assert infer_runtime("39", ["/usr/bin/proton", "run", "/game.exe"]) == "proton"
    slr = [
        "/x/SteamLinuxRuntime_sniper/_v2-entry-point",
        "--verb=waitforexitandrun",
        "--",
        "/game",
    ]
    assert infer_runtime("39", slr) == "native"
    assert infer_runtime("39", ["/usr/bin/game"]) == "native"
    assert infer_runtime("local-x", proton) == ""
    assert infer_runtime("39", []) == ""
    cfg = C.GameConfig()
    assert effective_runtime("39", cfg, proton) == "proton"
    cfg.runtime.type = "native"
    assert effective_runtime("39", cfg, proton) == "native"


def test_unconfigured_steam_game_infers_proton(xdg_env):
    cfg = C.GameConfig()
    cfg.general.appid = "39"
    C.save(cfg)
    proton = "/home/u/.steam/steamapps/common/Proton - Experimental/proton"
    r = _run(
        _env(xdg_env), "--appid", "39", "--dry-run", "--", proton, "waitforexitandrun", "/game.exe"
    )
    assert r.returncode == 0
    assert "Proton - Experimental/proton" in r.stdout
    assert "waitforexitandrun /game.exe" in r.stdout


def test_unconfigured_steam_game_infers_native(xdg_env):
    cfg = C.GameConfig()
    cfg.general.appid = "39"
    C.save(cfg)
    r = _run(_env(xdg_env), "--appid", "39", "--dry-run", "--", "/bin/echo", "hi")
    assert r.returncode == 0
    assert "Final: /bin/echo hi" in r.stdout


PROTON_CMD = ["/x/proton", "waitforexitandrun", "/game.exe"]


def test_first_run_prompts_for_unconfigured_steam(xdg_env, monkeypatch):
    from argparse import Namespace

    from tkarcade import launcher as L

    seen = {}

    def fake_menu(appid, **kwargs):
        seen.update(appid=appid, **kwargs)
        return "launch", appid

    monkeypatch.setattr(L, "run_editor_menu", fake_menu)
    args = Namespace(dry_run=False, edit=False, menu=False)
    rc, appid, _cfg = L._maybe_run_menus(args, "39", C.GameConfig(), PROTON_CMD)
    assert (rc, appid) == (None, "39")
    assert seen == {"appid": "39", "first_run": True, "runtime": "proton"}


def test_first_run_saved_config_is_reloaded(xdg_env, monkeypatch):
    from argparse import Namespace

    from tkarcade import launcher as L

    def fake_menu(appid, **kwargs):
        saved = C.GameConfig()
        saved.general.appid = appid
        saved.runtime.type = "proton"
        C.save(saved)
        return "saved", appid

    monkeypatch.setattr(L, "run_editor_menu", fake_menu)
    args = Namespace(dry_run=False, edit=False, menu=False)
    rc, appid, cfg = L._maybe_run_menus(args, "39", C.GameConfig(), PROTON_CMD)
    assert rc is None
    assert appid == "39"
    assert cfg.runtime.type == "proton"


def test_first_run_not_now_saves_nothing(xdg_env, monkeypatch):
    from argparse import Namespace

    from tkarcade import launcher as L

    monkeypatch.setattr(L, "run_editor_menu", lambda appid, **kw: ("launch", appid))
    args = Namespace(dry_run=False, edit=False, menu=False)
    rc, appid, _cfg = L._maybe_run_menus(args, "39", C.GameConfig(), ["/usr/bin/game"])
    assert (rc, appid) == (None, "39")
    assert not C.game_file("39").exists()


def test_first_run_failure_launches_directly(monkeypatch):
    from argparse import Namespace

    from tkarcade import launcher as L

    args = Namespace(dry_run=False, edit=False, menu=False)
    for outcome in ("crashed", "unavailable", "cancelled"):
        monkeypatch.setattr(
            L, "run_editor_menu", lambda appid, _outcome=outcome, **kw: (_outcome, appid)
        )
        rc, appid, _cfg = L._maybe_run_menus(args, "39", C.GameConfig(), PROTON_CMD)
        assert (rc, appid) == (None, "39"), outcome


def test_first_run_skip_conditions():
    from argparse import Namespace

    from tkarcade import launcher as L

    args = Namespace(dry_run=False, edit=False, menu=False)
    assert not L._needs_first_run(args, "local-x", C.GameConfig(), PROTON_CMD)
    configured = C.GameConfig()
    configured.runtime.type = "native"
    assert not L._needs_first_run(args, "39", configured, PROTON_CMD)
    dry = Namespace(dry_run=True, edit=False, menu=False)
    assert not L._needs_first_run(dry, "39", C.GameConfig(), PROTON_CMD)
    assert not L._needs_first_run(args, "39", C.GameConfig(), [])


def test_local_game_cannot_borrow_proton(xdg_env):
    cfg = C.GameConfig()
    cfg.general.appid = "local-nope"
    cfg.runtime.type = "proton"
    C.save(cfg)
    r = _run(_env(xdg_env), "--appid", "local-nope", "/bin/true")
    assert r.returncode == 18
    assert "Steam AppID" in r.stderr


def test_validate_flags_unset_environment(xdg_env):
    from tkarcade import launcher as L

    cfg = C.GameConfig()
    cfg.general.appid = "38"
    C.save(cfg)
    assert any("runtime not set" in i for i in L.validate_game("38"))


def test_wine_missing_binary_exit_14(xdg_env, tmp_path):
    cfg = C.GameConfig()
    cfg.general.appid = "local-wine"
    cfg.runtime.type = "wine"
    cfg.general.custom_executable = "/games/doom.exe"
    C.save(cfg)
    env = _env(xdg_env)
    env["PATH"] = str(tmp_path / "empty")
    r = _run(env, "--appid", "local-wine")
    assert r.returncode == 14
    assert "wine binary not found" in r.stderr


def test_run_and_pre_hook_abort(xdg_env):
    _save("steam-2", pre_post={"pre_command": "/bin/echo", "pre_args": ["ok"]})
    assert _run(_env(xdg_env), "--appid", "steam-2", "/bin/echo", "hi").returncode == 0
    _save("steam-2", pre_post={"pre_command": "/bin/false"})
    assert _run(_env(xdg_env), "--appid", "steam-2", "/bin/echo", "hi").returncode == 12


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


def test_signal_exit_is_128_plus_n(xdg_env):
    """A game killed by signal N reports 128+N, wrap or not."""
    import signal

    _save("local-sig")
    game = "import os, signal; os.kill(os.getpid(), signal.SIGTERM)"
    r = _run(_env(xdg_env), "--appid", "local-sig", sys.executable, "-c", game)
    assert r.returncode == 128 + signal.SIGTERM


def test_playtime_stops_at_game_exit(monkeypatch):
    """Playtime and the notification exclude the post-exit hook."""
    from tkarcade import launcher

    now = [100.0]
    monkeypatch.setattr(launcher.time, "monotonic", lambda: now[0])

    def run_game(*_args):
        now[0] = 105.0
        return False, 0

    def post_hook(*_args):
        now[0] = 130.0

    monkeypatch.setattr(launcher, "_pre_hook", lambda *a: None)
    monkeypatch.setattr(launcher, "_run_game_process", run_game)
    monkeypatch.setattr(launcher, "_post_hook", post_hook)
    logged = []
    monkeypatch.setattr(launcher, "write_global_log", lambda *a: logged.append(a[3]))
    cfg = C.GameConfig()
    cfg.notifications.notify_on_launch = False
    assert launcher._game_body("local-x", cfg, ["/g"], ["/g"], {}, "") == 0
    assert logged == [5.0]


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
    steam = C.GameConfig()
    steam.general.appid = "570"
    C.save(steam)
    r = _run(env, "--migrate-ids")
    assert r.returncode == 0
    assert "local-bad-hero---episode-1 -> local-bad-hero-episode-1" in r.stdout
    assert "570 -> steam-570" in r.stdout
    assert "Numeric Steam AppIDs in old launch" in r.stderr
    assert C.game_file("local-bad-hero-episode-1").is_file()
    r = _run(env, "--migrate-ids")
    assert r.returncode == 0 and "No Game ID needs renaming." in r.stdout


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
    _save("steam-9", notifications={"notify_on_launch": True})
    env = _env(xdg_env)  # inherits fake PATH + DISPLAY
    env.pop("TKARCADE_NO_NOTIFY", None)  # opt out of suite silence
    assert _run(env, "--appid", "steam-9", "/bin/true").returncode == 0
    assert "TKArcade" in log.read_text()
    log.unlink()
    _save("steam-9", notifications={"notify_on_launch": False})
    assert _run(env, "--appid", "steam-9", "/bin/true").returncode == 0
    assert not log.exists()


def test_session_end_notification(xdg_env, fake_bin, monkeypatch, tmp_path):
    log = tmp_path / "notify.log"
    fake_bin("notify-send", f'#!/bin/sh\necho "$@" >> "{log}"\n')
    monkeypatch.setenv("DISPLAY", ":0")
    _save("steam-10", notifications={"notify_on_launch": True})
    env = _env(xdg_env)
    env.pop("TKARCADE_NO_NOTIFY", None)  # opt out of suite silence
    assert _run(env, "--appid", "steam-10", "/bin/sleep", "0").returncode == 0
    out = log.read_text()
    assert "Finished steam-10" in out and "Played" in out


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
    cfg.runtime.type = "native"
    C.save(cfg)
    assert L.cmd_validate(["31"]) == 0


def test_validate_steam_note_only_for_steam_games(xdg_env, capsys):
    from tkarcade import launcher as L

    cfg = C.GameConfig()
    cfg.general.appid = "local-foo"
    cfg.runtime.type = "native"
    C.save(cfg)
    L.cmd_validate(["local-foo"])
    assert "no Steam installation found" not in capsys.readouterr().out
    L.cmd_validate(["steam-77"])
    assert "global: no Steam installation found" in capsys.readouterr().out


def test_proton_log_only_on_proton_and_umu(xdg_env, monkeypatch, tmp_path):
    from tkarcade import launcher as L

    monkeypatch.setattr(L, "proton_log_dir", lambda appid: tmp_path)
    cfg = C.GameConfig()
    cfg.general.appid = "local-doom"
    cfg.debug.proton_log = True
    for environment in ("proton", "umu"):
        env, _ = L._build_env(cfg, environment)
        assert env["PROTON_LOG"] == "1"
        assert env["PROTON_LOG_DIR"] == str(tmp_path)
    for environment in ("native", "wine"):
        env, _ = L._build_env(cfg, environment)
        assert "PROTON_LOG" not in env


def test_validate_flags_uninstalled_steam_game(xdg_env):
    from tkarcade import launcher as L

    steamapps = xdg_env["home"] / ".local/share/Steam/steamapps"
    game_dir = steamapps / "common" / "Doom"
    game_dir.mkdir(parents=True)
    (steamapps / "appmanifest_40.acf").write_text(
        '"AppState"\n{\n\t"appid"\t\t"40"\n\t"installdir"\t\t"Doom"\n}\n',
        encoding="utf-8",
    )
    _save("steam-40")
    assert L.missing_install("steam-40") is False
    assert L.validate_game("steam-40") == []
    game_dir.rmdir()
    assert L.missing_install("steam-40") is True
    issues = L.validate_game("steam-40")
    assert any("not installed in Steam" in i for i in issues)
    assert L.cmd_validate(["steam-40"]) == 17


def test_missing_install_needs_a_steam_root(xdg_env):
    from tkarcade import launcher as L

    _save("steam-41")
    # No Steam root: the install state is unknown, never a false issue.
    assert L.missing_install("steam-41") is False
    assert L.validate_game("steam-41") == []


def test_missing_install_flags_local_executable(xdg_env):
    from tkarcade import launcher as L

    cfg = C.GameConfig()
    cfg.general.appid = "local-gone"
    cfg.general.custom_executable = "/nonexistent/game"
    cfg.runtime.type = "native"
    C.save(cfg)
    assert L.missing_install("local-gone") is True
    cfg.general.custom_executable = sys.executable
    C.save(cfg)
    assert L.missing_install("local-gone") is False


def test_validate_issues_reports_severity(xdg_env):
    from tkarcade import launcher as L

    cfg = C.GameConfig()
    cfg.general.appid = "local-bad"
    cfg.general.custom_executable = "/nonexistent/game"
    cfg.pre_post.post_command = "/nonexistent/post"
    cfg.display.mode = "bogus"
    cfg.runtime.type = "native"
    C.save(cfg)
    report = L.validate_issues("local-bad")
    assert (
        "error",
        "local-bad: custom_executable not found: /nonexistent/game",
    ) in report
    assert ("warning", "local-bad: post_command not found: /nonexistent/post") in report
    assert (
        "warning",
        "local-bad: invalid display mode 'bogus'; use WIDTHxHEIGHT[@RATE]",
    ) in report
    # The CLI keeps the flat strings, in the same order.
    assert [message for _severity, message in report] == L.validate_game("local-bad")


def test_validate_steam_runtime_is_a_note_not_an_issue(
    xdg_env, fake_bin, monkeypatch, tmp_path, capsys
):
    from tkarcade import launcher as L

    fake_bin("umu-run")
    cfg = C.GameConfig()
    cfg.general.appid = "local-srl"
    cfg.general.name = "Srl"
    cfg.runtime.type = "native"
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
    assert "appid=steam-11" in line and " dur=" in line


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
    log = xdg_env["state"] / "tkarcade" / "games" / "steam-6.log"
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
    log = xdg_env["state"] / "tkarcade" / "games" / "steam-8.log"
    assert "no game command to run" in log.read_text()


def test_menu_flag_shows_editor_once_without_display(xdg_env, monkeypatch):
    _save("9", general={})
    monkeypatch.delenv("DISPLAY", raising=False)
    monkeypatch.delenv("WAYLAND_DISPLAY", raising=False)
    r = _run(_env(xdg_env), "--appid", "9", "--menu", "--", "/bin/echo", "hi")
    assert r.returncode == 0
    log = xdg_env["state"] / "tkarcade" / "games" / "steam-9.log"
    assert log.read_text().count("launching directly") == 1


def test_menu_positional_appid_resolves_like_edit(xdg_env, monkeypatch):
    """`--menu <appid>` peels the positional AppID exactly like `--edit`."""
    monkeypatch.delenv("DISPLAY", raising=False)
    monkeypatch.delenv("WAYLAND_DISPLAY", raising=False)
    r = _run(_env(xdg_env), "--menu", "21")
    assert r.returncode == 0, r.stderr
    assert "cannot resolve Game ID" not in r.stderr
    log = xdg_env["state"] / "tkarcade" / "games" / "steam-21.log"
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
    mixed = {
        "LD_PRELOAD": (
            "/usr/lib/libgtk3-nocsd.so:"
            "/home/u/.local/share/Steam/ubuntu12_64/gameoverlayrenderer.so"
        )
    }
    assert clean_gui_env(mixed)["LD_PRELOAD"] == "/usr/lib/libgtk3-nocsd.so"
    overlays = {
        "LD_PRELOAD": "/x/ubuntu12_32/gameoverlayrenderer.so /y/ubuntu12_64/gameoverlayrenderer.so"
    }
    assert "LD_PRELOAD" not in clean_gui_env(overlays)


def test_help_documents_exit_codes(xdg_env):
    r = _run(_env(xdg_env), "--help")
    assert r.returncode == 0
    assert "exit codes" in r.stdout and "  10  Game ID not resolved" in r.stdout


def test_help_exit_codes_format(xdg_env):
    r = _run(_env(xdg_env), "--help")
    assert r.returncode == 0
    assert "\n  10  Game ID not resolved\n" in r.stdout
    assert "\n  17  validation issues found\n" in r.stdout


def test_fresh_prefix_disarms_after_wipe(xdg_env, monkeypatch, tmp_path):
    pfx = tmp_path / "compatdata" / "77"
    (pfx / "pfx").mkdir(parents=True)
    monkeypatch.setenv("STEAM_COMPAT_DATA_PATH", str(pfx))
    _save("steam-77", runtime={"type": "proton", "fresh_prefix": True})
    assert _run(_env(xdg_env), "--appid", "steam-77", "/bin/echo", "hi").returncode == 0
    assert not pfx.exists()
    assert C.load("steam-77").runtime.fresh_prefix is False


def test_fresh_prefix_is_proton_only(xdg_env, monkeypatch, tmp_path):
    pfx = tmp_path / "compatdata" / "78"
    (pfx / "pfx").mkdir(parents=True)
    monkeypatch.setenv("STEAM_COMPAT_DATA_PATH", str(pfx))
    _save("local-78", runtime={"type": "native", "fresh_prefix": True})
    assert _run(_env(xdg_env), "--appid", "local-78", "/bin/echo", "hi").returncode == 0
    assert (pfx / "pfx").exists()
    assert C.load("local-78").runtime.fresh_prefix is True


def test_fresh_prefix_refuses_another_games_prefix(xdg_env, monkeypatch, tmp_path):
    other = tmp_path / "compatdata" / "88"
    (other / "pfx").mkdir(parents=True)
    monkeypatch.setenv("STEAM_COMPAT_DATA_PATH", str(other))
    _save("steam-77", runtime={"type": "proton", "fresh_prefix": True})
    assert _run(_env(xdg_env), "--appid", "steam-77", "/bin/echo", "hi").returncode == 0
    assert (other / "pfx").exists()
    assert C.load("steam-77").runtime.fresh_prefix is True


def test_fresh_prefix_wipes_the_configured_prefix(xdg_env, monkeypatch, tmp_path):
    env_prefix = tmp_path / "compatdata" / "77"
    (env_prefix / "pfx").mkdir(parents=True)
    configured = tmp_path / "custom" / "compatdata" / "77"
    (configured / "pfx").mkdir(parents=True)
    monkeypatch.setenv("STEAM_COMPAT_DATA_PATH", str(env_prefix))
    _save("steam-77", runtime={"type": "proton", "fresh_prefix": True, "prefix": str(configured)})
    assert _run(_env(xdg_env), "--appid", "steam-77", "/bin/echo", "hi").returncode == 0
    assert not configured.exists()
    assert (env_prefix / "pfx").exists()
    assert C.load("steam-77").runtime.fresh_prefix is False


def test_fresh_prefix_disarm_keeps_the_live_config(xdg_env, monkeypatch, tmp_path):
    pfx = tmp_path / "compatdata" / "77"
    (pfx / "pfx").mkdir(parents=True)
    monkeypatch.setenv("STEAM_COMPAT_DATA_PATH", str(pfx))
    _save("steam-77", runtime={"type": "proton"})
    live = C.load("steam-77")
    live.general.name = "Live"
    live.ludusavi.name_override = "Live"
    C.save(live)
    prof = C.load("steam-77")
    prof.general.name = "Profile"
    prof.ludusavi.name_override = "Profile"
    prof.runtime.fresh_prefix = True
    C.save_profile("steam-77", "alt", prof)
    live = C.load("steam-77")
    live.general.active_profile = "alt"
    C.save(live)
    assert _run(_env(xdg_env), "--appid", "steam-77", "/bin/echo", "hi").returncode == 0
    assert not pfx.exists()
    reloaded = C.load("steam-77")
    assert reloaded.general.name == "Live"
    assert reloaded.general.active_profile == "alt"
    assert reloaded.ludusavi.name_override == "Live"
    profile = C.load_profile("steam-77", "alt")
    assert profile.general.name == "Profile"
    assert profile.runtime.fresh_prefix is False


def test_validate_dangling_profile(xdg_env):
    from tkarcade import config as C
    from tkarcade import launcher as L

    cfg = C.GameConfig()
    cfg.general.appid = "33"
    cfg.general.active_profile = "gone"
    cfg.runtime.type = "native"
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
    cfg.runtime.type = "native"
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
    cfg.runtime.type = "native"
    C.save(cfg)
    assert L.main(["--appid", "local-doom", "--dry-run"]) == 0
    out = capsys.readouterr().out
    assert "Game ID: local-doom" in out
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


def test_state_paths_sanitize_the_game_id(xdg_env):
    from tkarcade import xdg
    from tkarcade.launcher import (
        _new_wrap_rc_file,
        _remove_wrap_rc_file,
        setup_logging,
        write_global_log,
    )

    odd = "../../evil"
    assert setup_logging(odd) == xdg.games_log_dir() / "evil.log"
    sentinel = _new_wrap_rc_file(odd)
    try:
        assert Path(sentinel).parent == xdg.app_state_dir()
        assert Path(sentinel).name.startswith("tkarcade-evil-")
    finally:
        _remove_wrap_rc_file(sentinel)
    write_global_log(odd, 0, ["/bin/true"])
    line = xdg.log_file().read_text(encoding="utf-8").strip().splitlines()[-1]
    assert " appid=evil exit=0 " in line


def test_winetricks_skips_a_custom_steam_prefix(xdg_env, monkeypatch, caplog):
    from tkarcade import launcher, proton

    calls = []
    monkeypatch.setattr(proton, "run_winetricks", lambda appid, verbs: calls.append(appid) or [])
    cfg = C.GameConfig()
    cfg.general.appid = "75"
    cfg.runtime.type = "proton"
    cfg.runtime.prefix = "/tmp/custom-prefix"
    cfg.runtime.winetricks_verbs = ["dotnet48"]
    C.save(cfg)
    with caplog.at_level("WARNING", logger="tkarcade"):
        assert launcher._prepare_launch("75", C.load("75"), []) is None
    assert calls == []
    assert "winetricks skipped: custom prefix" in caplog.text

    cfg.runtime.prefix = ""
    C.save(cfg)
    assert launcher._prepare_launch("75", C.load("75"), []) is None
    assert calls == ["75"]


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
    assert calls == ["steam-31"]


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


def test_editor_menu_crash_is_reported(monkeypatch):
    from tkarcade import launcher as L

    _fake_child(monkeypatch, returncode=-6, stderr="Failed to create RHI (backend 2)")
    assert L.run_editor_menu("7") == ("crashed", "7")


def test_config_menu_crash_launches_directly(monkeypatch):
    from tkarcade import config as cfgmod
    from tkarcade import launcher as L

    monkeypatch.setattr(L, "run_editor_menu", lambda *a, **k: ("crashed", "7"))
    cfg = cfgmod.GameConfig()
    assert L._config_menu("7", cfg, ["game"]) == (None, "7", cfg)


def test_explicit_edit_crash_returns_15(xdg_env, monkeypatch):
    _fake_child(monkeypatch, returncode=-6)
    from tkarcade import launcher as L

    assert L.main(["--edit", "7"]) == 15


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
    cfg.runtime.type = "native"
    cfg.general.appid = "77"
    cfg.network.block_internet = True
    cmd, _env, warnings = build_final_command(cfg, ["/bin/true"])
    assert not warnings
    assert cmd == ["unshare", "-Urn", "--", "/bin/true"]
    assert "Block Internet" in active_wrappers(cfg)


def test_proton_prefix_expands_home(xdg_env):
    """A ~ in [runtime] prefix reaches STEAM_COMPAT_DATA_PATH expanded."""
    from tkarcade.launcher import build_final_command

    cfg = C.GameConfig()
    cfg.general.appid = "77"
    cfg.runtime.type = "proton"
    cfg.runtime.prefix = "~/compatdata/77"
    _cmd, env, _warnings = build_final_command(cfg, ["/bin/true"])
    assert env["STEAM_COMPAT_DATA_PATH"] == str(xdg_env["home"] / "compatdata" / "77")


def test_dry_run_skips_mutations(xdg_env, monkeypatch, tmp_path, capsys):
    """--dry-run runs the read-only path only: no wipe, winetricks or menu."""
    import shlex

    from tkarcade import launcher, proton

    game_cmd = [str(tmp_path / "proton"), "waitforexitandrun", "/game.exe"]
    pfx = tmp_path / "compatdata" / "77"
    (pfx / "pfx").mkdir(parents=True)
    monkeypatch.setenv("STEAM_COMPAT_DATA_PATH", str(pfx))
    winetricks_calls = []
    monkeypatch.setattr(
        proton, "run_winetricks", lambda appid, verbs: winetricks_calls.append(appid) or []
    )
    menu_calls = []
    monkeypatch.setattr(
        launcher,
        "_config_menu",
        lambda appid, cfg, cmd: menu_calls.append(appid) or (None, appid, cfg),
    )
    _save(
        "steam-77",
        general={"show_menu": True},
        runtime={"type": "proton", "fresh_prefix": True, "winetricks_verbs": ["dotnet48"]},
    )
    assert launcher.main(["--appid", "steam-77", "--dry-run", "--", *game_cmd]) == 0
    assert (pfx / "pfx").exists()
    assert C.load("steam-77").runtime.fresh_prefix is True
    assert winetricks_calls == [] and menu_calls == []
    rc, expected, _env, _warnings = launcher._final_command(
        "steam-77", C.load("steam-77"), game_cmd, ""
    )
    assert rc == 0
    assert shlex.join(expected) in capsys.readouterr().out


def test_dry_run_keeps_the_legacy_prefix(xdg_env, tmp_path):
    """--dry-run checks the legacy move without moving anything."""
    from tkarcade import launcher

    root = tmp_path / "old"
    (root / "drive_c").mkdir(parents=True)
    (root / "system.reg").write_text("", encoding="utf-8")
    cfg = C.GameConfig()
    cfg.general.appid = "local-ww"
    cfg.runtime.type = "wine"
    cfg.runtime.prefix = str(root)
    assert launcher._prepare_launch("local-ww", cfg, [], dry_run=True) is None
    assert sorted(p.name for p in root.iterdir()) == ["drive_c", "system.reg"]
    # The same call without --dry-run folds the old prefix into its stem.
    assert launcher._prepare_launch("local-ww", cfg, []) is None
    assert [p.name for p in root.iterdir()] == [C.prefix_stem("local-ww", "", "")]


def test_block_internet_unavailable_exits_14(xdg_env, monkeypatch):
    from tkarcade.backends import network
    from tkarcade.launcher import _final_command

    monkeypatch.setattr(network, "available", lambda: False)
    cfg = C.GameConfig()
    cfg.general.appid = "78"
    cfg.runtime.type = "native"
    cfg.network.block_internet = True
    rc, cmd, _env, _warnings = _final_command("78", cfg, ["/bin/true"], "")
    assert rc == 14
    assert cmd == []
