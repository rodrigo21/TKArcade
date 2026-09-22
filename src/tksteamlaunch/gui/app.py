"""GUI entry point (PySide6)."""
from __future__ import annotations

import sys


def main() -> int:
    from PySide6.QtWidgets import QApplication

    from .main_window import MainWindow

    app = QApplication(sys.argv[1:])
    app.setApplicationName("TKSteamLaunch")
    app.setOrganizationName("TKSteamLaunch")
    w = MainWindow()
    w.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
