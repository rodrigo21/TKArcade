"""Window-scoped Ctrl+Q filter (safe: quit is a recorder, nothing closes)."""


def _press(key, modifiers):
    from PySide6.QtCore import QEvent
    from PySide6.QtGui import QKeyEvent

    return QKeyEvent(QEvent.Type.KeyPress, key, modifiers)


def test_quit_filter_quits_on_ctrl_q(qgui_app):
    from PySide6.QtCore import QObject, Qt

    from tkarcade.gui.model import _QuitFilter

    calls = []
    filt = _QuitFilter(quit_fn=lambda: calls.append(True))
    try:
        assert (
            filt.eventFilter(QObject(), _press(Qt.Key.Key_Q, Qt.KeyboardModifier.ControlModifier))
            is True
        )
        assert calls == [True]
        assert (
            filt.eventFilter(QObject(), _press(Qt.Key.Key_Q, Qt.KeyboardModifier.NoModifier))
            is False
        )
        assert (
            filt.eventFilter(QObject(), _press(Qt.Key.Key_W, Qt.KeyboardModifier.ControlModifier))
            is False
        )
        assert calls == [True]
    finally:
        qgui_app.removeEventFilter(filt)


def test_watchQuitKeys_installs_on_window(qgui_app, xdg_env):
    from PySide6.QtQuick import QQuickWindow

    from tkarcade.gui.model import GameListModel

    model = GameListModel()
    win = QQuickWindow()
    try:
        model.watchQuitKeys(win)  # must never raise, must not abort
        model.watchQuitKeys(None)
    finally:
        win.deleteLater()
    qgui_app.processEvents()


def test_escape_filter_closes_the_window(qgui_app):
    from PySide6.QtCore import Qt
    from PySide6.QtQuick import QQuickWindow

    from tkarcade.gui.model import _DialogKeyFilter

    win = QQuickWindow()
    win.show()
    filt = _DialogKeyFilter()
    win.installEventFilter(filt)
    try:
        assert win.isVisible() is True
        assert filt.eventFilter(win, _press(Qt.Key.Key_W, Qt.KeyboardModifier.NoModifier)) is False
        assert (
            filt.eventFilter(win, _press(Qt.Key.Key_Escape, Qt.KeyboardModifier.NoModifier)) is True
        )
        qgui_app.processEvents()
        assert win.isVisible() is False
    finally:
        win.removeEventFilter(filt)
        win.deleteLater()
    qgui_app.processEvents()


def test_watchDialogKeys_installs_on_window(qgui_app, xdg_env):
    from PySide6.QtQuick import QQuickWindow

    from tkarcade.gui.model import GameListModel

    model = GameListModel()
    win = QQuickWindow()
    try:
        model.watchDialogKeys(win)  # must never raise, must not abort
        model.watchDialogKeys(None)
    finally:
        win.deleteLater()
    qgui_app.processEvents()
