"""Kirigami game list model (QtCore only, no widgets)."""

from tkarcade import config as C


def _model(qgui_app):
    from tkarcade.gui.model import GameListModel

    return GameListModel()


def _rows(model):
    return [
        (
            model.data(model.index(i, 0), model.IdRole),
            model.data(model.index(i, 0), model.NameRole),
            model.data(model.index(i, 0), model.SourceRole),
            model.data(model.index(i, 0), model.PlayedRole),
            model.data(model.index(i, 0), model.TierRole),
        )
        for i in range(model.rowCount())
    ]


def test_model_lists_steam_and_local_sorted(qgui_app, xdg_env):
    steam = C.GameConfig()
    steam.general.appid = "213"
    C.save(steam)
    local = C.GameConfig()
    local.general.appid = "local-zebra"
    local.general.name = "Zebra"
    local.general.custom_executable = "/bin/true"
    local.general.game_type = "native"
    C.save(local)
    rows = _rows(_model(qgui_app))
    assert rows == [
        ("213", "213", "Steam", "—", ""),
        ("local-zebra", "Zebra", "Local", "—", ""),
    ]


def test_model_add_local_validation(qgui_app, xdg_env, tmp_path):
    model = _model(qgui_app)
    assert model.addLocal("", "/bin/true") == ""
    assert model.addLocal("Doom", "/nonexistent/doom") == ""
    exe = tmp_path / "doom"
    exe.write_text("#!/bin/sh\n")
    first = model.addLocal("Doom", str(exe))
    assert first == "local-doom"
    assert model.addLocal("Doom", str(exe)) == "local-doom-2"
    saved = C.load("local-doom")
    assert (saved.general.name, saved.general.game_type) == ("Doom", "native")
    assert saved.general.custom_executable == str(exe)


def test_model_play_routes(qgui_app, xdg_env, monkeypatch, tmp_path):
    from PySide6.QtGui import QDesktopServices

    from tkarcade import launcher as L
    from tkarcade.gui.model import GameListModel

    model = GameListModel()
    opened = []
    monkeypatch.setattr(
        QDesktopServices, "openUrl", lambda url: opened.append(url.toString()) or True
    )
    assert model.play("213") is True
    assert opened == ["steam://rungameid/213"]
    assert L.menu_skip_path("213").exists()
    calls = []
    monkeypatch.setattr(L, "launch_local_detached", lambda appid: calls.append(appid))
    assert model.play("local-doom") is True
    assert calls == ["local-doom"]


def test_launch_local_detached_spawns(xdg_env, monkeypatch):
    import subprocess

    from tkarcade import launcher as L

    calls = []
    monkeypatch.setattr(subprocess, "Popen", lambda *a, **k: calls.append((a, k)) or None)
    monkeypatch.setattr("shutil.which", lambda name: "/usr/bin/tkarcade")
    L.launch_local_detached("local-doom")
    assert L.menu_skip_path("local-doom").exists()  # one-shot skip planted
    (args, kwargs) = calls[0]
    assert args[0] == ["/usr/bin/tkarcade", "--appid", "local-doom"]
    assert kwargs.get("start_new_session") is True


def test_model_role_names_are_game_prefixed(qgui_app):
    from tkarcade.gui.model import GameListModel

    roles = GameListModel().roleNames()
    assert sorted(roles.values()) == [
        b"gameIcon",
        b"gameId",
        b"gameName",
        b"gamePlayed",
        b"gamePlayedSecs",
        b"gamePlayedTip",
        b"gameSource",
        b"gameTier",
        b"gameTierBg",
        b"gameTierFg",
    ]


def test_model_counts(qgui_app, xdg_env):
    from tkarcade.gui.model import GameListModel

    for appid in ("213", "local-a", "local-b"):
        cfg = C.GameConfig()
        cfg.general.appid = appid
        C.save(cfg)
    model = GameListModel()
    assert (model.totalCount, model.steamCount, model.localCount) == (3, 1, 2)


def test_model_counts_visible_to_qml(qgui_app, xdg_env):
    """Count properties must live on the QMetaObject (post-hoc fails QML)."""
    from tkarcade.gui.model import GameListModel

    meta = GameListModel.staticMetaObject
    names = {meta.property(i).name() for i in range(meta.propertyCount())}
    assert {"totalCount", "steamCount", "localCount", "steamDetectedCount"} <= names


