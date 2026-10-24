"""Kirigami window geometry: default size, persist, restore."""

import os
import subprocess
import sys
import textwrap
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


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


def test_the_app_can_build_a_widget(qgui_app):
    """Regression guard for the trap that killed the shell on Plasma.

    `QSystemTrayIcon.show()` reaches the Plasma platform theme, which
    builds a `KStatusNotifierItem` -- and its constructor a `QMenu` --
    deep inside Qt. Under a `QGuiApplication` that aborts the process
    ("Cannot create a QWidget without QApplication") while every offscreen
    test still passed, so the invariant worth pinning is the app type.
    """
    from PySide6.QtWidgets import QApplication, QWidget

    assert isinstance(qgui_app, QApplication)
    widget = QWidget()  # aborts the interpreter under a QGuiApplication
    assert widget.isWidgetType()


def test_single_instance_listens_and_wakes_the_primary(qgui_app, monkeypatch, tmp_path):
    """First launch listens; a follower pings it and the window comes back.

    TMPDIR pins the socket file inside tmp_path (Qt puts it in the system
    temp dir otherwise, where a real running instance could answer).
    """
    from PySide6.QtGui import QWindow

    from tkarcade.gui import kirigami_app as kapp

    monkeypatch.setenv("TMPDIR", str(tmp_path))
    name = f"tkarcade-test-{os.getpid()}"
    primary = kapp.single_instance(name)
    assert primary is not None
    try:
        assert kapp.single_instance(name) is None  # follower: pinged, then done
        qgui_app.processEvents()
        assert primary.hasPendingConnections()
        window = QWindow()
        window.hide()
        kapp.show_requested(primary, window)
        assert window.isVisible()
        assert not primary.hasPendingConnections()
    finally:
        primary.close()


def test_single_instance_recovers_a_stale_socket(qgui_app, monkeypatch, tmp_path):
    """A socket file left by a crash must not lock the user out for good."""
    import socket

    from tkarcade.gui import kirigami_app as kapp

    monkeypatch.setenv("TMPDIR", str(tmp_path))
    name = f"tkarcade-test-stale-{os.getpid()}"
    path = tmp_path / name
    stale = socket.socket(socket.AF_UNIX)
    stale.bind(str(path))
    stale.close()  # the file stays behind, with nobody listening on it
    assert path.exists()
    server = kapp.single_instance(name)
    assert server is not None
    try:
        assert server.fullServerName() == str(path)
    finally:
        server.close()


def _shell_env(tmp_path):
    """Environment for an out-of-process `main()`: sandboxed, offscreen."""
    env = dict(os.environ)
    env["PYTHONPATH"] = "src"
    env["QT_QPA_PLATFORM"] = "offscreen"
    env["HOME"] = str(tmp_path)
    # The single-instance socket lives in the temp dir: keep it inside the
    # sandbox so a real running shell cannot answer for this one.
    (tmp_path / "tmp").mkdir(exist_ok=True)
    env["TMPDIR"] = str(tmp_path / "tmp")
    for var in ("XDG_CONFIG_HOME", "XDG_STATE_HOME", "XDG_DATA_HOME", "XDG_CACHE_HOME"):
        (tmp_path / var).mkdir(exist_ok=True)
        env[var] = str(tmp_path / var)
    env.pop("TKARCADE_TEST_GUI", None)
    return env


def test_main_boots_the_shell(tmp_path):
    """`main()` builds its own QApplication and runs the shell.

    Out of process: `main()` builds its own application instance and the
    check is that a clean interpreter gets all the way through, which the
    in-process fixtures cannot show. A stand-in for `exec()` pumps the
    events a real loop would, instead of blocking.
    """
    script = textwrap.dedent(
        """
        from PySide6.QtWidgets import QApplication

        from tkarcade.gui import kirigami_app


        def fake_exec(self):
            for _ in range(20):
                self.processEvents()
            return 0


        QApplication.exec = fake_exec
        code = kirigami_app.main([])
        assert code == 0, code
        assert isinstance(QApplication.instance(), QApplication)
        print("OK")
        """
    )
    env = _shell_env(tmp_path)
    r = subprocess.run(
        [sys.executable, "-c", script],
        capture_output=True,
        text=True,
        cwd=ROOT,
        env=env,
        timeout=120,
    )
    assert r.returncode == 0 and "OK" in r.stdout, r.stdout + r.stderr


def test_main_installs_the_preferred_language(tmp_path):
    """The shell loads the catalog the preferences name, before the engine.

    Out of process for the same reason as the boot test, and because the
    translator is process-wide: `preferences.language = pt_BR` has to
    reach the QML strings and the Python-side tray menu, which only holds
    if `main()` installs it before the engine builds the window.
    """
    script = textwrap.dedent(
        """
        from PySide6.QtCore import QCoreApplication
        from PySide6.QtWidgets import QApplication

        from tkarcade import config as C
        from tkarcade.gui import kirigami_app

        prefs = C.load_preferences()
        prefs.language = "pt_BR"
        C.save_preferences(prefs)


        def fake_exec(self):
            for _ in range(20):
                self.processEvents()
            assert QCoreApplication.translate("MainPage", "Games") == "Jogos"
            assert QCoreApplication.translate("GameSettings", "Save") == "Salvar"
            assert (
                QCoreApplication.translate("TrayMenu", "Show / Hide")
                == "Mostrar / Ocultar"
            )
            return 0


        QApplication.exec = fake_exec
        code = kirigami_app.main([])
        assert code == 0, code
        print("OK")
        """
    )
    env = _shell_env(tmp_path)
    r = subprocess.run(
        [sys.executable, "-c", script],
        capture_output=True,
        text=True,
        cwd=ROOT,
        env=env,
        timeout=120,
    )
    assert r.returncode == 0 and "OK" in r.stdout, r.stdout + r.stderr


