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


def test_main_boots_on_a_qgui_application(tmp_path):
    """`main()` runs the shell (tray wiring included) without QtWidgets.

    Out of process: `main()` builds its own application instance and
    the check is that a clean interpreter never loads QtWidgets, which
    the in-process fixtures cannot show. A stand-in for `exec()` pumps
    the events a real loop would, instead of blocking.
    """
    script = textwrap.dedent(
        """
        import sys

        from PySide6.QtGui import QGuiApplication

        from tkarcade.gui import kirigami_app


        def fake_exec(self):
            for _ in range(20):
                self.processEvents()
            return 0


        QGuiApplication.exec = fake_exec
        code = kirigami_app.main([])
        assert code == 0, code
        assert "PySide6.QtWidgets" not in sys.modules, sorted(
            name for name in sys.modules if name.startswith("PySide6")
        )
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
