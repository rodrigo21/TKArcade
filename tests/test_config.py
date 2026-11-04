"""Config load/save: snapshots, defaults fallback, enums, forward-compat."""

import shutil
from pathlib import Path

from tkarcade import config as C


def test_categories_normalised(xdg_env):
    cfg = C.GameConfig()
    cfg.general.appid = "local-tags"
    cfg.general.categories = [" Action ", "action", "", "Retro"]
    C.save(cfg)
    assert C.load("local-tags").general.categories == ["Action", "Retro"]


def test_categories_store_roundtrip(xdg_env):
    assert C.load_categories() == []
    C.save_categories(
        [
            C.Category(" Retro "),
            C.Category("Action", "applications-games"),
            C.Category("action"),
        ]
    )
    assert [(c.name, c.icon) for c in C.load_categories()] == [
        ("Action", "applications-games"),
        ("Retro", "folder"),
    ]
    assert C.categories_file().is_file()
    C.save_categories([])
    assert C.load_categories() == []


def test_save_is_full_snapshot(xdg_env):
    cfg = C.GameConfig()
    cfg.general.appid = "8"
    text = C.save(cfg).read_text()
    assert 'gameid = "8"' in text
    assert 'type = ""' in text and "custom_prefix" in text


def test_save_requires_game_id(xdg_env):
    import pytest

    cfg = C.GameConfig()
    with pytest.raises(ValueError):
        C.save(cfg)
    cfg.general.appid = "   "
    with pytest.raises(ValueError):
        C.save(cfg)
    assert not C.game_file("unknown").exists()


def test_missing_file_falls_back_to_defaults(xdg_env):
    d = C.load_defaults()
    d.env.vars = {"D": "9"}
    C.save_defaults(d)
    assert C.load("nope").env.vars == {"D": "9"}


def test_save_defaults_drops_per_game_keys(xdg_env):
    cfg = C.GameConfig()
    cfg.general.name = "Template Name"
    cfg.general.categories = ["Retro"]
    cfg.general.custom_executable = "/tmp/game.exe"
    cfg.general.launch_cwd = "/tmp"
    cfg.general.active_profile = "main"
    cfg.general.show_menu = True
    cfg.metadata.version = "1.0"
    cfg.runtime.type = "proton"
    cfg.runtime.tool = "GE-Proton9-20"
    cfg.graphics.dxvk = True
    cfg.audio.sink = "alsa_output.hdmi"
    cfg.debug.proton_log = True
    cfg.artwork.cover = "cover.png"
    cfg.notes.text = "hello"
    cfg.gamemode.feral_gamemode = True
    C.save_defaults(cfg)
    text = C.xdg.defaults_file().read_text()
    for section in ("metadata", "runtime", "graphics", "audio", "debug", "artwork", "notes"):
        assert f"[{section}]" not in text
    for line in (
        'name = "Template Name"',
        "categories =",
        "custom_executable =",
        "launch_cwd =",
        "active_profile =",
    ):
        assert line not in text
    assert "show_menu = true" in text
    assert "feral_gamemode = true" in text
    back = C.load_defaults()
    assert back.runtime.type == ""
    assert back.general.categories == []
    assert back.notes.text == ""
    assert back.gamemode.feral_gamemode is True


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
    assert C.RuntimeType.NATIVE == "native"
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


def test_prepare_fresh_prefix(monkeypatch, tmp_path):
    from tkarcade import proton as pm

    pfx = tmp_path / "compatdata" / "70" / "pfx"
    pfx.mkdir(parents=True)
    (pfx / "save.dat").write_text("x")
    monkeypatch.setenv("STEAM_COMPAT_DATA_PATH", str(tmp_path / "compatdata" / "70"))
    assert pm.prepare_fresh_prefix("70") == (True, [])
    assert not (tmp_path / "compatdata" / "70").exists()
    assert pm.prepare_fresh_prefix("70")[0] is True
    assert "nothing to delete" in pm.prepare_fresh_prefix("70")[1][0]
    monkeypatch.delenv("STEAM_COMPAT_DATA_PATH")
    ok, warnings = pm.prepare_fresh_prefix("70")
    assert ok is False and "missing" in warnings[0]


def test_prepare_fresh_prefix_refuses_non_prefix(monkeypatch, tmp_path):
    from tkarcade import proton as pm

    victim = tmp_path / "precious"
    victim.mkdir()
    (victim / "save.dat").write_text("x")
    monkeypatch.setenv("STEAM_COMPAT_DATA_PATH", str(victim))
    ok, warnings = pm.prepare_fresh_prefix("70")
    assert ok is False and "refused" in warnings[0]
    assert (victim / "save.dat").exists()  # untouched
    nested = tmp_path / "steamapps" / "common" / "70"
    nested.mkdir(parents=True)
    monkeypatch.setenv("STEAM_COMPAT_DATA_PATH", str(nested))
    ok, warnings = pm.prepare_fresh_prefix("70")
    assert ok is False and "refused" in warnings[0]
    assert nested.exists()


def test_prepare_fresh_prefix_refuses_another_game(monkeypatch, tmp_path):
    from tkarcade import proton as pm

    other = tmp_path / "compatdata" / "71"
    (other / "pfx").mkdir(parents=True)
    monkeypatch.setenv("STEAM_COMPAT_DATA_PATH", str(other))
    ok, warnings = pm.prepare_fresh_prefix("70")
    assert ok is False and "refused" in warnings[0]
    assert (other / "pfx").exists()
    assert pm.prepare_fresh_prefix("local-70")[0] is False
    assert (other / "pfx").exists()


def test_prepare_fresh_prefix_uses_the_configured_prefix(monkeypatch, tmp_path):
    from tkarcade import proton as pm

    env_prefix = tmp_path / "compatdata" / "70"
    (env_prefix / "pfx").mkdir(parents=True)
    configured = tmp_path / "custom" / "compatdata" / "70"
    (configured / "pfx").mkdir(parents=True)
    monkeypatch.setenv("STEAM_COMPAT_DATA_PATH", str(env_prefix))
    assert pm.prepare_fresh_prefix("70", str(configured)) == (True, [])
    assert not configured.exists()
    assert (env_prefix / "pfx").exists()