def test_model_play_failure_consumes_skip(qgui_app, xdg_env, monkeypatch):
    from PySide6.QtGui import QDesktopServices

    from tkarcade import launcher as L
    from tkarcade.gui.model import GameListModel

    model = GameListModel()
    monkeypatch.setattr(QDesktopServices, "openUrl", lambda url: False)
    assert model.play("213") is False
    assert not L.menu_skip_path("213").exists()


def test_proxy_sort_by_role(qgui_app, xdg_env):
    from tkarcade.gui.model import GameFilterModel, GameListModel

    for appid in ("b-game", "a-game"):
        cfg = C.GameConfig()
        cfg.general.appid = appid
        C.save(cfg)
    model = GameListModel()
    proxy = GameFilterModel()
    proxy.setSourceModel(model)

    def ids():
        return [
            proxy.data(proxy.index(r, 0), GameListModel.IdRole) for r in range(proxy.rowCount())
        ]

    assert ids() == ["a-game", "b-game"]  # source order (name-sorted)
    proxy.sortBy("gameId", False)
    assert ids() == ["a-game", "b-game"]
    proxy.sortBy("gameId", True)
    assert ids() == ["b-game", "a-game"]
    proxy.sortBy("nope", False)  # unknown role falls back to name
    assert ids() == ["a-game", "b-game"]


def test_filter_model_source_and_text(qgui_app, xdg_env):
    from tkarcade.gui.model import GameFilterModel, GameListModel

    for appid, name in (("213", ""), ("local-doom", "Doom"), ("local-quake", "Quake")):
        cfg = C.GameConfig()
        cfg.general.appid = appid
        cfg.general.name = name
        C.save(cfg)
    source = GameListModel()
    proxy = GameFilterModel()
    proxy.setSourceModel(source)

    def shown():
        return sorted(
            proxy.data(proxy.index(i, 0), GameListModel.IdRole) for i in range(proxy.rowCount())
        )

    assert shown() == ["213", "local-doom", "local-quake"]
    proxy.sourceKey = "local"
    assert shown() == ["local-doom", "local-quake"]
    proxy.sourceKey = "steam"
    assert shown() == ["213"]
    proxy.sourceKey = "all"
    proxy.textQuery = "doom"
    assert shown() == ["local-doom"]
    proxy.textQuery = "LOCAL-"
    assert shown() == ["local-doom", "local-quake"]
    proxy.textQuery = ""
    assert shown() == ["213", "local-doom", "local-quake"]


def test_open_protondb_rejects_local(qgui_app, xdg_env):
    from tkarcade.gui.model import GameListModel

    assert GameListModel().openProtonDB("local-doom") is False


def test_open_protondb_handoff(qgui_app, xdg_env, monkeypatch):
    from PySide6.QtGui import QDesktopServices

    from tkarcade.gui.model import GameListModel

    opened = []
    monkeypatch.setattr(
        QDesktopServices, "openUrl", lambda url: opened.append(url.toString()) or True
    )
    assert GameListModel().openProtonDB("42") is True
    assert opened == ["https://www.protondb.com/app/42"]


def test_played_tip_role(qgui_app, xdg_env):
    from tkarcade.gui.model import GameFilterModel, GameListModel

    cfg = C.GameConfig()
    cfg.general.appid = "local-doom"
    C.save(cfg)
    model = GameListModel()
    proxy = GameFilterModel()
    proxy.setSourceModel(model)
    tip = proxy.data(proxy.index(0, 0), GameListModel.PlayedTipRole)
    assert tip == "No recorded sessions"


def test_ludusavi_missing_reports(qgui_app, xdg_env, monkeypatch):
    import shutil

    from tkarcade.gui.model import GameListModel

    monkeypatch.setattr(shutil, "which", lambda _name: None)
    assert GameListModel().openLudusavi() == "Ludusavi was not found in PATH."


def test_about_text_names_program(qgui_app, xdg_env):
    from tkarcade.gui.model import GameListModel

    body = GameListModel().aboutText()
    assert "TKArcade" in body and "GPL-3.0-or-later" in body


def test_history_summary_empty_without_log(qgui_app, xdg_env):
    from tkarcade.gui.model import GameListModel

    assert GameListModel().historySummary() == []


def test_copy_text_roundtrip(qgui_app, xdg_env):
    from PySide6.QtGui import QGuiApplication

    from tkarcade.gui.model import GameListModel

    clipboard = QGuiApplication.clipboard()
    if clipboard is None:
        assert "unavailable" in GameListModel().copyText("x").lower()
    else:
        assert GameListModel().copyText("tkarcade %command%").startswith("Copied")
        assert clipboard.text() == "tkarcade %command%"


