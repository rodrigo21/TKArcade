"""Config load/save: snapshots, defaults fallback, enums, forward-compat."""

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


def test_ui_show_preview_roundtrip(xdg_env):
    assert C.GameConfig().ui.show_preview is True
    cfg = C.GameConfig()
    cfg.general.appid = "73"
    cfg.ui.show_preview = False
    C.save(cfg)
    assert C.load("73").ui.show_preview is False
    text = C.game_file("73").read_text()
    assert "[ui]" in text and "show_preview" in text
