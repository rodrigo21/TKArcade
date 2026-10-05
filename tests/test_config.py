"""Config load/save: snapshots, defaults fallback, enums, forward-compat."""

import shutil

from tksteamlaunch import config as C


def test_save_load_roundtrip(xdg_env):
    cfg = C.GameConfig()
    cfg.general.appid = "7"
    cfg.env.vars = {"A": "1"}
    cfg.nightlight.disable_during_game = True
    cfg.ludusavi.enable = True
    cfg.ludusavi.name_override = "Alt Name"
    C.save(cfg)
    back = C.load("7")
    assert back.env.vars == {"A": "1"}
    assert back.ludusavi.name_override == "Alt Name"
    assert back.nightlight.disable_during_game is True
    assert back.ludusavi.enable is True


def test_save_is_full_snapshot(xdg_env):
    cfg = C.GameConfig()
    cfg.general.appid = "8"
    text = C.save(cfg).read_text()
    assert 'appid = "8"' in text
    assert "game_type" in text and "custom_prefix" in text


def test_missing_file_falls_back_to_defaults(xdg_env):
    d = C.load_defaults()
    d.env.vars = {"D": "9"}
    C.save_defaults(d)
    assert C.load("nope").env.vars == {"D": "9"}


def test_legacy_ludusavi_keys_ignored(xdg_env):
    C.game_file("1").parent.mkdir(parents=True, exist_ok=True)
    C.game_file("1").write_text(
        "[ludusavi]\nenable_restore = true\nenable_backup = true\n",
        encoding="utf-8",
    )
    loaded = C.load("1")
    assert loaded.ludusavi.enable is False


def test_unknown_keys_roundtrip(xdg_env):
    cfg = C.GameConfig()
    cfg.general.appid = "9"
    cfg.extra = {"future": {"thing": "kept"}}
    C.save(cfg)
    assert C.load("9").extra == {"future": {"thing": "kept"}}


def test_enums_match_wire_values():
    assert C.NightlightProvider.PLASMA == "plasma"
    assert C.GameType.NATIVE == "native"
    assert str(C.NightlightProvider.OFF) == "off"


def test_appid_sanitized_to_games_dir(xdg_env):
    path = C.game_file("../../evil")
    assert path.parent == C.xdg.games_dir()
    assert ".." not in path.name
    assert C.game_file("").name == "unknown.toml"


def test_invalid_toml_loads_fresh(xdg_env):
    C.game_file("1").parent.mkdir(parents=True, exist_ok=True)
    C.game_file("1").write_text("[general\nappid = oops", encoding="utf-8")
    loaded = C.load("1")
    assert loaded.general.appid == "1"
    assert loaded.env.vars == {}


def test_wrong_shaped_sections_load_fresh(xdg_env):
    C.game_file("2").parent.mkdir(parents=True, exist_ok=True)
    C.game_file("2").write_text(
        'general = "nope"\n[env]\nvars = [1, 2]\n[pre_post]\ntimeout = "soon"\npre_args = "x"\n',
        encoding="utf-8",
    )
    loaded = C.load("2")
    assert loaded.general.custom_executable == ""
    assert loaded.env.vars == {}
    assert loaded.pre_post.timeout == 60
    assert loaded.pre_post.pre_args == []


def test_proton_config_roundtrip(xdg_env):
    cfg = C.GameConfig()
    cfg.general.appid = "72"
    cfg.proton.fresh_prefix = True
    C.save(cfg)
    assert C.load("72").proton.fresh_prefix is True


