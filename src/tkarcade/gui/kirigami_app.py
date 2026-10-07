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
    from PySide6.QtCore import QUrl

    engine.load(QUrl(qml_url()))
    if not engine.rootObjects():
        print("tkarcade: could not load the Kirigami interface", file=sys.stderr)
        return 1
    return app.exec()
