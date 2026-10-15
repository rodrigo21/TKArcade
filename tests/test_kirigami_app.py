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
    env = dict(os.environ)
    env["PYTHONPATH"] = "src"
    env["QT_QPA_PLATFORM"] = "offscreen"
    env["HOME"] = str(tmp_path)
    for var in ("XDG_CONFIG_HOME", "XDG_STATE_HOME", "XDG_DATA_HOME", "XDG_CACHE_HOME"):
        (tmp_path / var).mkdir(exist_ok=True)
        env[var] = str(tmp_path / var)
    env.pop("TKARCADE_TEST_GUI", None)
    r = subprocess.run(
        [sys.executable, "-c", script],
        capture_output=True,
        text=True,
        cwd=ROOT,
        env=env,
        timeout=120,
    )
    assert r.returncode == 0 and "OK" in r.stdout, r.stdout + r.stderr