def test_prepare_fresh_prefix_refuses_a_symlink(monkeypatch, tmp_path):
    from tkarcade import proton as pm

    real = tmp_path / "real"
    (real / "pfx").mkdir(parents=True)
    link = tmp_path / "compatdata" / "70"
    link.parent.mkdir()
    link.symlink_to(real, target_is_directory=True)
    monkeypatch.setenv("STEAM_COMPAT_DATA_PATH", str(link))
    ok, warnings = pm.prepare_fresh_prefix("70")
    assert ok is False and "symlink" in warnings[0]
    assert link.is_symlink() and (real / "pfx").exists()


def test_sections_covered_by_key_map():
    assert set(C.to_toml_dict(C.GameConfig())) == set(C.SECTION_KEYS)


def test_save_stamps_installed_at(xdg_env):
    cfg = C.GameConfig()
    cfg.general.appid = "424242"
    path = C.save(cfg)
    stamp = C.load("424242").general.installed_at
    assert stamp and C.installed_stamp(path)
    cfg = C.load("424242")
    cfg.general.installed_at = "2026-01-02T03:04:05-03:00"
    C.save(cfg)
    assert C.load("424242").general.installed_at == "2026-01-02T03:04:05-03:00"


def test_save_backfills_installed_at_from_birth_time(xdg_env):
    cfg = C.GameConfig()
    cfg.general.appid = "local-old"
    path = C.save(cfg)
    text = "\n".join(
        line
        for line in path.read_text(encoding="utf-8").splitlines()
        if not line.startswith("installed_at")
    )
    path.write_text(text + "\n", encoding="utf-8")
    expected = C.installed_stamp(path)
    C.save(C.load("local-old"))
    assert C.load("local-old").general.installed_at == expected


def test_defaults_and_diff_skip_installed_at(xdg_env):
    defaults = C.load_defaults()
    defaults.general.installed_at = "2020-01-01T00:00:00+00:00"
    C.save_defaults(defaults)
    assert C.load_defaults().general.installed_at == ""
    cfg = C.GameConfig()
    cfg.general.appid = "70"
    C.save(cfg)
    assert "installed_at" not in C.diff_vs_defaults(C.load("70"))


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


def test_export_import_roundtrip(xdg_env, tmp_path):
    cfg = C.GameConfig()
    cfg.general.appid = "21"
    cfg.env.vars = {"A": "1"}
    C.save(cfg)
    C.save_defaults(C.GameConfig())
    C.save_categories([C.Category("Action", "applications-games")])
    dest = tmp_path / "backup.tar.gz"
    saved = C.export_configs(dest)
    assert saved.exists()
    (C.game_file("21")).unlink()
    C.xdg.defaults_file().unlink()
    C.categories_file().unlink()
    imported = C.import_configs(dest)
    assert imported == ["21"]
    assert C.load("21").env.vars == {"A": "1"}
    assert [(c.name, c.icon) for c in C.load_categories()] == [("Action", "applications-games")]


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
    from tkarcade import xdg as xdgmod

    xdgmod.games_dir().mkdir(parents=True, exist_ok=True)
    (xdgmod.games_dir() / "72.toml").write_text(
        '[general]\nappid = "72"\n[gamemode]\nferal_gamemode = "false"\n', encoding="utf-8"
    )
    assert C.load("72").gamemode.feral_gamemode is False


def test_preferences_invalid_values(xdg_env):
    from tkarcade import xdg as xdgmod

    xdgmod.app_config_dir().mkdir(parents=True, exist_ok=True)
    xdgmod.preferences_file().write_text(
        '[ui]\nshow_preview = "no"\ntray_icon = "rainbow"\ntray_enable = true\n'
        'minimize_to_tray = true\ncolumn_layout_version = "x"\n',
        encoding="utf-8",
    )
    back = C.load_preferences()
    assert back.show_preview is False
    assert back.tray_icon == "normal"
    assert back.minimize_to_tray is True
    assert back.column_layout_version == 0


#: Every persisted leaf field, set to a distinctive value that sits inside
#: the documented range. A load that silently drops or re-clamps one of
#: them (a bound narrower than what the writers produce: the column-width
#: map was capped at 5 logicals while the table writes 13) fails
#: test_every_field_roundtrips below.
_GAME_FIELDS = {
    "general.name": "Test Name",
    "general.custom_executable": "/tmp/opencode/exe",
    "runtime.type": "proton",
    "general.show_menu": True,
    "general.menu_timeout": 42,
    "general.custom_prefix": "zink-run",
    "general.active_profile": "prof2",
    "general.categories": ["Action", "Retro"],
    "general.launch_args": "--foo --bar",
    "general.launch_cwd": "/tmp/opencode/cwd",
    "general.installed_at": "2026-01-02T03:04:05-03:00",
    "metadata.version": "v0.3.5",
    "metadata.date": "2026-10-29",
    "metadata.tag": "Beta",
    "env.vars": {"A": "1", "B": "two words"},
    "pre_post.pre_command": "prescript",
    "pre_post.pre_args": ["a", "b"],
    "pre_post.post_command": "postscript",
    "pre_post.post_args": ["c"],
    "pre_post.timeout": 90,
    "pre_post.run_in_shell": True,
    "gamemode.feral_gamemode": True,
    "gamemode.cachyos_game_performance": True,
    "gamescope.enable": True,
    "gamescope.args": "-f -H 1080",
    "mangohud.enable": True,
    "mangohud.args": "-x",
    "mangohud.config_file": "custom.conf",
    "mangohud.fps_limit": 120,
    "ludusavi.enable": True,
    "ludusavi.restore": False,
    "ludusavi.backup": False,
    "ludusavi.name_override": "Alt Name",
    "ludusavi.use_gui": False,
    "nightlight.disable_during_game": True,
    "nightlight.provider": "plasma",
    "display.provider": "x11",
    "display.output": "HDMI-A-1",
    "display.mode": "1920x1080@144",
    "display.dip_seconds": 12,
    "notifications.notify_on_launch": False,
    "notes.text": "line1\nline2",
    "debug.proton_log": True,
    "debug.winedebug": "+all",
    "session.inhibit_idle": True,
    "network.block_internet": True,
    "runtime.fresh_prefix": True,
    "runtime.winetricks_verbs": ["corefonts"],
    "runtime.prefix": "/tmp/opencode/prefix",
    "runtime.tool": "GE-Proton9-1",
    "runtime.prefix_name": "Doom Eternal",
    "runtime.steam_runtime": "sniper",
    "graphics.dxvk": True,
    "graphics.dxvk_version": "v2.6.2",
    "graphics.vkd3d": "proton",
    "graphics.vkd3d_version": "v2.13",
    "audio.sink": "alsa_output.pci-0000_00_1f.3.analog-stereo",
    "rtupscale.enable": True,
    "rtupscale.args": "--scale",
    "artwork.icon": "/tmp/opencode/i.png",
    "artwork.cover": "/tmp/opencode/c.png",
    "artwork.banner": "/tmp/opencode/b.png",
    "artwork.artwork_appid": "123",
}