def test_prepare_fresh_prefix(monkeypatch, tmp_path):
    from tksteamlaunch import proton as pm

    pfx = tmp_path / "compatdata" / "70" / "pfx"
    pfx.mkdir(parents=True)
    (pfx / "save.dat").write_text("x")
    monkeypatch.setenv("STEAM_COMPAT_DATA_PATH", str(tmp_path / "compatdata" / "70"))
    assert pm.prepare_fresh_prefix() == (True, [])
    assert not (tmp_path / "compatdata" / "70").exists()
    assert pm.prepare_fresh_prefix()[0] is True
    assert "nothing to delete" in pm.prepare_fresh_prefix()[1][0]
    monkeypatch.delenv("STEAM_COMPAT_DATA_PATH")
    ok, warnings = pm.prepare_fresh_prefix()
    assert ok is False and "missing" in warnings[0]


def test_sections_covered_by_key_map():
    assert set(C.to_toml_dict(C.GameConfig())) == set(C.SECTION_KEYS)


def test_profiles_crud(xdg_env):
    cfg = C.GameConfig()
    cfg.general.appid = "70"
    cfg.env.vars = {"P": "1"}
    assert C.list_profiles("70") == []
    C.save_profile("70", "perf", cfg)
    C.save_profile("70", "../evil", cfg)
    names = C.list_profiles("70")
    assert "perf" in names and all("/" not in n for n in names)
    loaded = C.load_profile("70", "perf")
    assert loaded.general.appid == "70" and loaded.env.vars == {"P": "1"}
    assert C.profiles_dir("70").is_dir()
    C.delete_profile("70", "perf")
    assert "perf" not in C.list_profiles("70")


def test_notes_multiline_roundtrip(xdg_env):
    cfg = C.GameConfig()
    cfg.general.appid = "12"
    cfg.notes.text = "line one\nline two: FSR off in menus"
    C.save(cfg)
    assert C.load("12").notes.text == "line one\nline two: FSR off in menus"


def test_notifications_roundtrip(xdg_env):
    cfg = C.GameConfig()
    cfg.general.appid = "11"
    assert cfg.notifications.notify_on_launch is True
    cfg.notifications.notify_on_launch = False
    C.save(cfg)
    assert C.load("11").notifications.notify_on_launch is False
    assert "[notifications]" in C.game_file("11").read_text()


def test_export_import_roundtrip(xdg_env, tmp_path):
    cfg = C.GameConfig()
    cfg.general.appid = "21"
    cfg.env.vars = {"A": "1"}
    C.save(cfg)
    C.save_defaults(C.GameConfig())
    dest = tmp_path / "backup.tar.gz"
    saved = C.export_configs(dest)
    assert saved.exists()
    (C.game_file("21")).unlink()
    C.xdg.defaults_file().unlink()
    imported = C.import_configs(dest)
    assert imported == ["21"]
    assert C.load("21").env.vars == {"A": "1"}


def test_import_rejects_junk(xdg_env, tmp_path):
    import io
    import tarfile

    evil = tmp_path / "evil.tar.gz"
    with tarfile.open(evil, "w:gz") as tar:
        for name in ("../escape.toml", "/abs.toml", "notes.txt"):
            info = tarfile.TarInfo(name)
            data = b"x"
            info.size = len(data)
            tar.addfile(info, io.BytesIO(data))
    try:
        C.import_configs(evil)
    except ValueError:
        pass
    else:
        raise AssertionError("junk archive accepted")
    assert C.list_appids() == []


def test_import_missing_file(xdg_env, tmp_path):
    try:
        C.import_configs(tmp_path / "nope.tar.gz")
    except ValueError:
        pass
    else:
        raise AssertionError("missing file accepted")


def test_show_menu_roundtrip(xdg_env):
    cfg = C.GameConfig()
    cfg.general.appid = "70"
    cfg.general.show_menu = True
    C.save(cfg)
    assert C.load("70").general.show_menu is True
    assert C.load("71").general.show_menu is False


def test_as_bool_strings(xdg_env):
    assert C._as_bool("false", True) is False
    assert C._as_bool("0", True) is False
    assert C._as_bool("off", True) is False
    assert C._as_bool("true", False) is True
    assert C._as_bool("YES", False) is True
    assert C._as_bool("maybe", True) is True
    assert C._as_bool("maybe", False) is False
    assert C._as_bool(1, False) is True