def test_fetch_missing_killswitch(qgui_app, xdg_env, monkeypatch):
    import os
    import threading

    from tkarcade.gui.model import GameListModel

    calls = []
    monkeypatch.setattr(threading, "Thread", lambda **kw: calls.append(kw) or FakeThread())
    os.environ.pop("TKARCADE_NO_BG_FETCH", None)

    class FakeThread:
        def start(self):
            pass

    GameListModel().fetchMissing()
    assert len(calls) == 1


def test_remove_and_profiles_roundtrip(qgui_app, xdg_env):
    from tkarcade import config as C
    from tkarcade.gui.model import GameListModel

    cfg = C.GameConfig()
    cfg.general.appid = "local-doom"
    C.save(cfg)
    profiles = C.profiles_dir("local-doom")
    profiles.mkdir(parents=True, exist_ok=True)
    (profiles / "default.toml").write_text("[general]\n")
    model = GameListModel()
    assert model.leftoverProfiles(["local-doom"]) == ["local-doom"]
    assert model.cleanProfiles(["local-doom"]) == 1
    assert model.removeGames(["local-doom"]) == ""
    assert not C.game_file("local-doom").exists()


def test_clear_history_removes_log_lines(qgui_app, xdg_env):
    from tkarcade import xdg
    from tkarcade.gui.model import GameListModel

    log = xdg.log_file()
    log.parent.mkdir(parents=True, exist_ok=True)
    log.write_text(
        "2026-01-01T10:00:00 appid=42 exit=0 dur=60\n2026-01-01T11:00:00 appid=43 exit=0 dur=30\n",
        encoding="utf-8",
    )
    assert GameListModel().clearHistory("42") == 1
    assert "appid=42" not in log.read_text(encoding="utf-8")
    assert "appid=43" in log.read_text(encoding="utf-8")


def test_column_prefs_roundtrip(qgui_app, xdg_env):
    from tkarcade.gui.model import GameFilterModel, GameListModel

    source = GameListModel()
    proxy = GameFilterModel()
    proxy.setSourceModel(source)
    assert proxy.columnLogical(0) == 0
    proxy.moveColumn(2, 1)
    assert [proxy.columnLogical(c) for c in range(6)] == [0, 1, 3, 2, 4, 5]
    assert C.load_preferences().column_order.split(",")[:3] == ["0", "1", "3"]
    proxy.showAppId = False
    assert "2" in C.load_preferences().hidden_columns.split(",")
    proxy.resetColumns()
    assert [proxy.columnLogical(c) for c in range(6)] == [0, 1, 2, 3, 4, 5]
    assert C.load_preferences().hidden_columns == ""


def test_column_width_autofit_persists(qgui_app, xdg_env):
    from tkarcade.gui.model import GameFilterModel, GameListModel

    proxy = _filtered(qgui_app)
    assert proxy.columnWidth(1) == 0
    width = proxy.autofitColumn(1)
    assert width >= 40  # header title alone guarantees the minimum
    assert proxy.columnWidth(1) == width
    assert f"1={width}" in C.load_preferences().column_widths.split(",")
    import json

    assert json.loads(proxy.columnWidthsJson()) == {"1": width}
    assert proxy.autofitColumn(99) == 0
    fresh = GameFilterModel()
    fresh.setSourceModel(GameListModel())
    assert fresh.columnWidth(1) == width
    fresh.fitDefaults()
    assert 40 <= fresh.columnWidth(1) <= 300
    assert 40 <= fresh.columnWidth(2) <= 300
    proxy.resetColumns()
    assert 40 <= proxy.columnWidth(1) <= 300  # reset fits, capped
    assert C.load_preferences().column_widths != ""


def test_column_width_drag_preview_then_save(qgui_app, xdg_env):

    proxy = _filtered(qgui_app)
    proxy.setColumnWidth(2, 150)
    assert proxy.columnWidth(2) == 150
    assert C.load_preferences().column_widths == ""  # preview: no save yet
    proxy.saveColumnWidths()
    assert C.load_preferences().column_widths == "2=150"
    proxy.setColumnWidth(2, 5)  # below minimum: rejected
    assert proxy.columnWidth(2) == 150
    proxy.setColumnWidth(9, 150)  # unknown column: rejected
    assert proxy.columnWidth(9) == 0


