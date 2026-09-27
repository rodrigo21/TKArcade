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


def test_main_table_columns(qapp, xdg_env, monkeypatch):
    from tksteamlaunch import config as C
    from tksteamlaunch import protondb as pdbmod
    from tksteamlaunch.gui.main_window import MainWindow

    cfg = C.GameConfig()
    cfg.general.appid = "80"
    C.save(cfg)
    monkeypatch.setattr(pdbmod, "refresh", lambda appid: {"tier": "gold", "total": 5})
    w = MainWindow()
    w.show()
    qapp.processEvents()
    assert w.table.columnCount() == 3
    assert w.table.rowCount() == 1
    assert w.table.item(0, 1).text() == "80"
    for _ in range(100):
        cell = w.table.item(0, 2)
        if cell is not None and cell.text() == "Gold":
            break
        qapp.processEvents()
        import time

        time.sleep(0.02)
    assert w.table.item(0, 2).text() == "Gold"
    w._stop_pdb_worker()


def test_launch_mode_buttons(qapp, xdg_env):
    from PySide6.QtWidgets import QDialog, QPushButton

    from tksteamlaunch import config as C
    from tksteamlaunch.gui.game_dialog import GameDialog

    d = GameDialog(None, "21", "T", launch_mode=True)
    assert d.launch_requested is False
    btn = next(b for b in d.findChildren(QPushButton) if b.text() == "Save && Launch")
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


def test_detected_runtime_row(qapp, xdg_env, monkeypatch, tmp_path):
    from tksteamlaunch.gui.game_dialog import GameDialog

    root = tmp_path / "steam"
    (root / "config").mkdir(parents=True)
    (root / "config" / "config.vdf").write_text(
        '"InstallConfigStore"\n{\n"Software"\n{\n"Valve"\n{\n"Steam"\n'
        '{\n"CompatToolMapping"\n{\n"25"\n{\n"name" "proton_9"\n}\n}\n}\n}\n}\n}\n'
    )
    tooldir = root / "steamapps" / "common" / "proton_9"
    tooldir.mkdir(parents=True)
    (tooldir / "version").write_text("9.0-test\n")
    monkeypatch.setenv("STEAM_ROOT", str(root))
    d = GameDialog(None, "25", "T")
    assert d.e_runtime.text() == "proton_9 (9.0-test)"
    d2 = GameDialog(None, "26", "T2")
    assert d2.e_runtime.text() == "Proton"


def test_preview_command(qapp, xdg_env):
    from PySide6.QtCore import QTimer
    from PySide6.QtWidgets import QApplication, QMessageBox, QPushButton

    from tksteamlaunch.gui.game_dialog import GameDialog

    d = GameDialog(None, "24", "T")
    d.c_feral.setChecked(True)
    QTimer.singleShot(
        300,
        lambda: [w.close() for w in QApplication.topLevelWidgets() if isinstance(w, QMessageBox)],
    )
    btn = next(b for b in d.findChildren(QPushButton) if "Preview" in b.text())
    btn.click()
    qapp.processEvents()
    assert d.result() == 0  # preview must not accept/reject the dialog


def _auto_close_boxes(interval_ms=200):
    from PySide6.QtCore import QTimer

    timer = QTimer()
    timer.timeout.connect(_close_boxes)
    timer.start(interval_ms)
    return timer


def _pump_until(qapp, predicate, timeout_s=5.0):
    import time

    deadline = time.monotonic() + timeout_s
    while time.monotonic() < deadline:
        qapp.processEvents()
        _close_boxes()
        if predicate():
            return True
        time.sleep(0.02)
    qapp.processEvents()
    _close_boxes()
    return predicate()


def _close_boxes():
    from PySide6.QtWidgets import QApplication, QMessageBox

    for w in QApplication.topLevelWidgets():
        if isinstance(w, QMessageBox):
            w.close()


def test_coverage_button(qapp, xdg_env, monkeypatch, tmp_path):
    from PySide6.QtWidgets import QPushButton

    from tksteamlaunch.gui.game_dialog import GameDialog

    monkeypatch.setenv("PATH", str(tmp_path))  # no ludusavi -> unavailable path
    d = GameDialog(None, "28", "T")
    btn = next(b for b in d.findChildren(QPushButton) if "Coverage" in b.text())
    closer = _auto_close_boxes()
    try:
        btn.click()
        assert _pump_until(qapp, lambda: btn.isEnabled())
    finally:
        closer.stop()
    assert d.result() == 0
    d.reject()


def test_coverage_no_double_run(qapp, xdg_env, monkeypatch):
    import threading

    from PySide6.QtWidgets import QPushButton

    from tksteamlaunch.backends import ludusavi as lu
    from tksteamlaunch.gui.game_dialog import GameDialog

    entered, release, calls = threading.Event(), threading.Event(), []

    def slow(appid, override):
        calls.append(1)
        entered.set()
        release.wait(5)
        return ("covered", "x")

    monkeypatch.setattr(lu, "check_coverage", slow)
    d = GameDialog(None, "29", "T")
    btn = next(b for b in d.findChildren(QPushButton) if "Coverage" in b.text())
    closer = _auto_close_boxes()
    try:
        btn.click()
        assert entered.wait(5)
        btn.click()  # ignored while a check is running
        release.set()
        assert _pump_until(qapp, lambda: btn.isEnabled())
    finally:
        closer.stop()
    assert len(calls) == 1
    d.reject()