_PREF_FIELDS = {
    "show_preview": False,
    "show_dependency_status": False,
    "tray_enable": True,
    "tray_icon": "mono",
    "minimize_to_tray": True,
    "close_to_tray": True,
    "sgdb_api_key": "secret-key",
    "artwork_source": "sgdb",
    "column_order": "1,2,3,4,5,6,7,8,9,10,11",
    "hidden_columns": "4,5",
    "column_widths": "1=210,2=90,11=150",
    "column_layout_version": 1,
    "tray_quick_launch": False,
    "tray_quick_count": 7,
    "language": "pt_BR",
    "main_window_size": "1600x900",
    "main_window_maximized": True,
    "drawer_mode": "overlay",
    "drawer_collapsed": False,
    "prefix_base": "/tmp/opencode/prefixes",
    "wine_binary": "/tmp/opencode/wine",
    "proton_dirs": "/tmp/opencode/proton-a:/tmp/opencode/proton-b",
    "dxvk_dirs": "/tmp/opencode/dxvk",
    "vkd3d_dirs": "/tmp/opencode/vkd3d",
    "dxvk_repo": "Someone/dxvk-sarek",
    "vkd3d_repo": "Someone/vkd3d-fork",
}


def _walk(obj, path):
    for part in path.split("."):
        obj = getattr(obj, part)
    return obj


def test_every_field_roundtrips(xdg_env):
    cfg = C.GameConfig()
    cfg.general.appid = "424242"
    for path, value in _GAME_FIELDS.items():
        target = _walk(cfg, path.rpartition(".")[0]) if "." in path else cfg
        setattr(target, path.rpartition(".")[2], value)
    cfg.extra = {"future": {"k": "v"}}
    C.save(cfg)
    back = C.load("424242")
    for path, value in _GAME_FIELDS.items():
        assert _walk(back, path) == value, f"{path} did not survive save/load"
    assert back.extra == {"future": {"k": "v"}}

    prefs = C.Preferences()
    for name, value in _PREF_FIELDS.items():
        setattr(prefs, name, value)
    C.save_preferences(prefs)
    loaded = C.load_preferences()
    for name, value in _PREF_FIELDS.items():
        assert getattr(loaded, name) == value, f"{name} did not survive save/load"


def test_prefix_dir_resolution(xdg_env, monkeypatch):
    from tkarcade import xdg as xdgmod

    monkeypatch.setenv("XDG_DATA_HOME", "/tmp/opencode/data")
    assert C.prefix_dir("local-doom") == Path("/tmp/opencode/data/tkarcade/prefixes/local-doom")
    assert C.prefix_dir("../evil") == Path("/tmp/opencode/data/tkarcade/prefixes/evil")
    assert C.prefix_dir("local-doom", base="/tmp/opencode/base") == Path(
        "/tmp/opencode/base/local-doom"
    )
    # The per-game dir is the base: the prefix is always a subfolder.
    assert C.prefix_dir("local-doom", per_game="/tmp/opencode/custom") == Path(
        "/tmp/opencode/custom/local-doom"
    )
    assert C.prefix_dir("local-doom", base="/tmp/opencode/base", name="Doom Eternal") == Path(
        "/tmp/opencode/base/DoomEternal"
    )
    # The explicit name wins over the game name, which wins over the AppID.
    assert C.prefix_dir(
        "local-doom", per_game="/tmp/opencode/custom", name="Friendly Doom"
    ) == Path("/tmp/opencode/custom/FriendlyDoom")
    assert C.prefix_dir("local-doom", game_name="TK's good-game_1") == Path(
        "/tmp/opencode/data/tkarcade/prefixes/TKsGoodGame1"
    )
    assert C.prefix_dir("local-doom", name="Doom Eternal", game_name="Other") == Path(
        "/tmp/opencode/data/tkarcade/prefixes/DoomEternal"
    )
    assert C.prefix_dir("local-doom", game_name="!!!") == Path(
        "/tmp/opencode/data/tkarcade/prefixes/local-doom"
    )
    # Blank or dot-only names fall back to the safe AppID.
    assert C.prefix_dir("local-doom", name="   ") == Path(
        "/tmp/opencode/data/tkarcade/prefixes/local-doom"
    )
    assert C.prefix_dir("local-doom", name="../") == Path(
        "/tmp/opencode/data/tkarcade/prefixes/local-doom"
    )
    assert xdgmod.default_prefix_base() == Path("/tmp/opencode/data/tkarcade/prefixes")