def test_string_bools_in_toml(xdg_env):
    from tksteamlaunch import xdg as xdgmod

    xdgmod.games_dir().mkdir(parents=True, exist_ok=True)
    (xdgmod.games_dir() / "72.toml").write_text(
        '[general]\nappid = "72"\n[gamemode]\nferal_gamemode = "false"\n', encoding="utf-8"
    )
    assert C.load("72").gamemode.feral_gamemode is False


def test_preferences_roundtrip(xdg_env):
    from tksteamlaunch import xdg as xdgmod

    prefs = C.load_preferences()
    assert prefs.show_preview is True and prefs.tray_enable is False
    assert prefs.tray_icon == "normal"
    prefs.show_preview = False
    prefs.tray_enable = True
    prefs.tray_icon = "mono"
    prefs.close_to_tray = True
    C.save_preferences(prefs)
    back = C.load_preferences()
    assert back.show_preview is False and back.tray_enable is True
    assert back.tray_icon == "mono" and back.close_to_tray is True
    assert back.minimize_to_tray is False
    text = xdgmod.preferences_file().read_text()
    assert "[ui]" in text and "tray_enable" in text


def test_preferences_invalid_values(xdg_env):
    from tksteamlaunch import xdg as xdgmod

    xdgmod.app_config_dir().mkdir(parents=True, exist_ok=True)
    xdgmod.preferences_file().write_text(
        '[ui]\nshow_preview = "no"\ntray_icon = "rainbow"\ntray_enable = true\n'
        "minimize_to_tray = true\n",
        encoding="utf-8",
    )
    back = C.load_preferences()
    assert back.show_preview is False
    assert back.tray_icon == "normal"
    assert back.minimize_to_tray is True


def test_winetricks_runs_and_skips_repeat(xdg_env, fake_bin, monkeypatch, tmp_path):
    from tksteamlaunch import proton as pm

    calls = tmp_path / "calls.log"
    fake_bin(
        "protontricks",
        f'#!/bin/sh\necho "$@" >> "{calls}"\nexit 0\n',
    )
    assert pm.run_winetricks("75", ["dotnet48", "vcrun2022"]) == []
    assert "75 -q dotnet48 vcrun2022" in calls.read_text()
    calls.unlink()
    assert pm.run_winetricks("75", ["vcrun2022", "dotnet48"]) == []
    assert not calls.exists()  # fingerprint skips reinstall
    assert "non-Steam" in pm.run_winetricks("abc", ["dotnet48"])[0]


def test_winetricks_missing_binary(xdg_env, monkeypatch, tmp_path):
    from tksteamlaunch import proton as pm

    monkeypatch.setenv("PATH", str(tmp_path))
    assert "not found" in pm.run_winetricks("76", ["dotnet48"])[0]
    assert pm.run_winetricks("76", []) == []


def test_diff_vs_defaults(xdg_env):
    cfg = C.GameConfig()
    cfg.general.appid = "90"
    assert C.diff_vs_defaults(cfg) == ""
    cfg.env.vars = {"A": "1"}
    diff = C.diff_vs_defaults(cfg)
    assert '"A" = "1"' in diff and diff.startswith("---")


def test_flavor_prefix_boundaries():
    from tksteamlaunch import proton as pm

    assert pm.flavor("proton-cachyos-slr") == "cachyos"
    assert pm.flavor("GE-Proton9-15") == "ge"
    assert pm.flavor("DW-Proton Latest") == "dw"
    assert pm.flavor("dwproton-10") == "dw"
    assert pm.flavor("proton_9") == "valve"
    assert pm.flavor("generic-tool") == "valve"
    assert pm.flavor("") == "valve"


