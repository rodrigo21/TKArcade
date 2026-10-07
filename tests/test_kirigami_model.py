"""Kirigami game list model (QtCore only, no widgets)."""

from tkarcade import config as C


def _model(qgui_app):
    from tkarcade.gui.model import GameListModel

    return GameListModel()


def _rows(model):
    return [
        (
            model.data(model.index(i), model.IdRole),
            model.data(model.index(i), model.NameRole),
            model.data(model.index(i), model.SourceRole),
            model.data(model.index(i), model.PlayedRole),
            model.data(model.index(i), model.TierRole),
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
    from tkarcade.gui.model import GameListModel

    model = GameListModel()
    assert model.columnOrder() == [0, 1, 2, 3, 4]
    assert model.hiddenColumns() == []
    assert model.saveColumns([0, 2, 1, 3, 4], [2, 9]) is True
    assert model.columnOrder() == [0, 2, 1, 3, 4]
    assert model.hiddenColumns() == [2]
    assert model.saveColumns([9, 9], []) is True  # garbage order ignored
    assert model.columnOrder() == [0, 2, 1, 3, 4]


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