def test_prefix_target_resolution(xdg_env, monkeypatch, tmp_path):
    compatdata = tmp_path / "steamapps" / "compatdata" / "77"
    compatdata.mkdir(parents=True)
    monkeypatch.setenv("STEAM_ROOT", str(tmp_path))

    steam = C.GameConfig()
    steam.general.appid = "steam-77"
    assert C.prefix_target("steam-77", steam) == C.PrefixTarget(
        compatdata, compatdata / "pfx", False
    )
    assert C.prefix_target("steam-78", steam) is None  # never launched

    steam.runtime.prefix = "~/custom-prefix"
    custom = Path.home() / "custom-prefix"
    assert C.prefix_target("steam-77", steam) == C.PrefixTarget(custom, custom / "pfx", True)

    local = C.GameConfig()
    local.general.appid = "local-doom"
    local.general.name = "Doom"
    local.runtime.prefix = str(tmp_path / "base")
    prefix = tmp_path / "base" / "Doom"
    assert C.prefix_target("local-doom", local) == C.PrefixTarget(prefix, prefix, True)

    prefs = C.load_preferences()
    prefs.prefix_base = str(tmp_path / "prefs")
    fallback = tmp_path / "prefs" / "local-gone"
    assert C.prefix_target("local-gone", None, prefs) == C.PrefixTarget(fallback, fallback, True)


def test_folder_stem_normalises_readable_names():
    from tkarcade import xdg as xdgmod

    assert xdgmod.folder_stem("TK's good-game_1") == "TKsGoodGame1"
    assert xdgmod.folder_stem("Friendly Doom") == "FriendlyDoom"
    assert xdgmod.folder_stem("TK3DTests") == "TK3DTests"
    assert xdgmod.folder_stem("don\u2019t stop") == "DontStop"
    assert xdgmod.folder_stem("  ") == ""
    assert xdgmod.folder_stem("../") == ""
    assert xdgmod.folder_stem("") == ""


def test_iter_prefixes_only_complete_windows_prefixes(xdg_env, tmp_path):
    from tkarcade import xdg as xdgmod

    base = tmp_path / "prefixes"
    (base / "good" / "drive_c").mkdir(parents=True)
    (base / "good" / "system.reg").write_text("")
    (base / "incomplete" / "drive_c").mkdir(parents=True)
    (base / "plain").mkdir()
    (base / "file").write_text("")
    assert [p.name for p in xdgmod.iter_prefixes(str(base))] == ["good"]
    assert xdgmod.iter_prefixes(str(tmp_path / "missing")) == []


def test_winetricks_runs_and_skips_repeat(xdg_env, fake_bin, monkeypatch, tmp_path):
    from tkarcade import proton as pm

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
    from tkarcade import proton as pm

    monkeypatch.setenv("PATH", str(tmp_path))
    assert "not found" in pm.run_winetricks("76", ["dotnet48"])[0]
    assert pm.run_winetricks("76", []) == []


def test_winetricks_gui_command(xdg_env, fake_bin, monkeypatch, tmp_path):
    from tkarcade import proton as pm

    exe = fake_bin("protontricks")
    assert pm.gui_command("620") == ([str(exe), "--gui", "620"], "")
    assert "Steam AppID" in pm.gui_command("local-doom")[1]
    monkeypatch.setenv("PATH", str(tmp_path / "empty"))
    assert "Protontricks Was Not Found" in pm.gui_command("620")[1]


def test_diff_vs_defaults(xdg_env):
    cfg = C.GameConfig()
    cfg.general.appid = "90"
    assert C.diff_vs_defaults(cfg) == ""
    cfg.env.vars = {"A": "1"}
    diff = C.diff_vs_defaults(cfg)
    assert '"A" = "1"' in diff and diff.startswith("---")


def test_diff_hides_identity_fields(xdg_env):
    cfg = C.GameConfig()
    cfg.general.appid = "91"
    cfg.general.name = "My Game"
    cfg.general.active_profile = "p1"
    assert C.diff_vs_defaults(cfg) == ""


def test_flavor_prefix_boundaries():
    from tkarcade import proton as pm

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
    from tkarcade import xdg as xdgmod

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


def test_write_atomic_keeps_a_symlink(xdg_env, tmp_path):
    """A dotfiles symlink keeps pointing at its target after a write."""
    target = tmp_path / "real.toml"
    target.write_text("old", encoding="utf-8")
    link = tmp_path / "link.toml"
    link.symlink_to(target)
    C.write_atomic(link, "new")
    assert link.is_symlink()
    assert target.read_text(encoding="utf-8") == "new"


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
    from tkarcade import xdg as xdgmod

    xdgmod.preferences_file().parent.mkdir(parents=True, exist_ok=True)
    xdgmod.preferences_file().write_text("[ui]\nshow_preview = false\n", encoding="utf-8")

    def _denied(*a, **k):
        raise PermissionError("denied")

    monkeypatch.setattr(C.tomllib, "load", _denied)
    prefs = C.load_preferences()  # must not raise: dialogs stay open
    assert prefs.show_preview is False


def test_needs_newer_app(xdg_env):
    assert C.needs_newer_app(C.game_file("120")) is False  # missing
    C.game_file("120").parent.mkdir(parents=True, exist_ok=True)
    C.game_file("120").write_text("not toml [[[", encoding="utf-8")
    assert C.needs_newer_app(C.game_file("120")) is False  # unparsable
    cfg = C.GameConfig()
    cfg.general.appid = "121"
    C.save(cfg)
    assert C.needs_newer_app(C.game_file("121")) is False  # current stamp
    C.game_file("122").parent.mkdir(parents=True, exist_ok=True)
    C.game_file("122").write_text(
        '[general]\nappid = "122"\nconfig_version = 999\n', encoding="utf-8"
    )
    assert C.needs_newer_app(C.game_file("122")) is True


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


def test_column_width_prefs_roundtrip(xdg_env):
    prefs = C.load_preferences()
    prefs.column_widths = "1=210,2=90"
    C.save_preferences(prefs)
    assert C.load_preferences().column_widths == "1=210,2=90"
    # Every logical column of the 13-column table survives (0-12); only
    # out-of-range widths and unknown logics are dropped.
    prefs.column_widths = "x,1=5,2=99,9=50,3=3000,12=100,13=100"
    C.save_preferences(prefs)
    assert C.load_preferences().column_widths == "2=99,9=50,12=100"
    prefs.column_widths = "6=140,7=120,11=95"
    C.save_preferences(prefs)
    assert C.load_preferences().column_widths == "6=140,7=120,11=95"