def test_menu_timeout_roundtrip_and_clamp(xdg_env):
    cfg = C.GameConfig()
    cfg.general.appid = "74"
    cfg.general.menu_timeout = 15
    C.save(cfg)
    assert C.load("74").general.menu_timeout == 15
    from tksteamlaunch import xdg as xdgmod

    xdgmod.games_dir().mkdir(parents=True, exist_ok=True)
    (xdgmod.games_dir() / "75.toml").write_text(
        '[general]\nappid = "75"\nmenu_timeout = -5\n', encoding="utf-8"
    )
    assert C.load("75").general.menu_timeout == 0


def test_control_chars_roundtrip(xdg_env):
    import tomllib

    cfg = C.GameConfig()
    cfg.general.appid = "90"
    cfg.notes.text = "linha1\r\nlinha2\ttab\x1besc\x00nul"
    cfg.env.vars = {"K": "v\r2"}
    path = C.save(cfg)
    tomllib.loads(path.read_text(encoding="utf-8"))  # file stays parseable
    loaded = C.load("90")
    assert loaded.notes.text == cfg.notes.text
    assert loaded.env.vars == {"K": "v\r2"}


def test_quoted_keys_roundtrip(xdg_env):
    cfg = C.GameConfig()
    cfg.general.appid = "91"
    cfg.extra = {"future section": {'weird "key"': "kept"}}
    C.save(cfg)
    assert C.load("91").extra == {"future section": {'weird "key"': "kept"}}


def test_save_is_atomic_and_leaves_no_tmp(xdg_env, monkeypatch):
    cfg = C.GameConfig()
    cfg.general.appid = "92"
    cfg.notes.text = "first"
    C.save(cfg)
    path = C.game_file("92")
    before = path.read_text(encoding="utf-8")

    def boom(*a, **k):
        raise OSError("disk full")

    monkeypatch.setattr(C.os, "replace", boom)
    cfg.notes.text = "second"
    try:
        C.save(cfg)
    except OSError:
        pass
    else:
        raise AssertionError("save should propagate the failed rename")
    monkeypatch.undo()
    assert path.read_text(encoding="utf-8") == before  # original intact
    assert not list(path.parent.glob(".*.tmp"))  # no temp litter


def test_save_sweeps_stale_crash_tmps(xdg_env):
    cfg = C.GameConfig()
    cfg.general.appid = "93"
    C.save(cfg)
    path = C.game_file("93")
    stale = path.parent / f".{path.name}.deadbeef.tmp"
    stale.write_text("crash leftover", encoding="utf-8")
    cfg.notes.text = "after crash"
    C.save(cfg)
    assert not stale.exists()
    assert not list(path.parent.glob(".*.tmp"))
    assert C.load("93").notes.text == "after crash"


def test_toml_error_reports_and_stays_quiet(xdg_env):
    assert C.toml_error(C.game_file("999")) is None  # missing file
    cfg = C.GameConfig()
    cfg.general.appid = "93"
    C.save(cfg)
    assert C.toml_error(C.game_file("93")) is None  # valid file
    C.game_file("94").parent.mkdir(parents=True, exist_ok=True)
    C.game_file("94").write_text("[general\noops", encoding="utf-8")
    assert "table" in (C.toml_error(C.game_file("94")) or "")


def test_load_with_warning_missing_file(xdg_env):
    cfg, warning = C.load_with_warning("100")
    assert warning is None
    assert cfg.general.appid == "100"


def test_load_with_warning_valid_file(xdg_env):
    cfg = C.GameConfig()
    cfg.general.appid = "101"
    cfg.pre_post.pre_command = "/ok.sh"
    C.save(cfg)
    loaded, warning = C.load_with_warning("101")
    assert warning is None
    assert loaded.pre_post.pre_command == "/ok.sh"


