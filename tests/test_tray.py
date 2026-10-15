"""System tray controller (fake availability, no desktop needed).

The controller is the only part of the tree that touches QtWidgets (the
menu itself is QML -- see test_kirigami_qml_cases.py for its entries), and
availability is stubbed so the suite never needs a real tray host.
"""

from types import SimpleNamespace


def _enable_tray(**kw):
    from tkarcade import config as C

    prefs = C.load_preferences()
    prefs.tray_enable = True
    for key, value in kw.items():
        setattr(prefs, key, value)
    C.save_preferences(prefs)


def _fake_model():
    """Model stub recording what the controller asks it to do."""
    calls = {"play": [], "menu": [], "action": []}
    model = SimpleNamespace(
        play=lambda appid: calls["play"].append(appid) or True,
        requestTrayMenu=lambda x, y: calls["menu"].append((x, y)),
        trayAction=lambda name: calls["action"].append(name),
    )
    return model, calls


def _controller(available=True):
    from tkarcade.gui.tray import TrayController

    model, calls = _fake_model()
    ctl = TrayController(model)
    ctl.is_available = lambda: available
    return ctl, calls


def test_apply_disabled_drops(qgui_app, xdg_env):
    ctl, _calls = _controller()
    assert ctl.apply() is False
    assert ctl.tray is None


def test_apply_unavailable_drops(qgui_app, xdg_env):
    _enable_tray()
    ctl, _calls = _controller(available=False)
    assert ctl.apply() is False
    assert ctl.tray is None


def test_apply_shows_the_icon_and_rebuilds_in_place(qgui_app, xdg_env):
    _enable_tray()
    ctl, _calls = _controller()
    assert ctl.apply() is True
    icon = ctl.tray
    assert icon is not None
    try:
        # Prefs changes reuse the icon: the menu rebuilds in QML.
        assert ctl.apply() is True
        assert ctl.tray is icon
    finally:
        ctl.drop()
    assert ctl.tray is None


def test_clicks_and_menu_requests_reach_the_model(qgui_app, xdg_env):
    """Both gestures go through the model, the only dispatch path."""
    ctl, calls = _controller()
    ctl.click()
    assert calls["action"] == ["toggle"]
    ctl.open_menu()
    assert len(calls["menu"]) == 1
    x, y = calls["menu"][0]
    assert isinstance(x, int) and isinstance(y, int)


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

    def fake_apply():
        calls.append(True)
        return True

    model._tray_refresher = fake_apply
    assert model.savePrefs({"trayEnable": True, "closeToTray": True}) is True
    assert calls == [True]
    # The refresher result must reach the model: tray-gated slots flip on.
    assert model.hideOnClose() is True


def test_close_to_tray_hides_window(qgui_app, xdg_env):
    import sys

    sys.path.insert(0, "tests")
    from kirigami_qml_cases import _load_main

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


def test_app_icon_comes_from_the_bundle(qgui_app, xdg_env):
    """The GUI icon helper is QtGui-only and loads the packaged SVGs.

    It used to live in the parked widgets package and fall back to
    `QApplication.style()`; the theme lookup replaces that without
    pulling QtWidgets into the tray module.
    """
    from tkarcade.gui import icons

    assert icons.icon_path("normal").is_file()
    assert icons.icon_path("mono").is_file()
    assert icons.icon_path("anything-else") == icons.icon_path("normal")
    assert not icons.app_icon().isNull()
    assert not icons.app_icon("mono").isNull()