def test_drawer_collapsed_prefs_roundtrip(xdg_env):
    prefs = C.load_preferences()
    assert prefs.drawer_collapsed is True
    prefs.drawer_collapsed = False
    C.save_preferences(prefs)
    assert C.load_preferences().drawer_collapsed is False


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
    from tkarcade import artwork, winetricks
    from tkarcade import xdg as xdgmod
    from tkarcade.launcher import proton_log_dir

    for bad in ("../../evil", "/abs", "a/b", ""):
        assert xdgmod.game_log_file(bad).parent == xdgmod.games_log_dir()
        assert ".." not in proton_log_dir(bad).parts[-3:]
        assert C.game_file(bad).parent == C.xdg.games_dir()
        assert winetricks.state_path(bad).parent == xdgmod.app_state_dir() / "winetricks"
        assert artwork.grid_path(bad, "cover").parent == xdgmod.app_cache_dir() / "grids"


def test_language_prefs_roundtrip_and_clamp(xdg_env):
    prefs = C.load_preferences()
    assert prefs.language == "system"
    prefs.language = "pt_BR"
    C.save_preferences(prefs)
    assert C.load_preferences().language == "pt_BR"
    prefs.language = "!!!junk!!!"
    C.save_preferences(prefs)
    assert C.load_preferences().language == "system"


def test_window_size_prefs_roundtrip_and_clamp(xdg_env):
    prefs = C.load_preferences()
    assert prefs.main_window_size == ""
    prefs.main_window_size = "1024x768"
    C.save_preferences(prefs)
    assert C.load_preferences().main_window_size == "1024x768"
    prefs.main_window_size = "100x100"
    C.save_preferences(prefs)
    assert C.load_preferences().main_window_size == "640x480"
    prefs.main_window_size = "junk"
    C.save_preferences(prefs)
    assert C.load_preferences().main_window_size == ""


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


def test_new_local_id_unique_slug(xdg_env):
    assert C.new_local_id("Doom") == "local-doom"
    cfg = C.GameConfig()
    cfg.general.appid = "local-doom"
    C.save(cfg)
    assert C.new_local_id("Doom") == "local-doom-2"
    assert C.new_local_id("213") == "local-213"


def test_local_slug_collapses_separators():
    assert C.local_slug("Bad Hero - Episode 1") == "bad-hero-episode-1"
    assert C.local_slug("Hero's Rhapsody -_- Jianghu Dream") == "heros-rhapsody-jianghu-dream"
    assert C.local_slug("Pokémon Café") == "pokemon-cafe"
    assert C.local_slug("  Straße  ") == "strasse"
    assert C.local_slug("Game v1.2") == "game-v1-2"
    assert C.local_slug("!!!") == ""
    assert C.local_slug("英雄伝説") == ""


def test_local_slug_truncates_long_names():
    slug = C.local_slug("A Very Long " + "Word " * 40 + "End")
    assert len(slug) <= C.SLUG_MAX
    assert not slug.endswith("-")


def test_new_local_id_hash_fallback(xdg_env):
    import hashlib

    jp = C.new_local_id("英雄伝説")
    digest = hashlib.sha1("英雄伝説".encode()).hexdigest()[:8]
    assert jp == f"local-{digest}"
    assert C.new_local_id("   ") == f"local-{hashlib.sha1(b'').hexdigest()[:8]}"


def _seed_legacy_game():
    """One local game carrying every file keyed by its old AppID."""
    from tkarcade import artwork, winetricks, xdg

    cfg = C.GameConfig()
    cfg.general.appid = "local-bad-hero---episode-1"
    cfg.general.name = "Bad Hero - Episode 1"
    C.save(cfg)
    C.save_profile(cfg.general.appid, "Default", cfg)
    artwork.manual_dir(cfg.general.appid).mkdir(parents=True)
    (artwork.manual_dir(cfg.general.appid) / "cover.png").write_bytes(b"png")
    artwork.grid_path(cfg.general.appid).parent.mkdir(parents=True, exist_ok=True)
    artwork.grid_path(cfg.general.appid).write_bytes(b"png")
    winetricks.state_path(cfg.general.appid).parent.mkdir(parents=True, exist_ok=True)
    winetricks.state_path(cfg.general.appid).write_text("{}")
    xdg.game_log_file(cfg.general.appid).parent.mkdir(parents=True, exist_ok=True)
    xdg.game_log_file(cfg.general.appid).write_text("log")
    prefix = C.prefix_dir(
        cfg.general.appid, "", C.load_preferences().prefix_base, "", cfg.general.name
    )
    (prefix / "drive_c").mkdir(parents=True)
    xdg.log_file().parent.mkdir(parents=True, exist_ok=True)
    xdg.log_file().write_text(
        "2026-10-01T10:00:00 appid=local-bad-hero---episode-1 exit=0 dur=5 cmd=game\n"
    )
    return cfg


def test_migrate_ids_renames_every_store(xdg_env):
    from tkarcade import artwork, winetricks, xdg

    old = "local-bad-hero---episode-1"
    new = "local-bad-hero-episode-1"
    _seed_legacy_game()
    prefix_old = C.prefix_dir(old, "", C.load_preferences().prefix_base, "", "Bad Hero - Episode 1")
    donor = C.GameConfig()
    donor.general.appid = "42"
    donor.artwork.artwork_appid = old
    C.save(donor)

    renamed = dict(C.migrate_ids())
    assert renamed[old] == new
    assert renamed["42"] == "steam-42"
    assert old not in C.list_appids() and new in C.list_appids()
    assert C.load(new).general.appid == new
    assert not C.game_file(old).exists()
    assert C.profiles_dir(new).joinpath("Default.toml").is_file()
    assert artwork.manual_dir(new).joinpath("cover.png").is_file()
    assert artwork.grid_path(new).is_file()
    assert winetricks.state_path(new).is_file()
    assert xdg.game_log_file(new).is_file()
    assert C.load("steam-42").artwork.artwork_appid == new
    assert f"appid={new}" in xdg.log_file().read_text()
    # The stem comes from the game name, so the AppID change leaves the
    # prefix exactly where it was.
    base = C.load_preferences().prefix_base
    migrated = C.load(new)
    assert migrated.runtime.prefix_name == ""
    assert (
        C.prefix_dir(
            new,
            migrated.runtime.prefix,
            base,
            migrated.runtime.prefix_name,
            migrated.general.name,
        )
        == prefix_old
    )
    assert (prefix_old / "drive_c").is_dir()
    # Idempotent.
    assert C.migrate_ids() == []