def test_load_with_warning_invalid_toml(xdg_env):
    C.game_file("102").parent.mkdir(parents=True, exist_ok=True)
    C.game_file("102").write_text("[general\nappid = oops", encoding="utf-8")
    loaded, warning = C.load_with_warning("102")
    assert loaded.general.appid == "102"  # falls back, keeps appid
    assert warning and "invalid TOML" in warning and "overwrite" in warning


def test_load_with_warning_unreadable_file(xdg_env, monkeypatch):
    cfg = C.GameConfig()
    cfg.general.appid = "103"
    C.save(cfg)

    def _denied(*a, **k):
        raise PermissionError("denied")

    monkeypatch.setattr(C.tomllib, "load", _denied)
    assert "unreadable" in (C.toml_error(C.game_file("103")) or "")
    loaded, warning = C.load_with_warning("103")
    assert loaded.general.appid == "103"
    assert warning and "could not be read" in warning


def test_preferences_unreadable_falls_back_to_defaults(xdg_env, monkeypatch):
    from tksteamlaunch import xdg as xdgmod

    xdgmod.preferences_file().parent.mkdir(parents=True, exist_ok=True)
    xdgmod.preferences_file().write_text("[ui]\nshow_preview = false\n", encoding="utf-8")

    def _denied(*a, **k):
        raise PermissionError("denied")

    monkeypatch.setattr(C.tomllib, "load", _denied)
    prefs = C.load_preferences()  # must not raise: dialogs stay open
    assert prefs.show_preview is True


def test_load_effective_uses_active_profile(xdg_env):
    live = C.GameConfig()
    live.general.appid = "110"
    live.pre_post.pre_command = "/live.sh"
    live.general.active_profile = "p1"
    C.save(live)
    prof = C.GameConfig()
    prof.general.appid = "110"
    prof.pre_post.pre_command = "/prof.sh"
    C.save_profile("110", "p1", prof)
    assert C.load_effective("110").pre_post.pre_command == "/prof.sh"


def test_load_effective_no_selection_uses_live(xdg_env):
    cfg = C.GameConfig()
    cfg.general.appid = "111"
    cfg.pre_post.pre_command = "/live.sh"
    C.save(cfg)
    assert C.load_effective("111").pre_post.pre_command == "/live.sh"


def test_load_effective_dangling_profile_falls_back_to_live(xdg_env):
    cfg = C.GameConfig()
    cfg.general.appid = "112"
    cfg.pre_post.pre_command = "/live.sh"
    cfg.general.active_profile = "gone"
    C.save(cfg)
    assert C.load_effective("112").pre_post.pre_command == "/live.sh"


def test_load_effective_unreadable_profile_falls_back_to_live(xdg_env):
    cfg = C.GameConfig()
    cfg.general.appid = "113"
    cfg.pre_post.pre_command = "/live.sh"
    cfg.general.active_profile = "bad"
    C.save(cfg)
    C.save_profile("113", "bad", cfg)
    C.profile_file("113", "bad").write_text("[general\nappid = oops", encoding="utf-8")
    assert C.load_effective("113").pre_post.pre_command == "/live.sh"


def test_orphaned_profiles(xdg_env):
    cfg = C.GameConfig()
    cfg.general.appid = "140"
    C.save(cfg)
    C.save_profile("140", "p1", cfg)
    ghost = C.GameConfig()
    ghost.general.appid = "141"
    C.save_profile("141", "p1", ghost)
    C.save_profile("141", "p2", ghost)
    C.game_file("141").unlink(missing_ok=True)
    C.profiles_dir("142").mkdir(parents=True)  # empty dir: nothing to clean
    assert C.orphaned_profiles() == [("141", 2)]


def test_display_config_roundtrip(xdg_env):
    cfg = C.GameConfig()
    cfg.general.appid = "160"
    cfg.display.provider = "plasma"
    cfg.display.output = "DP-3"
    cfg.display.mode = "1920x1080@60"
    C.save(cfg)
    back = C.load("160")
    assert back.display.provider == "plasma"
    assert back.display.output == "DP-3"
    assert back.display.mode == "1920x1080@60"
    assert "[display]" in C.game_file("160").read_text()


