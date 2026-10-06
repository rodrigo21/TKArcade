"""Backend unit tests with fake PATH binaries where needed."""

import os

import pytest

from tkarcade import config as C
from tkarcade import steam as S
from tkarcade.backends import gamemode as gm
from tkarcade.backends import ludusavi as lu
from tkarcade.backends import nightlight as nl
from tkarcade.backends import overlay as ov
from tkarcade.backends import prepost as pp
from tkarcade.launcher import (
    PrefixNotFoundError,
    build_final_command,
    detect_game_type,
    swap_native_executable,
    swap_proton_executable,
)


def test_swap_proton_run_marker():
    assert swap_proton_executable(["/p/proton", "run", "/g/old.exe", "-x"], "/g/new.exe") == [
        "/p/proton",
        "run",
        "/g/new.exe",
        "-x",
    ]


def test_swap_proton_dashdash_marker():
    assert swap_proton_executable(["a", "--", "old"], "new") == [
        "a",
        "--",
        "old".replace("old", "new"),
    ]


def test_swap_native_argv0():
    assert swap_native_executable(["/g/old", "-x"], "/g/new") == ["/g/new", "-x"]
    assert swap_native_executable([], "/g/new") == ["/g/new"]


def test_detect_game_type():
    assert detect_game_type([], "proton") == "proton"
    assert type(detect_game_type([], "proton")) is str
    assert detect_game_type(["/p/proton", "run", "x"], "auto") == "proton"
    assert detect_game_type(["/usr/bin/game"], "auto") == "native"


def test_detect_game_type_compat_env(monkeypatch):
    monkeypatch.setenv("STEAM_COMPAT_DATA_PATH", "/x/123")
    assert detect_game_type(["/usr/bin/game"], "auto") == "proton"


def test_gamemode_tiebreak_feral_wins(fake_bin):
    fake_bin("gamemoderun")
    cmd, warnings = gm.prefix(["/bin/true"], feral=True, cachy=True)
    assert cmd == ["gamemoderun", "/bin/true"]
    assert any("mutually exclusive" in w for w in warnings)


def test_gamemode_missing_binary_warns(xdg_env):
    cmd, warnings = gm.prefix(["/bin/true"], feral=True, cachy=False)
    assert cmd == ["/bin/true"] or "gamemoderun" in cmd[0]
    if cmd == ["/bin/true"]:
        assert warnings


def test_overlay_missing_binaries_warn(xdg_env, monkeypatch, tmp_path):
    monkeypatch.setenv("PATH", str(tmp_path))
    cmd, warnings = ov.apply_mangohud(["/bin/true"], True, "")
    assert cmd == ["/bin/true"] and warnings
    cmd, warnings = ov.apply_gamescope(["/bin/true"], True, "")
    assert cmd == ["/bin/true"] and warnings


def test_overlay_disabled_passthrough():
    assert ov.apply_mangohud(["/bin/true"], False, "")[0] == ["/bin/true"]
    assert ov.apply_gamescope(["/bin/true"], False, "")[0] == ["/bin/true"]


def test_ludusavi_off_passthrough():
    assert lu.wrap_command(["/bin/true"], enabled=False) == (["/bin/true"], [])


def test_ludusavi_find_paths(fake_bin, monkeypatch, tmp_path):
    path, warning = lu.find()
    if path and "flatpak" not in path:
        assert warning is None
    flatdir = tmp_path / "flatpak" / "bin"
    flatdir.mkdir(parents=True)
    script = flatdir / "ludusavi"
    script.write_text("#!/bin/sh\nexit 0\n")
    script.chmod(0o755)
    monkeypatch.setenv("PATH", str(flatdir))
    path, warning = lu.find()
    assert path is not None and warning is not None


def test_ludusavi_missing_binary_warns(xdg_env, monkeypatch, tmp_path):
    monkeypatch.setenv("PATH", str(tmp_path))
    cmd, warnings = lu.wrap_command(["/bin/true"], enabled=True)
    assert cmd == ["/bin/true"] and warnings