def _seed_legacy_steam_game():
    """One Steam game carrying every file keyed by its bare AppID."""
    from tkarcade import artwork, winetricks, xdg

    cfg = C.GameConfig()
    cfg.general.appid = "570"
    cfg.general.name = "Dota"
    C.save(cfg)
    C.save_profile("570", "Default", cfg)
    artwork.manual_dir("570").mkdir(parents=True)
    (artwork.manual_dir("570") / "cover.png").write_bytes(b"png")
    artwork.grid_path("570").parent.mkdir(parents=True, exist_ok=True)
    artwork.grid_path("570").write_bytes(b"png")
    winetricks.state_path("570").parent.mkdir(parents=True, exist_ok=True)
    winetricks.state_path("570").write_text("{}")
    xdg.game_log_file("570").parent.mkdir(parents=True, exist_ok=True)
    xdg.game_log_file("570").write_text("log")
    xdg.log_file().parent.mkdir(parents=True, exist_ok=True)
    xdg.log_file().write_text("2026-10-01T10:00:00 appid=570 exit=0 cmd=game\n")
    return cfg


def test_migrate_ids_renames_steam_stores(xdg_env):
    from tkarcade import artwork, winetricks, xdg

    _seed_legacy_steam_game()
    assert C.migrate_ids() == [("570", "steam-570")]
    assert C.load("steam-570").general.appid == "steam-570"
    assert not C.game_file("570").exists()
    assert C.profiles_dir("steam-570").joinpath("Default.toml").is_file()
    assert C.load_profile("steam-570", "Default").general.appid == "steam-570"
    assert 'gameid = "steam-570"' in C.profile_file("steam-570", "Default").read_text()
    # Steam art is keyed by the numeric AppID: the rename leaves it in place.
    assert artwork.manual_dir("steam-570").joinpath("cover.png").is_file()
    assert artwork.grid_path("steam-570").is_file()
    assert winetricks.state_path("steam-570").is_file()
    assert not winetricks.state_path("570").exists()
    assert xdg.game_log_file("steam-570").is_file()
    assert "appid=steam-570" in xdg.log_file().read_text()
    assert C.migrate_ids() == []


def test_migrate_ids_converts_bare_local(xdg_env):
    cfg = C.GameConfig()
    cfg.general.appid = "glxgears"
    cfg.general.name = "GlxGears"
    C.save(cfg)

    assert C.migrate_ids() == [("glxgears", "local-glxgears")]
    assert C.load("local-glxgears").general.name == "GlxGears"


def test_migrate_ids_steam_target_exists(xdg_env):
    old = C.GameConfig()
    old.general.appid = "570"
    old.general.name = "Old"
    C.save(old)
    new = C.GameConfig()
    new.general.appid = "steam-570"
    new.general.name = "New"
    C.save(new)

    assert C.migrate_ids() == []
    assert C.load("steam-570").general.name == "New"
    assert C.load("570").general.name == "Old"


def test_migrate_ids_skips_running(xdg_env):
    import json
    import os

    from tkarcade import running

    steam = C.GameConfig()
    steam.general.appid = "213"
    C.save(steam)
    busy_steam = C.GameConfig()
    busy_steam.general.appid = "214"
    C.save(busy_steam)
    busy = C.GameConfig()
    busy.general.appid = "local-running_game"
    busy.general.name = "Running Game"
    C.save(busy)
    for appid in ("214", "local-running_game"):
        running.record_path(appid).parent.mkdir(parents=True, exist_ok=True)
        record = {
            "appid": appid,
            "pid": os.getpid(),
            "start": running.process_start_time(os.getpid()),
        }
        running.record_path(appid).write_text(json.dumps(record))

    assert C.migrate_ids() == [("213", "steam-213")]
    assert C.game_file("steam-213").is_file()
    assert C.game_file("214").is_file()
    assert C.game_file("local-running_game").is_file()


def test_migrate_ids_collision_gets_suffix(xdg_env):
    first = C.GameConfig()
    first.general.appid = "local-doom---episode"
    first.general.name = "Doom - Episode"
    C.save(first)
    other = C.GameConfig()
    other.general.appid = "local-doom-episode"
    other.general.name = "Doom Episode"
    C.save(other)

    assert C.migrate_ids() == [("local-doom---episode", "local-doom-episode-2")]
    # A game already holding the clean slug keeps it.
    assert C.game_file("local-doom-episode").is_file()


def test_migrate_ids_keeps_hand_picked_ids(xdg_env):
    cfg = C.GameConfig()
    cfg.general.appid = "local-custom_id"
    cfg.general.name = "Something Else"
    C.save(cfg)
    clone = C.GameConfig()
    clone.general.appid = "local-new"
    clone.general.name = "Doom"
    C.save(clone)

    assert C.migrate_ids() == [("local-custom_id", "local-something-else")]
    assert C.game_file("local-new").is_file()
    assert C.load("local-new").general.name == "Doom"


def test_rename_appid_in_history(tmp_path):
    from tkarcade import history

    log = tmp_path / "launcher.log"
    log.write_text(
        "2026-10-01T10:00:00 appid=8 exit=0 cmd=x\n"
        "2026-10-01T11:00:00 appid=80 exit=0 cmd=x\n"
        "2026-10-01T12:00:00 appid=local-x---y exit=0 cmd=x\n"
    )
    assert history.rename_appid(log, "local-x---y", "local-x-y") == 1
    assert history.rename_appid(log, "8", "9") == 1  # never catches "80"
    texts = log.read_text().splitlines()
    assert "appid=local-x-y" in texts[2]
    assert "appid=9 exit=0" in texts[0]
    assert "appid=80 exit=0" in texts[1]
    assert history.rename_appid(log, "missing", "x") == 0


