"""SteamTinkerLaunch importer: parsing, mapping, AppID matching."""

from tksteamlaunch import stl_import as sti


def _write(path, text):
    path.write_text(text, encoding="utf-8")
    return path


def test_parse_shell_assignments(tmp_path):
    conf = tmp_path / "1.conf"
    _write(
        conf,
        '## comment\n\nUSEGAMEMODERUN="1"\n'
        "CUSTOMCMD_ARGS='--hidraw --emulate-xpad'\n"
        "PLAIN=bare\n"
        'BAD="unbalanced\n'
        "not-an-assignment\n",
    )
    data = sti.parse_stl_conf(conf)
    assert data["USEGAMEMODERUN"] == "1"
    assert data["CUSTOMCMD_ARGS"] == "--hidraw --emulate-xpad"
    assert data["PLAIN"] == "bare"
    assert data["BAD"] == '"unbalanced'
    assert "" not in data
    assert sti.parse_stl_conf(tmp_path / "missing.conf") == {}


def test_list_stl_appids(tmp_path, monkeypatch):
    d = tmp_path / "steamtinkerlaunch" / "gamecfgs" / "id"
    d.mkdir(parents=True)
    (d / "60.conf").write_text("A=1\n")
    (d / "notes.txt").write_text("x\n")
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
    assert sti.list_stl_appids() == ["60"]
    assert sti.stl_config_dir() == tmp_path / "steamtinkerlaunch"


def test_map_full_game():
    stl = {
        "USEGAMEMODERUN": "1",
        "USEGAMESCOPE": "1",
        "GAMESCOPE_ARGS": "-f -e --",
        "USEMANGOHUD": "1",
        "USECUSTOMCMD": "1",
        "ONLY_CUSTOMCMD": "1",
        "CUSTOMCMD": "/games/launcher.exe",
        "USERSTART": "/s/pre.sh",
        "USERSTOP": "/s/post.sh",
        "WINETRICKSPAKS": "dotnet48 vcrun2022",
        "PROTON_LOG": "1",
        "STLWINEDEBUG": "-all",
        "PROTON_FORCE_LARGE_ADDRESS_AWARE": "1",
        "PROTON_LOG_DIR": "STLCFGDIR/logs",
        "USEPROTON": "GE-Proton9-1",
        "SOMETHING_ELSE": "0",
    }
    cfg, report = sti.map_to_gameconfig("60", stl)
    assert cfg.general.appid == "60"
    assert cfg.gamemode.feral_gamemode is True
    assert cfg.gamescope.enable and cfg.gamescope.args == "-f -e"
    assert cfg.mangohud.enable is True
    assert cfg.general.custom_executable == "/games/launcher.exe"
    assert cfg.pre_post.pre_command == "/s/pre.sh"
    assert cfg.pre_post.post_command == "/s/post.sh"
    assert cfg.proton.winetricks_verbs == ["dotnet48", "vcrun2022"]
    assert cfg.debug.proton_log is True
    assert cfg.debug.winedebug == "-all"
    assert cfg.env.vars == {"PROTON_FORCE_LARGE_ADDRESS_AWARE": "1"}
    assert cfg.notes.text.startswith("Imported from SteamTinkerLaunch")
    text = " ".join(report)
    assert "STL paths" in text and "STL-only" in text


def test_map_customcmd_as_pre_with_args():
    stl = {"USECUSTOMCMD": "1", "CUSTOMCMD": "/s/helper", "CUSTOMCMD_ARGS": "--a --b"}
    cfg, report = sti.map_to_gameconfig("61", stl)
    assert cfg.general.custom_executable == ""
    assert cfg.pre_post.pre_command == "/s/helper"
    assert cfg.pre_post.pre_args == ["--a", "--b"]
    assert any("alongside" in note for note in report)


def test_map_empty_and_unknown_winedebug():
    cfg, _ = sti.map_to_gameconfig("62", {})
    assert cfg.general.custom_executable == ""
    assert cfg.pre_post.pre_command == ""
    assert cfg.env.vars == {}
    cfg2, report = sti.map_to_gameconfig("62", {"STLWINEDEBUG": "+trace"})
    assert cfg2.debug.winedebug == ""
    assert any("no equivalent" in note for note in report)
