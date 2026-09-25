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
