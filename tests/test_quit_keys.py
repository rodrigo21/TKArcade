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