def test_show_menu_checkbox_roundtrip(qapp, xdg_env):
    from tksteamlaunch import config as C
    from tksteamlaunch.gui.game_dialog import GameDialog

    d = GameDialog(None, "22", "T")
    assert d.c_show_menu.isChecked() is False
    d.c_show_menu.setChecked(True)
    d.accept()
    assert C.load("22").general.show_menu is True


def test_coverage_button_hidden_in_defaults_mode(qapp, xdg_env):
    from tksteamlaunch.gui.game_dialog import GameDialog

    def buttons(dlg):
        return [b.text() for b in dlg.findChildren(QtWidgets.QPushButton)]

    assert "Check Coverage..." not in buttons(GameDialog(None, defaults_mode=True))
    assert "Check Coverage..." in buttons(GameDialog(None, "23", "T"))


def test_launch_button_hidden_without_command(qapp, xdg_env):
    from tksteamlaunch.gui.game_dialog import GameDialog

    def buttons(dlg):
        return [b.text() for b in dlg.findChildren(QtWidgets.QPushButton)]

    assert "Save && Launch" not in buttons(
        GameDialog(None, "24", "T", launch_mode=True, can_launch=False)
    )
    assert "Save && Launch" in buttons(GameDialog(None, "24", "T", launch_mode=True))


def test_gamemode_conflict_resolved_on_load(qapp, xdg_env):
    from tksteamlaunch import config as C
    from tksteamlaunch.gui.game_dialog import GameDialog

    cfg = C.GameConfig()
    cfg.general.appid = "30"
    cfg.gamemode.feral_gamemode = True
    cfg.gamemode.cachyos_game_performance = True
    C.save(cfg)
    d = GameDialog(None, "30", "T")
    assert d.c_feral.isChecked() and not d.c_cachy.isChecked()


def test_add_blank_choice_ignored(qapp, xdg_env, monkeypatch):
    from PySide6.QtWidgets import QInputDialog

    from tksteamlaunch.gui import main_window as mw

    monkeypatch.setattr(mw.steammod, "list_games", lambda: [("1", "G")])
    monkeypatch.setattr(QInputDialog, "getItem", lambda *a, **k: ("   ", True))

    def boom(*a, **k):
        raise AssertionError("dialog must not open")

    monkeypatch.setattr(mw, "GameDialog", boom)
    mw.MainWindow()._add()


def test_copy_launch_without_clipboard(qapp, xdg_env, monkeypatch):
    from PySide6.QtGui import QGuiApplication

    from tksteamlaunch.gui.main_window import MainWindow

    monkeypatch.setattr(QGuiApplication, "clipboard", classmethod(lambda cls: None))
    w = MainWindow()
    w._copy_launch()  # must not raise
    assert "unavailable" in w.status.text()


def test_launch_buttons_order_and_icons(qapp, xdg_env):
    from PySide6.QtWidgets import QDialogButtonBox

    from tksteamlaunch.gui.game_dialog import GameDialog

    d = GameDialog(None, "25", "T", launch_mode=True)
    box = d.findChild(QDialogButtonBox)
    texts = [b.text() for b in box.buttons()]
    assert texts.index("Launch") < texts.index("Save") < texts.index("Save && Launch")
    icons = {b.text(): b.icon() for b in box.buttons()}
    assert not icons["Launch"].isNull()
    assert not icons["Save && Launch"].isNull()


def test_launch_without_save_keeps_file(qapp, xdg_env):
    from PySide6.QtWidgets import QPushButton

    from tksteamlaunch import config as C
    from tksteamlaunch.gui.game_dialog import GameDialog

    cfg = C.GameConfig()
    cfg.general.appid = "26"
    C.save(cfg)
    before = C.game_file("26").read_bytes()
    d = GameDialog(None, "26", "T", launch_mode=True)
    d.e_exe.setText("/tmp/unsaved.exe")
    btn = next(b for b in d.findChildren(QPushButton) if b.text() == "Launch")
    btn.click()
    assert d.launch_requested is True
    assert C.game_file("26").read_bytes() == before
    assert C.load("26").general.custom_executable == ""


def test_steam_options_hidden_in_defaults_mode(qapp, xdg_env):
    from tksteamlaunch.gui.game_dialog import GameDialog

    assert "steam-options" not in GameDialog(None, defaults_mode=True)._status_labels
    assert "steam-options" in GameDialog(None, "31", "T")._status_labels


def test_exclusive_backends_visibility(qapp, xdg_env):
    from tksteamlaunch import config as C
    from tksteamlaunch.gui.game_dialog import GameDialog

    def vis(appid, feral, cachy):
        cfg = C.GameConfig()
        cfg.general.appid = appid
        cfg.gamemode.feral_gamemode = feral
        cfg.gamemode.cachyos_game_performance = cachy
        C.save(cfg)
        d = GameDialog(None, appid, "T")
        return (
            not d._status_labels["gamemoderun"].isHidden(),
            not d._status_labels["game-performance"].isHidden(),
        )

    assert vis("32", False, False) == (True, True)
    assert vis("33", True, False) == (True, False)
    assert vis("34", False, True) == (False, True)
