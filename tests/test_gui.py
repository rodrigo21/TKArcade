"""GUI smoke tests (offscreen). Skipped without PySide6."""

import pytest

QtWidgets = pytest.importorskip("PySide6.QtWidgets")


@pytest.fixture(scope="module")
def qapp():
    from PySide6.QtWidgets import QApplication

    app = QApplication.instance() or QApplication([])
    yield app


def test_dialogs_construct(qapp, xdg_env):
    from tksteamlaunch.gui.game_dialog import GameDialog
    from tksteamlaunch.gui.main_window import MainWindow

    w = MainWindow()
    w.show()
    GameDialog(w, "1", "T").show()
    GameDialog(w, defaults_mode=True).show()
    qapp.processEvents()


def test_launch_mode_buttons(qapp, xdg_env):
    from PySide6.QtWidgets import QDialog, QPushButton

    from tksteamlaunch import config as C
    from tksteamlaunch.gui.game_dialog import GameDialog

    d = GameDialog(None, "21", "T", launch_mode=True)
    assert d.launch_requested is False
    btn = next(b for b in d.findChildren(QPushButton) if "Launch" in b.text())
    btn.click()
    assert d.result() == QDialog.DialogCode.Accepted
    assert d.launch_requested is True
    assert C.game_file("21").exists()

    plain = GameDialog(None, "22", "T2")
    assert not any("Launch" in b.text() for b in plain.findChildren(QPushButton))


def test_provider_combo_data(qapp, xdg_env):
    from tksteamlaunch.gui.game_dialog import GameDialog

    d = GameDialog(None, "23", "T")
    datas = [d.cb_nl.itemData(i) for i in range(d.cb_nl.count())]
    assert datas == ["auto", "plasma", "gnome", "off"]
    d.cb_nl.setCurrentIndex(1)
    d.accept()
    from tksteamlaunch import config as C

    assert C.load("23").nightlight.provider == "plasma"


def test_preview_command(qapp, xdg_env):
    from PySide6.QtCore import QTimer
    from PySide6.QtWidgets import QApplication, QMessageBox, QPushButton

    from tksteamlaunch.gui.game_dialog import GameDialog

    d = GameDialog(None, "24", "T")
    d.c_feral.setChecked(True)
    QTimer.singleShot(
        300,
        lambda: [
            w.close()
            for w in QApplication.topLevelWidgets()
            if isinstance(w, QMessageBox)
        ],
    )
    btn = next(b for b in d.findChildren(QPushButton) if "Preview" in b.text())
    btn.click()
    qapp.processEvents()
    assert d.result() == 0  # preview must not accept/reject the dialog
