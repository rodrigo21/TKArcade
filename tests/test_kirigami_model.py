"""Kirigami game list model (QtCore only, no widgets)."""

import time

from tkarcade import config as C


def _model(qgui_app):
    from tkarcade.gui.model import GameListModel

    return GameListModel()


def _rows(model):
    return [
        (
            model.data(model.index(i, 0), model.IdRole),
            model.data(model.index(i, 0), model.NameRole),
            model.data(model.index(i, 0), model.OriginRole),
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
    local.runtime.type = "native"
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
    assert (saved.general.name, saved.runtime.type) == ("Doom", "native")
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
    import sys

    from tkarcade import launcher as L

    calls = []
    monkeypatch.setattr(subprocess, "Popen", lambda *a, **k: calls.append((a, k)) or None)
    # A stale system package on PATH must never be the child: the spawn
    # goes through the interpreter that owns this install.
    monkeypatch.setattr("shutil.which", lambda name: "/usr/bin/tkarcade")
    monkeypatch.setattr(sys, "executable", "/opt/venv/bin/python")
    L.launch_local_detached("local-doom")
    assert L.menu_skip_path("local-doom").exists()  # one-shot skip planted
    (args, kwargs) = calls[0]
    assert args[0] == [
        "/opt/venv/bin/python",
        "-m",
        "tkarcade.launcher",
        "--appid",
        "local-doom",
    ]
    assert kwargs.get("start_new_session") is True


def test_model_role_names_are_game_prefixed(qgui_app):
    from tkarcade.gui.model import GameListModel

    roles = GameListModel().roleNames()
    assert sorted(roles.values()) == [
        b"gameCategory",
        b"gameCover",
        b"gameIcon",
        b"gameId",
        b"gameInstallDir",
        b"gameLastPlayed",
        b"gameLastSecs",
        b"gameName",
        b"gameOrigin",
        b"gamePlatform",
        b"gamePlayed",
        b"gamePlayedSecs",
        b"gamePlayedTip",
        b"gameRunning",
        b"gameRuntime",
        b"gameTier",
        b"gameTierBg",
        b"gameTierFg",
        b"gameWine",
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


def test_model_play_reports_launch(qgui_app, xdg_env, monkeypatch):
    """play() reports (ok, kind, name, detail) so the UI can speak.

    The widgets wrote the status line and the handoff warnings in the
    same code path the tray used; the QML shell gets the same events.
    """
    from PySide6.QtGui import QDesktopServices

    from tkarcade import launcher as L
    from tkarcade.gui.model import GameListModel

    model = GameListModel()
    reports = []
    model.launchReported.connect(lambda *args: reports.append(args))

    monkeypatch.setattr(QDesktopServices, "openUrl", lambda url: False)
    assert model.play("213") is False
    assert reports[-1][0] is False
    assert reports[-1][1] == "steam"

    monkeypatch.setattr(L, "launch_local_detached", lambda appid: None)
    assert model.play("local-doom") is True
    ok, kind, name, detail = reports[-1]
    assert (ok, kind, detail) == (True, "local", "")
    assert name != ""

    def boom(appid):
        raise OSError("spawn failed")

    monkeypatch.setattr(L, "launch_local_detached", boom)
    assert model.play("local-doom") is False
    assert reports[-1][0] is False
    assert reports[-1][3] == "spawn failed"


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
    assert tip == "No Recorded Sessions"


def test_ludusavi_missing_reports(qgui_app, xdg_env, monkeypatch):
    import shutil

    from tkarcade.gui.model import GameListModel

    monkeypatch.setattr(shutil, "which", lambda _name: None)
    assert GameListModel().openLudusavi() == "Ludusavi Was Not Found in PATH."


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


def test_leftovers_include_logs_history_and_prefix(qgui_app, xdg_env, tmp_path):
    from tkarcade import config as C
    from tkarcade import xdg
    from tkarcade.gui.model import GameListModel

    base = tmp_path / "pfx"
    prefix = C.prefix_dir("local-doom", str(base), "", "", "Doom")
    prefix.mkdir(parents=True)
    cfg = C.GameConfig()
    cfg.general.appid = "local-doom"
    cfg.general.name = "Doom"
    cfg.runtime.prefix = str(base)
    C.save(cfg)
    profiles = C.profiles_dir("local-doom")
    profiles.mkdir(parents=True)
    (profiles / "default.toml").write_text("[general]\n")
    logs = xdg.games_log_dir()
    logs.mkdir(parents=True, exist_ok=True)
    xdg.game_log_file("local-doom").write_text("log\n", encoding="utf-8")
    (logs / "local-doom" / "proton").mkdir(parents=True)
    xdg.log_file().parent.mkdir(parents=True, exist_ok=True)
    xdg.log_file().write_text(
        "2026-01-02T10:00:00 appid=local-doom exit=0 dur=60 cmd=tkarcade\n", encoding="utf-8"
    )
    model = GameListModel()
    assert model.orphanedLeftovers() == []  # live config holds it
    model.removeGames(["local-doom"])
    rows = model.leftoverData(["local-doom"])
    assert len(rows) == 1
    row = rows[0]
    assert row["name"] == "Doom"
    assert row["profiles"] == 1
    assert row["session_log"] is True
    assert row["proton_log"] is True
    assert row["history"] == 1
    assert row["prefix"] == str(prefix.resolve())
    assert model.cleanLeftovers(["local-doom"], False) == 1
    assert not profiles.exists()
    assert not xdg.game_log_file("local-doom").exists()
    assert not (logs / "local-doom").exists()
    assert "local-doom" not in xdg.log_file().read_text(encoding="utf-8")
    assert prefix.is_dir()  # unchecked option keeps the prefix


def test_leftover_prefix_option_deletes_owned_prefix(qgui_app, xdg_env, tmp_path):
    from tkarcade import config as C
    from tkarcade.gui.model import GameListModel

    base = tmp_path / "pfx"
    prefix = C.prefix_dir("local-quake", str(base), "", "", "Quake")
    prefix.mkdir(parents=True)
    cfg = C.GameConfig()
    cfg.general.appid = "local-quake"
    cfg.general.name = "Quake"
    cfg.runtime.prefix = str(base)
    C.save(cfg)
    model = GameListModel()
    model.removeGames(["local-quake"])
    rows = model.orphanedLeftovers()  # nothing left: prefix not discoverable
    assert rows == []
    rows = model.leftoverData(["local-quake"])
    assert len(rows) == 1
    assert rows[0]["prefix"] == str(prefix.resolve())
    assert model.cleanLeftovers(["local-quake"], True) == 1
    assert not prefix.exists()


def test_orphaned_leftovers_finds_unconfigured_logs(qgui_app, xdg_env):
    from tkarcade import xdg
    from tkarcade.gui.model import GameListModel

    logs = xdg.games_log_dir()
    logs.mkdir(parents=True)
    xdg.game_log_file("gone-game").write_text("log\n", encoding="utf-8")
    (logs / "gone-game" / "proton").mkdir(parents=True)
    xdg.log_file().parent.mkdir(parents=True, exist_ok=True)
    xdg.log_file().write_text(
        "2026-01-02T10:00:00 appid=gone-game exit=1 dur=10 cmd=tkarcade\n", encoding="utf-8"
    )
    model = GameListModel()
    rows = model.orphanedLeftovers()
    assert [r["appid"] for r in rows] == ["gone-game"]
    assert rows[0]["session_log"] is True
    assert rows[0]["proton_log"] is True
    assert rows[0]["history"] == 1
    assert model.cleanLeftovers(["gone-game"], False) == 1
    assert model.orphanedLeftovers() == []


def test_validate_report_uses_the_game_name(qgui_app, xdg_env, monkeypatch):
    from tkarcade import config as C
    from tkarcade import launcher
    from tkarcade.gui.model import GameListModel

    cfg = C.GameConfig()
    cfg.general.appid = "local-doom"
    cfg.general.name = "Doom"
    C.save(cfg)
    monkeypatch.setattr(
        launcher, "validate_game", lambda appid: [f"{appid}: custom_executable not found"]
    )
    report = GameListModel().validateReport("local-doom")
    assert report["name"] == "Doom"
    assert report["issues"] == ["custom_executable not found"]


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
    assert [proxy.columnLogical(c) for c in range(11)] == [0, 1, 3, 2, 4, 5, 6, 7, 8, 9, 10]
    assert C.load_preferences().column_order.split(",")[:3] == ["0", "1", "3"]
    proxy.showAppId = False
    assert "2" in C.load_preferences().hidden_columns.split(",")
    proxy.resetColumns()
    assert [proxy.columnLogical(c) for c in range(11)] == [0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10]
    assert C.load_preferences().hidden_columns == "7,8,9,10"


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
    proxy.setColumnWidth(99, 150)  # unknown column: rejected
    assert proxy.columnWidth(99) == 0


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
    cfg.runtime.type = "native"
    C.save(cfg)
    model = GameListModel()
    fields = model.loadGame("local-doom")
    assert fields["name"] == "Doom"
    assert fields["runtime_type"] == "native"
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


def test_metadata_suffix_and_name_split(qgui_app, xdg_env):
    from tkarcade.gui.model import GameFilterModel, GameListModel

    cfg = C.GameConfig()
    cfg.general.appid = "local-doom"
    cfg.general.name = "Doom"
    C.save(cfg)
    model = GameListModel()
    out = dict(model.loadGame("local-doom"))
    out["name"] = "Doom [v1.2]"
    out["tag"] = "Beta"
    assert model.saveGame("local-doom", out) == "local-doom"
    saved = C.load("local-doom")
    assert saved.general.name == "Doom"
    assert saved.metadata.version == "v1.2"
    assert saved.metadata.tag == "Beta"
    proxy = GameFilterModel()
    proxy.setSourceModel(model)
    assert proxy.rowData(0)["gameName"] == "Doom [v1.2] (Beta)"
    assert model.metadataDateValid("2026-10") is True
    assert model.metadataDateValid("2026-13") is False


def test_settings_create_and_profiles(qgui_app, xdg_env):
    from tkarcade.gui.model import GameListModel

    model = GameListModel()
    created = model.saveGame(
        "", {"name": "Doom", "custom_executable": "/bin/true", "runtime_type": "native"}
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


def test_library_schema_slots(qgui_app, xdg_env, tmp_path):
    import os

    from tkarcade.gui.model import GameListModel

    cfg = C.GameConfig()
    cfg.general.appid = "local-doom"
    cfg.general.name = "Doom"
    cfg.general.custom_executable = "/bin/true"
    C.save(cfg)
    model = GameListModel()
    assert model.allCategories() == []
    assert model.setCategories([], "Action") == "Select Games First."
    assert model.setCategories(["local-doom"], "Action, Retro ,") == (
        "Set 2 Categor(ies) on 1 Game(s)."
    )
    assert C.load("local-doom").general.categories == ["Action", "Retro"]
    assert model.allCategories() == ["Action", "Retro"]
    art = tmp_path / "icon.png"
    art.write_bytes(b"\x89PNG\r\n\x1a\n")
    assert model.storeArtwork("local-doom", "icon", os.fspath(art)) == ""
    assert C.load("local-doom").artwork.icon.endswith("icon.png")
    assert model.storeArtwork("local-doom", "icon", os.fspath(tmp_path / "nope.png")) != ""
    assert model.clearArtwork("local-doom", "icon") is True
    assert C.load("local-doom").artwork.icon == ""
    assert isinstance(model.wineTools(), list)
    assert model.applyWineVersion("local-doom", "proton_9") == (
        "Version Selection Needs a Steam Game."
    )
    local_prefix = model.prefixDir("local-doom")
    assert local_prefix.endswith("/prefixes/Doom")
    assert model.ensurePrefix("local-doom") == ""
    assert os.path.isdir(local_prefix)
    assert model.clearCustomPrefix("local-doom") == f"Cleared {local_prefix}."
    assert not os.path.exists(local_prefix)


def test_library_columns_roles(qgui_app, xdg_env):
    from tkarcade.gui.model import GameFilterModel, GameListModel

    cfg = C.GameConfig()
    cfg.general.appid = "local-doom"
    cfg.general.name = "Doom"
    cfg.general.categories = ["Action"]
    cfg.runtime.type = "native"
    C.save(cfg)
    model = GameListModel()
    assert model.columnCount() == 12
    row = model.rowData(0)
    assert row["gamePlatform"] == "Linux"
    assert row["gameCategory"] == "Action"
    assert row["gameRuntime"] == "Native"
    assert row["gameLastPlayed"] == "—"
    assert row["gameLastSecs"] == -1
    game_filter = GameFilterModel()
    game_filter.setSourceModel(model)
    assert game_filter.columnCount() == 11
    assert game_filter._order == [0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10]
    assert game_filter._hidden == {7, 8, 9, 10}
    assert game_filter.showLastPlayed is True
    game_filter.sortBy("gameLastSecs", True)


def test_settings_preview_diff(qgui_app, xdg_env):
    from tkarcade.gui.model import GameListModel

    cfg = C.GameConfig()
    cfg.general.appid = "local-doom"
    cfg.general.name = "Doom"
    cfg.general.custom_executable = "/bin/true"
    cfg.runtime.type = "native"
    C.save(cfg)
    model = GameListModel()
    res = model.previewCommand(
        "local-doom", {"custom_executable": "/bin/true", "runtime_type": "native"}
    )
    assert "/bin/true" in res["command"]
    assert isinstance(res["warnings"], list)
    assert res["wrappers"] != ""
    assert model.diffDefaults("", {}) == ""
    diff = model.diffDefaults(
        "local-doom", {"custom_executable": "/bin/true", "runtime_type": "native"}
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


def test_settings_dependency_status(qgui_app, xdg_env, monkeypatch):
    import shutil as shutilmod

    from tkarcade.gui.model import GameListModel

    cfg = C.GameConfig()
    cfg.general.appid = "local-doom"
    cfg.general.name = "Doom"
    C.save(cfg)
    model = GameListModel()
    existing = lambda name, *a, **k: f"/usr/bin/{name}"  # noqa: E731

    # A clean local game: no prefix, every probed tool present but off.
    monkeypatch.setattr(shutilmod, "which", existing)
    rows = model.dependencyStatus("local-doom", {})
    by_key = {row["key"]: row for row in rows}
    assert by_key["custom_prefix"]["msg"] == "prefix-none"
    assert by_key["mangohud"]["kind"] == "ok"
    assert by_key["mangohud"]["msg"] == "binary-off"
    assert by_key["mangohud"]["args"] == ["mangohud", "/usr/bin/mangohud"]
    # The wording is QML's business (GameSettings.statusText).
    assert "text" not in by_key["mangohud"]
    # Steam options only exist for Steam games.
    assert "steam-options" not in by_key
    # Both wheels are listed while neither is enabled.
    assert "gamemoderun" in by_key and "game-performance" in by_key

    # Cachy's wheel sidelines Feral's (and vice versa).
    keys = [row["key"] for row in model.dependencyStatus("local-doom", {"gamemode_cachy": True})]
    assert "game-performance" in keys and "gamemoderun" not in keys
    keys = [row["key"] for row in model.dependencyStatus("local-doom", {"gamemode_feral": True})]
    assert "gamemoderun" in keys and "game-performance" not in keys

    # Missing binaries: a warning when enabled, a note when off.
    monkeypatch.setattr(shutilmod, "which", lambda name, *a, **k: None)
    by_key = {
        row["key"]: row for row in model.dependencyStatus("local-doom", {"mangohud_enable": True})
    }
    assert by_key["mangohud"]["kind"] == "warn"
    assert by_key["mangohud"]["msg"] == "binary-missing"
    assert by_key["gamescope"]["kind"] == "note"
    assert by_key["rt-upscale"]["msg"] == "binary-absent"

    # Empty hook paths stay hidden; a broken one warns and links to its folder.
    monkeypatch.setattr(shutilmod, "which", lambda name, *a, **k: None)
    sibling = C.game_file("local-doom").parent
    rows = model.dependencyStatus(
        "local-doom", {"pre_command": str(sibling / "gone.sh"), "post_command": ""}
    )
    by_key = {row["key"]: row for row in rows}
    assert "post_hook" not in by_key
    assert by_key["pre_hook"]["kind"] == "warn"
    assert by_key["pre_hook"]["msg"] == "hook-missing"
    assert by_key["pre_hook"]["args"] == ["pre-hook", str(sibling / "gone.sh")]
    assert by_key["pre_hook"]["link"] == str(sibling)

    # The prefix probe reports the wrapper it would run ('' when missing).
    monkeypatch.setattr(shutilmod, "which", existing)
    rows = model.dependencyStatus("local-doom", {"custom_prefix": "zink-run"})
    entry = next(r for r in rows if r["key"] == "custom_prefix")
    assert entry["msg"] == "binary-ok"
    assert entry["args"] == ["zink-run", "/usr/bin/zink-run"]


def test_settings_dependency_steam_options_cached(qgui_app, xdg_env, monkeypatch):
    from tkarcade import steam as S
    from tkarcade.gui.model import GameListModel

    cfg = C.GameConfig()
    cfg.general.appid = "620"
    C.save(cfg)
    calls = []

    def probe(appid):
        calls.append(appid)
        return "ok", "tkarcade %command%"

    monkeypatch.setattr(S, "launch_options_status", probe)
    # The row compares the `tkarcade` on PATH with this build: pin the
    # probe so the test never spawns an installed binary.
    import tkarcade.gui.model as modelmod
    from tkarcade import __version__ as gui_version

    monkeypatch.setattr(
        modelmod, "_path_tkarcade_version", lambda: ("/usr/bin/tkarcade", gui_version)
    )
    model = GameListModel()
    rows = model.dependencyStatus("620", {}, check_steam=True)
    assert [row["key"] for row in rows].count("steam-options") == 1
    entry = next(row for row in rows if row["key"] == "steam-options")
    # The raw options travel to QML, which words and translates the line.
    assert entry["msg"] == "steam-ok"
    assert entry["args"] == ["tkarcade %command%"]
    # Keystroke refreshes reuse the probe; the dialog asks again explicitly.
    model.dependencyStatus("620", {"mangohud_enable": True})
    model.dependencyStatus("620", {"mangohud_enable": True})
    assert calls == ["620"]
    model.dependencyStatus("620", {}, check_steam=True)
    assert calls == ["620", "620"]

    # A stale system package is named instead of silently launching it.
    monkeypatch.setattr(
        modelmod, "_path_tkarcade_version", lambda: ("/usr/bin/tkarcade", "0.0.0.old")
    )
    entry = next(
        row for row in model.dependencyStatus("620", {}, True) if row["key"] == "steam-options"
    )
    assert entry["kind"] == "warn"
    assert entry["msg"] == "steam-stale"
    assert entry["args"] == ["/usr/bin/tkarcade", "0.0.0.old", gui_version]
    # Not on PATH at all: Steam would fail to expand the options.
    monkeypatch.setattr(modelmod, "_path_tkarcade_version", lambda: ("", ""))
    entry = next(
        row for row in model.dependencyStatus("620", {}, True) if row["key"] == "steam-options"
    )
    assert entry["msg"] == "steam-no-binary"


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
    assert model.cloneGameTo("local-doom", "local-doom", False) == "Source and Target Are the Same."
    assert model.cloneGameTo("local-doom", "local-quake", False) == "OVERWRITE"
    assert model.cloneGameTo("local-doom", "local-new", False) == "Cloned local-doom to local-new."
    assert C.game_file("local-new").is_file()
    assert (C.profiles_dir("local-new") / "fast.toml").is_file()
    assert model.cloneGameTo("local-doom", "local-quake", True).startswith("Cloned")
    assert model.resetGames([]) == "Select Games First."
    assert model.resetGames(["local-doom"]) == "Reset 1 Game(s) to the Global Defaults Template."
    assert C.load("local-doom").general.name == ""
    assert (C.profiles_dir("local-doom") / "fast.toml").is_file()


def test_settings_steam_create(qgui_app, xdg_env):
    from tkarcade.gui.model import GameListModel

    model = GameListModel()
    assert model.saveGame("99", {"runtime_type": "proton"}) == "99"
    assert C.game_file("99").is_file()
    assert C.load("99").runtime.type == "proton"


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
    cfg.network.block_internet = True
    cfg.nightlight.disable_during_game = True
    cfg.nightlight.provider = "plasma"
    C.save(cfg)
    model = GameListModel()
    fields = model.loadGame("local-doom")
    assert fields["ludusavi_enable"] is True
    assert fields["ludusavi_restore"] is True
    assert fields["ludusavi_name"] == "Doom 3"
    assert fields["inhibit_idle"] is True
    assert fields["block_internet"] is True
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
    cfg.runtime.fresh_prefix = True
    cfg.runtime.winetricks_verbs = ["dotnet48"]
    cfg.runtime.tool = "GE-Proton9-1"
    cfg.runtime.prefix = "/tmp/opencode/pfx"
    cfg.debug.proton_log = True
    cfg.debug.winedebug = "+err"
    C.save(cfg)
    model = GameListModel()
    fields = model.loadGame("99")
    assert fields["fresh_prefix"] is True
    assert fields["winetricks_verbs"] == "dotnet48"
    assert fields["runtime_tool"] == "GE-Proton9-1"
    assert fields["runtime_prefix"] == "/tmp/opencode/pfx"
    assert fields["proton_log"] is True
    assert fields["winedebug"] == "+err"
    assert model.protonLogDir("99").endswith("99/proton")
    out = dict(fields)
    out["winedebug"] = "bogus"
    out["winetricks_verbs"] = "vcrun2022 dotnet48"
    out["runtime_tool"] = "wine-9.0"
    assert model.saveGame("99", out) == "99"
    reloaded = C.load("99")
    assert reloaded.debug.winedebug == ""
    assert reloaded.runtime.winetricks_verbs == ["vcrun2022", "dotnet48"]
    assert reloaded.runtime.tool == "wine-9.0"


def test_prefix_name_state_and_choices(qgui_app, xdg_env, tmp_path):
    from tkarcade.gui.model import GameListModel

    prefs = C.load_preferences()
    prefs.prefix_base = str(tmp_path / "prefixes")
    C.save_preferences(prefs)
    base = tmp_path / "prefixes"
    (base / "Doom" / "drive_c").mkdir(parents=True)
    (base / "Doom" / "system.reg").write_text("")
    (base / "NotAPrefix").mkdir()

    for appid, name in (("local-a", "Doom"), ("local-b", "Doom")):
        cfg = C.GameConfig()
        cfg.general.appid = appid
        cfg.runtime.prefix_name = name
        C.save(cfg)

    model = GameListModel()
    fields = model.loadGame("local-a")
    assert fields["runtime_prefix_name"] == "Doom"
    out = dict(fields)
    out["runtime_prefix_name"] = "Doom Eternal"
    assert model.saveGame("local-a", out) == "local-a"
    assert C.load("local-a").runtime.prefix_name == "Doom Eternal"

    state = model.prefixNameState("local-a", "Doom")
    assert state["target"] == str(base / "Doom")
    assert state["sanitized"] == "Doom"
    assert state["renamed"] is False
    assert state["exists"] is True
    assert state["is_prefix"] is True
    assert len(state["shared"]) == 1

    renamed = model.prefixNameState("local-a", "My Doom")
    assert renamed["sanitized"] == "MyDoom"
    assert renamed["renamed"] is True
    assert renamed["exists"] is False

    # A typed dir is the base: the prefix is always a subfolder of it.
    custom = tmp_path / "elsewhere" / "base"
    state = model.prefixNameState("local-a", "Doom", str(custom))
    assert state["target"] == str(custom / "Doom")
    assert state["exists"] is False
    # With no explicit name the game name derives the folder.
    derived = model.prefixNameState("local-a", "", "", "TK's good-game_1")
    assert derived["target"] == str(base / "TKsGoodGame1")
    assert derived["renamed"] is False

    choices = model.prefixChoices("local-a")
    assert [c["name"] for c in choices] == ["Doom"]
    assert choices[0]["path"] == str(base / "Doom")

    # A per-game base wins over the Preferences base for the picker.
    other_base = tmp_path / "other"
    other_prefix = other_base / "Styled"
    (other_prefix / "drive_c").mkdir(parents=True)
    (other_prefix / "system.reg").write_text("")
    custom_choices = model.prefixChoices("local-a", str(other_base))
    assert [c["name"] for c in custom_choices] == ["Styled"]
    assert custom_choices[0]["path"] == str(other_prefix)


def test_save_game_pins_the_prefix_folder(qgui_app, xdg_env, tmp_path):
    """The name-derived folder is stored, so a rename never moves it."""
    from tkarcade.gui.model import GameListModel

    prefs = C.load_preferences()
    prefs.prefix_base = str(tmp_path / "prefixes")
    C.save_preferences(prefs)
    model = GameListModel()
    fields = model.factoryGame("")
    fields.update(
        {
            "name": "TK's good-game_1",
            "custom_executable": "/bin/true",
            "runtime_type": "wine",
        }
    )
    appid = model.saveGame("", fields)
    assert appid
    cfg = C.load(appid)
    assert cfg.runtime.prefix_name == "TKsGoodGame1"
    pinned = C.prefix_dir(appid, cfg.runtime.prefix, prefs.prefix_base, cfg.runtime.prefix_name)
    assert pinned == tmp_path / "prefixes" / "TKsGoodGame1"

    # Renaming the game keeps both the stored name and the path.
    out = dict(model.loadGame(appid))
    out["name"] = "Renamed"
    assert model.saveGame(appid, out) == appid
    cfg = C.load(appid)
    assert cfg.runtime.prefix_name == "TKsGoodGame1"
    assert (
        C.prefix_dir(appid, cfg.runtime.prefix, prefs.prefix_base, cfg.runtime.prefix_name)
        == pinned
    )


def test_ensure_and_clear_the_local_prefix(qgui_app, xdg_env, tmp_path):
    from tkarcade.gui.model import GameListModel

    prefs = C.load_preferences()
    prefs.prefix_base = str(tmp_path / "prefixes")
    C.save_preferences(prefs)
    base = tmp_path / "prefixes"
    for appid, name in (("local-a", "Doom"), ("local-b", "Doom")):
        cfg = C.GameConfig()
        cfg.general.appid = appid
        cfg.general.name = name
        cfg.runtime.type = "wine"
        cfg.runtime.prefix_name = "Doom"  # both share the same prefix
        C.save(cfg)
    model = GameListModel()
    assert model.ensurePrefix("local-a") == ""
    assert (base / "Doom").is_dir()
    # The base itself is never the target, and a shared prefix is refused.
    assert model.clearCustomPrefix("local-a").startswith("Shared Prefix")
    assert (base / "Doom").is_dir()
    (C.game_file("local-b")).unlink()
    assert model.clearCustomPrefix("local-a") == f"Cleared {base / 'Doom'}."
    assert not (base / "Doom").exists()
    assert base.is_dir()


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
    # Reset applies the template (menu_timeout 11 above), not factory values.
    assert model.templateGame("local-doom")["menu_timeout"] == 11
    assert model.templateGame("local-doom")["appid"] == "local-doom"
    # Downgrade gate: template and live file here are current, the last one
    # stamps a future version.
    assert model.needsNewerApp("local-doom", "") is False
    assert model.needsNewerApp("", "") is False
    C.game_file("local-new").parent.mkdir(parents=True, exist_ok=True)
    C.game_file("local-new").write_text(
        '[general]\nappid = "local-new"\nconfig_version = 999\n', encoding="utf-8"
    )
    assert model.needsNewerApp("local-new", "") is True


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


def test_settings_coverage_uses_the_dialog_name(qgui_app, xdg_env, monkeypatch):
    """A local game resolves saves by the dialog name, before any Save."""
    import time

    from tkarcade.backends import ludusavi as lumod
    from tkarcade.gui.model import GameListModel

    seen = []
    monkeypatch.setattr(
        lumod,
        "check_coverage",
        lambda appid, name="": (seen.append((appid, name)), ("no-entry", ""))[1],
    )
    model = GameListModel()

    def run(*args):
        out = []
        model.coverageFinished.connect(lambda s, d: out.append((s, d)))
        model.checkCoverage(*args)
        deadline = time.monotonic() + 30
        while not out and time.monotonic() < deadline:
            qgui_app.processEvents()
            time.sleep(0.01)
        model.coverageFinished.disconnect()
        assert out, f"no coverage result for {args}"
        return out[0]

    # The dialog name, the override, then Steam (its id infers the title).
    run("local-dialog", "", "Doom")
    run("local-dialog", "Other", "Doom")
    run("12345", "", "Portal 2")
    assert seen == [
        ("local-dialog", "Doom"),
        ("local-dialog", "Other"),
        ("12345", ""),
    ]

    # Without a dialog name a local game falls back to the saved one.
    cfg = C.GameConfig()
    cfg.general.appid = "local-saved"
    cfg.general.name = "Quake"
    C.save(cfg)
    run("local-saved", "", "")
    assert seen[-1] == ("local-saved", "Quake")


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
    assert model.exportTarball(str(tmp_path / "missing" / "x.tar.gz")).startswith("Export Failed")
    C.game_file("99").unlink()
    assert model.importTarball(str(dest)) == "Imported 1 Game(s)"
    assert C.game_file("99").is_file()
    assert model.importTarball("") == ""
    assert model.importTarball(str(tmp_path / "nope.tar.gz")).startswith("Import Failed")


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
    assert "steamtinkerlaunch' Profile" in model.importStl(["99"])
    assert C.profile_file("99", "steamtinkerlaunch").is_file()
    assert "Skipped" in model.importStl(["100"])
    assert model.importStl([]) == "Nothing Selected."


def test_import_predecessor_without_source(qgui_app, xdg_env):
    from tkarcade.gui.model import GameListModel

    assert GameListModel().importPredecessor().startswith("Import Failed")


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


def test_proxy_is_eleven_column_table(qgui_app, xdg_env):
    from PySide6.QtCore import Qt

    proxy = _filtered(qgui_app)
    assert proxy.columnCount() == 11
    assert proxy.columnCount(proxy.index(0, 0)) == 0
    assert [proxy.headerData(c, Qt.Orientation.Horizontal) for c in range(11)] == [
        "#",
        "Game",
        "App ID",
        "Played",
        "ProtonDB",
        "Origin",
        "Last Played",
        "Platform",
        "Runtime",
        "Wine",
        "Install Dir",
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
    assert proxy.columnCount() == 11
    assert (
        proxy.headerData(2, __import__("PySide6.QtCore", fromlist=["x"]).Qt.Orientation.Horizontal)
        == "Played"
    )
    assert C.load_preferences().column_order.split(",")[:3] == ["0", "1", "3"]
    proxy.showAppId = False
    assert proxy.columnCount() == 11  # hidden columns keep mapped slots
    assert "2" in C.load_preferences().hidden_columns.split(",")
    proxy.resetColumns()
    assert proxy.columnCount() == 11
    assert C.load_preferences().hidden_columns == "7,8,9,10"
    proxy.moveColumn(0, -1)  # edge: no-op, stays valid
    assert proxy.columnCount() == 11


def test_refresh_counts_only_steam_detected(qgui_app, xdg_env):
    from tkarcade.gui.model import GameListModel

    cfg = C.GameConfig()
    cfg.general.appid = "local-doom"
    cfg.general.name = "Doom"
    cfg.general.custom_executable = "/bin/true"
    C.save(cfg)
    model = GameListModel()
    model.refresh()
    assert model.steamDetectedCount == 0  # local games must not inflate it


def test_game_issues_cache_invalidated_on_refresh(qgui_app, xdg_env):
    from tkarcade.gui.model import GameListModel

    cfg = C.GameConfig()
    cfg.general.appid = "local-broken"
    cfg.general.name = "Broken"
    cfg.general.custom_executable = "/nonexistent/doom"
    cfg.runtime.type = "native"
    C.save(cfg)  # missing executable -> validation issue
    model = GameListModel()
    assert model.gameIssues("local-broken") != []
    fixed = C.load("local-broken")
    fixed.general.custom_executable = "/bin/true"
    C.save(fixed)
    model.refresh()
    assert model.gameIssues("local-broken") == []


def test_tray_recents_rows(qgui_app, xdg_env, monkeypatch):
    """Tray recents: [appid, label], gated by the quick-launch prefs."""
    from tkarcade.gui.model import GameListModel

    model = GameListModel()
    monkeypatch.setattr(
        model,
        "historySummary",
        lambda: [
            {"appid": "99", "name": "Doom 3", "total": "1h"},
            {"appid": "local-doom", "name": "Doom", "total": "30m"},
        ],
    )
    prefs = C.load_preferences()
    prefs.tray_quick_launch = False
    C.save_preferences(prefs)
    assert model.trayRecentGames() == []
    prefs.tray_quick_launch = True
    prefs.tray_quick_count = 1
    C.save_preferences(prefs)
    assert model.trayRecentGames() == [["99", "Doom 3 (1h)"]]


def test_tray_action_dispatch(qgui_app, xdg_env, monkeypatch):
    """trayAction: registered entries run, "play:<appid>" plays."""
    from tkarcade.gui.model import GameListModel

    model = GameListModel()
    played = []
    monkeypatch.setattr(model, "play", lambda appid: played.append(appid) or True)
    ran = []
    model._tray_actions = {"prefs": lambda: ran.append("prefs")}
    assert model.trayDefaultsAvailable() is False
    model.trayAction("prefs")
    model.trayAction("play:local-doom")
    model.trayAction("")  # unknown entries are ignored
    model.trayAction("nope")
    assert ran == ["prefs"]
    assert played == ["local-doom"]
    model._tray_actions["defaults"] = lambda: None
    assert model.trayDefaultsAvailable() is True


def test_audio_sinks_pair_name_and_label(qgui_app, xdg_env, monkeypatch):
    """audioSinks keeps the node name for config and the label for the UI."""
    from tkarcade.backends import audio as aubackend
    from tkarcade.gui.model import GameListModel

    model = GameListModel()
    monkeypatch.setattr(
        aubackend,
        "list_sinks",
        lambda: [("alsa_hdmi", "HDMI Estéreo"), ("alsa_usb", "")],
    )
    assert model.audioSinks() == [["alsa_hdmi", "HDMI Estéreo"], ["alsa_usb", "alsa_usb"]]
    monkeypatch.setattr(aubackend, "list_sinks", lambda: [])
    assert model.audioSinks() == []


def test_model_running_role_and_terminate(qgui_app, xdg_env):
    import json
    import signal
    import subprocess
    import sys

    from tkarcade import running
    from tkarcade.gui.model import GameListModel

    cfg = C.GameConfig()
    cfg.general.appid = "local-run"
    cfg.general.name = "Runtime"
    cfg.general.custom_executable = "/bin/true"
    cfg.runtime.type = "native"
    C.save(cfg)
    child = subprocess.Popen(
        [sys.executable, "-c", "import time; time.sleep(60)"], start_new_session=True
    )
    try:
        path = running.record_path("local-run")
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            json.dumps(
                {
                    "appid": "local-run",
                    "pid": child.pid,
                    "start": running.process_start_time(child.pid),
                    "started": 0,
                }
            )
        )
        model = GameListModel()
        model._refresh_running()
        assert model.isRunning("local-run") is True
        assert model.runningIds == ["local-run"]
        row = next(
            i
            for i in range(model.rowCount())
            if model.data(model.index(i, 0), model.IdRole) == "local-run"
        )
        assert model.data(model.index(row, 0), model.RunningRole) is True
        assert model.rowData(row)["gameRunning"] is True
        reported = []
        model.terminateReported.connect(lambda *args: reported.append(args))
        assert model.terminate("local-run") is True
        assert child.wait(timeout=10) == -signal.SIGTERM
        assert reported == [(True, "Runtime", "")]
        model._refresh_running()
        assert model.isRunning("local-run") is False
        assert model.runningIds == []
        assert model.data(model.index(row, 0), model.RunningRole) is False
        # Stop the model's timers before the next test: its 10 s kill
        # timer would otherwise fire mid-QML-suite, in a process that no
        # longer owns the C++ object (pytestqt processes events there).
        model._stop_timers()
        model.deleteLater()
        qgui_app.processEvents()
    finally:
        if child.poll() is None:
            child.kill()
            child.wait(timeout=10)
        running.record_path("local-run").unlink(missing_ok=True)


def test_row_icon_uses_the_artwork_source_appid(qgui_app, xdg_env):
    """A local game's row icon is the source AppID's downloaded art."""
    from tkarcade import artwork

    local = C.GameConfig()
    local.general.appid = "local-doom"
    local.general.name = "Doom"
    local.general.custom_executable = "/bin/true"
    local.runtime.type = "native"
    local.artwork.artwork_appid = "480"
    C.save(local)
    donor_icon = artwork.grid_path("480", "icon")
    donor_icon.parent.mkdir(parents=True, exist_ok=True)
    donor_icon.write_bytes(b"I")
    model = _model(qgui_app)
    row = next(
        i
        for i in range(model.rowCount())
        if model.data(model.index(i, 0), model.IdRole) == "local-doom"
    )
    assert model.data(model.index(row, 0), model.IconRole) == str(donor_icon)
    assert model.effectiveArtwork("local-doom", "icon") == str(donor_icon)
    # cover is not covered by the source: the status says so
    assert model.artworkStatus("local-doom") == "donor"
    assert model.artworkStatus("local-missing") == "none"


def test_row_cover_uses_the_artwork_source_appid(qgui_app, xdg_env):
    """A local game's card cover is the source AppID's portrait art."""
    from tkarcade import artwork

    local = C.GameConfig()
    local.general.appid = "local-doom"
    local.general.name = "Doom"
    local.general.custom_executable = "/bin/true"
    local.runtime.type = "native"
    local.artwork.artwork_appid = "480"
    C.save(local)
    donor_cover = artwork.grid_path("480", "cover")
    donor_cover.parent.mkdir(parents=True, exist_ok=True)
    donor_cover.write_bytes(b"C")
    model = _model(qgui_app)
    row = next(
        i
        for i in range(model.rowCount())
        if model.data(model.index(i, 0), model.IdRole) == "local-doom"
    )
    assert model.data(model.index(row, 0), model.CoverRole) == str(donor_cover)
    assert model.rowData(row)["gameCover"] == str(donor_cover)


def test_fetch_artwork_needs_a_source_appid_not_a_key(qgui_app, xdg_env, monkeypatch):
    """Official Steam art needs no key: only the source AppID is required."""
    from tkarcade import artwork

    calls = []

    def fake_best(appid, provider="steam", api_key="", kinds=artwork.ART_KINDS, force=False):
        calls.append((appid, provider, api_key, force))
        return {
            "art": {"icon": __import__("pathlib").Path("/tmp/x.png")},
            "provider": "steam",
            "error": "",
            "name": "Spacewar",
            "valid": True,
        }

    monkeypatch.setattr(artwork, "fetch_best", fake_best)
    local = C.GameConfig()
    local.general.appid = "local-quake"
    local.general.name = "Quake"
    local.general.custom_executable = "/bin/true"
    C.save(local)
    model = _model(qgui_app)
    assert model.fetchArtwork("") == "no-game"
    assert model.fetchArtwork("local-quake") == "no-appid"
    local.artwork.artwork_appid = "480"
    C.save(local)
    # A Steam AppID is enough with no key at all: the thread starts.
    started = []
    model.artworkFetched.connect(lambda gid, status, prov: started.append(status))
    assert model.fetchArtwork("local-quake") == ""
    for _ in range(50):
        if started:
            break
        qgui_app.processEvents()
        time.sleep(0.05)
    assert started == ["ok"], started
    # Forced, so a provider change in Preferences takes effect, and the
    # official provider is tried with no key at all.
    assert calls == [("480", "steam", "", True)]
    assert model.artworkSourceName("local-quake") == "Spacewar"


def test_clear_fetched_artwork_uses_the_source_appid(qgui_app, xdg_env):
    """Clear removes the source AppID's cache, even before Save."""
    from tkarcade import artwork

    local = C.GameConfig()
    local.general.appid = "local-doom"
    local.general.name = "Doom"
    local.general.custom_executable = "/bin/true"
    C.save(local)
    model = _model(qgui_app)
    assert model.clearFetchedArtwork("") == "no-game"
    assert model.clearFetchedArtwork("local-doom") == "no-appid"
    cover = artwork.grid_path("480", "cover")
    cover.parent.mkdir(parents=True, exist_ok=True)
    cover.write_bytes(b"P")
    # The draft value wins over the saved config, like Fetch Artwork.
    assert model.clearFetchedArtwork("local-doom", "480") == "done"
    assert artwork.cached_path("480", "cover") is None
    assert artwork.is_cleared("480") is True
    # The mark reaches the status row instead of looking like art that
    # simply never arrived.
    assert model.artworkStatus("local-doom", "480") == "cleared"


def test_settings_winetricks_verbs_pending(qgui_app, xdg_env, tmp_path, monkeypatch):
    from tkarcade import steam as S
    from tkarcade.gui.model import GameListModel

    model = GameListModel()

    # Local game: the WINEPREFIX holds the log directly.
    base = tmp_path / "base"
    prefix = C.prefix_dir("local-doom", str(base), "", "", "Doom")
    (prefix / "drive_c").mkdir(parents=True)
    (prefix / "winetricks.log").write_text("corefonts\n", encoding="utf-8")
    cfg = C.GameConfig()
    cfg.general.appid = "local-doom"
    cfg.general.name = "Doom"
    cfg.runtime.type = "wine"
    cfg.runtime.prefix = str(base)
    C.save(cfg)
    state = model.installedVerbs("local-doom", "corefonts vcrun2022")
    assert state["installed"] == ["corefonts"]
    assert state["pending"] == ["vcrun2022"]
    assert model.installedVerbs("local-doom", "") == {"installed": ["corefonts"], "pending": []}

    # Steam game: Steam's compatdata container, log inside its pfx.
    container = tmp_path / "compatdata" / "620"
    (container / "pfx").mkdir(parents=True)
    (container / "pfx" / "winetricks.log").write_text("dotnet48\n", encoding="utf-8")
    cfg = C.GameConfig()
    cfg.general.appid = "620"
    C.save(cfg)
    monkeypatch.setattr(S, "prefix_dir", lambda appid: container)
    assert model.installedVerbs("620", "")["installed"] == ["dotnet48"]
    # A custom prefix wins over Steam's own compatdata dir.
    cfg.runtime.prefix = str(container)
    C.save(cfg)
    monkeypatch.setattr(S, "prefix_dir", lambda appid: tmp_path / "gone")
    assert model.installedVerbs("620", "")["installed"] == ["dotnet48"]


def test_settings_winetricks_gui_refusals(qgui_app, xdg_env, tmp_path, monkeypatch):
    from tkarcade import steam as S
    from tkarcade.gui.model import GameListModel

    model = GameListModel()
    cfg = C.GameConfig()
    cfg.general.appid = "620"
    cfg.runtime.prefix = str(tmp_path / "pfx")
    C.save(cfg)
    # A custom prefix takes winetricks, which needs the game's Proton.
    from tkarcade import proton as P

    monkeypatch.setattr(P, "compat_tool_name", lambda appid: None)
    assert "Proton" in model.openWinetricksGui("620")
    cfg.runtime.prefix = ""
    C.save(cfg)
    # protontricks refuses games that never ran: it needs their compatdata.
    monkeypatch.setattr(S, "prefix_dir", lambda appid: None)
    assert "Launched Once" in model.openWinetricksGui("620")
    # With a compatdata prefix present the missing binary is the refusal.
    monkeypatch.setattr(S, "prefix_dir", lambda appid: tmp_path / "compatdata" / "620")
    monkeypatch.setenv("PATH", str(tmp_path / "empty"))
    assert "Protontricks Was Not Found" in model.openWinetricksGui("620")
    # A native local game has nothing to install into.
    local = C.GameConfig()
    local.general.appid = "local-native"
    local.runtime.type = "native"
    C.save(local)
    assert "Wine or Proton" in model.openWinetricksGui("local-native")


def test_settings_winetricks_gui_custom_prefix(qgui_app, xdg_env, fake_bin, tmp_path, monkeypatch):
    """A Steam game with a custom prefix runs winetricks against its pfx."""
    import time

    from tkarcade import proton as P
    from tkarcade.gui.model import GameListModel

    calls = tmp_path / "calls.log"
    fake_bin("winetricks", f'#!/bin/sh\necho "$WINEPREFIX|$WINE|$@" >> "{calls}"\n')
    proton = tmp_path / "GE-Proton9-1"
    (proton / "files" / "bin").mkdir(parents=True)
    wine = proton / "files" / "bin" / "wine"
    wine.write_text("#!/bin/sh\n")
    wine.chmod(0o755)
    container = tmp_path / "custom-compatdata"
    (container / "pfx" / "drive_c").mkdir(parents=True)
    cfg = C.GameConfig()
    cfg.general.appid = "620"
    cfg.runtime.prefix = str(container)
    cfg.runtime.tool = str(proton)  # an explicit tool wins over the mapping
    C.save(cfg)
    monkeypatch.setattr(P, "compat_tool_name", lambda appid: None)
    model = GameListModel()
    assert model.openWinetricksGui("620") == ""
    deadline = time.time() + 5
    while not calls.exists() and time.time() < deadline:
        time.sleep(0.02)
    assert calls.read_text().strip() == f"{container / 'pfx'}|{wine}|--gui"


def test_steam_runtime_state(qgui_app, xdg_env):
    """The dialog hint reads umu's own layout; a missing one is not an error."""
    from pathlib import Path

    model = _model(qgui_app)
    assert model.steamRuntimeState("") == {"installed": False, "label": "", "path": ""}
    assert model.steamRuntimeState("bogus")["label"] == ""
    state = model.steamRuntimeState("sniper")
    assert state["label"] == "Steam Linux Runtime 3.0 (sniper)"
    assert state["path"].endswith("umu/steamrt3")
    assert state["installed"] is False
    Path(state["path"]).mkdir(parents=True)
    assert model.steamRuntimeState("sniper")["installed"] is True


def test_settings_winetricks_gui_launch(qgui_app, xdg_env, fake_bin, tmp_path):
    import time

    from tkarcade.gui.model import GameListModel

    calls = tmp_path / "calls.log"
    fake_bin("winetricks", f'#!/bin/sh\necho "$WINEPREFIX|$WINE|$@" >> "{calls}"\n')
    wine = fake_bin("wine")
    base = tmp_path / "base"
    prefix = C.prefix_dir("local-doom", str(base), "", "", "Doom")
    (prefix / "drive_c").mkdir(parents=True)
    cfg = C.GameConfig()
    cfg.general.appid = "local-doom"
    cfg.general.name = "Doom"
    cfg.runtime.type = "wine"
    cfg.runtime.prefix = str(base)
    cfg.runtime.tool = str(wine)
    C.save(cfg)
    model = GameListModel()
    assert model.openWinetricksGui("local-doom") == ""
    deadline = time.time() + 5
    while not calls.exists() and time.time() < deadline:
        time.sleep(0.02)
    assert calls.read_text().strip() == f"{prefix}|{wine}|--gui"


def test_settings_winetricks_gui_reports_failure(qgui_app, xdg_env, fake_bin, tmp_path):
    """A tool that dies leaves its output in a log and the exit is news."""
    import time

    from tkarcade import xdg
    from tkarcade.gui.model import GameListModel

    fake_bin("winetricks", "#!/bin/sh\necho 'no such verb' >&2\nexit 3\n")
    wine = fake_bin("wine")
    base = tmp_path / "base"
    prefix = C.prefix_dir("local-doom", str(base), "", "", "Doom")
    (prefix / "drive_c").mkdir(parents=True)
    cfg = C.GameConfig()
    cfg.general.appid = "local-doom"
    cfg.general.name = "Doom"
    cfg.runtime.type = "wine"
    cfg.runtime.prefix = str(base)
    cfg.runtime.tool = str(wine)
    C.save(cfg)
    model = GameListModel()
    seen: list[tuple[str, str]] = []
    model.verbToolClosed.connect(lambda status, detail: seen.append((status, detail)))
    assert model.openWinetricksGui("local-doom") == ""
    deadline = time.time() + 5
    while not seen and time.time() < deadline:
        qgui_app.processEvents()
        time.sleep(0.02)
    log_path = xdg.games_log_dir() / "local-doom-winetricks.log"
    assert seen == [("failed", str(log_path))]
    assert "no such verb" in log_path.read_text(encoding="utf-8")