def test_import_tksteamlaunch_copies_missing_only(xdg_env, tmp_path, monkeypatch):
    import os
    from pathlib import Path

    legacy = Path(os.environ["XDG_CONFIG_HOME"]) / "tksteamlaunch"
    (legacy / "games").mkdir(parents=True)
    (legacy / "profiles" / "213").mkdir(parents=True)
    (legacy / "games" / "213.toml").write_text('[general]\nappid = "213"\n')
    (legacy / "profiles" / "213" / "P.toml").write_text('[general]\nappid = "213"\n')
    (legacy / "profiles" / "deep" / "x" / "Y.toml").parent.mkdir(parents=True, exist_ok=True)
    (legacy / "profiles" / "deep" / "x" / "Y.toml").write_text("y = 1\n")
    (legacy / "defaults.toml").write_text("[general]\n")
    imported, skipped = C.import_tksteamlaunch()
    assert skipped == []
    assert sorted(imported) == [
        "defaults.toml",
        "games/213.toml",
        "profiles/213/P.toml",
    ]
    assert C.game_file("213").is_file()
    imported2, skipped2 = C.import_tksteamlaunch()
    assert imported2 == []
    assert sorted(skipped2) == sorted(imported)
    assert C.load("213").general.appid == "213"


def test_import_tksteamlaunch_empty_legacy(xdg_env):
    import pytest

    with pytest.raises(ValueError):
        C.import_tksteamlaunch()


def test_clone_game_rewrites_appid(xdg_env):
    import tomllib

    cfg = C.GameConfig()
    cfg.general.appid = "211"
    cfg.general.active_profile = "p1"
    C.save(cfg)
    C.save_profile("211", "p1", cfg)
    C.clone_game("211", "212")
    dest = C.load("212")
    assert dest.general.appid == "212"
    assert dest.general.active_profile == "p1"  # selection survives (profiles cloned too)
    assert C.load_profile("212", "p1").general.appid == "212"
    with C.game_file("212").open("rb") as f:
        assert tomllib.load(f)["general"]["gameid"] == "212"


def test_prefs_cleaners_drop_nondecimal_digits(xdg_env):
    prefs = C.load_preferences()
    prefs.column_order = "0,1²,2"
    prefs.column_widths = "1=2²,2=99"
    C.save_preferences(prefs)  # must not raise on the ² pair
    back = C.load_preferences()
    assert back.column_order == "0,2"
    assert back.column_widths == "2=99"


def test_prefs_repo_cleaner_keeps_only_owner_name(xdg_env):
    prefs = C.load_preferences()
    prefs.dxvk_repo = "not a repo"
    prefs.vkd3d_repo = "/Someone/vkd3d-fork/"
    C.save_preferences(prefs)
    back = C.load_preferences()
    assert back.dxvk_repo == ""
    assert back.vkd3d_repo == "Someone/vkd3d-fork"


def test_pre_post_timeout_clamped(xdg_env):
    from tkarcade import xdg as xdgmod

    xdgmod.games_dir().mkdir(parents=True, exist_ok=True)
    C.game_file("214").write_text(
        '[general]\nappid = "214"\n[pre_post]\ntimeout = -5\n', encoding="utf-8"
    )
    assert C.load("214").pre_post.timeout == 1
    C.game_file("215").write_text(
        '[general]\nappid = "215"\n[pre_post]\ntimeout = 99999\n', encoding="utf-8"
    )
    assert C.load("215").pre_post.timeout == 3600


def test_runtime_axes_are_derived():
    """One stored axis: origin and platform come from the id and runtime."""
    assert C.platform_for("") == ""
    assert C.platform_for("bogus") == ""
    assert C.platform_for("native") == "Linux"
    assert C.platform_for("proton") == "Windows"
    assert C.platform_for("wine") == "Windows"
    assert C.platform_for("umu") == "Windows"

    assert C.runtime_label("", True) == ""
    assert C.runtime_label("proton", True) == "Steam Proton"
    assert C.runtime_label("native", True) == "Steam Runtime"
    assert C.runtime_label("native", False) == "Native"
    assert C.runtime_label("wine", False) == "Wine"
    assert C.runtime_label("umu", False) == "UMU"

    # A local native game names its Steam Linux Runtime; the column stays
    # short, because the full label only fits the dialog's combo.
    assert C.runtime_label("native", False, "sniper") == "Steam Runtime (sniper)"
    assert C.runtime_label("native", False, "bogus") == "Native"
    # Steam picks the runtime itself, so its label never carries one.
    assert C.runtime_label("native", True, "sniper") == "Steam Runtime"
    # Proton is Steam-exclusive and Wine/UMU are local-only, so an invalid
    # pairing labels nothing (the launcher refuses it at launch).
    assert C.runtime_label("proton", False, "sniper") == ""
    assert C.runtime_label("wine", True, "sniper") == ""
    assert C.runtime_label("umu", True, "sniper") == ""

    # The library column shortens the SLR names; the dialog keeps the full.
    assert C.runtime_short_label("native", True) == "SLR"
    assert C.runtime_short_label("native", False) == "Native"
    assert C.runtime_short_label("native", False, "scout") == "SLR 1.0"
    assert C.runtime_short_label("native", False, "steamrt4") == "SLR 4.0"
    assert C.runtime_short_label("native", False, "bogus") == "Native"
    assert C.runtime_short_label("proton", True) == "Steam Proton"


def test_steam_runtime_names():
    assert C.normalize_steam_runtime("  SNIPER ") == "sniper"
    assert C.normalize_steam_runtime("") == ""
    assert C.normalize_steam_runtime("steamrt5") == ""
    assert C.steam_runtime_label("soldier") == "Steam Linux Runtime 2.0 (soldier)"
    assert C.steam_runtime_label("steamrt4") == "Steam Linux Runtime 4.0 (steamrt4)"
    assert C.steam_runtime_label("bogus") == ""


