"""Kirigami GUI entry point (kirigami branch spike)."""

from __future__ import annotations

import os
import signal
import sys
from pathlib import Path


def qml_url(name: str = "main.qml") -> str:
    """File URL of a QML document (kept tiny for tests)."""
    from PySide6.QtCore import QUrl

    return QUrl.fromLocalFile(str(Path(__file__).parent / "qml" / name)).toString()


def build_engine(name: str = "main.qml"):
    """A QML engine with the model context wired in, the document loaded.

    Shared by the shell and the standalone editor (gui/edit.py). Models
    are parented to the engine: QML takes no ownership, so an unparented
    Python model would die with its wrapper (GC) and read as null in the
    UI. Returns (engine, model, game_filter); the caller checks
    `engine.rootObjects()` for a load failure.
    """
    from PySide6.QtCore import QUrl
    from PySide6.QtQml import QQmlApplicationEngine

    from .model import GameFilterModel, GameListModel

    engine = QQmlApplicationEngine()
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
    engine.load(QUrl(qml_url(name)))
    return engine, model, game_filter


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


def single_instance(name: str | None = None):
    """Ensure a single GUI instance. Returns the server, or None in followers.

    A follower pings the primary (which shows its window) and the caller
    exits 0. Stale sockets left behind by a crash are cleaned up. QtNetwork,
    so no new dependency; the socket name carries the uid so two users
    never fight over the same one. The shell can be hidden in the tray, so
    the ping means "come back", not just "raise".
    """
    from PySide6.QtNetwork import QLocalServer, QLocalSocket

    name = name or f"tkarcade-gui-{getattr(os, 'getuid', lambda: 0)()}"
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


def show_requested(server, window) -> None:
    """Drain show requests from follower instances and raise the window."""
    from PySide6.QtCore import Qt

    while server.hasPendingConnections():
        sock = server.nextPendingConnection()
        if sock is None:
            continue
        if sock.waitForReadyRead(500):
            sock.readAll()
        sock.disconnectFromServer()
    if window.windowState() & Qt.WindowState.WindowMinimized:
        window.setWindowState(window.windowState() & ~Qt.WindowState.WindowMinimized)
    window.setVisible(True)
    window.raise_()
    window.requestActivate()


def verbose_requested(argv: list[str] | None = None) -> bool:
    """Debug logging switch, so portal: lines show up when diagnosing."""
    return "--verbose" in (argv if argv is not None else sys.argv) or bool(
        os.environ.get("TKARCADE_VERBOSE")
    )


def _debug_geometry() -> None:
    """Print the themed icon inventory when TKARCADE_DEBUG_GEOMETRY=1."""
    if os.environ.get("TKARCADE_DEBUG_GEOMETRY") != "1":
        return
    from PySide6.QtGui import QIcon

    names = [
        "view-list-details",
        "view-list-icons",
        "view-grid",
        "view-column",
        "table",
        "overflow-menu",
        "sidebar-collapse-left",
        "media-playback-start",
        "list-add",
        "document-edit",
        "edit-delete",
        "input-gamepad",
        "go-down",
        "go-up",
    ]
    print("TKARCADE_ICONS theme=" + QIcon.themeName(), flush=True)
    for name in names:
        icon = QIcon.fromTheme(name)
        sizes = sorted({s.width() for s in icon.availableSizes()})
        pixnull = icon.pixmap(22, 22).isNull()
        print(
            "TKARCADE_ICONS "
            + name
            + "="
            + ("ok" if QIcon.hasThemeIcon(name) else "MISSING")
            + " sizes="
            + ",".join(map(str, sizes))
            + " nullpix="
            + str(pixnull),
            flush=True,
        )


def _tray_action(log, name: str, action):
    """Wrap a tray callback so a failure only logs and never takes the shell down."""

    def run() -> None:
        try:
            action()
        except Exception as e:
            log.warning("tray %s failed: %s", name, e)

    return run


def _tray_callbacks(root, log) -> dict:
    """Callbacks the native tray menu entries trigger (gui/tray.py)."""
    from PySide6.QtCore import QObject

    def toggle_visible() -> None:
        root.setVisible(not root.isVisible())
        if root.isVisible():
            root.requestActivate()

    def open_prefs() -> None:
        dlg = root.findChild(QObject, "prefsDialog")
        dlg.load()
        dlg.open()

    def open_about() -> None:
        root.findChild(QObject, "aboutDialog").open()

    def open_defaults() -> None:
        # Same path as the hamburger entry: sets the transient parent so the
        # editor is centered on the main window.
        root.findChild(QObject, "gamesPage").openDefaultsSettings()

    return {
        "toggle": _tray_action(log, "toggle", toggle_visible),
        "prefs": _tray_action(log, "prefs", open_prefs),
        "about": _tray_action(log, "about", open_about),
        "defaults": open_defaults,
    }


#: Tab index of "Artwork/Notes" in GameSettings.qml's TabBar (General
#: first, System before it). Keep in step when a tab is inserted.
SETTINGS_TAB_ARTWORK = 7


def parse_open_request(spec: str) -> tuple[str, str]:
    """Split a `TKARCADE_OPEN` value into (surface, argument).

    `settings:730` and `artwork:730` carry an AppID; `prefs`, `about`,
    `defaults`, `add` and `category` take none. A bare `settings` or
    `artwork` means "whatever is selected", which is what a display
    check usually wants.
    """
    surface, _, arg = spec.partition(":")
    return surface.strip().lower(), arg.strip()