_FAKE_LUDUSAVI = """#!/bin/sh
if [ "$1" = "find" ]; then
  case "$*" in
    *"Empty Game"*)
      echo '{"games": {"Empty Game": {"score": 1.0}}}'; exit 0;;
    *"Known Game"*|*"--steam-id 42"*)
      echo '{"games": {"Known Game": {"score": 1.0}}}'; exit 0;;
    *) echo '{"games": {}}'; exit 1;;
  esac
elif [ "$1" = "backup" ]; then
  case "$*" in
    *"Empty Game"*)
      echo '{"games": {"Empty Game": {"decision": "Processed", "files": {}, "registry": {}}}}'; exit 0;;
    *) echo '{"games": {"Known Game": {"decision": "Processed", "files": {"/s/save.dat": {"bytes": 10}}, "registry": {}}}}'; exit 0;;
  esac
fi
exit 2
"""


def test_check_coverage_states(fake_bin, monkeypatch, tmp_path):
    bindir = tmp_path / "covbin"
    bindir.mkdir()
    script = bindir / "ludusavi"
    script.write_text(_FAKE_LUDUSAVI)
    script.chmod(0o755)
    monkeypatch.setenv("PATH", str(bindir))
    assert lu.check_coverage("42")[0] == "covered"
    assert lu.check_coverage("43")[0] == "no-entry"
    assert lu.check_coverage("9", "Empty Game")[0] == "no-local-saves"


def test_check_coverage_no_binary(monkeypatch, tmp_path):
    monkeypatch.setenv("PATH", str(tmp_path))
    assert lu.check_coverage("42")[0] == "unavailable"


def test_ludusavi_wrap_shape(fake_bin):
    fake_bin("ludusavi")
    cmd, warnings = lu.wrap_command(
        ["/bin/true"], enabled=True, restore=False, backup=True, use_gui=True
    )
    assert not warnings
    assert cmd[0].endswith("ludusavi") and cmd[1] == "wrap"
    assert "--infer" in cmd and "steam" in cmd
    assert "--no-restore" in cmd and "--gui" in cmd
    assert cmd[-2:] == ["--", "/bin/true"]
    assert "sh" not in cmd  # no sentinel shim without rc_file


def test_ludusavi_wrap_sentinel(fake_bin, tmp_path):
    fake_bin("ludusavi")
    rc = str(tmp_path / "game.rc")
    cmd, warnings = lu.wrap_command(["/bin/false"], enabled=True, rc_file=rc)
    assert not warnings
    assert cmd[cmd.index("--") + 1 : cmd.index("--") + 4] == ["sh", "-c", lu._SH_EXIT_SENTINEL]
    assert cmd[-2] == rc and cmd[-1] == "/bin/false"


def test_prepost_echo_and_failure():
    assert pp.run_hook("t", "/bin/echo", ["hi"], timeout=10) == 0
    assert pp.run_hook("t", "/bin/false", [], timeout=10) == 1
    assert pp.run_hook("t", "", [], timeout=10) == -1


def test_prepost_shell_receives_env():
    rc = pp.run_hook(
        "t",
        "/bin/sh",
        ["-c", 'test "$TK_TEST" = hello'],
        timeout=10,
        run_in_shell=False,
        extra_env={"TK_TEST": "hello"},
    )
    assert rc == 0
    rc = pp.run_hook(
        "t",
        'test "$TK_TEST" = hello',
        [],
        timeout=10,
        run_in_shell=True,
        extra_env={"TK_TEST": "hello"},
    )
    assert rc == 0


def test_nightlight_detect_matrix(monkeypatch, tmp_path):
    monkeypatch.setenv("PATH", str(tmp_path))
    monkeypatch.setenv("XDG_CURRENT_DESKTOP", "KDE")
    assert nl.detect_provider("auto") == "plasma"
    assert type(nl.detect_provider("auto")) is str
    assert nl.detect_provider("plasma") == "plasma"
    assert nl.detect_provider("off") == "off"
    monkeypatch.setenv("XDG_CURRENT_DESKTOP", "")
    monkeypatch.delenv("DESKTOP_SESSION", raising=False)
    assert nl.detect_provider("auto") == "off"
    assert nl.detect_provider("kde") == "off"  # unknown value falls back


def test_resolve_appid(monkeypatch):
    assert S.resolve_appid("42") == "42"
    monkeypatch.setenv("STEAMAPPID", "99")
    assert S.resolve_appid("") == "99"
    monkeypatch.delenv("STEAMAPPID")
    monkeypatch.setenv("STEAM_COMPAT_DATA_PATH", "/x/123")
    assert S.resolve_appid("") == "123"


