"""GUI entry point (PySide6)."""

from __future__ import annotations

import os
import sys


def bundled_style() -> str:
    """Style override for self-contained bundles (AppImage).

    System theme plugins (Breeze, qt6ct, ...) build against the distro
    Qt and cannot load in the bundled one, so default to stock Fusion
    unless the user overrode the style explicitly.
    """
    if os.environ.get("APPIMAGE") and "QT_STYLE_OVERRIDE" not in os.environ:
        return "Fusion"
    return ""


def single_instance(name: str = "tksteamlaunch-gui"):
    """Ensure a single GUI instance. Returns the server, or None in followers.

    A follower notifies the primary (which shows its window) and the
    caller should exit 0. Stale sockets from crashes are cleaned up.
    """
    from PySide6.QtNetwork import QLocalServer, QLocalSocket

    server = QLocalServer()
    if server.listen(name):
        return server
    sock = QLocalSocket()
    sock.connectToServer(name)
    if sock.waitForConnected(1000):
        sock.write(b"show")
        sock.waitForBytesWritten(1000)
        sock.disconnectFromServer()
        return None
    # Nobody listening: stale socket left by a crash.
    QLocalServer.removeServer(name)
    server = QLocalServer()
    return server if server.listen(name) else None


def main() -> int:
    from PySide6.QtWidgets import QApplication

    from . import icons as iconsmod
    from .main_window import MainWindow

    style = bundled_style()
    if style:
        QApplication.setStyle(style)
    app = QApplication(sys.argv[1:])
    app.setApplicationName("TKSteamLaunch")
    app.setOrganizationName("TKSteamLaunch")
    app.setWindowIcon(iconsmod.app_icon())
    server = single_instance()
    if server is None:
        return 0
    w = MainWindow()
    server.newConnection.connect(lambda: _on_show_request(server, w))
    w.show()
    return app.exec()


def _on_show_request(server, window) -> None:
    """Drain show requests from follower instances and raise the window."""
    from PySide6.QtCore import Qt

    while server.hasPendingConnections():
        sock = server.nextPendingConnection()
        if sock is None:
            continue
        if sock.waitForReadyRead(500):
            sock.readAll()
        sock.disconnectFromServer()
    window.setWindowState(window.windowState() & ~Qt.WindowState.WindowMinimized)
    window.show()
    window.raise_()
    window.activateWindow()


if __name__ == "__main__":
    raise SystemExit(main())