def test_role_id_maps_names(qgui_app, xdg_env):
    from tkarcade.gui.model import GameListModel

    model = GameListModel()
    assert model.roleId("gameId") == GameListModel.IdRole
    assert model.roleId("gameName") == GameListModel.NameRole
    assert model.roleId("nope") == -1


def test_row_data_roundtrip(qgui_app, xdg_env):
    from tkarcade import config as C
    from tkarcade.gui.model import GameFilterModel, GameListModel

    cfg = C.GameConfig()
    cfg.general.appid = "local-doom"
    cfg.general.name = "Doom"
    C.save(cfg)
    model = GameListModel()
    proxy = GameFilterModel()
    proxy.setSourceModel(model)
    row = proxy.rowData(0)
    assert row["gameId"] == "local-doom"
    assert row["gameName"] == "Doom"
    assert proxy.rowData(99) == {}


def test_drawer_mode_roundtrip(qgui_app, xdg_env):
    from tkarcade import config as C
    from tkarcade.gui.model import GameListModel

    model = GameListModel()
    assert model.drawerMode() == "collapsible"
    model.saveDrawerMode("overlay")
    assert C.load_preferences().drawer_mode == "overlay"
    model.saveDrawerMode("bogus")
    assert C.load_preferences().drawer_mode == "collapsible"


def test_drawer_collapsed_roundtrip(qgui_app, xdg_env):
    from tkarcade.gui.model import GameListModel

    model = GameListModel()
    assert model.drawerCollapsed() is True
    model.saveDrawerCollapsed(False)
    assert C.load_preferences().drawer_collapsed is False
    assert GameListModel().drawerCollapsed() is False


def test_settings_load_save_roundtrip(qgui_app, xdg_env):
    from tkarcade.gui.model import GameListModel

    cfg = C.GameConfig()
    cfg.general.appid = "local-doom"
    cfg.general.name = "Doom"
    cfg.general.custom_executable = "/bin/true"
    cfg.general.game_type = "native"
    C.save(cfg)
    model = GameListModel()
    fields = model.loadGame("local-doom")
    assert fields["name"] == "Doom"
    assert fields["game_type"] == "native"
    assert fields["is_steam"] is False
    assert fields["profiles"] == []
    out = dict(fields)
    out["name"] = "Doom II"
    out["menu_timeout"] = 30
    out["notes"] = "rip and tear"
    assert model.saveGame("local-doom", out) == "local-doom"
    reloaded = C.load("local-doom")
    assert reloaded.general.name == "Doom II"
    assert reloaded.general.menu_timeout == 30
    assert reloaded.notes.text == "rip and tear"
    assert model.saveGame("nope-missing", {}) == ""
    assert model.loadGame("nope-missing")["name"] == ""
    assert model.saveGame("", {"name": "", "custom_executable": "/bin/true"}) == ""


def test_settings_create_and_profiles(qgui_app, xdg_env):
    from tkarcade.gui.model import GameListModel

    model = GameListModel()
    created = model.saveGame(
        "", {"name": "Doom", "custom_executable": "/bin/true", "game_type": "native"}
    )
    assert created.startswith("local-")
    assert C.load(created).general.name == "Doom"
    assert model.saveGameProfile(created, "fast", {"custom_executable": "/bin/true"}) is True
    assert model.loadGame(created)["profiles"] == ["fast"]
    assert model.saveGameProfile(created, "", {}) is False
    assert model.profileExists(created, "fast") is True
    assert model.profileExists(created, "missing") is False
    assert model.cloneGameProfile(created, "fast", "faster", {}) is True
    assert model.cloneGameProfile(created, "missing", "x", {}) is False
    assert model.cloneGameProfile(created, "fast", "fast", {}) is False
    assert (
        model.cloneGameProfile(created, "", "livecopy", {"custom_executable": "/bin/true"}) is True
    )
    assert model.profileExists(created, "livecopy") is True
    content = model.profileContent(created, "fast")
    assert content["custom_executable"] == "/bin/true"
    assert model.profileContent(created, "missing") == {}
    assert C.load(created).general.active_profile == ""
    assert model.markActiveProfile(created, "fast") is True
    assert C.load(created).general.active_profile == "fast"
    out = dict(model.loadGame(created))
    out["name"] = "Doom II"
    out["active_profile"] = "fast"
    assert model.saveGame(created, out) == created
    assert C.load(created).general.name == "Doom"
    assert C.load_profile(created, "fast").general.name == "Doom II"
    assert model.deleteGameProfile(created, "fast") is True
    assert C.load(created).general.active_profile == ""
    assert model.loadGame(created)["profiles"] == ["faster", "livecopy"]