def test_list_games_fake_root(monkeypatch, tmp_path, xdg_env):
    root = tmp_path / "steamapps"
    root.mkdir()
    (root / "appmanifest_10.acf").write_text('"AppState"\n{\n"appid" "10"\n"name" "B Game"\n}\n')
    (root / "appmanifest_9.acf").write_text('"AppState"\n{\n"appid" "9"\n"name" "A Game"\n}\n')
    monkeypatch.setenv("STEAM_ROOT", str(tmp_path))
    assert S.list_games() == [("9", "A Game"), ("10", "B Game")]


def test_games_cache_refresh(monkeypatch, tmp_path, xdg_env):
    root = tmp_path / "steamapps"
    root.mkdir()
    (root / "appmanifest_10.acf").write_text('"AppState"\n{\n"appid" "10"\n}\n')
    monkeypatch.setenv("STEAM_ROOT", str(tmp_path))
    assert [a for a, _ in S.list_games()] == ["10"]
    (root / "appmanifest_11.acf").write_text('"AppState"\n{\n"appid" "11"\n}\n')
    assert [a for a, _ in S.list_games()] == ["10"]  # stale until cleared
    S.clear_games_cache()
    assert [a for a, _ in S.list_games()] == ["10", "11"]


def test_loads_kv1_without_vdf(monkeypatch):
    import sys

    monkeypatch.setitem(sys.modules, "vdf", None)
    assert S.loads_kv1('"a" { "b" "c" }') is None
    assert S.loads_kv1("not vdf {{{") is None


def test_find_game_icon_layouts(monkeypatch, tmp_path, xdg_env):
    root = tmp_path / "steam"
    modern = root / "appcache" / "librarycache" / "11"
    modern.mkdir(parents=True)
    hashed = modern / ("a" * 40 + ".jpg")
    hashed.write_bytes(b"x")
    (modern / "logo.png").write_bytes(b"y")
    legacy = root / "appcache" / "librarycache"
    (legacy / "12_icon.jpg").write_bytes(b"z")
    monkeypatch.setenv("STEAM_ROOT", str(root))
    assert S.find_game_icon("11") == hashed
    assert S.find_game_icon("12") == legacy / "12_icon.jpg"
    assert S.find_game_icon("13") is None


def test_build_prefix_order(fake_bin):
    fake_bin("gamemoderun")
    fake_bin("gamescope")
    fake_bin("mangohud")
    cfg = C.GameConfig()
    cfg.general.appid = "1"
    cfg.gamemode.feral_gamemode = True
    cfg.mangohud.enable = True
    cfg.gamescope.enable = True
    cfg.gamescope.args = "-f"
    cmd, _env, _ = build_final_command(cfg, ["/bin/true"])
    assert cmd == ["gamescope", "-f", "--", "gamemoderun", "mangohud", "/bin/true"]


def test_build_prefix_missing_raises(xdg_env, monkeypatch, tmp_path):
    monkeypatch.setenv("PATH", str(tmp_path))
    cfg = C.GameConfig()
    cfg.general.appid = "1"
    cfg.general.custom_prefix = "nope-bin --flag"
    with pytest.raises(PrefixNotFoundError):
        build_final_command(cfg, ["/bin/true"])


def test_notify_noop_without_server(xdg_env, monkeypatch, tmp_path):
    from tkarcade.backends import notify as ntf

    monkeypatch.setenv("PATH", str(tmp_path))
    assert not ntf.available()
    ntf.send("hi")  # must not raise


def test_suite_silences_notifications_by_default(xdg_env, monkeypatch, tmp_path):
    """The autouse fixture keeps real notifications out of test runs."""
    import os
    import stat

    from tkarcade.backends import notify as ntf

    assert os.environ.get("TKARCADE_NO_NOTIFY") == "1"
    bindir = tmp_path / "bin"
    bindir.mkdir()
    fake = bindir / "notify-send"
    fake.write_text("#!/bin/sh\nexit 0\n")
    fake.chmod(fake.stat().st_mode | stat.S_IXUSR)
    monkeypatch.setenv("PATH", str(bindir))
    monkeypatch.setenv("DISPLAY", ":0")
    assert not ntf.available()  # kill-switch wins over binary + server