def test_column_layout_prefs_roundtrip(xdg_env):
    prefs = C.load_preferences()
    prefs.column_order = "0,2,1,3"
    prefs.hidden_columns = "2"
    C.save_preferences(prefs)
    back = C.load_preferences()
    assert back.column_order == "0,2,1,3"
    assert back.hidden_columns == "2"
    prefs.hidden_columns = "x,1,,2"
    C.save_preferences(prefs)
    assert C.load_preferences().hidden_columns == "1,2"


def test_tray_quick_prefs_roundtrip(xdg_env):
    prefs = C.load_preferences()
    assert prefs.tray_quick_launch is True and prefs.tray_quick_count == 5
    prefs.tray_quick_launch = False
    prefs.tray_quick_count = 99
    C.save_preferences(prefs)
    back = C.load_preferences()
    assert back.tray_quick_launch is False and back.tray_quick_count == 10
    prefs.tray_quick_count = 0
    C.save_preferences(prefs)
    assert C.load_preferences().tray_quick_count == 1


def test_config_version_stamped_and_legacy_loads(xdg_env):
    cfg = C.GameConfig()
    cfg.general.appid = "190"
    C.save(cfg)
    assert "config_version = 1" in C.game_file("190").read_text()
    C.game_file("191").parent.mkdir(parents=True, exist_ok=True)
    C.game_file("191").write_text('[general]\nappid = "191"\n', encoding="utf-8")
    assert C.load("191").general.appid == "191"  # pre-versioning loads as-is


def test_config_version_newer_raises(xdg_env):
    C.game_file("192").parent.mkdir(parents=True, exist_ok=True)
    C.game_file("192").write_text(
        '[general]\nappid = "192"\nconfig_version = 99\n', encoding="utf-8"
    )
    try:
        C.load("192")
    except C.ConfigVersionError as e:
        assert "99" in str(e)
    else:
        raise AssertionError("newer config must raise")
    cfg, warning = C.load_with_warning("192")
    assert cfg.general.appid == "192" and warning and "newer" in warning


def test_load_effective_newer_falls_back(xdg_env):
    live = C.GameConfig()
    live.general.appid = "193"
    live.pre_post.pre_command = "/live.sh"
    C.save(live)
    C.game_file("193").write_text(
        C.game_file("193").read_text().replace("config_version = 1", "config_version = 99"),
        encoding="utf-8",
    )
    assert C.load_effective("193").pre_post.pre_command == ""
    prof = C.GameConfig()
    prof.general.appid = "194"
    C.save(prof)
    C.save_profile("194", "p1", prof)
    C.profile_file("194", "p1").write_text(
        C.profile_file("194", "p1")
        .read_text()
        .replace("config_version = 1", "config_version = 99"),
        encoding="utf-8",
    )
    live2 = C.GameConfig()
    live2.general.appid = "194"
    live2.pre_post.pre_command = "/live.sh"
    live2.general.active_profile = "p1"
    C.save(live2)
    assert C.load_effective("194").pre_post.pre_command == "/live.sh"


def test_export_import_includes_profiles(xdg_env, tmp_path):
    cfg = C.GameConfig()
    cfg.general.appid = "200"
    cfg.general.active_profile = "p1"
    cfg.env.vars = {"A": "1"}
    C.save(cfg)
    prof = C.GameConfig()
    prof.general.appid = "200"
    prof.env.vars = {"P": "2"}
    C.save_profile("200", "p1", prof)
    dest = tmp_path / "backup.tar.gz"
    C.export_configs(dest)
    C.game_file("200").unlink()
    shutil.rmtree(C.profiles_dir("200"))
    C.import_configs(dest)
    assert C.load("200").env.vars == {"A": "1"}
    assert C.load("200").general.active_profile == "p1"
    assert C.load_profile("200", "p1").env.vars == {"P": "2"}