def test_settings_env_prepost_roundtrip(qgui_app, xdg_env):
    from tkarcade.gui.model import GameListModel

    cfg = C.GameConfig()
    cfg.general.appid = "local-doom"
    cfg.general.name = "Doom"
    cfg.general.custom_executable = "/bin/true"
    cfg.env.vars = {"FOO": "bar", "QUOTED": "a b"}
    cfg.pre_post.pre_command = "/bin/echo"
    cfg.pre_post.pre_args = ["a b", "c"]
    cfg.pre_post.timeout = 30
    cfg.pre_post.run_in_shell = True
    C.save(cfg)
    model = GameListModel()
    fields = model.loadGame("local-doom")
    assert {"key": "FOO", "value": "bar"} in fields["env_vars"]
    assert fields["pre_args"] == "'a b' c"
    assert fields["pp_timeout"] == 30
    assert fields["run_in_shell"] is True
    out = dict(fields)
    out["env_vars"] = [{"key": "NEW", "value": "1"}, {"key": "", "value": "x"}]
    out["pre_args"] = 'x "y z"'
    out["pp_timeout"] = 9999
    assert model.saveGame("local-doom", out) == "local-doom"
    reloaded = C.load("local-doom")
    assert reloaded.env.vars == {"NEW": "1"}
    assert reloaded.pre_post.pre_args == ["x", "y z"]
    assert reloaded.pre_post.timeout == 3600


def test_settings_gamemode_roundtrip(qgui_app, xdg_env):
    from tkarcade.gui.model import GameListModel

    cfg = C.GameConfig()
    cfg.general.appid = "local-doom"
    cfg.general.name = "Doom"
    cfg.general.custom_executable = "/bin/true"
    cfg.gamemode.feral_gamemode = True
    C.save(cfg)
    model = GameListModel()
    assert model.loadGame("local-doom")["gamemode_feral"] is True
    out = dict(model.loadGame("local-doom"))
    out["gamemode_feral"] = False
    out["gamemode_cachy"] = True
    assert model.saveGame("local-doom", out) == "local-doom"
    reloaded = C.load("local-doom")
    assert reloaded.gamemode.feral_gamemode is False
    assert reloaded.gamemode.cachyos_game_performance is True


def test_settings_display_roundtrip(qgui_app, xdg_env):
    from tkarcade.gui.model import GameListModel

    cfg = C.GameConfig()
    cfg.general.appid = "local-doom"
    cfg.general.name = "Doom"
    cfg.general.custom_executable = "/bin/true"
    cfg.display.provider = "x11"
    cfg.display.output = "DP-1"
    cfg.display.mode = "1920x1080@60"
    cfg.display.dip_seconds = 5
    cfg.gamescope.enable = True
    cfg.gamescope.args = "-f"
    cfg.mangohud.config_file = "foo.conf"
    cfg.rtupscale.enable = True
    C.save(cfg)
    model = GameListModel()
    fields = model.loadGame("local-doom")
    assert fields["display_provider"] == "x11"
    assert fields["display_mode"] == "1920x1080@60"
    assert fields["dip_seconds"] == 5
    assert fields["gamescope_args"] == "-f"
    out = dict(fields)
    out["display_provider"] = "bogus"
    out["dip_seconds"] = 99
    out["rt_args"] = "-m 4x24"
    assert model.saveGame("local-doom", out) == "local-doom"
    reloaded = C.load("local-doom")
    assert reloaded.display.provider == "auto"
    assert reloaded.display.dip_seconds == 15
    assert reloaded.rtupscale.args == "-m 4x24"
    assert model.displayModesMatch("1920x1080@60", "1920x1080@60") is True
    assert model.displayModesMatch("1920x1080@60", "1280x720@60") is False
    assert model.displayModesMatch("garbage", "1920x1080@60") is False
    assert "1080p 144Hz Fullscreen" in model.gamescopePresets()
    assert model.gamescopePreset("1080p 144Hz Fullscreen") == "-f -W 1920 -H 1080 -r 144"
    assert model.gamescopePreset("nope") == ""
    assert model.mangohudConfigs() == []
    assert model.createMangohudConfig("test-game", "minimal") != ""
    assert "test-game.conf" in model.mangohudConfigs()
    assert model.createMangohudConfig("", "minimal") == ""