def test_notify_calls_server(monkeypatch, tmp_path):
    from tkarcade.backends import notify as ntf

    bindir = tmp_path / "bin"
    bindir.mkdir()
    logged = tmp_path / "notify.log"
    script = bindir / "notify-send"
    script.write_text(f'#!/bin/sh\necho "$@" >> "{logged}"\n')
    script.chmod(0o755)
    monkeypatch.setenv("PATH", str(bindir))
    monkeypatch.setenv("DISPLAY", ":0")
    monkeypatch.delenv("TKARCADE_NO_NOTIFY", raising=False)  # opt out of suite silence
    ntf.send("summary", "body", "critical")
    for _ in range(100):
        if logged.exists():
            break
        import time

        time.sleep(0.02)
    assert "summary" in logged.read_text()


def test_launch_summary_shapes():
    from tkarcade.backends import notify as ntf

    title, body = ntf.launch_summary(
        appid="1",
        name="Some Game",
        game_type="proton",
        wrappers=["GameMode", "MangoHud"],
        custom_executable="/g/dir/game.exe",
        proton_display="Proton 9.0-2",
    )
    assert title == "TKArcade — Some Game"
    assert body.splitlines() == [
        "Proton 9.0-2 · GameMode · MangoHud",
        "Exe: game.exe",
    ]
    title, body = ntf.launch_summary(appid="2", game_type="native")
    assert (title, body) == ("TKArcade — 2", "Native")
    title, body = ntf.launch_summary(appid="3", game_type="proton")
    assert body == "Proton"
    title, body = ntf.launch_summary(appid="4", game_type="native", runtime="soldier")
    assert body == "Native · soldier"
    title, body = ntf.launch_summary(appid="5", game_type="proton", wrappers=["A", "", "B"])
    assert body == "Proton · A · B"
    assert all(not line.endswith((" ", "·")) for line in body.splitlines())


def test_launch_summary_proton_log_warning():
    from tkarcade.backends import notify as ntf

    _, body = ntf.launch_summary(appid="5", proton_log=True)
    assert "Proton logging on" in body
    _, body = ntf.launch_summary(appid="5", proton_log=False)
    assert "Proton logging" not in body


def test_proton_log_env(xdg_env):
    cfg = C.GameConfig()
    cfg.general.appid = "51"
    cfg.debug.proton_log = True
    _cmd, env, _ = build_final_command(cfg, ["/bin/true"])
    assert env.get("PROTON_LOG") == "1"
    assert env.get("PROTON_LOG_DIR", "").endswith("51/proton")
    cfg.debug.proton_log = False
    _cmd, env, _ = build_final_command(cfg, ["/bin/true"])
    assert "PROTON_LOG" not in env and "PROTON_LOG_DIR" not in env


def test_winedebug_env(xdg_env):
    cfg = C.GameConfig()
    cfg.general.appid = "53"
    cfg.debug.winedebug = "+err"
    _cmd, env, _ = build_final_command(cfg, ["/bin/true"])
    assert env.get("WINEDEBUG") == "+err"
    cfg.debug.winedebug = ""
    _cmd, env, _ = build_final_command(cfg, ["/bin/true"])
    assert "WINEDEBUG" not in env


def test_debug_section_roundtrip(xdg_env):
    cfg = C.GameConfig()
    cfg.general.appid = "54"
    cfg.debug.proton_log = True
    cfg.debug.winedebug = "-all"
    C.save(cfg)
    back = C.load("54")
    assert back.debug.proton_log is True and back.debug.winedebug == "-all"


def test_format_duration():
    from tkarcade.backends import notify as ntf

    assert ntf.format_duration(0) == "0s"
    assert ntf.format_duration(38) == "38s"
    assert ntf.format_duration(60) == "1m 00s"
    assert ntf.format_duration(45 * 60 + 12) == "45m 12s"
    assert ntf.format_duration(2 * 3600 + 13 * 60) == "2h 13m"
    assert ntf.format_duration(-5) == "0s"


def test_native_runtime_sniffing():
    from tkarcade import proton as pm

    soldier = [
        "/home/u/.steam/steam/steamapps/common/SteamLinuxRuntime_soldier/_v2-entry-point",
        "--verb=waitforexitandrun",
        "--",
        "/game/run.sh",
    ]
    assert pm.native_runtime(soldier) == "soldier"
    assert pm.native_runtime(["/x/SteamLinuxRuntime_sniper/run", "--", "/g"]) == "sniper"
    assert pm.native_runtime(["/usr/bin/game"]) is None
    # game path mentioning scout without a runtime marker: no false positive
    assert pm.native_runtime(["/games/scout-adventure/run.sh"]) is None