def test_toolbar_survives_translated_labels(tmp_path):
    """Wider translated labels must not hide the header actions.

    The title row's filter width used to follow a fixed guess (380px for
    the four text buttons). pt_BR labels are wider than English, and at
    the maximized 1440p/1.5 width (~1700) the row overran its slot and
    Kirigami pushed the whole actions row (view, Columns, hamburger) into
    overflow. Out of process: the desktop style is pinned at application
    creation, and it is the style whose extra padding tips the row over.
    """
    script = textwrap.dedent(
        """
        from PySide6.QtCore import QPointF
        from PySide6.QtGui import QFont
        from PySide6.QtQuick import QQuickItem
        from PySide6.QtWidgets import QApplication

        from tkarcade.gui import i18n
        from tkarcade.gui.kirigami_app import build_engine

        app = QApplication([])
        font = QFont(app.font())
        font.setPointSizeF(11)
        app.setFont(font)
        assert i18n.install_translations(app, "pt_BR") == "pt_BR"
        engine, _model, _filter = build_engine("main.qml")
        win = engine.rootObjects()[0]
        win.setProperty("width", 1700)
        win.setProperty("height", 900)
        win.show()
        for _ in range(40):
            app.processEvents()

        def visible(name):
            for item in win.findChildren(QQuickItem, name):
                if item.property("visible"):
                    return item
            return None

        remove = visible("titleRemove")
        assert remove is not None and remove.property("text") == "Remover"
        for name in ("toolbarIcons", "columnsButton", "hamburgerButton"):
            item = visible(name)
            assert item is not None, name
            left = item.mapToScene(QPointF(0, 0)).x()
            right = item.mapToScene(QPointF(item.property("width"), 0)).x()
            assert 0 <= left and right <= win.property("width"), (name, left, right)
        print("OK")
        """
    )
    env = _shell_env(tmp_path)
    env["QT_QUICK_CONTROLS_STYLE"] = "org.kde.desktop"
    r = subprocess.run(
        [sys.executable, "-c", script],
        capture_output=True,
        text=True,
        cwd=ROOT,
        env=env,
        timeout=120,
    )
    assert r.returncode == 0 and "OK" in r.stdout, r.stdout + r.stderr


# --- TKARCADE_OPEN: open one dialog at launch (real-display checks) --------


class _Stub:
    """Records the QML methods called on it, whatever their name."""

    def __init__(self, name):
        self.name = name
        self.calls = []

    def __getattr__(self, attr):
        def record(*args):
            self.calls.append((attr, args))

        return record


class _FakeRoot:
    """`findChild(QObject, name)` over a fixed set of stubs."""

    def __init__(self, *names):
        self.stubs = {name: _Stub(name) for name in names}

    def findChild(self, _type, name):
        return self.stubs.get(name)

    def calls(self, name):
        return self.stubs[name].calls


def test_parse_open_request():
    from tkarcade.gui.kirigami_app import parse_open_request

    assert parse_open_request("settings:730") == ("settings", "730")
    assert parse_open_request("artwork: 730 ") == ("artwork", "730")
    assert parse_open_request("Settings") == ("settings", "")
    assert parse_open_request("prefs") == ("prefs", "")
    assert parse_open_request("prefs:") == ("prefs", "")
    assert parse_open_request("") == ("", "")


def test_open_surface_opens_the_named_dialog():
    import logging

    from tkarcade.gui.kirigami_app import SETTINGS_TAB_ARTWORK, open_surface

    log = logging.getLogger("test")
    root = _FakeRoot(
        "gamesPage", "settingsTabs", "addGameDialog", "categoryDialog", "prefsDialog", "aboutDialog"
    )

    assert open_surface(root, log, "settings:730") is True
    assert root.calls("gamesPage") == [("openGameSettings", ("730",))]

    assert open_surface(root, log, "settings") is True
    assert root.calls("gamesPage")[-1] == ("openSettingsForSelection", ())

    assert open_surface(root, log, "artwork:730") is True
    assert root.calls("settingsTabs")[-1] == ("setProperty", ("currentIndex", SETTINGS_TAB_ARTWORK))

    assert open_surface(root, log, "add") is True
    assert root.calls("addGameDialog") == [("open", ())]

    assert open_surface(root, log, "category") is True
    assert root.calls("categoryDialog") == [("openDialog", ())]

    assert open_surface(root, log, "defaults") is True
    assert root.calls("gamesPage")[-1] == ("openDefaultsSettings", ())

    assert open_surface(root, log, "prefs") is True
    assert root.calls("prefsDialog") == [("load", ()), ("open", ())]

    assert open_surface(root, log, "about") is True
    assert root.calls("aboutDialog") == [("open", ())]


def test_open_surface_refuses_an_unknown_name(caplog):
    import logging

    from tkarcade.gui.kirigami_app import open_surface

    root = _FakeRoot("gamesPage")
    with caplog.at_level(logging.WARNING, logger="test"):
        assert open_surface(root, logging.getLogger("test"), "nope:1") is False
    assert "unknown surface" in caplog.text
    assert "settings" in caplog.text  # the message lists the valid names


def test_open_surface_survives_a_missing_dialog(caplog):
    """A broken check logs and lets the shell come up (no crash, no exit)."""
    import logging

    from tkarcade.gui.kirigami_app import open_surface

    root = _FakeRoot("gamesPage")  # no aboutDialog at all
    with caplog.at_level(logging.WARNING, logger="test"):
        assert open_surface(root, logging.getLogger("test"), "about") is False
    assert "TKARCADE_OPEN=about failed" in caplog.text