def test_settings_preview_diff(qgui_app, xdg_env):
    from tkarcade.gui.model import GameListModel

    cfg = C.GameConfig()
    cfg.general.appid = "local-doom"
    cfg.general.name = "Doom"
    cfg.general.custom_executable = "/bin/true"
    cfg.general.game_type = "native"
    C.save(cfg)
    model = GameListModel()
    res = model.previewCommand(
        "local-doom", {"custom_executable": "/bin/true", "game_type": "native"}
    )
    assert "/bin/true" in res["command"]
    assert isinstance(res["warnings"], list)
    assert res["wrappers"] != ""
    assert model.diffDefaults("", {}) == ""
    diff = model.diffDefaults(
        "local-doom", {"custom_executable": "/bin/true", "game_type": "native"}
    )
    assert "custom_executable" in diff


def test_settings_load_warning(qgui_app, xdg_env):
    from tkarcade.gui.model import GameListModel

    cfg = C.GameConfig()
    cfg.general.appid = "local-doom"
    C.save(cfg)
    assert GameListModel().loadGame("local-doom")["load_warning"] == ""
    C.game_file("local-doom").write_text("general = [broken\n")
    assert "invalid TOML" in GameListModel().loadGame("local-doom")["load_warning"]


def test_settings_tool_availability(qgui_app, xdg_env, monkeypatch):
    import shutil

    from tkarcade.gui.model import GameListModel

    assert GameListModel().toolAvailable("sh") is True
    assert GameListModel().toolAvailable("tkarcade-no-such-tool-xyz") is False
    monkeypatch.setattr(shutil, "which", lambda *a, **k: None)
    assert GameListModel().toolAvailable("sh") is False


def test_settings_env_bulk_preset(qgui_app, xdg_env):
    from tkarcade.gui.model import GameListModel

    model = GameListModel()
    assert model.envToText([{"key": "A", "value": "1"}, {"key": "", "value": "x"}]) == "A=1"
    assert model.textToEnv("# c\n\nA=1\nB = x y\nBAD\n=novalue\n") == [
        {"key": "A", "value": "1"},
        {"key": "B", "value": " x y"},
    ]
    labels = model.envPresetLabels()
    assert len(labels) > 0
    name = model.envPresetName(labels[0])
    assert name != ""
    assert model.envPresetName("no such preset") == ""
    assert isinstance(model.envPresetMismatch(name, ""), str)
    res = model.applyEnvPreset([], name)
    assert res["added"] > 0
    again = model.applyEnvPreset(res["rows"], name)
    assert again["added"] == 0
    assert len(again["rows"]) == len(res["rows"])


def test_clone_reset_games(qgui_app, xdg_env):
    from tkarcade.gui.model import GameListModel

    for appid in ("local-doom", "local-quake"):
        cfg = C.GameConfig()
        cfg.general.appid = appid
        cfg.general.name = appid
        C.save(cfg)
    prof = C.profiles_dir("local-doom")
    prof.mkdir(parents=True, exist_ok=True)
    (prof / "fast.toml").write_text("[general]\n")
    model = GameListModel()
    targets = model.cloneTargets("local-doom")
    assert targets == [["local-quake", "local-quake"]]
    assert model.cloneGameTo("local-doom", "???", False) == "Invalid game ID: ???"
    assert model.cloneGameTo("local-doom", "local-doom", False) == "Source and target are the same."
    assert model.cloneGameTo("local-doom", "local-quake", False) == "OVERWRITE"
    assert model.cloneGameTo("local-doom", "local-new", False) == "Cloned local-doom to local-new."
    assert C.game_file("local-new").is_file()
    assert (C.profiles_dir("local-new") / "fast.toml").is_file()
    assert model.cloneGameTo("local-doom", "local-quake", True).startswith("Cloned")
    assert model.resetGames([]) == "Select games first."
    assert model.resetGames(["local-doom"]) == "Reset 1 game(s) to the Global Defaults template."
    assert C.load("local-doom").general.name == ""
    assert (C.profiles_dir("local-doom") / "fast.toml").is_file()


