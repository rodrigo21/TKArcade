"""Kirigami GUI entry point (kirigami branch spike)."""

from __future__ import annotations

import os
import signal
import sys
from pathlib import Path


def qml_url() -> str:
    """File URL of the main QML document (kept tiny for tests)."""
    from PySide6.QtCore import QUrl

    return QUrl.fromLocalFile(str(Path(__file__).parent / "qml" / "main.qml")).toString()


DEFAULT_SIZE = (1280, 720)


def saved_size() -> tuple[int, int]:
    """Last window size, or the 1280x720 default (never raises)."""
    from .. import config as cfgmod

    try:
        raw = cfgmod.load_preferences().main_window_size or ""
        w, h = (int(x) for x in raw.split("x"))
        return max(640, w), max(480, h)
    except Exception:
        return DEFAULT_SIZE


def apply_window_geometry(win) -> None:
    """1280x720 (or the saved size), maximized when last closed so."""
    from PySide6.QtCore import QTimer

    from .. import config as cfgmod

    width, height = saved_size()
    win.setProperty("width", width)
    win.setProperty("height", height)
    try:
        if cfgmod.load_preferences().main_window_maximized:
            win.showMaximized()
    except Exception:
        pass
    timer = QTimer(win)
    timer.setSingleShot(True)
    timer.setInterval(500)
    timer.timeout.connect(lambda: save_window_geometry(win))
    win.widthChanged.connect(lambda _w: timer.start())
    win.heightChanged.connect(lambda _h: timer.start())


def save_window_geometry(win) -> None:
    """Persist size/maximized state (best effort, never raises)."""
    from PySide6.QtGui import QWindow

    from .. import config as cfgmod

    try:
        prefs = cfgmod.load_preferences()
    except Exception:
        return
    try:
        maximized = win.visibility() == QWindow.Visibility.Maximized
    except Exception:
        maximized = False
    prefs.main_window_maximized = maximized
    if not maximized:
        try:
            width, height = int(win.property("width")), int(win.property("height"))
        except Exception:
            return
        prefs.main_window_size = f"{max(640, width)}x{max(480, height)}"
    try:
        cfgmod.save_preferences(prefs)
    except OSError:
        pass


def verbose_requested(argv: list[str] | None = None) -> bool:
    """Debug logging switch, so portal: lines show up when diagnosing."""
    return "--verbose" in (argv if argv is not None else sys.argv) or bool(
        os.environ.get("TKARCADE_VERBOSE")
    )


def main(argv: list[str] | None = None) -> int:
    """Run the Kirigami application (list, add and launch local games)."""
    import logging

    from PySide6.QtGui import QGuiApplication
    from PySide6.QtQml import QQmlApplicationEngine

    from .model import GameFilterModel, GameListModel

    if verbose_requested(argv):
        logging.basicConfig(level=logging.DEBUG)
    if not os.environ.get("QT_QUICK_CONTROLS_STYLE"):
        os.environ["QT_QUICK_CONTROLS_STYLE"] = "org.kde.desktop"
    app = QGuiApplication(sys.argv if argv is None else argv)
    app.setApplicationName("TKArcade")
    app.setOrganizationName("TKArcade")
    signal.signal(signal.SIGINT, signal.SIG_DFL)
    engine = QQmlApplicationEngine()
    # Parent to the engine: QML takes no ownership, so an unparented
    # model would die with its Python wrapper (GC) and read as null.
    model = GameListModel(engine)
    engine.rootContext().setContextProperty("gameModel", model)
    game_filter = GameFilterModel(engine)
    game_filter.setSourceModel(model)
    engine.rootContext().setContextProperty("gameFilter", game_filter)
    engine.rootContext().setContextProperty(
        "TKARCADE_DEBUG_CLICKS", os.environ.get("TKARCADE_DEBUG_CLICKS", "")
    )
    engine.rootContext().setContextProperty(
        "TKARCADE_DEBUG_GEOMETRY", os.environ.get("TKARCADE_DEBUG_GEOMETRY", "")
    )
    from PySide6.QtCore import QUrl

    engine.load(QUrl(qml_url()))
    if not engine.rootObjects():
        print("tkarcade: could not load the Kirigami interface", file=sys.stderr)
        return 1
    apply_window_geometry(engine.rootObjects()[0])
    return app.exec()