def _child(root, name: str):
    """A QML object by `objectName`, looked up the way the tray does it."""
    from PySide6.QtCore import QObject

    return root.findChild(QObject, name)


def _open_settings(root, appid: str) -> None:
    page = _child(root, "gamesPage")
    if appid:
        page.openGameSettings(appid)
    else:
        # No AppID given: whatever the table has selected, like the menu.
        page.openSettingsForSelection()


def _open_artwork(root, appid: str) -> None:
    _open_settings(root, appid)
    _child(root, "settingsTabs").setProperty("currentIndex", SETTINGS_TAB_ARTWORK)


def _open_prefs(root) -> None:
    dlg = _child(root, "prefsDialog")
    dlg.load()
    dlg.open()


def _surface_handlers(root) -> dict:
    """One callable per `TKARCADE_OPEN` surface, mirroring the menu paths."""
    return {
        "settings": lambda arg: _open_settings(root, arg),
        "artwork": lambda arg: _open_artwork(root, arg),
        "add": lambda _arg: _child(root, "addGameDialog").open(),
        "category": lambda _arg: _child(root, "categoryDialog").openDialog(),
        "defaults": lambda _arg: _child(root, "gamesPage").openDefaultsSettings(),
        "prefs": lambda _arg: _open_prefs(root),
        "about": lambda _arg: _child(root, "aboutDialog").open(),
    }


def open_surface(root, log, spec: str) -> bool:
    """Open the dialog named by a `TKARCADE_OPEN` value.

    Diagnostic only (docs/plans/real-display-checks.md): it saves hunting
    through the menus on a real display. A bad name or a failure while
    opening logs and returns False, so the shell still comes up.
    """
    surface, arg = parse_open_request(spec)
    handlers = _surface_handlers(root)
    handler = handlers.get(surface)
    if handler is None:
        log.warning(
            "TKARCADE_OPEN=%s: unknown surface (want one of %s)",
            spec,
            ", ".join(sorted(handlers)),
        )
        return False
    try:
        handler(arg)
    except Exception as e:  # a broken check must never stop the launch
        log.warning("TKARCADE_OPEN=%s failed: %s", spec, e)
        return False
    return True


def main(argv: list[str] | None = None) -> int:
    """Run the Kirigami application (list, add and launch local games)."""
    import logging

    from PySide6.QtWidgets import QApplication

    log = logging.getLogger("tkarcade.kirigami")
    if verbose_requested(argv):
        logging.basicConfig(level=logging.DEBUG)
    if not os.environ.get("QT_QUICK_CONTROLS_STYLE"):
        os.environ["QT_QUICK_CONTROLS_STYLE"] = "org.kde.desktop"
    # A QApplication, not a QGuiApplication: on Plasma the platform theme
    # supplies the tray icon through KStatusNotifierItem, whose constructor
    # creates a QMenu -- a QWidget -- so QSystemTrayIcon.show() aborts the
    # process ("Cannot create a QWidget without QApplication") under a
    # QGuiApplication. Measured on Plasma 6/Wayland; see docs/QML-NOTES.md.
    # The UI stays QML: tests/test_no_widgets.py still bans every widget
    # class from the tree but this application object.
    app = QApplication(sys.argv if argv is None else argv)
    app.setApplicationName("TKArcade")
    app.setOrganizationName("TKArcade")
    signal.signal(signal.SIGINT, signal.SIG_DFL)
    # The interface language comes from the preferences (the picker in
    # Preferences), not from LANG, and the catalog has to be installed
    # before the engine loads: every qsTr() in the QML, and the Python-side
    # tray strings, resolve at creation time. Without this the shipped
    # pt_BR catalog was only ever used by the standalone editor.
    from .i18n import install_translations, preferred_language

    language = install_translations(app, preferred_language())
    if language:
        log.debug("interface language: %s", language)
    # Before the UI: a follower has nothing to build, it just wakes the
    # primary (which may be sitting in the tray) and exits 0.
    server = single_instance()
    if server is None:
        log.info("another instance is already running; asked it to show itself")
        return 0
    _debug_geometry()
    engine, model, _game_filter = build_engine("main.qml")
    if not engine.rootObjects():
        print("tkarcade: could not load the Kirigami interface", file=sys.stderr)
        return 1
    root = engine.rootObjects()[0]
    model.watchQuitKeys(root)
    server.newConnection.connect(lambda: show_requested(server, root))

    # The tray context menu is a native QMenu (gui/tray.py): these are the
    # callbacks its entries trigger.
    actions = _tray_callbacks(root, log)
    # Same as Ctrl+Q: quits without going through onClosing, so
    # Close-to-tray can never swallow the tray quit.
    actions["quit"] = app.quit
    model._tray_actions = actions

    from .tray import TrayController

    tray = TrayController(model)
    model._tray_refresher = tray.apply
    model.setTrayActive(tray.apply())
    apply_window_geometry(root)
    open_request = os.environ.get("TKARCADE_OPEN", "").strip()
    if open_request:
        open_surface(root, log, open_request)
    return app.exec()