def test_settings_steam_create(qgui_app, xdg_env):
    from tkarcade.gui.model import GameListModel

    model = GameListModel()
    assert model.saveGame("99", {"game_type": "proton"}) == "99"
    assert C.game_file("99").is_file()
    assert C.load("99").general.game_type == "proton"


def test_icon_name_first_available(qgui_app, xdg_env, monkeypatch):
    from PySide6.QtGui import QIcon

    from tkarcade.gui.model import GameListModel

    model = GameListModel()
    monkeypatch.setattr(QIcon, "hasThemeIcon", lambda name: name == "table")
    assert model.iconName(["view-column", "table"]) == "table"
    monkeypatch.setattr(QIcon, "hasThemeIcon", lambda name: True)
    assert model.iconName(["view-column", "table"]) == "view-column"
    monkeypatch.setattr(QIcon, "hasThemeIcon", lambda name: False)
    assert model.iconName(["view-column", "table"]) == "view-column"
    assert model.iconName([]) == ""


def test_settings_ludusavi_system_roundtrip(qgui_app, xdg_env):
    from tkarcade.gui.model import GameListModel

    cfg = C.GameConfig()
    cfg.general.appid = "local-doom"
    cfg.general.name = "Doom"
    cfg.general.custom_executable = "/bin/true"
    cfg.ludusavi.enable = True
    cfg.ludusavi.name_override = "Doom 3"
    cfg.session.inhibit_idle = True
    cfg.nightlight.disable_during_game = True
    cfg.nightlight.provider = "plasma"
    C.save(cfg)
    model = GameListModel()
    fields = model.loadGame("local-doom")
    assert fields["ludusavi_enable"] is True
    assert fields["ludusavi_restore"] is True
    assert fields["ludusavi_name"] == "Doom 3"
    assert fields["inhibit_idle"] is True
    assert fields["nl_provider"] == "plasma"
    assert model.gameLogFile("local-doom").endswith("local-doom.log")
    out = dict(fields)
    out["ludusavi_backup"] = False
    out["notify_on_launch"] = False
    out["nl_provider"] = "bogus"
    assert model.saveGame("local-doom", out) == "local-doom"
    reloaded = C.load("local-doom")
    assert reloaded.ludusavi.backup is False
    assert reloaded.notifications.notify_on_launch is False
    assert reloaded.nightlight.provider == "auto"


def test_settings_wine_roundtrip(qgui_app, xdg_env):
    from tkarcade.gui.model import GameListModel

    cfg = C.GameConfig()
    cfg.general.appid = "99"
    cfg.proton.fresh_prefix = True
    cfg.proton.winetricks_verbs = ["dotnet48"]
    cfg.debug.proton_log = True
    cfg.debug.winedebug = "+err"
    C.save(cfg)
    model = GameListModel()
    fields = model.loadGame("99")
    assert fields["fresh_prefix"] is True
    assert fields["winetricks_verbs"] == "dotnet48"
    assert fields["proton_log"] is True
    assert fields["winedebug"] == "+err"
    assert model.protonLogDir("99").endswith("99/proton")
    out = dict(fields)
    out["winedebug"] = "bogus"
    out["winetricks_verbs"] = "vcrun2022 dotnet48"
    assert model.saveGame("99", out) == "99"
    reloaded = C.load("99")
    assert reloaded.debug.winedebug == ""
    assert reloaded.proton.winetricks_verbs == ["vcrun2022", "dotnet48"]


def test_settings_defaults_roundtrip(qgui_app, xdg_env):
    from tkarcade.gui.model import GameListModel

    model = GameListModel()
    fields = model.loadDefaults()
    assert fields["gamemode_feral"] is False
    out = dict(fields)
    out["gamemode_feral"] = True
    out["menu_timeout"] = 11
    assert model.saveDefaults(out) is True
    assert C.load_defaults().gamemode.feral_gamemode is True
    assert C.load_defaults().general.menu_timeout == 11
    assert model.factoryGame("local-doom")["name"] == ""


def test_settings_coverage_reports(qgui_app, xdg_env):
    import threading

    from tkarcade.gui.model import GameListModel

    model = GameListModel()
    done, out = threading.Event(), []
    model.coverageFinished.connect(lambda s, d: (out.append((s, d)), done.set()))
    model.checkCoverage("local-missing", "")
    import time

    deadline = time.monotonic() + 30
    while not done.is_set() and time.monotonic() < deadline:
        qgui_app.processEvents()
        done.wait(0.05)
    assert done.is_set()
    assert out[0][0] in ("covered", "no-local-saves", "no-entry", "unavailable")


