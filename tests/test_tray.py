"""System tray controller (fake availability, no desktop needed)."""

from types import SimpleNamespace


def _enable_tray(**kw):
    from tkarcade import config as C

    prefs = C.load_preferences()
    prefs.tray_enable = True
    for key, value in kw.items():
        setattr(prefs, key, value)
    C.save_preferences(prefs)


def _fake_model():
    played = []
    model = SimpleNamespace(
        historySummary=lambda: [
            {"appid": "99", "name": "Doom 3", "total": "1h"},
            {"appid": "local-doom", "name": "Doom", "total": "30m"},
        ],
        play=lambda appid: played.append(appid) or True,
    )
    return model, played


def _controller(model=None):
    from tkarcade.gui.tray import TrayController

    toggled, prefs_opened, about_opened, defaults_opened = [], [], [], []
    ctl = TrayController(
        model or _fake_model()[0],
        lambda: toggled.append(True),
        lambda: prefs_opened.append(True),
        lambda: about_opened.append(True),
        lambda: defaults_opened.append(True),
    )
    return ctl, toggled, prefs_opened, about_opened


def _available(monkeypatch, yes):
    from PySide6.QtWidgets import QSystemTrayIcon

    monkeypatch.setattr(QSystemTrayIcon, "isSystemTrayAvailable", lambda: yes)


def test_apply_disabled_drops(qgui_app, xdg_env):
    ctl, _t, _p, _a = _controller()
    assert ctl.apply() is False
    assert ctl.tray is None


def test_apply_unavailable_drops(qgui_app, xdg_env, monkeypatch):
    _enable_tray()
    _available(monkeypatch, False)
    ctl, _t, _p, _a = _controller()
    assert ctl.apply() is False
    assert ctl.tray is None


def test_apply_builds_menu_with_recents(qgui_app, xdg_env, monkeypatch):
    _enable_tray(tray_quick_launch=True, tray_quick_count=5)
    _available(monkeypatch, True)
    model, played = _fake_model()
    ctl, toggled, _p, _a = _controller(model)
    assert ctl.apply() is True
    assert ctl.tray is not None
    try:
        labels = [a.text() for a in ctl.menu.actions() if not a.isSeparator()]
        assert labels == [
            "Show / Hide",
            "Doom 3 (1h)",
            "Doom (30m)",
            "Global Defaults...",
            "Preferences...",
            "About...",
            "Quit",
        ]
        for action in ctl.menu.actions():
            if action.text() == "Show / Hide":
                action.trigger()
            if action.text() == "Doom 3 (1h)":
                action.trigger()
        assert toggled == [True]
        assert played == ["99"]
        from PySide6.QtWidgets import QSystemTrayIcon

        ctl._on_activated(QSystemTrayIcon.ActivationReason.Trigger)
        assert toggled == [True, True]
    finally:
        ctl.drop()
    assert ctl.tray is None


def test_hide_slots_follow_prefs_and_flag(qgui_app, xdg_env):
    from tkarcade import config as C
    from tkarcade.gui.model import GameListModel

    model = GameListModel()
    assert model.hideOnClose() is False
    assert model.hideOnMinimize() is False
    prefs = C.load_preferences()
    prefs.tray_enable = True
    prefs.close_to_tray = True
    prefs.minimize_to_tray = True
    C.save_preferences(prefs)
    assert model.hideOnClose() is False  # no tray up yet
    model.setTrayActive(True)
    assert model.hideOnClose() is True
    assert model.hideOnMinimize() is True
    model.setTrayActive(False)
    assert model.hideOnClose() is False


def test_save_prefs_refreshes_tray(qgui_app, xdg_env):
    from tkarcade.gui.model import GameListModel

    model = GameListModel()
    calls = []
    model._tray_refresher = lambda: calls.append(True)
    assert model.savePrefs({"trayEnable": True}) is True
    assert calls == [True]


def test_close_to_tray_hides_window(qgui_app, xdg_env):
    import sys

    sys.path.insert(0, "tests")
    from test_kirigami_qml import _load_main

    _enable_tray(close_to_tray=True)
    win, engine, _proxy, warnings = _load_main(qgui_app)
    model = engine.rootContext().contextProperty("gameModel")
    model.setTrayActive(True)
    assert win.isVisible() is True
    win.close()
    qgui_app.processEvents()
    assert win.isVisible() is False
    win.setVisible(True)
    assert win.isVisible() is True
    real = [w for w in warnings if "graphics scene" not in w]
    assert real == []
    win.close()
    model.setTrayActive(False)
    engine.deleteLater()
    qgui_app.processEvents()