def test_send_icon_and_expiry(monkeypatch, tmp_path):
    from tkarcade.backends import notify as ntf

    bindir = tmp_path / "bin"
    bindir.mkdir()
    logged = tmp_path / "notify.log"
    script = bindir / "notify-send"
    script.write_text(f'#!/bin/sh\necho "$@" >> "{logged}"\n')
    script.chmod(0o755)
    monkeypatch.setenv("PATH", str(bindir))
    monkeypatch.setenv("DISPLAY", ":0")
    monkeypatch.delenv("TKARCADE_NO_NOTIFY", raising=False)  # opt out of suite silence
    ntf.send("t", "b", icon="/i.png", expire_ms=5000)
    for _ in range(100):
        if logged.exists():
            break
        import time

        time.sleep(0.02)
    out = logged.read_text()
    assert "--icon=/i.png" in out and "--expire-time=5000" in out


def test_proton_version_lookup(monkeypatch, tmp_path, xdg_env):
    import sys

    from tkarcade import proton as pm

    root = tmp_path / "steam"
    (root / "config").mkdir(parents=True)
    (root / "config" / "config.vdf").write_text(
        '"InstallConfigStore"\n{\n"Software"\n{\n"Valve"\n{\n"Steam"\n'
        '{\n"CompatToolMapping"\n{\n"42"\n{\n"name" "GE-Proton9-15"\n}\n}\n}\n}\n}\n}\n'
    )
    tooldir = root / "compatibilitytools.d" / "GE-Proton9-15"
    tooldir.mkdir(parents=True)
    (tooldir / "version").write_text("GE-Proton9-15\n")
    monkeypatch.setenv("STEAM_ROOT", str(root))
    assert pm.tool_display("42") == "GE-Proton9-15 (GE-Proton9-15)"
    assert pm.tool_display("43") == "Proton"

    # stdlib regex fallback without the vdf package
    monkeypatch.setitem(sys.modules, "vdf", None)
    assert pm.tool_display("42") == "GE-Proton9-15 (GE-Proton9-15)"


def test_mangohud_create_templates(xdg_env):
    from tkarcade.backends import overlay as ov

    for key in ("minimal", "fps-cap", "full", "empty"):
        path, source, error = ov.create_mangohud_config(f"t-{key}", template=key)
        assert (source, error) == (key, ""), (key, source, error)
        text = path.read_text()
        assert text == ov.MANGOHUD_TEMPLATES.get(key, "# MangoHud configuration\n")
    assert ov.create_mangohud_config("t-minimal", template="minimal")[1] == "exists"
    assert "fps_limit=60" in ov.MANGOHUD_TEMPLATES["fps-cap"]


def test_gamescope_presets():
    from tkarcade.backends import overlay as ov

    assert set(ov.GAMESCOPE_PRESETS) == {
        "1080p 144Hz Fullscreen",
        "1440p 165Hz Fullscreen",
        "4K 60Hz Fullscreen",
        "Borderless Windowed",
        "Steam Deck 1280x800",
    }
    for args in ov.GAMESCOPE_PRESETS.values():
        assert args.startswith("-")


def test_mangohud_config_env(xdg_env):
    os.makedirs(os.path.join(os.environ["XDG_CONFIG_HOME"], "MangoHud"), exist_ok=True)
    with open(os.path.join(os.environ["XDG_CONFIG_HOME"], "MangoHud", "custom.conf"), "w") as f:
        f.write("fps_limit=60\n")
    cfg = C.GameConfig()
    cfg.general.appid = "1"
    cfg.mangohud.config_file = "custom.conf"
    _cmd, env, _ = build_final_command(cfg, ["/bin/true"])
    assert env["MANGOHUD_CONFIGFILE"].endswith("custom.conf")


def _write_localconfig(root, uid, apps_body):
    confdir = root / "userdata" / uid / "config"
    confdir.mkdir(parents=True)
    (confdir / "localconfig.vdf").write_text(
        '"UserLocalConfigStore"\n{\n"Software"\n{\n"Valve"\n{\n"Steam"\n'
        '{\n"Apps"\n{\n' + apps_body + "\n}\n}\n}\n}\n}\n"
    )


