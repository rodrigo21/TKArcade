"""Static QML wiring checks: source assertions, no Qt instance needed.

These read the shipped `.qml` files and assert the wiring every dialog
must carry (Ctrl+Q, Escape and Enter). They live in the fast suite so a
wiring regression fails in milliseconds instead of taking a slot in the
QML driver's subprocess batches.
"""

import pathlib

from tkarcade.gui import kirigami_app as kapp

QML = pathlib.Path(kapp.__file__).parent / "qml"


def test_quit_keys_on_every_window():
    """Every window handles Ctrl+Q through the focus chain (Shortcut backup)."""
    for name in (
        "MainPage.qml",
        "GameSettings.qml",
        "HistoryView.qml",
        "PrefsDialog.qml",
        "ImportDialog.qml",
        "AboutDialog.qml",
    ):
        src = (QML / name).read_text()
        assert "Keys.onPressed" in src, name
        assert "Qt.Key_Q" in src, name


def test_every_dialog_watches_escape():
    """Every separate dialog Window registers the Escape filter.

    A QML Window has no QDialog reject(): the model filter is what turns
    Escape into a cancel (and dismisses an open popup first).
    """
    for name in (
        "AboutDialog.qml",
        "AddDialog.qml",
        "EditorPicker.qml",
        "GameSettings.qml",
        "HistoryView.qml",
        "ImportDialog.qml",
        "PrefsDialog.qml",
        "PrelaunchMenu.qml",
    ):
        src = (QML / name).read_text()
        assert "watchDialogKeys" in src, name


def test_every_dialog_has_a_default_button():
    """Every dialog body routes Enter to its default button.

    QQC2 buttons ignore Enter, so `Keys.onReturnPressed` on the body is
    what reproduces the widgets QDialog default button (a window
    `Shortcut` would steal the key from an editable TextArea).
    """
    for name in (
        "AboutDialog.qml",
        "AddDialog.qml",
        "EditorPicker.qml",
        "GameSettings.qml",
        "HistoryView.qml",
        "ImportDialog.qml",
        "PrefsDialog.qml",
        "PrelaunchMenu.qml",
    ):
        src = (QML / name).read_text()
        assert "Keys.onReturnPressed" in src, name
        assert "gameModel.pressDefault" in src, name


def test_kirigami_quit_action_neutered():
    """Kirigami's built-in Quit (close()) must not own Ctrl+Q."""
    src = (QML / "main.qml").read_text()
    assert 'quitAction.shortcut = ""' in src
