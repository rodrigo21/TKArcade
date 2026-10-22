"""System tray controller (fake availability, no desktop needed).

The controller owns the only QtWidgets use in the tree: the icon and the
native context menu the host shows on right-click. Availability is stubbed
so the suite never needs a real tray host, and the menu entries are
inspected directly instead of through a live popup.
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
    calls = {"action": []}
    state = {"recents": [], "defaults": False}
    model = SimpleNamespace(
        trayRecentGames=lambda: list(state["recents"]),
        trayDefaultsAvailable=lambda: state["defaults"],
        trayAction=lambda name: calls["action"].append(name),
    )
    return model, calls, state


def _controller(available=True):
    from tkarcade.gui.tray import TrayController

    model, calls, state = _fake_model()
    ctl = TrayController(model)
    ctl.is_available = lambda: available
    return ctl, calls, state


def _menu_texts(menu):
    """Labels of the visible entries, separators dropped."""
    return [a.text() for a in menu.actions() if not a.isSeparator()]


def _menu_controller(recents=None, defaults=False):
    """A shown controller whose menu can be inspected without a host."""
    _enable_tray()
    ctl, calls, state = _controller()
    state["recents"] = list(recents or [])
    state["defaults"] = defaults
    assert ctl.apply() is True
    return ctl, calls, state


def test_apply_disabled_drops(qgui_app, xdg_env):
    ctl, _calls, _state = _controller()
    assert ctl.apply() is False
    assert ctl.tray is None
    assert ctl.menu is None


def test_apply_unavailable_drops(qgui_app, xdg_env):
    _enable_tray()
    ctl, _calls, _state = _controller(available=False)
    assert ctl.apply() is False
    assert ctl.tray is None
    assert ctl.menu is None


def test_apply_shows_the_icon_and_rebuilds_in_place(qgui_app, xdg_env):
    _enable_tray()
    ctl, _calls, _state = _controller()
    assert ctl.apply() is True
    icon = ctl.tray
    assert icon is not None
    assert ctl.menu is not None
    from PySide6.QtWidgets import QMenu

    assert isinstance(ctl.menu, QMenu)
    try:
        # Prefs changes reuse the icon; the menu rebuilds on every open.
        assert ctl.apply() is True
        assert ctl.tray is icon
    finally:
        ctl.drop()
    assert ctl.tray is None
    assert ctl.menu is None


def test_click_and_activation_reach_the_model(qgui_app, xdg_env):
    """Left click toggles; Context is the host's to show, not ours."""
    from PySide6.QtWidgets import QSystemTrayIcon

    ctl, calls, _state = _controller()
    reasons = QSystemTrayIcon.ActivationReason
    ctl._on_activated(reasons.Context)
    assert calls["action"] == []  # no QML menu left to open
    ctl._on_activated(reasons.Trigger)
    ctl._on_activated(reasons.DoubleClick)
    assert calls["action"] == ["toggle", "toggle"]


def test_menu_without_recents_or_defaults(qgui_app, xdg_env):
    ctl, _calls, _state = _menu_controller()
    try:
        assert _menu_texts(ctl.menu) == ["Show / Hide", "Preferences...", "About...", "Quit"]
    finally:
        ctl.drop()


def test_menu_interleaves_recents_and_defaults(qgui_app, xdg_env):
    """Recents sit after Show / Hide, Global Defaults before Preferences."""
    ctl, calls, _state = _menu_controller(
        recents=[("99", "Doom 3 (1h)"), ("local-doom", "Doom (30m)")],
        defaults=True,
    )
    try:
        assert _menu_texts(ctl.menu) == [
            "Show / Hide",
            "Doom 3 (1h)",
            "Doom (30m)",
            "Global Defaults...",
            "Preferences...",
            "About...",
            "Quit",
        ]
        by_name = {a.objectName(): a for a in ctl.menu.actions()}
        for name in (
            "trayShowHide",
            "trayRecent0",
            "trayRecent1",
            "trayDefaults",
            "trayPrefs",
            "trayAbout",
            "trayQuit",
        ):
            by_name[name].trigger()
        assert calls["action"] == [
            "toggle",
            "play:99",
            "play:local-doom",
            "defaults",
            "prefs",
            "about",
            "quit",
        ]
    finally:
        ctl.drop()


def test_menu_refreshes_recents_on_about_to_show(qgui_app, xdg_env):
    """The host's aboutToShow rebuilds the dynamic entries, as QML did."""
    ctl, _calls, state = _menu_controller()
    try:
        assert _menu_texts(ctl.menu) == ["Show / Hide", "Preferences...", "About...", "Quit"]
        state["recents"] = [("99", "Doom 3 (1h)")]
        state["defaults"] = True
        ctl.menu.aboutToShow.emit()
        assert _menu_texts(ctl.menu) == [
            "Show / Hide",
            "Doom 3 (1h)",
            "Global Defaults...",
            "Preferences...",
            "About...",
            "Quit",
        ]
    finally:
        ctl.drop()


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