def test_legacy_keys_load_as_unset(xdg_env, tmp_path, monkeypatch):
    """The dropped runtime key and platform label are ignored, not migrated."""
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "config"))
    path = tmp_path / "config" / "tkarcade" / "games" / "9.toml"
    path.parent.mkdir(parents=True)
    path.write_text(
        '[general]\nappid = "9"\nenvironment = "proton"\ngame_type = "native"\nplatform = "PC"\n'
    )
    cfg = C.load("9")
    assert cfg.runtime.type == ""
    assert not hasattr(cfg.general, "platform")
    C.save(cfg)
    # Full snapshots carry gameid now; the renamed and dropped keys are
    # known-but-ignored, while the older unknown keys ride along (forward
    # compat), never rewritten into the new one.
    text = path.read_text()
    assert 'type = ""' in text
    assert 'gameid = "9"' in text
    assert "\nappid = " not in text  # the key, not artwork_appid
    assert "environment" not in text
    assert 'game_type = "native"' in text


def test_artwork_source_defaults_to_steam_and_rejects_junk(xdg_env):
    from tkarcade import xdg as xdgmod

    assert C.load_preferences().artwork_source == "steam"
    prefs = C.load_preferences()
    prefs.artwork_source = "sgdb"
    C.save_preferences(prefs)
    assert C.load_preferences().artwork_source == "sgdb"
    text = (
        xdgmod.preferences_file()
        .read_text()
        .replace('artwork_source = "sgdb"', 'artwork_source = "bogus"')
    )
    xdgmod.preferences_file().write_text(text)
    assert C.load_preferences().artwork_source == "steam"


def test_move_legacy_prefix_folds_the_base_into_the_subfolder(xdg_env, tmp_path):
    base = tmp_path / "base"
    (base / "drive_c").mkdir(parents=True)
    (base / "system.reg").write_text("")
    (base / "user.reg").write_text("")
    (base / "stray").mkdir()
    (base / "stray" / "file.txt").write_text("x")
    ok, message = C.move_legacy_prefix(base, "MyGame")
    assert ok is True
    assert message.endswith(str(base / "MyGame"))
    moved = base / "MyGame"
    assert (moved / "drive_c").is_dir()
    assert (moved / "user.reg").is_file()
    assert (moved / "stray" / "file.txt").is_file()
    # The base is no longer a prefix: the next launch is a no-op.
    assert C.move_legacy_prefix(base, "MyGame") == (True, "")


def test_move_legacy_prefix_refuses_an_occupied_target(xdg_env, tmp_path):
    base = tmp_path / "base"
    (base / "drive_c").mkdir(parents=True)
    (base / "system.reg").write_text("")
    (base / "MyGame").mkdir()
    (base / "MyGame" / "keep.txt").write_text("x")
    ok, message = C.move_legacy_prefix(base, "MyGame")
    assert ok is False
    assert "already has files" in message
    assert (base / "drive_c").is_dir()  # nothing moved


def test_launch_folds_a_legacy_prefix_into_the_subfolder(xdg_env, tmp_path):
    from tkarcade import launcher as L

    base = tmp_path / "Wine"
    (base / "drive_c").mkdir(parents=True)
    (base / "system.reg").write_text("")
    cfg = C.GameConfig()
    cfg.general.appid = "local-tk3dtests"
    cfg.general.name = "TK's good-game_1"
    cfg.runtime.type = "umu"
    cfg.runtime.prefix = str(base)
    ok, message = L._legacy_prefix("local-tk3dtests", cfg, "umu")
    assert ok is True
    assert "TKsGoodGame1" in message
    assert (base / "TKsGoodGame1" / "drive_c").is_dir()
    assert not (base / "drive_c").exists()


def test_name_version_split():
    assert C.split_name_version("Jogo Bom [v0.3.5]") == ("Jogo Bom", "v0.3.5")
    assert C.split_name_version("Jogo Bom  [0.3] ") == ("Jogo Bom", "0.3")
    assert C.split_name_version("Jogo Bom") == ("Jogo Bom", "")
    assert C.split_name_version("[v1]") == ("[v1]", "")
    assert C.split_name_version("Jogo [Bom] [v1]") == ("Jogo [Bom]", "v1")


def test_display_name_suffixes():
    cfg = C.GameConfig()
    assert C.game_display_name("Doom", cfg) == "Doom"
    cfg.metadata.version = "v1"
    assert C.game_display_name("Doom", cfg) == "Doom [v1]"
    cfg.metadata.tag = "Beta"
    assert C.game_display_name("Doom", cfg) == "Doom [v1] (Beta)"
    cfg.metadata.version = ""
    assert C.game_display_name("Doom", cfg) == "Doom (Beta)"
    assert C.game_display_name("Doom", None) == "Doom"


def test_metadata_date_shapes():
    for text in ("", "2026", "2026-10", "2024-02-29", "2026-02-28"):
        assert C.metadata_date_valid(text), text
    for text in ("26", "2026-13", "2026-00", "2026-02-29", "2026-1", "2026-01-1", "soon"):
        assert not C.metadata_date_valid(text), text


def test_local_id_for_executable(xdg_env, tmp_path):
    exe = tmp_path / "game.sh"
    exe.write_text("#!/bin/sh\n")
    one = C.GameConfig()
    one.general.appid = "local-one"
    one.general.custom_executable = str(exe)
    C.save(one)
    steam = C.GameConfig()
    steam.general.appid = "steam-9"
    steam.general.custom_executable = str(exe)
    C.save(steam)
    assert C.local_id_for_executable(str(exe)) == "local-one"
    assert C.local_id_for_executable(f'"{exe}"') == "local-one"
    assert C.local_id_for_executable(str(tmp_path / "missing")) == ""
    other = tmp_path / "other.sh"
    other.write_text("")
    assert C.local_id_for_executable(str(other)) == ""
    two = C.GameConfig()
    two.general.appid = "local-two"
    two.general.custom_executable = str(exe)
    C.save(two)
    assert C.local_id_for_executable(str(exe)) == ""