def test_export_import_tarball_roundtrip(qgui_app, xdg_env, tmp_path):
    from tkarcade.gui.model import GameListModel

    cfg = C.GameConfig()
    cfg.general.appid = "99"
    C.save(cfg)
    model = GameListModel()
    dest = tmp_path / "out.tar.gz"
    assert "Exported to" in model.exportTarball(str(dest))
    assert dest.is_file()
    assert model.exportTarball("") == ""
    assert model.exportTarball(str(tmp_path / "missing" / "x.tar.gz")).startswith("Export failed")
    C.game_file("99").unlink()
    assert model.importTarball(str(dest)) == "Imported 1 game(s)"
    assert C.game_file("99").is_file()
    assert model.importTarball("") == ""
    assert model.importTarball(str(tmp_path / "nope.tar.gz")).startswith("Import failed")


def test_stl_import_flow(qgui_app, xdg_env, monkeypatch):
    import os
    from pathlib import Path

    import tkarcade.steam as steammod
    from tkarcade.gui.model import GameListModel

    monkeypatch.setattr(steammod, "list_games", lambda: [("99", "Doom 3")])
    cfg = C.GameConfig()
    cfg.general.appid = "99"
    C.save(cfg)
    stl_id = Path(os.environ["XDG_CONFIG_HOME"]) / "steamtinkerlaunch" / "gamecfgs" / "id"
    stl_id.mkdir(parents=True)
    (stl_id / "99.conf").write_text('USE_GAMEMODE="1"\n')
    model = GameListModel()
    assert model.stlCandidates() == [["99", "Doom 3"]]
    assert "steamtinkerlaunch' profile" in model.importStl(["99"])
    assert C.profile_file("99", "steamtinkerlaunch").is_file()
    assert "Skipped" in model.importStl(["100"])
    assert model.importStl([]) == "Nothing selected."


def test_import_predecessor_without_source(qgui_app, xdg_env):
    from tkarcade.gui.model import GameListModel

    assert GameListModel().importPredecessor().startswith("Import failed")


def _filtered(qgui_app, appids=("213", "local-doom")):
    from tkarcade.gui.model import GameFilterModel, GameListModel

    for appid in appids:
        cfg = C.GameConfig()
        cfg.general.appid = appid
        if not appid[0].isdigit():
            cfg.general.name = "Doom"
        C.save(cfg)
    source = GameListModel()
    proxy = GameFilterModel()
    proxy.setSourceModel(source)
    return proxy


def test_proxy_is_six_column_table(qgui_app, xdg_env):
    from PySide6.QtCore import Qt

    proxy = _filtered(qgui_app)
    assert proxy.columnCount() == 6
    assert proxy.columnCount(proxy.index(0, 0)) == 0
    assert [proxy.headerData(c, Qt.Orientation.Horizontal) for c in range(6)] == [
        "#",
        "Game",
        "App ID",
        "Played",
        "ProtonDB",
        "Source",
    ]
    assert proxy.data(proxy.index(0, 0)) == "1"
    assert proxy.data(proxy.index(0, 1)) == "213"
    assert proxy.data(proxy.index(1, 2)) == "local-doom"
    assert proxy.data(proxy.index(1, 5)) == "Local"
    assert proxy.data(proxy.index(9, 0)) is None
    # custom roles stay row-based: delegates keep working per column
    from tkarcade.gui.model import GameListModel

    assert proxy.data(proxy.index(1, 4), GameListModel.IdRole) == "local-doom"


def test_proxy_move_hide_reset_columns(qgui_app, xdg_env):
    proxy = _filtered(qgui_app)
    proxy.moveColumn(2, 1)
    assert proxy.columnCount() == 6
    assert (
        proxy.headerData(2, __import__("PySide6.QtCore", fromlist=["x"]).Qt.Orientation.Horizontal)
        == "Played"
    )
    assert C.load_preferences().column_order.split(",")[:3] == ["0", "1", "3"]
    proxy.showAppId = False
    assert proxy.columnCount() == 6  # hidden columns keep mapped slots
    assert "2" in C.load_preferences().hidden_columns.split(",")
    proxy.resetColumns()
    assert proxy.columnCount() == 6
    assert C.load_preferences().hidden_columns == ""
    proxy.moveColumn(0, -1)  # edge: no-op, stays valid
    assert proxy.columnCount() == 6
