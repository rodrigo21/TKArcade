"""Kirigami window geometry: default size, persist, restore."""


def test_window_geometry_defaults(qgui_app, xdg_env):
    from tkarcade.gui import kirigami_app as kapp

    assert kapp.saved_size() == (1280, 720)


def test_window_geometry_roundtrip(qgui_app, xdg_env):
    from PySide6.QtQuick import QQuickWindow

    from tkarcade import config as C
    from tkarcade.gui import kirigami_app as kapp

    win = QQuickWindow()
    win.setProperty("width", 1400)
    win.setProperty("height", 900)
    kapp.save_window_geometry(win)
    assert C.load_preferences().main_window_size == "1400x900"
    assert kapp.saved_size() == (1400, 900)
    win.setProperty("width", 100)
    win.setProperty("height", 100)
    kapp.save_window_geometry(win)
    assert C.load_preferences().main_window_size == "640x480"