def test_launch_options_status(monkeypatch, tmp_path, xdg_env):
    root = tmp_path / "steam"
    _write_localconfig(root, "u1", '"60"\n{\n"LaunchOptions" "tkarcade %command%"\n}')
    _write_localconfig(root, "u2", '"61"\n{\n"LaunchOptions" "gamemoderun %command%"\n}')
    monkeypatch.setenv("STEAM_ROOT", str(root))
    assert S.launch_options_status("60")[0] == "ok"
    assert S.launch_options_status("61")[0] == "missing"
    assert S.launch_options_status("62")[0] == "missing"


def test_launch_options_unknown_without_userdata(monkeypatch, tmp_path, xdg_env):
    monkeypatch.setenv("STEAM_ROOT", str(tmp_path / "empty"))
    assert S.launch_options_status("60")[0] == "unknown"


def test_launch_options_regex_fallback(monkeypatch, tmp_path, xdg_env):
    import sys

    root = tmp_path / "steam"
    _write_localconfig(root, "u1", '"60"\n{\n"LaunchOptions" "TKARCADE %command%"\n}')
    monkeypatch.setenv("STEAM_ROOT", str(root))
    monkeypatch.setitem(sys.modules, "vdf", None)
    assert S.launch_options_status("60")[0] == "ok"


def test_nightlight_start_idempotent(monkeypatch):
    calls = []

    class FakeProc:
        def __init__(self, *a, **k):
            calls.append((a, k))
            self.stdout = object()  # select() raises immediately: no 5s wait

        def poll(self):
            return None

    monkeypatch.setattr(nl.subprocess, "Popen", FakeProc)
    session = nl.NightlightSession("plasma")
    session.start()
    assert len(calls) == 1
    assert session.start() == []
    assert len(calls) == 1


def test_split_args_never_raises():
    from tkarcade.backends import split_args

    assert split_args('foo "bar') == ["foo", '"bar']
    assert split_args("") == []
    assert split_args("--dlsym -x") == ["--dlsym", "-x"]


def test_coverage_bytes_coercion(monkeypatch):
    from tkarcade.backends import ludusavi as lu

    monkeypatch.setattr(lu, "find", lambda: ("/bin/ludusavi", None))

    def fake_run(cmd, **kw):
        class R:
            returncode = 0

        if "find" in cmd:
            R.stdout = '{"games": {"G": {}}}'
        else:
            R.stdout = '{"games": {"G": {"files": {"/s": {"bytes": "7"}, "/t": {}}}}}'
        return R()

    monkeypatch.setattr(lu.subprocess, "run", fake_run)
    assert lu.check_coverage("1") == ("covered", "Entry 'G': 2 file(s), 0 bytes")


def test_list_games_cached_per_process(monkeypatch, tmp_path):
    root = tmp_path / "steamapps"
    root.mkdir()
    (root / "appmanifest_1.acf").write_text('"AppState"\n{\n"appid" "1"\n"name" "Solo"\n}\n')
    monkeypatch.setenv("STEAM_ROOT", str(tmp_path))
    monkeypatch.setenv("HOME", str(tmp_path))
    first = S.list_games()
    assert first == [("1", "Solo")]
    (root / "appmanifest_2.acf").write_text('"AppState"\n{\n"appid" "2"\n"name" "Duo"\n}\n')
    assert S.list_games() is first  # cached: no rescan
    S._GAMES_CACHE.clear()
    assert S.list_games() == [("2", "Duo"), ("1", "Solo")]


def test_launch_options_real_world_shape(monkeypatch, tmp_path, xdg_env):
    # Faithful to real localconfig.vdf: lowercase "apps" node and a nested
    # "cloud" block between the AppID and its LaunchOptions.
    from tkarcade.steam import _launch_options_from_text

    body = (
        '"UserLocalConfigStore"\n{\n"Software"\n{\n"Valve"\n{\n"Steam"\n'
        '{\n"apps"\n{\n"63"\n{\n"LastPlayed" "1"\n"cloud"\n{\n"last_sync_state"'
        ' "synchronized"\n}\n"LaunchOptions" "/opt/tkarcade --menu %command%"\n'
        '}\n"64"\n{\n"LastPlayed" "2"\n}\n}\n}\n}\n}\n}\n'
    )
    assert _launch_options_from_text(body, "63") == "/opt/tkarcade --menu %command%"
    assert _launch_options_from_text(body, "64") is None
    assert _launch_options_from_text(body, "65") is None