def test_import_rejects_nested_profiles(xdg_env, tmp_path):
    import io
    import tarfile

    evil = tmp_path / "evil.tar.gz"
    with tarfile.open(evil, "w:gz") as tar:
        for name in ("profiles/a/b/c.toml", "profiles/../escape.toml"):
            info = tarfile.TarInfo(name)
            data = b"x"
            info.size = len(data)
            tar.addfile(info, io.BytesIO(data))
    try:
        C.import_configs(evil)
    except ValueError:
        pass
    else:
        raise AssertionError("nested profile paths accepted")
    assert C.list_appids() == []


def test_clone_game(xdg_env):
    cfg = C.GameConfig()
    cfg.general.appid = "201"
    cfg.env.vars = {"A": "1"}
    C.save(cfg)
    C.save_profile("201", "p1", cfg)
    C.clone_game("201", "202")
    assert C.load("202").env.vars == {"A": "1"}
    assert C.load_profile("202", "p1").env.vars == {"A": "1"}
    try:
        C.clone_game("201", "201")
    except ValueError:
        pass
    else:
        raise AssertionError("self-clone accepted")
    try:
        C.clone_game("999", "203")
    except ValueError:
        pass
    else:
        raise AssertionError("missing source accepted")


def test_clone_replaces_dest_profiles(xdg_env):
    cfg = C.GameConfig()
    cfg.general.appid = "206"
    C.save(cfg)
    C.save_profile("206", "p1", cfg)
    stale = C.GameConfig()
    stale.general.appid = "207"
    C.save(stale)
    C.save_profile("207", "stale", stale)
    C.clone_game("206", "207")
    assert C.list_profiles("207") == ["p1"]


def test_export_skips_nested_profile_junk(xdg_env, tmp_path):
    import tarfile

    cfg = C.GameConfig()
    cfg.general.appid = "208"
    C.save(cfg)
    C.save_profile("208", "p1", cfg)
    nested = C.profiles_dir("208") / "deep" / "x.toml"
    nested.parent.mkdir(parents=True)
    nested.write_text("[general]\n")
    dest = tmp_path / "b.tar.gz"
    C.export_configs(dest)
    with tarfile.open(dest, "r:gz") as tar:
        assert "profiles/208/deep/x.toml" not in tar.getnames()
        assert "profiles/208/p1.toml" in tar.getnames()


def test_appid_paths_cannot_escape(xdg_env):
    from tksteamlaunch import xdg as xdgmod
    from tksteamlaunch.launcher import proton_log_dir

    for bad in ("../../evil", "/abs", "a/b", ""):
        assert xdgmod.game_log_file(bad).parent == xdgmod.games_log_dir()
        assert ".." not in proton_log_dir(bad).parts[-3:]
        assert C.game_file(bad).parent == C.xdg.games_dir()


def test_language_prefs_roundtrip_and_clamp(xdg_env):
    prefs = C.load_preferences()
    assert prefs.language == "system"
    prefs.language = "pt_BR"
    C.save_preferences(prefs)
    assert C.load_preferences().language == "pt_BR"
    prefs.language = "!!!junk!!!"
    C.save_preferences(prefs)
    assert C.load_preferences().language == "system"


def test_export_import_includes_preferences(xdg_env, tmp_path):
    prefs = C.load_preferences()
    prefs.tray_quick_count = 8
    prefs.language = "pt_BR"
    C.save_preferences(prefs)
    dest = tmp_path / "backup.tar.gz"
    C.export_configs(dest)
    prefs2 = C.load_preferences()
    prefs2.tray_quick_count = 5
    prefs2.language = "system"
    C.save_preferences(prefs2)
    C.import_configs(dest)
    back = C.load_preferences()
    assert (back.tray_quick_count, back.language) == (8, "pt_BR")
