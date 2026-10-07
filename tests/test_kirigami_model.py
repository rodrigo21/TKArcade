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