def test_launch_options_lowercase_apps_status(monkeypatch, tmp_path, xdg_env):
    root = tmp_path / "steam"
    confdir = root / "userdata" / "u9" / "config"
    confdir.mkdir(parents=True)
    (confdir / "localconfig.vdf").write_text(
        '"UserLocalConfigStore"\n{\n"Software"\n{\n"Valve"\n{\n"Steam"\n'
        '{\n"apps"\n{\n"66"\n{\n"cloud"\n{\n"x" "y"\n}\n"LaunchOptions"'
        ' "tkarcade --menu %command%"\n}\n}\n}\n}\n}\n}\n'
    )
    monkeypatch.setenv("STEAM_ROOT", str(root))
    assert S.launch_options_status("66")[0] == "ok"


def test_inhibit_idle_prefix(fake_bin):
    fake_bin("systemd-inhibit")
    cfg = C.GameConfig()
    cfg.general.appid = "67"
    cfg.session.inhibit_idle = True
    cmd, _env, warnings = build_final_command(cfg, ["/bin/true"])
    assert not warnings
    assert cmd[:5] == [
        "systemd-inhibit",
        "--what=idle",
        "--who=TKArcade",
        "--why=67",
        "--",
    ]
    assert cmd[-1] == "/bin/true"


def test_inhibit_idle_missing_binary(xdg_env, monkeypatch, tmp_path):
    monkeypatch.setenv("PATH", str(tmp_path))
    cfg = C.GameConfig()
    cfg.general.appid = "68"
    cfg.session.inhibit_idle = True
    cmd, _env, warnings = build_final_command(cfg, ["/bin/true"])
    assert cmd == ["/bin/true"]
    assert any("systemd-inhibit" in w for w in warnings)


def test_rtupscale_wrap_and_xwayland(fake_bin):
    fake_bin("upscale")
    cfg = C.GameConfig()
    cfg.general.appid = "81"
    cfg.rtupscale.enable = True
    cfg.rtupscale.args = "-m 4x24"
    cmd, env, warnings = build_final_command(cfg, ["/bin/true"])
    assert not warnings
    assert cmd[:5] == ["upscale", "-m", "4x24", "--", "/bin/true"]
    assert env.get("PROTON_ENABLE_WAYLAND") == "0"


def test_rtupscale_conflict_warns(fake_bin):
    fake_bin("upscale")
    cfg = C.GameConfig()
    cfg.general.appid = "82"
    cfg.rtupscale.enable = True
    cfg.env.vars = {"PROTON_ENABLE_WAYLAND": "1"}
    _cmd, env, warnings = build_final_command(cfg, ["/bin/true"])
    assert env["PROTON_ENABLE_WAYLAND"] == "0"
    assert any("XWayland" in w for w in warnings)


def test_rtupscale_missing_binary(xdg_env, monkeypatch, tmp_path):
    monkeypatch.setenv("PATH", str(tmp_path))
    cfg = C.GameConfig()
    cfg.general.appid = "83"
    cfg.rtupscale.enable = True
    cmd, _env, warnings = build_final_command(cfg, ["/bin/true"])
    assert cmd == ["/bin/true"]
    assert any("upscale" in w for w in warnings)


def test_active_wrappers_lists_enabled():
    from tkarcade import config as C
    from tkarcade.launcher import active_wrappers

    assert active_wrappers(C.GameConfig()) == []
    cfg = C.GameConfig()
    cfg.mangohud.enable = True
    cfg.ludusavi.enable = True
    assert active_wrappers(cfg) == ["MangoHud", "Ludusavi"]
    cfg.gamemode.feral_gamemode = True
    cfg.gamemode.cachyos_game_performance = True
    assert active_wrappers(cfg) == ["GameMode", "game-performance", "MangoHud", "Ludusavi"]


def test_find_game_icon_landscape_pref(monkeypatch, tmp_path, xdg_env):
    from tkarcade import steam as S

    root = tmp_path / "steam" / "appcache" / "librarycache" / "76"
    root.mkdir(parents=True)
    hashed = "b" * 40 + ".jpg"
    (root / hashed).write_bytes(b"tiny")
    (root / "header.jpg").write_bytes(b"wide")
    monkeypatch.setenv("STEAM_ROOT", str(tmp_path / "steam"))
    assert S.find_game_icon("76").name == hashed
    assert S.find_game_icon("76", landscape=True).name == "header.jpg"
    (root / "header.jpg").unlink()
    assert S.find_game_icon("76", landscape=True).name == hashed


