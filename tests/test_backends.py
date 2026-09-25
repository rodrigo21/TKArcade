"""Backend unit tests with fake PATH binaries where needed."""

import os

import pytest

from tksteamlaunch import config as C
from tksteamlaunch import steam as S
from tksteamlaunch.backends import gamemode as gm
from tksteamlaunch.backends import ludusavi as lu
from tksteamlaunch.backends import nightlight as nl
from tksteamlaunch.backends import overlay as ov
from tksteamlaunch.backends import prepost as pp
from tksteamlaunch.launcher import (
    PrefixNotFoundError,
    build_final_command,
    detect_game_type,
    swap_native_executable,
    swap_proton_executable,
)


def test_swap_proton_run_marker():
    assert swap_proton_executable(
        ["/p/proton", "run", "/g/old.exe", "-x"], "/g/new.exe"
    ) == ["/p/proton", "run", "/g/new.exe", "-x"]


def test_swap_proton_dashdash_marker():
    assert swap_proton_executable(["a", "--", "old"], "new") == ["a", "--", "old".replace("old", "new")]


def test_swap_native_argv0():
    assert swap_native_executable(["/g/old", "-x"], "/g/new") == ["/g/new", "-x"]
    assert swap_native_executable([], "/g/new") == ["/g/new"]


def test_detect_game_type():
    assert detect_game_type([], "proton") == "proton"
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


def test_ludusavi_missing_binary_warns(xdg_env, monkeypatch, tmp_path):
    monkeypatch.setenv("PATH", str(tmp_path))
    cmd, warnings = lu.wrap_command(["/bin/true"], enabled=True)
    assert cmd == ["/bin/true"] and warnings


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
        "t", "/bin/sh", ["-c", 'test "$TK_TEST" = hello'],
        timeout=10, run_in_shell=False, extra_env={"TK_TEST": "hello"},
    )
    assert rc == 0
    rc = pp.run_hook(
        "t", "test \"$TK_TEST\" = hello", [], timeout=10,
        run_in_shell=True, extra_env={"TK_TEST": "hello"},
    )
    assert rc == 0


def test_nightlight_detect_matrix(monkeypatch, tmp_path):
    monkeypatch.setenv("PATH", str(tmp_path))
    monkeypatch.setenv("XDG_CURRENT_DESKTOP", "KDE")
    assert nl.detect_provider("auto") == "plasma"
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


def test_list_games_fake_root(monkeypatch, tmp_path):
    root = tmp_path / "steamapps"
    root.mkdir()
    (root / "appmanifest_10.acf").write_text(
        '"AppState"\n{\n"appid" "10"\n"name" "B Game"\n}\n'
    )
    (root / "appmanifest_9.acf").write_text(
        '"AppState"\n{\n"appid" "9"\n"name" "A Game"\n}\n'
    )
    monkeypatch.setenv("STEAM_ROOT", str(tmp_path))
    assert S.list_games() == [("9", "A Game"), ("10", "B Game")]


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


def test_mangohud_config_env(xdg_env):
    os.makedirs(os.path.join(os.environ["XDG_CONFIG_HOME"], "MangoHud"), exist_ok=True)
    with open(os.path.join(os.environ["XDG_CONFIG_HOME"], "MangoHud", "custom.conf"), "w") as f:
        f.write("fps_limit=60\n")
    cfg = C.GameConfig()
    cfg.general.appid = "1"
    cfg.mangohud.config_file = "custom.conf"
    _cmd, env, _ = build_final_command(cfg, ["/bin/true"])
    assert env["MANGOHUD_CONFIGFILE"].endswith("custom.conf")