def _fake_lib(tmp_path, appid, installdir=None):
    sap = tmp_path / "steamapps"
    (sap / "common").mkdir(parents=True, exist_ok=True)
    acf = f'"AppState"\n{{\n"appid" "{appid}"\n"name" "T Game"'
    if installdir is not None:
        acf += f'\n"installdir" "{installdir}"'
        (sap / "common" / installdir).mkdir(exist_ok=True)
    acf += "\n}\n"
    (sap / f"appmanifest_{appid}.acf").write_text(acf)
    return sap


def test_install_and_prefix_dirs(monkeypatch, tmp_path, xdg_env):
    from tkarcade import steam as S

    _fake_lib(tmp_path, "77", "TGame")
    (tmp_path / "steamapps" / "compatdata" / "77").mkdir(parents=True)
    monkeypatch.setenv("STEAM_ROOT", str(tmp_path))
    assert S.install_dir("77") == tmp_path / "steamapps" / "common" / "TGame"
    assert S.prefix_dir("77") == tmp_path / "steamapps" / "compatdata" / "77"


def test_install_and_prefix_missing(monkeypatch, tmp_path, xdg_env):
    from tkarcade import steam as S

    _fake_lib(tmp_path, "78")
    monkeypatch.setenv("STEAM_ROOT", str(tmp_path))
    assert S.install_dir("78") is None  # no installdir key
    assert S.prefix_dir("78") is None  # never launched
    assert S.install_dir("nope") is None
    assert S.prefix_dir("../evil") is None  # no path escape


def test_unconfigured_games(monkeypatch, tmp_path, xdg_env):
    from tkarcade import steam as S

    root = tmp_path / "steamapps"
    root.mkdir()
    (root / "appmanifest_10.acf").write_text('"AppState"\n{\n"appid" "10"\n"name" "B Game"\n}\n')
    (root / "appmanifest_9.acf").write_text('"AppState"\n{\n"appid" "9"\n"name" "A Game"\n}\n')
    monkeypatch.setenv("STEAM_ROOT", str(tmp_path))
    assert S.unconfigured_games({"9"}) == [("10", "B Game")]
    assert S.unconfigured_games({"9", "10"}) == []


def test_shader_dir_and_size(monkeypatch, tmp_path, xdg_env):
    from tkarcade import steam as S

    sap = tmp_path / "steamapps"
    (sap / "shadercache" / "77").mkdir(parents=True)
    (sap / "shadercache" / "77" / "foz.db").write_bytes(b"x" * 2048)
    monkeypatch.setenv("STEAM_ROOT", str(tmp_path))
    assert S.shader_dir("77") == sap / "shadercache" / "77"
    assert S.dir_size(sap / "shadercache" / "77") == 2048
    assert S.shader_dir("78") is None
    assert S.shader_dir("../evil") is None
    assert S.format_size(0) == "0 B"
    assert S.format_size(2048) == "2.0 KB"
    assert S.format_size(3 * 1024**3) == "3.0 GB"


def test_tool_mapping_cached_by_mtime(monkeypatch, tmp_path, xdg_env):
    from tkarcade import proton as pm

    pm.clear_tool_cache()
    root = tmp_path / "steam"
    cfgdir = root / "config"
    cfgdir.mkdir(parents=True)
    vdf = cfgdir / "config.vdf"
    vdf.write_text(
        '"InstallConfigStore"\n{\n"Software"\n{\n"Valve"\n{\n"Steam"\n{\n'
        '"CompatToolMapping"\n{\n"42"\n{\n"name" "GE-Proton9-15"\n}\n}\n}\n}\n}\n}\n'
    )
    monkeypatch.setenv("STEAM_ROOT", str(root))
    assert pm.compat_tool_name("42") == "GE-Proton9-15"
    vdf.write_text(
        '"InstallConfigStore"\n{\n"Software"\n{\n"Valve"\n{\n"Steam"\n{\n'
        '"CompatToolMapping"\n{\n"42"\n{\n"name" "proton_9"\n}\n}\n}\n}\n}\n}\n'
    )
    import os
    import time

    stamp = time.time() + 5
    os.utime(vdf, (stamp, stamp))  # force a newer mtime: cache must miss
    assert pm.compat_tool_name("42") == "proton_9"
    assert pm.compat_tool_name("43") is None
    pm.clear_tool_cache()
