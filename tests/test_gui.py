"""GUI smoke tests (offscreen). Skipped without PySide6."""

import pytest

QtWidgets = pytest.importorskip("PySide6.QtWidgets")


@pytest.fixture(autouse=True)
def _no_display_backend_calls(monkeypatch):
    """Dialog tests must never spawn real backend subprocesses.

    A wedged kscreen-doctor once hung dialog construction mid-suite;
    production code queries in a worker thread, but tests stay fully
    hermetic (backend coverage lives in test_display.py fakes).
    """
    from tksteamlaunch.backends import display as dispmod

    monkeypatch.setattr(dispmod, "offered_modes", lambda *a, **k: [])


def test_dialogs_construct(qt_app, xdg_env):
    from tksteamlaunch.gui.game_dialog import GameDialog
    from tksteamlaunch.gui.main_window import MainWindow

    w = MainWindow()
    w.show()
    GameDialog(w, "1", "T").show()
    GameDialog(w, defaults_mode=True).show()
    qt_app.processEvents()


def test_main_table_columns(qt_app, xdg_env, monkeypatch):
    from tksteamlaunch import config as C
    from tksteamlaunch import protondb as pdbmod
    from tksteamlaunch.gui.main_window import MainWindow

    cfg = C.GameConfig()
    cfg.general.appid = "80"
    C.save(cfg)
    monkeypatch.setattr(pdbmod, "refresh", lambda appid: {"tier": "gold", "total": 5})
    w = MainWindow()
    w.show()
    qt_app.processEvents()
    assert w.table.columnCount() == 4
    assert w.table.rowCount() == 1
    assert w.table.item(0, 1).text() == "80"
    for _ in range(100):
        cell = w.table.item(0, 3)
        if cell is not None and cell.text() == "Gold":
            break
        qt_app.processEvents()
        import time

        time.sleep(0.02)
    assert w.table.item(0, 3).text() == "Gold"
    w._stop_pdb_worker()
    w._stop_art_worker()


def test_grid_icon_preferred(qt_app, xdg_env):
    from tksteamlaunch import artwork as artmod
    from tksteamlaunch import config as C
    from tksteamlaunch.gui.main_window import MainWindow

    cfg = C.GameConfig()
    cfg.general.appid = "86"
    C.save(cfg)
    import base64

    grid = artmod.grid_path("86")
    grid.parent.mkdir(parents=True, exist_ok=True)
    grid.write_bytes(
        base64.b64decode(
            "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8BQDwAEhQGAhKmMIQAAAABJRU5ErkJggg=="
        )
    )
    w = MainWindow()
    w.show()
    assert w.table.item(0, 0).icon().isNull() is False
    w._stop_pdb_worker()
    w._stop_art_worker()


def test_launch_mode_buttons(qt_app, xdg_env):
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


def test_provider_combo_data(qt_app, xdg_env):
    from tksteamlaunch.gui.game_dialog import GameDialog

    d = GameDialog(None, "23", "T")
    datas = [d.cb_nl.itemData(i) for i in range(d.cb_nl.count())]
    assert datas == ["auto", "plasma", "gnome", "off"]
    d.cb_nl.setCurrentIndex(1)
    d.accept()
    from tksteamlaunch import config as C

    assert C.load("23").nightlight.provider == "plasma"


def test_detected_runtime_row(qt_app, xdg_env, monkeypatch, tmp_path):
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


def _all_bins_present(monkeypatch):
    import shutil

    real_which = shutil.which
    monkeypatch.setattr(
        shutil, "which", lambda name, *a, **k: f"/bin/{name}" if name else real_which(name)
    )


def test_preview_command(qt_app, xdg_env, monkeypatch):
    from tksteamlaunch import config as C
    from tksteamlaunch.gui.game_dialog import GameDialog

    _all_bins_present(monkeypatch)
    cfg = C.GameConfig()
    cfg.general.appid = "24"
    cfg.ludusavi.enable = True
    C.save(cfg)
    d = GameDialog(None, "24", "T")
    d.c_feral.setChecked(True)
    qt_app.processEvents()
    text = d._preview_edit.toPlainText()
    assert "ludusavi wrap --infer steam" in text
    assert "/usr/bin/ludusavi" not in text
    assert "stands in for" not in text
    assert "gamemoderun" in text or "game-performance" in text
    d.reject()


def _auto_close_boxes(interval_ms=200):
    from PySide6.QtCore import QTimer

    timer = QTimer()
    timer.timeout.connect(_close_boxes)
    timer.start(interval_ms)
    return timer


def _pump_until(qt_app, predicate, timeout_s=5.0):
    import time

    deadline = time.monotonic() + timeout_s
    while time.monotonic() < deadline:
        qt_app.processEvents()
        _close_boxes()
        if predicate():
            return True
        time.sleep(0.02)
    qt_app.processEvents()
    _close_boxes()
    return predicate()


def _close_boxes():
    from PySide6.QtWidgets import QApplication, QMessageBox

    for w in QApplication.topLevelWidgets():
        if isinstance(w, QMessageBox):
            w.close()


def test_coverage_button(qt_app, xdg_env, monkeypatch, tmp_path):
    from PySide6.QtWidgets import QPushButton

    from tksteamlaunch.gui.game_dialog import GameDialog

    monkeypatch.setenv("PATH", str(tmp_path))  # no ludusavi -> unavailable path
    d = GameDialog(None, "28", "T")
    btn = next(b for b in d.findChildren(QPushButton) if "Coverage" in b.text())
    closer = _auto_close_boxes()
    try:
        btn.click()
        assert _pump_until(qt_app, lambda: btn.isEnabled())
    finally:
        closer.stop()
    assert d.result() == 0
    d.reject()


def test_coverage_no_double_run(qt_app, xdg_env, monkeypatch):
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
        assert _pump_until(qt_app, lambda: btn.isEnabled())
    finally:
        closer.stop()
    assert len(calls) == 1
    d.reject()


def test_show_menu_checkbox_roundtrip(qt_app, xdg_env):
    from tksteamlaunch import config as C
    from tksteamlaunch.gui.game_dialog import GameDialog

    d = GameDialog(None, "22", "T")
    assert d.c_show_menu.isChecked() is False
    d.c_show_menu.setChecked(True)
    d.accept()
    assert C.load("22").general.show_menu is True


def test_coverage_button_hidden_in_defaults_mode(qt_app, xdg_env):
    from tksteamlaunch.gui.game_dialog import GameDialog

    def buttons(dlg):
        return [b.text() for b in dlg.findChildren(QtWidgets.QPushButton)]

    assert "Check Coverage..." not in buttons(GameDialog(None, defaults_mode=True))
    assert "Check Coverage..." in buttons(GameDialog(None, "23", "T"))


def test_launch_button_hidden_without_command(qt_app, xdg_env):
    from tksteamlaunch.gui.game_dialog import GameDialog

    def buttons(dlg):
        return [b.text() for b in dlg.findChildren(QtWidgets.QPushButton)]

    assert "Save && Launch" not in buttons(
        GameDialog(None, "24", "T", launch_mode=True, can_launch=False)
    )
    assert "Save && Launch" in buttons(GameDialog(None, "24", "T", launch_mode=True))


def test_gamemode_conflict_resolved_on_load(qt_app, xdg_env, monkeypatch):
    from tksteamlaunch import config as C
    from tksteamlaunch.gui.game_dialog import GameDialog

    _all_bins_present(monkeypatch)
    cfg = C.GameConfig()
    cfg.general.appid = "30"
    cfg.gamemode.feral_gamemode = True
    cfg.gamemode.cachyos_game_performance = True
    C.save(cfg)
    d = GameDialog(None, "30", "T")
    assert d.c_feral.isChecked() and not d.c_cachy.isChecked()


def test_add_blank_choice_ignored(qt_app, xdg_env, monkeypatch):
    from PySide6.QtWidgets import QInputDialog

    from tksteamlaunch.gui import main_window as mw

    monkeypatch.setattr(mw.steammod, "list_games", lambda: [("1", "G")])
    monkeypatch.setattr(QInputDialog, "getItem", lambda *a, **k: ("   ", True))

    def boom(*a, **k):
        raise AssertionError("dialog must not open")

    monkeypatch.setattr(mw, "GameDialog", boom)
    mw.MainWindow()._add()


def test_copy_launch_without_clipboard(qt_app, xdg_env, monkeypatch):
    from PySide6.QtGui import QGuiApplication

    from tksteamlaunch.gui.main_window import MainWindow

    monkeypatch.setattr(QGuiApplication, "clipboard", classmethod(lambda cls: None))
    w = MainWindow()
    w._copy_launch()  # must not raise
    assert "unavailable" in w.status.text()


def test_launch_buttons_order_and_icons(qt_app, xdg_env):
    from PySide6.QtWidgets import QDialogButtonBox

    from tksteamlaunch.gui.game_dialog import GameDialog

    d = GameDialog(None, "25", "T", launch_mode=True)
    box = d.findChild(QDialogButtonBox)
    texts = [b.text() for b in box.buttons()]
    assert texts.index("Launch") < texts.index("Save") < texts.index("Save && Launch")
    icons = {b.text(): b.icon() for b in box.buttons()}
    assert not icons["Launch"].isNull()
    assert not icons["Save && Launch"].isNull()


def test_launch_without_save_keeps_file(qt_app, xdg_env):
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


def test_steam_options_hidden_in_defaults_mode(qt_app, xdg_env):
    from tksteamlaunch.gui.game_dialog import GameDialog

    assert "steam-options" not in GameDialog(None, defaults_mode=True)._status_labels
    assert "steam-options" in GameDialog(None, "31", "T")._status_labels


def test_exclusive_backends_visibility(qt_app, xdg_env, monkeypatch):
    from tksteamlaunch import config as C
    from tksteamlaunch.gui.game_dialog import GameDialog

    _all_bins_present(monkeypatch)

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


def test_missing_binaries_disable_toggles(qt_app, xdg_env, monkeypatch):
    import shutil

    from tksteamlaunch import config as C
    from tksteamlaunch.gui.game_dialog import GameDialog

    monkeypatch.setattr(shutil, "which", lambda *a, **k: None)
    cfg = C.GameConfig()
    cfg.general.appid = "40"
    cfg.gamemode.feral_gamemode = True
    cfg.ludusavi.enable = True
    C.save(cfg)
    d = GameDialog(None, "40", "T")
    for cb in (d.c_feral, d.c_cachy, d.c_gs, d.c_mh, d.c_lu_enable):
        assert not cb.isEnabled()
        assert not cb.isChecked()


def test_preview_toggle_lives_in_preferences(qt_app, xdg_env):
    from tksteamlaunch import config as C
    from tksteamlaunch.gui.game_dialog import GameDialog
    from tksteamlaunch.gui.preferences_dialog import PreferencesDialog

    assert not hasattr(GameDialog(None, "41", "T"), "c_show_preview")
    prefs = PreferencesDialog(None)
    assert prefs.c_show_preview.isChecked() is True
    prefs.c_show_preview.setChecked(False)
    prefs.accept()
    assert C.load_preferences().show_preview is False
    assert GameDialog(None, "41", "T")._preview_edit is None


def test_preview_updates_live(qt_app, xdg_env):
    from tksteamlaunch.gui.game_dialog import GameDialog

    d = GameDialog(None, "42", "T")
    before = d._preview_edit.toPlainText()
    d.e_prefix.setText("zink-run")
    qt_app.processEvents()
    after = d._preview_edit.toPlainText()
    assert after != before and "zink-run" in after
    d.reject()


def test_preferences_dialog_roundtrip(qt_app, xdg_env):
    from tksteamlaunch import config as C
    from tksteamlaunch.gui.preferences_dialog import PreferencesDialog

    prefs = PreferencesDialog(None)
    assert prefs.c_show_preview.isChecked() is True
    assert prefs.cb_tray_icon.isEnabled() is False  # tray off gates dependents
    prefs.c_tray.setChecked(True)
    assert prefs.cb_tray_icon.isEnabled() is True
    prefs.cb_tray_icon.setCurrentIndex(1)
    prefs.c_close.setChecked(True)
    prefs.accept()
    back = C.load_preferences()
    assert (back.tray_enable, back.tray_icon, back.close_to_tray) == (True, "mono", True)
    assert back.minimize_to_tray is False


def test_tray_absent_offscreen(qt_app, xdg_env):
    from tksteamlaunch import config as C
    from tksteamlaunch.gui.main_window import MainWindow

    prefs = C.load_preferences()
    prefs.tray_enable = True
    C.save_preferences(prefs)
    w = MainWindow()  # no tray available offscreen: must not crash
    assert w._tray is None
    w.close()
    assert not w.isVisible()  # close proceeds normally without a tray


def test_close_to_tray_needs_tray(qt_app, xdg_env):
    from tksteamlaunch import config as C
    from tksteamlaunch.gui.main_window import MainWindow

    prefs = C.load_preferences()
    prefs.tray_enable = True
    prefs.close_to_tray = True
    C.save_preferences(prefs)
    w = MainWindow()
    w.show()
    assert w._tray is None  # offscreen: no tray to hide into
    w.close()  # must close normally, not hang hidden
    assert not w.isVisible()


def test_bundled_icons_valid(qt_app):
    import xml.etree.ElementTree as ET

    from PySide6.QtSvg import QSvgRenderer

    from tksteamlaunch.gui import icons as iconsmod

    for style in ("normal", "mono"):
        path = iconsmod.icon_path(style)
        assert path is not None and path.is_file()
        ET.parse(str(path))  # well-formed XML
        assert QSvgRenderer(str(path)).isValid()
    assert iconsmod.icon_path("nope") == iconsmod.icon_path("normal")  # fallback
    assert not iconsmod.app_icon("normal").isNull()


def test_tray_reuse_and_teardown(qt_app, xdg_env, monkeypatch):
    from PySide6 import QtWidgets

    from tksteamlaunch import config as C
    from tksteamlaunch.gui.main_window import MainWindow

    created = []

    class FakeSignal:
        def connect(self, *a):
            pass

    class FakeTray:
        def __init__(self, icon=None, parent=None):
            self.icon = icon
            self.activated = FakeSignal()
            created.append(self)

        @staticmethod
        def isSystemTrayAvailable():
            return True

        def setToolTip(self, t):
            pass

        def setContextMenu(self, m):
            self.menu = m

        def setIcon(self, icon):
            self.icon = icon

        def show(self):
            pass

        def hide(self):
            pass

        def deleteLater(self):
            pass

    monkeypatch.setattr(QtWidgets, "QSystemTrayIcon", FakeTray)
    prefs = C.load_preferences()
    prefs.tray_enable = True
    C.save_preferences(prefs)
    w = MainWindow()
    assert isinstance(w._tray, FakeTray) and w._tray_menu is not None
    first = w._tray
    prefs.tray_icon = "mono"
    C.save_preferences(prefs)
    w._apply_tray()  # update in place: same object, new icon
    assert w._tray is first and len(created) == 1
    prefs.tray_enable = False
    C.save_preferences(prefs)
    w._apply_tray()
    assert w._tray is None and w._tray_menu is None
    w.close()


def test_quit_shortcut_quits_app(qt_app, xdg_env):
    from unittest import mock

    from PySide6.QtWidgets import QApplication

    from tksteamlaunch.gui.main_window import MainWindow

    calls = []
    fake = type("FakeApp", (), {"quit": staticmethod(lambda: calls.append(1))})()
    window = MainWindow()
    # NOTE: patched inside the test body (not via monkeypatch fixture) so
    # QApplication.instance is restored before pytest-qt's teardown hook
    # runs; a leaked patch crashes teardown for every following test.
    with mock.patch.object(QApplication, "instance", classmethod(lambda cls: fake)):
        window._quit()
    assert calls == [1]
    window.close()


def test_close_drops_tray(qt_app, xdg_env, monkeypatch):
    from PySide6 import QtWidgets

    from tksteamlaunch import config as C
    from tksteamlaunch.gui.main_window import MainWindow

    class FakeSignal:
        def connect(self, *a):
            pass

    class FakeTray:
        def __init__(self, icon=None, parent=None):
            self.activated = FakeSignal()

        @staticmethod
        def isSystemTrayAvailable():
            return True

        def setToolTip(self, t):
            pass

        def setContextMenu(self, m):
            pass

        def setIcon(self, i):
            pass

        def show(self):
            pass

        def hide(self):
            pass

        def deleteLater(self):
            pass

    monkeypatch.setattr(QtWidgets, "QSystemTrayIcon", FakeTray)
    prefs = C.load_preferences()
    prefs.tray_enable = True
    C.save_preferences(prefs)
    w = MainWindow()
    assert isinstance(w._tray, FakeTray)
    w.close()
    assert w._tray is None


def test_single_instance_secondary_bows_out(qt_app):
    from tksteamlaunch.gui.app import single_instance

    name = "tksteamlaunch-gui-test-single"
    primary = single_instance(name)
    assert primary is not None
    try:
        assert single_instance(name) is None
    finally:
        primary.close()
        from PySide6.QtNetwork import QLocalServer

        QLocalServer.removeServer(name)


def test_show_request_raises_window(qt_app, xdg_env):
    from tksteamlaunch.gui.app import _on_show_request
    from tksteamlaunch.gui.main_window import MainWindow

    class NoConnections:
        def hasPendingConnections(self):
            return False

    w = MainWindow()
    w.hide()
    _on_show_request(NoConnections(), w)
    assert w.isVisible()
    w.close()


def test_about_text_contents():
    from tksteamlaunch.gui.main_window import _about_text

    text = _about_text()
    assert "TKSteamLaunch" in text and "GPL-3.0-or-later" in text
    assert "PySide6" in text and "Config:" in text and "Logs:" in text
    assert "vdf" in text and "jeepney" in text


def test_section_boxes_present(qt_app, xdg_env):
    from PySide6.QtWidgets import QGroupBox, QLabel

    from tksteamlaunch.gui.main_window import MainWindow

    w = MainWindow()
    groups = w.findChildren(QGroupBox)
    assert len(groups) == 3 and all(box.title() == "" for box in groups)
    labels = [label.text() for label in w.findChildren(QLabel)]
    assert {"Games", "Tools", "Application"} <= set(labels)
    w._apply_default_size()
    assert w.width() >= 640 and w.height() >= 480
    w.close()


def test_section_row_centered(qt_app):
    from PySide6.QtWidgets import QGroupBox, QLabel, QPushButton, QSpacerItem

    from tksteamlaunch.gui.main_window import MainWindow

    def noop() -> None:
        pass

    row = MainWindow._section_row("T", (("A", noop), ("B", noop), ("C", noop)))
    assert isinstance(row, QGroupBox)
    assert row.title() == ""
    layout = row.layout()
    assert isinstance(layout.itemAt(0).widget(), QLabel)
    assert (
        sum(isinstance(layout.itemAt(i).widget(), QPushButton) for i in range(layout.count())) == 3
    )
    spacers = [i for i in range(layout.count()) if isinstance(layout.itemAt(i), QSpacerItem)]
    assert spacers == [1, layout.count() - 2]  # group centered on the full row width
    assert layout.itemAt(layout.count() - 1).widget().minimumWidth() == 90


def test_menu_launch_cancel_and_nolaunch(qt_app, xdg_env):
    from PySide6.QtWidgets import QDialog

    from tksteamlaunch.gui.menu_dialog import MenuDialog

    m = MenuDialog(None, "77", "Menu Game")
    assert m.launch_requested is False and m.b_launch.isEnabled()
    m.b_launch.click()
    assert m.launch_requested is True
    assert m.result() == QDialog.DialogCode.Accepted

    m2 = MenuDialog(None, "77", "Menu Game", can_launch=False)
    assert not m2.b_launch.isEnabled()

    m3 = MenuDialog(None, "77", "Menu Game")
    m3.reject()
    assert m3.launch_requested is False


def test_menu_settings_returns_to_menu(qt_app, xdg_env):
    from PySide6.QtCore import QTimer
    from PySide6.QtWidgets import QApplication, QPushButton

    from tksteamlaunch.gui.menu_dialog import MenuDialog

    m = MenuDialog(None, "78", "Menu Game")
    m.show()
    qt_app.processEvents()

    def close_nested():
        modal = QApplication.activeModalWidget()
        if modal is not None and modal is not m:
            modal.reject()

    QTimer.singleShot(400, close_nested)
    btn = next(b for b in m.findChildren(QPushButton) if "Settings" in b.text())
    btn.click()
    qt_app.processEvents()
    assert m.isVisible() and m.result() == 0 and m.launch_requested is False
    m.close()


def test_edit_menu_cancel_reports_json(qt_app, xdg_env, capsys):
    from PySide6.QtCore import QTimer
    from PySide6.QtWidgets import QApplication, QDialog

    from tksteamlaunch.gui import edit as editmod

    def reject_modal():
        modal = QApplication.activeModalWidget()
        if isinstance(modal, QDialog):
            modal.reject()

    QTimer.singleShot(400, reject_modal)
    assert editmod.main(["--appid", "79", "--menu"]) == 0
    assert '"outcome": "cancelled"' in capsys.readouterr().out


def test_dialog_tab_map(qt_app, xdg_env):
    from PySide6.QtWidgets import QTabWidget

    from tksteamlaunch.gui.game_dialog import GameDialog

    def tabs(dlg):
        tab = dlg.findChild(QTabWidget)
        return [tab.tabText(i) for i in range(tab.count())]

    assert tabs(GameDialog(None, "50", "T")) == [
        "General",
        "Environment",
        "Pre/Post Commands",
        "Performance",
        "Display",
        "Ludusavi",
        "System",
        "Wine / Proton",
        "Notes",
    ]
    assert "Notes" not in tabs(GameDialog(None, defaults_mode=True))


def test_preview_group_collapsible(qt_app, xdg_env):
    from PySide6.QtWidgets import QGroupBox

    from tksteamlaunch.gui.game_dialog import GameDialog

    d = GameDialog(None, "51", "T")
    groups = [g for g in d.findChildren(QGroupBox) if g.title() == "Launch Command Preview"]
    assert len(groups) == 1
    group = groups[0]
    assert group.isCheckable() and group.isChecked()
    group.setChecked(False)
    assert not d._preview_edit.isVisibleTo(d)
    group.setChecked(True)
    assert d._preview_edit.toPlainText() != ""


def test_wrappers_summary_updates(qt_app, xdg_env):
    from tksteamlaunch.gui.game_dialog import GameDialog

    d = GameDialog(None, "52", "T")
    assert d.wrappers_summary.text() == "No wrappers enabled"
    d.c_mh.setChecked(True)
    d.c_feral.setChecked(True)
    qt_app.processEvents()
    text = d.wrappers_summary.text()
    assert text.startswith("Will launch with: ")
    assert "MangoHud" in text and "GameMode" in text
    d.c_mh.setChecked(False)
    d.c_feral.setChecked(False)
    qt_app.processEvents()
    assert d.wrappers_summary.text() == "No wrappers enabled"


def _visible_labels(d) -> list:
    return [d._tabs.tabText(i) for i in range(d._tabs.count()) if d._tabs.isTabVisible(i)]


def test_all_tabs_always_visible(qt_app, xdg_env):
    from tksteamlaunch import config as C
    from tksteamlaunch.gui.game_dialog import GameDialog

    cfg = C.GameConfig()
    cfg.general.appid = "54"
    C.save(cfg)
    d = GameDialog(None, "54", "T")
    qt_app.processEvents()
    labels = _visible_labels(d)
    for tab in ("General", "Display", "Environment", "Pre/Post Commands", "Wine / Proton"):
        assert tab in labels
    assert not hasattr(d, "c_advanced")
    d.close()


def test_env_values_survive_profile_switch(qt_app, xdg_env):
    from tksteamlaunch import config as C
    from tksteamlaunch.gui.game_dialog import GameDialog

    cfg = C.GameConfig()
    cfg.general.appid = "55"
    cfg.env.vars = {"FOO": "1"}
    C.save(cfg)
    C.save_profile("55", "p1", cfg)
    d = GameDialog(None, "55", "T")
    d.cb_profile.setCurrentIndex(d.cb_profile.findData("p1"))
    qt_app.processEvents()
    d._collect()
    assert d.cfg.env.vars.get("FOO") == "1"
    d.close()


def test_hook_status_actionable(qt_app, xdg_env, tmp_path, monkeypatch):
    from tksteamlaunch.gui import game_dialog as gd
    from tksteamlaunch.gui.game_dialog import GameDialog

    d = GameDialog(None, "56", "T")
    d.show()
    qt_app.processEvents()
    assert d._status_labels["pre_hook"].isHidden()
    real = tmp_path / "hooks"
    real.mkdir()
    hook = real / "pre.sh"
    hook.write_text("#!/bin/sh\n")
    missing = str(real / "missing-hook.sh")
    d.e_pre.setText(missing)
    qt_app.processEvents()
    label = d._status_labels["pre_hook"]
    assert label.isVisible()
    assert "not found" in label.text()
    assert "Open folder" in label.text()
    assert f'href="{real}"' in label.text()
    d.e_pre.setText(str(hook))
    qt_app.processEvents()
    assert "not found" not in label.text()
    assert "Open folder" not in label.text()
    opened = []
    monkeypatch.setattr(gd, "open_path", lambda p: opened.append(p))
    d._on_status_link("/nope")
    assert opened == ["/nope"]


def test_empty_state_guided(qt_app, xdg_env):
    from tksteamlaunch.gui import main_window as mw

    w = mw.MainWindow()
    w.show()
    qt_app.processEvents()
    assert w.table.rowCount() == 0
    assert w.empty_state.isVisible()
    assert not w.table.isVisible()
    assert w.empty_title.text() == "No games configured yet"
    assert "tksteamlaunch %command%" in w.empty_steps.text()
    assert w.empty_add.text() == "Add Game..."
    assert w.empty_import.text() == "Import..."
    assert w.empty_copy.text() == "Copy Launch Options"
    w._stop_pdb_worker()
    w._stop_art_worker()


def test_empty_state_hides_when_configured(qt_app, xdg_env):
    from tksteamlaunch import config as C
    from tksteamlaunch.gui import main_window as mw

    cfg = C.GameConfig()
    cfg.general.appid = "81"
    C.save(cfg)
    w = mw.MainWindow()
    w.show()
    qt_app.processEvents()
    assert w.table.rowCount() == 1
    assert not w.empty_state.isVisible()
    assert w.table.isVisible()
    w._stop_pdb_worker()
    w._stop_art_worker()


def test_filter_by_text(qt_app, xdg_env, monkeypatch):
    from tksteamlaunch import config as C
    from tksteamlaunch.gui import main_window as mw

    monkeypatch.setattr(mw.steammod, "list_games", lambda: [("1", "Alpha"), ("2", "Zulu")])
    for appid in ("1", "2"):
        cfg = C.GameConfig()
        cfg.general.appid = appid
        C.save(cfg)
    w = mw.MainWindow()
    w.show()
    qt_app.processEvents()
    assert not w.table.isRowHidden(0)
    w.filter_input.setText("zul")
    qt_app.processEvents()
    hidden = [w.table.isRowHidden(r) for r in range(w.table.rowCount())]
    assert sorted(hidden) == [False, True]
    assert "1 shown" in w.status.text()
    w.filter_input.clear()
    qt_app.processEvents()
    assert not any(w.table.isRowHidden(r) for r in range(w.table.rowCount()))
    w._stop_pdb_worker()
    w._stop_art_worker()


def test_filter_issues_only(qt_app, xdg_env, monkeypatch):
    from PySide6.QtCore import Qt

    from tksteamlaunch import config as C
    from tksteamlaunch.gui import main_window as mw

    monkeypatch.setattr(mw.steammod, "list_games", lambda: [("1", "Alpha"), ("2", "Zulu")])
    good = C.GameConfig()
    good.general.appid = "1"
    C.save(good)
    bad = C.GameConfig()
    bad.general.appid = "2"
    bad.pre_post.pre_command = "/nope/missing-hook.sh"
    C.save(bad)
    w = mw.MainWindow()
    w.show()
    qt_app.processEvents()
    w.issues_only.setChecked(True)
    qt_app.processEvents()
    states = {}
    for r in range(w.table.rowCount()):
        item = w.table.item(r, 0)
        states[str(item.data(Qt.ItemDataRole.UserRole) or item.text())] = w.table.isRowHidden(r)
    assert any("2" in k for k, v in states.items() if not v)
    assert any("1" in k for k, v in states.items() if v)
    w._stop_pdb_worker()
    w._stop_art_worker()


def test_games_sorted_by_default(qt_app, xdg_env, monkeypatch):
    from PySide6.QtCore import Qt

    from tksteamlaunch import config as C
    from tksteamlaunch.gui import main_window as mw

    monkeypatch.setattr(mw.steammod, "list_games", lambda: [("2", "Zulu"), ("1", "Alpha")])
    for appid in ("1", "2"):
        cfg = C.GameConfig()
        cfg.general.appid = appid
        C.save(cfg)
    w = mw.MainWindow()
    assert w.table.item(0, 0).text() == "Alpha"
    assert w.table.item(1, 0).text() == "Zulu"
    w.table.sortByColumn(1, Qt.SortOrder.DescendingOrder)
    assert w.table.item(0, 1).text() == "2"
    w.close()


def test_dialog_default_size(qt_app, xdg_env):
    from tksteamlaunch.gui.game_dialog import GameDialog

    for dlg in (GameDialog(None, "60", "T"), GameDialog(None, defaults_mode=True)):
        assert dlg.width() >= 640 and dlg.height() >= 480
        dlg.close()


def test_status_grid_packs_visible_first(qt_app, xdg_env, monkeypatch):
    import shutil

    from tksteamlaunch import config as C
    from tksteamlaunch.gui.game_dialog import GameDialog

    monkeypatch.setattr(shutil, "which", lambda *a, **k: "/bin/x")
    cfg = C.GameConfig()
    cfg.general.appid = "61"
    cfg.gamemode.cachyos_game_performance = True
    C.save(cfg)
    d = GameDialog(None, "61", "T")
    grid = d._status_grid
    cells = set()
    for i in range(grid.count()):
        r, c, _, _ = grid.getItemPosition(i)
        w = grid.itemAt(i).widget()
        assert w is not None and not w.isHidden()
        cells.add((r, c))
    assert cells == {(i // 2, i % 2) for i in range(len(cells))}
    d.close()


def test_menu_dialog_rich_header(qt_app, xdg_env, monkeypatch):
    from PySide6.QtWidgets import QLabel

    from tksteamlaunch.gui import menu_dialog as md

    d = md.MenuDialog(None, "55", "Test Game")
    assert d.windowTitle() == "TKSteamLaunch — Test Game"
    assert d.minimumWidth() >= 400
    pixmaps = [label.pixmap() for label in d.findChildren(QLabel) if label.pixmap() is not None]
    assert pixmaps, "expected a game icon label"
    texts = [label.text() for label in d.findChildren(QLabel)]
    assert any("Test Game" in t and "55" in t for t in texts)
    d.close()


def test_menu_settings_keeps_name(qt_app, xdg_env, monkeypatch):
    from tksteamlaunch.gui import menu_dialog as md

    seen = {}
    monkeypatch.setattr(
        "tksteamlaunch.gui.game_dialog.GameDialog",
        lambda parent, appid, name="", **kw: (
            seen.update(appid=appid, name=name) or type("D", (), {"exec": lambda self: 0})()
        ),
    )
    d = md.MenuDialog(None, "55", "Test Game")
    d._open_settings()
    assert seen == {"appid": "55", "name": "Test Game"}
    d.close()


def test_menu_rich_header_and_timeout(qt_app, xdg_env):
    from PySide6.QtWidgets import QLabel, QPushButton

    from tksteamlaunch.gui import menu_dialog as md

    d = md.MenuDialog(None, "55", "Test Game", timeout=5)
    assert d.windowTitle() == "TKSteamLaunch — Test Game"
    assert d.minimumWidth() >= 400
    texts = [label.text() for label in d.findChildren(QLabel)]
    assert any("Test Game (55)" in t for t in texts)
    launch_btn = next(b for b in d.findChildren(QPushButton) if b.text() == "Launch")
    assert not launch_btn.icon().isNull()
    assert d._remaining == 5
    d._remaining = 1
    d._tick()
    assert d.launch_requested is True and d.result() != 0
    d.close()


def test_menu_no_timeout_by_default(qt_app, xdg_env):
    from tksteamlaunch.gui import menu_dialog as md

    d = md.MenuDialog(None, "55", "Test Game")
    assert d._remaining == 0 and not d._count_label.isVisibleTo(d)
    d.close()


def test_import_chooser_codes(qt_app):
    from PySide6.QtWidgets import QPushButton

    from tksteamlaunch.gui.import_dialog import ImportChooserDialog, StlImportDialog, usage_notice

    labels = [b.text() for b in ImportChooserDialog(None).findChildren(QPushButton)]
    assert "TKSteamLaunch Export..." in labels
    assert "SteamTinkerLaunch..." in labels
    assert usage_notice(["60"], ["61"]).startswith("Imported as the 'steamtinkerlaunch' profile")
    assert "61" in usage_notice(["60"], ["61"])
    assert usage_notice([], []) == ""
    dlg = StlImportDialog(None, [("60", "B Game"), ("61", "A Game")])
    assert dlg.table.rowCount() == 2
    assert dlg.table.item(0, 1).text() == "A Game"  # sorted by name
    assert dlg._checked_appids() == ["61", "60"]
    dlg.table.item(1, 0).setCheckState(
        __import__("PySide6.QtCore", fromlist=["Qt"]).Qt.CheckState.Unchecked
    )
    assert dlg._checked_appids() == ["61"]
    dlg.close()


def test_stl_import_writes_profile(qt_app, xdg_env, monkeypatch, tmp_path):
    from PySide6.QtCore import QTimer

    from tksteamlaunch import config as C
    from tksteamlaunch import stl_import as sti
    from tksteamlaunch.gui.import_dialog import StlImportDialog

    stl_dir = tmp_path / "steamtinkerlaunch" / "gamecfgs" / "id"
    stl_dir.mkdir(parents=True)
    (stl_dir / "60.conf").write_text('USEGAMEMODERUN="1"\nUSERSTOP="/s/post.sh"\n')
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
    assert sti.list_stl_appids() == ["60"]
    dlg = StlImportDialog(None, [("60", "G")])
    QTimer.singleShot(300, _close_boxes)
    dlg._do_import()
    assert C.load_profile("60", "steamtinkerlaunch").gamemode.feral_gamemode is True
    assert C.load_profile("60", "steamtinkerlaunch").pre_post.post_command == "/s/post.sh"
    assert C.load("60").gamemode.feral_gamemode is False  # live untouched
    dlg.close()


def test_profile_clone_button(qt_app, xdg_env, monkeypatch):
    from PySide6.QtWidgets import QInputDialog, QMessageBox

    from tksteamlaunch import config as C
    from tksteamlaunch.gui.game_dialog import GameDialog

    cfg = C.GameConfig()
    cfg.general.appid = "62"
    cfg.env.vars = {"A": "1"}
    C.save(cfg)
    monkeypatch.setattr(QInputDialog, "getText", lambda *a, **k: ("copy1", True))
    monkeypatch.setattr(QMessageBox, "question", lambda *a, **k: QMessageBox.StandardButton.Yes)
    d = GameDialog(None, "62", "T")
    d._on_profile_clone()
    assert C.load_profile("62", "copy1").env.vars == {"A": "1"}
    assert d._active_profile == "copy1"
    d.close()


def test_active_profile_persists(qt_app, xdg_env):
    from tksteamlaunch import config as C
    from tksteamlaunch.gui.game_dialog import GameDialog

    cfg = C.GameConfig()
    cfg.general.appid = "80"
    C.save(cfg)
    C.save_profile("80", "p1", cfg)
    d = GameDialog(None, "80", "T")
    assert d.cb_profile.currentData() in (None, "")
    d._active_profile = "p1"
    d._collect()
    d.accept()
    assert C.load("80").general.active_profile == "p1"
    d2 = GameDialog(None, "80", "T")
    assert d2.cb_profile.currentData() == "p1"
    d2.close()


def test_active_profile_missing_falls_back(qt_app, xdg_env):
    from tksteamlaunch import config as C
    from tksteamlaunch.gui.game_dialog import GameDialog

    cfg = C.GameConfig()
    cfg.general.appid = "81"
    cfg.general.active_profile = "ghost"
    C.save(cfg)
    d = GameDialog(None, "81", "T")
    assert d._active_profile == ""
    assert d.cb_profile.currentData() in (None, "")
    d.close()


def test_save_profile_strips_selection(qt_app, xdg_env):
    from tksteamlaunch import config as C

    cfg = C.GameConfig()
    cfg.general.appid = "82"
    cfg.general.active_profile = "p1"
    C.save_profile("82", "copy", cfg)
    assert C.load_profile("82", "copy").general.active_profile == ""


def test_clone_without_selection_confirms(qt_app, xdg_env, monkeypatch):
    from PySide6.QtWidgets import QInputDialog, QMessageBox

    from tksteamlaunch import config as C
    from tksteamlaunch.gui.game_dialog import GameDialog

    cfg = C.GameConfig()
    cfg.general.appid = "83"
    C.save(cfg)
    monkeypatch.setattr(QInputDialog, "getText", lambda *a, **k: ("c1", True))
    monkeypatch.setattr(QMessageBox, "question", lambda *a, **k: QMessageBox.StandardButton.No)
    d = GameDialog(None, "83", "T")
    d._on_profile_clone()
    assert C.list_profiles("83") == []
    monkeypatch.setattr(QMessageBox, "question", lambda *a, **k: QMessageBox.StandardButton.Yes)
    d._on_profile_clone()
    assert C.list_profiles("83") == ["c1"]
    d.close()


def test_focus_refreshes_profile_list(qt_app, xdg_env):
    from PySide6.QtCore import QEvent
    from PySide6.QtGui import QFocusEvent

    from tksteamlaunch import config as C
    from tksteamlaunch.gui.game_dialog import GameDialog

    cfg = C.GameConfig()
    cfg.general.appid = "84"
    C.save(cfg)
    d = GameDialog(None, "84", "T")
    assert d.cb_profile.count() == 1  # "(Game Defaults)"
    C.save_profile("84", "late", cfg)
    d.focusInEvent(QFocusEvent(QEvent.Type.FocusIn))
    assert d.cb_profile.count() == 2
    d.close()


def test_open_loads_persisted_profile_content(qt_app, xdg_env):
    from tksteamlaunch import config as C
    from tksteamlaunch.gui.game_dialog import GameDialog

    live = C.GameConfig()
    live.general.appid = "85"
    live.pre_post.pre_command = "/live/pre.sh"
    live.general.active_profile = "stl"
    C.save(live)
    prof = C.GameConfig()
    prof.general.appid = "85"
    prof.pre_post.pre_command = "/prof/pre.sh"
    C.save_profile("85", "stl", prof)
    d = GameDialog(None, "85", "T")
    assert d.cb_profile.currentData() == "stl"
    assert d.e_pre.text() == "/prof/pre.sh"
    d.close()


def test_switch_to_game_defaults_reloads_live(qt_app, xdg_env):
    from tksteamlaunch import config as C
    from tksteamlaunch.gui.game_dialog import GameDialog

    live = C.GameConfig()
    live.general.appid = "86"
    live.pre_post.pre_command = "/live/pre.sh"
    live.general.active_profile = "stl"
    C.save(live)
    prof = C.GameConfig()
    prof.general.appid = "86"
    prof.pre_post.pre_command = "/prof/pre.sh"
    C.save_profile("86", "stl", prof)
    d = GameDialog(None, "86", "T")
    assert d.e_pre.text() == "/prof/pre.sh"
    d.cb_profile.setCurrentIndex(0)  # "(Game Defaults)"
    assert d.cb_profile.currentData() == ""
    assert d._active_profile == ""
    assert d.e_pre.text() == "/live/pre.sh"
    d.close()


def test_is_dirty_tracks_edits(qt_app, xdg_env):
    from tksteamlaunch import config as C
    from tksteamlaunch.gui.game_dialog import GameDialog

    cfg = C.GameConfig()
    cfg.general.appid = "87"
    C.save(cfg)
    C.save_profile("87", "p1", cfg)
    d = GameDialog(None, "87", "T")
    assert not d._is_dirty()
    d.e_pre.setText("/edited.sh")
    assert d._is_dirty()
    d.close()


def test_switch_cancel_restores_selection(qt_app, xdg_env, monkeypatch):
    from tksteamlaunch import config as C
    from tksteamlaunch.gui.game_dialog import GameDialog

    cfg = C.GameConfig()
    cfg.general.appid = "88"
    C.save(cfg)
    C.save_profile("88", "p1", cfg)
    d = GameDialog(None, "88", "T")
    d.cb_profile.setCurrentIndex(d.cb_profile.findData("p1"))
    assert d._active_profile == "p1"
    d.e_pre.setText("/edited.sh")
    monkeypatch.setattr(d, "_confirm_discard_changes", lambda: False)
    d.cb_profile.setCurrentIndex(0)
    assert d._active_profile == "p1"
    assert d.cb_profile.currentData() == "p1"
    assert d.e_pre.text() == "/edited.sh"
    d.close()


def test_switch_save_persists_edits(qt_app, xdg_env, monkeypatch):
    from PySide6.QtWidgets import QMessageBox

    from tksteamlaunch import config as C
    from tksteamlaunch.gui.game_dialog import GameDialog

    cfg = C.GameConfig()
    cfg.general.appid = "89"
    C.save(cfg)
    C.save_profile("89", "p1", cfg)
    d = GameDialog(None, "89", "T")
    d.e_pre.setText("/edited.sh")
    monkeypatch.setattr(QMessageBox, "exec", lambda self: QMessageBox.StandardButton.Save)
    d.cb_profile.setCurrentIndex(d.cb_profile.findData("p1"))
    assert d._active_profile == "p1"
    assert C.load("89").pre_post.pre_command == "/edited.sh"
    d.close()


def test_invalid_config_shows_warning_on_open(qt_app, xdg_env, monkeypatch):
    from PySide6.QtWidgets import QMessageBox

    from tksteamlaunch import config as C
    from tksteamlaunch.gui.game_dialog import GameDialog

    C.game_file("95").parent.mkdir(parents=True, exist_ok=True)
    C.game_file("95").write_text("[general\nappid = oops", encoding="utf-8")
    seen = []
    monkeypatch.setattr(
        QMessageBox, "warning", lambda *a, **k: seen.append(str(a[2]) if len(a) > 2 else "")
    )
    d = GameDialog(None, "95", "T")
    assert seen and "could not be read" in seen[0]
    assert d.cfg.general.appid == "95"  # falls back to defaults but keeps appid
    d.close()


def test_valid_config_opens_without_warning(qt_app, xdg_env, monkeypatch):
    from PySide6.QtWidgets import QMessageBox

    from tksteamlaunch import config as C
    from tksteamlaunch.gui.game_dialog import GameDialog

    cfg = C.GameConfig()
    cfg.general.appid = "96"
    C.save(cfg)
    called = []
    monkeypatch.setattr(QMessageBox, "warning", lambda *a, **k: called.append(a))
    d = GameDialog(None, "96", "T")
    assert called == []
    d.close()


def test_switch_to_corrupt_profile_warns(qt_app, xdg_env, monkeypatch):
    from PySide6.QtWidgets import QMessageBox

    from tksteamlaunch import config as C
    from tksteamlaunch.gui.game_dialog import GameDialog

    cfg = C.GameConfig()
    cfg.general.appid = "97"
    C.save(cfg)
    C.save_profile("97", "bad", cfg)
    C.profile_file("97", "bad").write_text("[general\nappid = oops", encoding="utf-8")
    seen = []
    monkeypatch.setattr(
        QMessageBox, "warning", lambda *a, **k: seen.append(str(a[2]) if len(a) > 2 else "")
    )
    d = GameDialog(None, "97", "T")
    assert seen == []  # live file is fine: no warning on open
    d.cb_profile.setCurrentIndex(d.cb_profile.findData("bad"))
    assert len(seen) == 1 and "could not be read" in seen[0]
    d.close()


def test_switch_back_to_corrupt_live_warns(qt_app, xdg_env, monkeypatch):
    from PySide6.QtWidgets import QMessageBox

    from tksteamlaunch import config as C
    from tksteamlaunch.gui.game_dialog import GameDialog

    live = C.GameConfig()
    live.general.appid = "98"
    C.save(live)
    prof = C.GameConfig()
    prof.general.appid = "98"
    C.save_profile("98", "good", prof)
    seen = []
    monkeypatch.setattr(
        QMessageBox, "warning", lambda *a, **k: seen.append(str(a[2]) if len(a) > 2 else "")
    )
    d = GameDialog(None, "98", "T")
    assert seen == []  # everything valid on open
    C.game_file("98").write_text("[general\nappid = oops", encoding="utf-8")
    d.cb_profile.setCurrentIndex(d.cb_profile.findData("good"))
    assert seen == []  # profile itself is fine
    d.cb_profile.setCurrentIndex(0)  # "(Game Defaults)" reloads the corrupt live file
    assert len(seen) == 1 and "could not be read" in seen[0]
    d.close()


def test_no_pytest_qt_fixture_leak():
    """The suite must pass without pytest-qt: only the local qt_app fixture."""
    import re
    from pathlib import Path

    offenders = [
        f"{p.name}:{i}"
        for p in sorted(Path(__file__).parent.glob("test_*.py"))
        for i, line in enumerate(p.read_text(encoding="utf-8").splitlines(), 1)
        if re.search(r"\bqapp\b", line)
    ]
    assert not offenders, f"use the local qt_app fixture instead: {offenders}"


def test_save_on_profile_writes_profile_not_live(qt_app, xdg_env):
    from tksteamlaunch import config as C
    from tksteamlaunch.gui.game_dialog import GameDialog

    cfg = C.GameConfig()
    cfg.general.appid = "104"
    cfg.general.active_profile = "p1"
    cfg.ludusavi.enable = True
    C.save(cfg)
    C.save_profile("104", "p1", cfg)
    d = GameDialog(None, "104", "T")
    assert d.cb_profile.currentData() == "p1"
    assert d.c_lu_enable.isChecked()
    d.c_lu_enable.setChecked(False)
    d.accept()
    assert C.load_profile("104", "p1").ludusavi.enable is False
    live = C.load("104")
    assert live.ludusavi.enable is True  # Game Defaults stays pristine
    assert live.general.active_profile == "p1"  # selection persists
    d2 = GameDialog(None, "104", "T")
    assert not d2.c_lu_enable.isChecked()
    d2.close()


def test_save_on_profile_writes_profile_env_not_live(qt_app, xdg_env):
    from PySide6.QtWidgets import QTableWidgetItem

    from tksteamlaunch import config as C
    from tksteamlaunch.gui.game_dialog import GameDialog

    cfg = C.GameConfig()
    cfg.general.appid = "105"
    cfg.general.active_profile = "p1"
    C.save(cfg)
    C.save_profile("105", "p1", cfg)
    d = GameDialog(None, "105", "T")
    assert d.cb_profile.currentData() == "p1"
    d.t_env.insertRow(0)
    d.t_env.setItem(0, 0, QTableWidgetItem("MY_VAR"))
    d.t_env.setItem(0, 1, QTableWidgetItem("1"))
    d.accept()
    assert C.load_profile("105", "p1").env.vars.get("MY_VAR") == "1"
    live = C.load("105")
    assert "MY_VAR" not in live.env.vars  # Game Defaults stays pristine
    assert live.general.active_profile == "p1"
    d2 = GameDialog(None, "105", "T")
    assert d2.cfg.env.vars.get("MY_VAR") == "1"
    d2.close()


def test_switch_save_mirrors_origin_profile(qt_app, xdg_env, monkeypatch):
    from PySide6.QtWidgets import QMessageBox

    from tksteamlaunch import config as C
    from tksteamlaunch.gui.game_dialog import GameDialog

    cfg = C.GameConfig()
    cfg.general.appid = "106"
    cfg.general.active_profile = "p1"
    C.save(cfg)
    C.save_profile("106", "p1", cfg)
    C.save_profile("106", "p2", cfg)
    d = GameDialog(None, "106", "T")
    d.cb_profile.setCurrentIndex(d.cb_profile.findData("p1"))
    d.e_pre.setText("/edited.sh")
    monkeypatch.setattr(QMessageBox, "exec", lambda self: QMessageBox.StandardButton.Save)
    d.cb_profile.setCurrentIndex(d.cb_profile.findData("p2"))
    assert C.load_profile("106", "p1").pre_post.pre_command == "/edited.sh"
    assert C.load("106").pre_post.pre_command == ""  # live untouched by profile edits
    d.close()


def _answer(button):
    return lambda *a, **k: button


def test_reset_persists_defaults_immediately(qt_app, xdg_env, monkeypatch):
    from PySide6.QtWidgets import QMessageBox

    from tksteamlaunch import config as C
    from tksteamlaunch.gui.game_dialog import GameDialog

    tpl = C.GameConfig()
    tpl.pre_post.pre_command = "/tpl.sh"
    C.save_defaults(tpl)
    cfg = C.GameConfig()
    cfg.general.appid = "114"
    cfg.pre_post.pre_command = "/live.sh"
    C.save(cfg)
    monkeypatch.setattr(QMessageBox, "question", _answer(QMessageBox.StandardButton.Reset))
    d = GameDialog(None, "114", "T")
    d.e_pre.setText("/dirty.sh")
    d._on_reset()
    assert C.load("114").pre_post.pre_command == "/tpl.sh"
    assert d.e_pre.text() == "/tpl.sh"
    assert d.cb_profile.currentData() == ""
    assert not d._is_dirty()
    d.close()


def test_reset_on_profile_keeps_profile_file(qt_app, xdg_env, monkeypatch):
    from PySide6.QtWidgets import QMessageBox

    from tksteamlaunch import config as C
    from tksteamlaunch.gui.game_dialog import GameDialog

    tpl = C.GameConfig()
    tpl.pre_post.pre_command = "/tpl.sh"
    C.save_defaults(tpl)
    cfg = C.GameConfig()
    cfg.general.appid = "115"
    cfg.general.active_profile = "p1"
    C.save(cfg)
    prof = C.GameConfig()
    prof.general.appid = "115"
    prof.pre_post.pre_command = "/prof.sh"
    C.save_profile("115", "p1", prof)
    monkeypatch.setattr(QMessageBox, "question", _answer(QMessageBox.StandardButton.Reset))
    d = GameDialog(None, "115", "T")
    assert d.cb_profile.currentData() == "p1"
    d.e_pre.setText("/dirty.sh")
    d._on_reset()
    assert C.load_profile("115", "p1").pre_post.pre_command == "/prof.sh"
    live = C.load("115")
    assert live.pre_post.pre_command == "/tpl.sh"
    assert live.general.active_profile == ""
    assert d.cb_profile.currentData() == ""
    d2 = GameDialog(None, "115", "T")
    assert d2.e_pre.text() == "/tpl.sh"
    d2.close()


def test_reset_cancel_changes_nothing(qt_app, xdg_env, monkeypatch):
    from PySide6.QtWidgets import QMessageBox

    from tksteamlaunch import config as C
    from tksteamlaunch.gui.game_dialog import GameDialog

    cfg = C.GameConfig()
    cfg.general.appid = "116"
    cfg.pre_post.pre_command = "/live.sh"
    C.save(cfg)
    monkeypatch.setattr(QMessageBox, "question", _answer(QMessageBox.StandardButton.Cancel))
    d = GameDialog(None, "116", "T")
    d.e_pre.setText("/dirty.sh")
    d._on_reset()
    assert C.load("116").pre_post.pre_command == "/live.sh"
    assert d.e_pre.text() == "/dirty.sh"
    d.close()


def test_reset_populates_late_fields(qt_app, xdg_env, monkeypatch):
    from PySide6.QtWidgets import QMessageBox

    from tksteamlaunch import config as C
    from tksteamlaunch.gui.game_dialog import GameDialog

    tpl = C.GameConfig()
    tpl.ludusavi.enable = True
    tpl.debug.proton_log = True
    tpl.proton.fresh_prefix = True
    tpl.proton.winetricks_verbs = ["dxvk"]
    C.save_defaults(tpl)
    cfg = C.GameConfig()
    cfg.general.appid = "117"
    C.save(cfg)
    monkeypatch.setattr(QMessageBox, "question", lambda *a, **k: QMessageBox.StandardButton.Reset)
    d = GameDialog(None, "117", "T")
    assert not d.c_lu_enable.isChecked()
    d._on_reset()
    assert d.c_lu_enable.isChecked()
    assert d.c_protonlog.isChecked()
    assert d.c_fresh.isChecked()
    assert d.e_verbs.text() == "dxvk"
    saved = C.load("117")
    assert saved.ludusavi.enable is True
    assert saved.debug.proton_log is True
    assert saved.proton.fresh_prefix is True
    assert saved.proton.winetricks_verbs == ["dxvk"]
    d.close()


def test_switch_populates_late_fields(qt_app, xdg_env):
    from tksteamlaunch import config as C
    from tksteamlaunch.gui.game_dialog import GameDialog

    live = C.GameConfig()
    live.general.appid = "118"
    live.general.active_profile = "p1"
    C.save(live)
    p1 = C.GameConfig()
    p1.general.appid = "118"
    C.save_profile("118", "p1", p1)
    p2 = C.GameConfig()
    p2.general.appid = "118"
    p2.ludusavi.enable = True
    p2.debug.proton_log = True
    p2.proton.fresh_prefix = True
    C.save_profile("118", "p2", p2)
    d = GameDialog(None, "118", "T")
    assert not d.c_lu_enable.isChecked()
    d.cb_profile.setCurrentIndex(d.cb_profile.findData("p2"))
    qt_app.processEvents()
    assert d.c_lu_enable.isChecked()
    assert d.c_protonlog.isChecked()
    assert d.c_fresh.isChecked()
    d.accept()
    assert C.load_profile("118", "p2").ludusavi.enable is True
    d.close()


def _main_window_with_game(qt_app, appid="120", monkeypatch=None):
    from tksteamlaunch import config as C
    from tksteamlaunch import protondb as pdbmod
    from tksteamlaunch.gui.main_window import MainWindow

    if monkeypatch is not None:
        monkeypatch.setattr(pdbmod, "refresh", lambda aid: {"tier": "gold", "total": 5})
    cfg = C.GameConfig()
    cfg.general.appid = appid
    C.save(cfg)
    w = MainWindow()
    w.show()
    qt_app.processEvents()
    return w


def _menu_actions(w, appid):
    return w._build_game_menu(appid).actions()


def test_context_menu_actions_no_steam_dirs(qt_app, xdg_env, monkeypatch, tmp_path):
    monkeypatch.setenv("STEAM_ROOT", str(tmp_path))  # empty: no install/prefix
    w = _main_window_with_game(qt_app, "120", monkeypatch)
    texts = [(a.text(), a.isEnabled()) for a in _menu_actions(w, "120")]
    labels = [t for t, _ in texts]
    assert labels == [
        "Copy Launch Options",
        "Edit Settings",
        "",
        "Copy App ID",
        "Copy Game Name",
        "",
        "Open Install Folder",
        "Open Proton Prefix",
        "Clear Shader Cache",
        "Open ProtonDB Page",
        "Validate Game",
        "Clear History",
        "Clone Settings To...",
        "",
        "Remove 1 Game",
        "Reset to Global Defaults",
    ]
    state = dict(texts)
    assert state["Open Install Folder"] is False
    assert state["Open Proton Prefix"] is False
    assert state["Copy App ID"] is True
    w.close()


def test_context_menu_folders_enabled_with_steam_dirs(qt_app, xdg_env, monkeypatch, tmp_path):
    sap = tmp_path / "steamapps"
    (sap / "common" / "TGame").mkdir(parents=True)
    (sap / "compatdata" / "121").mkdir(parents=True)
    (sap / "appmanifest_121.acf").write_text(
        '"AppState"\n{\n"appid" "121"\n"name" "T"\n"installdir" "TGame"\n}\n'
    )
    monkeypatch.setenv("STEAM_ROOT", str(tmp_path))
    w = _main_window_with_game(qt_app, "121", monkeypatch)
    state = {a.text(): a.isEnabled() for a in _menu_actions(w, "121")}
    assert state["Open Install Folder"] is True
    assert state["Open Proton Prefix"] is True
    w.close()


def test_context_menu_copy_and_validate(qt_app, xdg_env, monkeypatch):
    from PySide6.QtGui import QGuiApplication
    from PySide6.QtWidgets import QMessageBox

    w = _main_window_with_game(qt_app, "122", monkeypatch)
    pasted = []
    monkeypatch.setattr(QGuiApplication, "clipboard", lambda *a: None)
    w._copy_text("hello", "Thing")
    assert "unavailable" in w.status.text()
    monkeypatch.setattr(
        QGuiApplication, "clipboard", lambda *a: type("C", (), {"setText": pasted.append})()
    )
    w._copy_text("122", "App ID")
    assert pasted == ["122"]
    assert "122" in w.status.text()

    from tksteamlaunch import launcher as L

    monkeypatch.setattr(L, "validate_game", lambda appid: [])
    infos = []
    monkeypatch.setattr(QMessageBox, "information", lambda *a: infos.append(a))
    w._validate_selected("122")
    assert infos and "No issues" in str(infos[0])
    warns = []
    monkeypatch.setattr(QMessageBox, "warning", lambda *a: warns.append(a))
    monkeypatch.setattr(L, "validate_game", lambda appid: ["122: bad"])
    w._validate_selected("122")
    assert warns and "bad" in str(warns[0])
    w.close()


def test_double_click_protondb_opens_url(qt_app, xdg_env, monkeypatch):
    from PySide6.QtGui import QDesktopServices

    w = _main_window_with_game(qt_app, "123", monkeypatch)
    opened = []
    monkeypatch.setattr(QDesktopServices, "openUrl", lambda url: opened.append(url.toString()))
    tier = None
    for _ in range(100):
        tier = w.table.item(0, 3)
        if tier is not None:
            break
        qt_app.processEvents()
    assert tier is not None, "tier cell never populated"
    w._on_double_click(tier)
    assert opened == ["https://www.protondb.com/app/123"]
    w.close()


def test_appid_column_sorts_numerically(qt_app, xdg_env, monkeypatch):
    from PySide6.QtCore import Qt

    from tksteamlaunch import config as C
    from tksteamlaunch.gui import main_window as mw

    for appid in ("1044620", "80", "9", "vette"):
        cfg = C.GameConfig()
        cfg.general.appid = appid
        C.save(cfg)
    w = _main_window_with_game(qt_app, "80", monkeypatch)
    w.table.sortByColumn(1, Qt.SortOrder.AscendingOrder)
    qt_app.processEvents()
    got = [w.table.item(r, 1).text() for r in range(w.table.rowCount())]
    assert got == ["9", "80", "1044620", "vette"]
    assert isinstance(w.table.item(0, 1), mw._AppIdItem)
    w.close()


def _select_rows(w, *rows):
    for row in rows:
        w.table.item(row, 0).setSelected(True)


def test_remove_selected_multi(qt_app, xdg_env, monkeypatch):
    from PySide6.QtWidgets import QMessageBox

    from tksteamlaunch import config as C

    for appid in ("130", "131", "132"):
        cfg = C.GameConfig()
        cfg.general.appid = appid
        C.save(cfg)
    w = _main_window_with_game(qt_app, "130", monkeypatch)
    _select_rows(w, 0, 1)
    assert w._selected_appids() == ["130", "131"]
    monkeypatch.setattr(QMessageBox, "question", lambda *a: QMessageBox.StandardButton.No)
    w._remove_selected()
    assert C.game_file("130").exists() and C.game_file("131").exists()
    monkeypatch.setattr(QMessageBox, "question", lambda *a: QMessageBox.StandardButton.Yes)
    w._remove_selected()
    assert not C.game_file("130").exists()
    assert not C.game_file("131").exists()
    assert C.game_file("132").exists()
    w.close()


def test_remove_offers_profile_cleanup(qt_app, xdg_env, monkeypatch):
    from PySide6.QtWidgets import QDialog, QMessageBox

    import tksteamlaunch.gui.main_window as mw
    from tksteamlaunch import config as C

    cfg = C.GameConfig()
    cfg.general.appid = "133"
    C.save(cfg)
    C.save_profile("133", "p1", cfg)
    C.save_profile("133", "p2", cfg)
    w = _main_window_with_game(qt_app, "133", monkeypatch)
    seen = []

    class FakeDialog:
        def __init__(self, parent, entries):
            seen.append(entries)

        def exec(self):
            return QDialog.DialogCode.Accepted

        def selected(self):
            return ["133"]  # clean it all

    monkeypatch.setattr(mw, "_ProfileCleanupDialog", FakeDialog)
    monkeypatch.setattr(QMessageBox, "question", lambda *a: QMessageBox.StandardButton.Yes)
    w.table.selectRow(0)
    w._remove_selected()
    assert seen and seen[0][0][0] == "133" and seen[0][0][2] == 2
    assert not C.profiles_dir("133").exists()
    assert not C.game_file("133").exists()
    w.close()


def test_remove_cleanup_reject_keeps_profiles(qt_app, xdg_env, monkeypatch):
    from PySide6.QtWidgets import QDialog, QMessageBox

    import tksteamlaunch.gui.main_window as mw
    from tksteamlaunch import config as C

    cfg = C.GameConfig()
    cfg.general.appid = "134"
    C.save(cfg)
    C.save_profile("134", "p1", cfg)
    w = _main_window_with_game(qt_app, "134", monkeypatch)

    class FakeDialog:
        def __init__(self, parent, entries):
            pass

        def exec(self):
            return QDialog.DialogCode.Rejected

        def selected(self):
            raise AssertionError("must not clean on reject")

    monkeypatch.setattr(mw, "_ProfileCleanupDialog", FakeDialog)
    monkeypatch.setattr(QMessageBox, "question", lambda *a: QMessageBox.StandardButton.Yes)
    w.table.selectRow(0)
    w._remove_selected()
    assert C.profile_file("134", "p1").exists()
    w.close()


def test_cleanup_dialog_selection(qt_app):
    from PySide6.QtCore import Qt

    import tksteamlaunch.gui.main_window as mw

    dlg = mw._ProfileCleanupDialog(None, [("135", "G", 2), ("136", "H", 1)])
    assert dlg.selected() == ["135", "136"]
    dlg._table.item(0, 0).setCheckState(Qt.CheckState.Unchecked)
    assert dlg.selected() == ["136"]
    dlg.close()


def test_reset_selected_multi(qt_app, xdg_env, monkeypatch):
    from PySide6.QtWidgets import QMessageBox

    from tksteamlaunch import config as C

    tpl = C.GameConfig()
    tpl.pre_post.pre_command = "/tpl.sh"
    C.save_defaults(tpl)
    for appid in ("137", "138"):
        cfg = C.GameConfig()
        cfg.general.appid = appid
        cfg.pre_post.pre_command = "/live.sh"
        C.save(cfg)
        C.save_profile(appid, "p1", cfg)
    w = _main_window_with_game(qt_app, "139", monkeypatch)
    _select_rows(w, 0, 1)
    monkeypatch.setattr(QMessageBox, "question", lambda *a: QMessageBox.StandardButton.No)
    w._reset_selected()
    assert C.load("137").pre_post.pre_command == "/live.sh"
    monkeypatch.setattr(QMessageBox, "question", lambda *a: QMessageBox.StandardButton.Yes)
    w._reset_selected()
    for appid in ("137", "138"):
        live = C.load(appid)
        assert live.pre_post.pre_command == "/tpl.sh"
        assert live.general.active_profile == ""
        assert C.profile_file(appid, "p1").exists()  # profiles kept
    w.close()


def test_ensure_row_selected_preserves_multi(qt_app, xdg_env, monkeypatch):
    w = _main_window_with_game(qt_app, "130", monkeypatch)
    from tksteamlaunch import config as C

    for appid in ("131", "132"):
        cfg = C.GameConfig()
        cfg.general.appid = appid
        C.save(cfg)
    w.refresh()
    _select_rows(w, 0, 1)
    w._ensure_row_selected(1)  # already selected: keep both
    assert w._selected_appids() == ["130", "131"]
    w._ensure_row_selected(2)  # unselected: collapse to it
    assert w._selected_appids() == ["132"]
    w.close()


def test_context_menu_multi_shows_only_multi_actions(qt_app, xdg_env, monkeypatch):
    from tksteamlaunch import config as C

    for appid in ("143", "144"):
        cfg = C.GameConfig()
        cfg.general.appid = appid
        C.save(cfg)
    w = _main_window_with_game(qt_app, "143", monkeypatch)
    _select_rows(w, 0, 1)
    labels = [a.text() for a in w._build_game_menu("143").actions()]
    assert labels == [
        "Copy Launch Options",
        "Remove 2 Games",
        "Reset to Global Defaults",
    ]
    w.close()


def test_remove_reset_without_selection_hints(qt_app, xdg_env, monkeypatch):
    w = _main_window_with_game(qt_app, "145", monkeypatch)
    w.table.clearSelection()
    w._remove_selected()
    assert w.status.text() == "Select games first."
    w._reset_selected()
    assert w.status.text() == "Select games first."
    w.close()


def test_clean_profiles_button(qt_app, xdg_env, monkeypatch):
    from PySide6.QtWidgets import QDialog, QMessageBox

    import tksteamlaunch.gui.main_window as mw
    from tksteamlaunch import config as C

    ghost = C.GameConfig()
    ghost.general.appid = "146"
    C.save_profile("146", "p1", ghost)
    w = _main_window_with_game(qt_app, "147", monkeypatch)

    class FakeDialog:
        def __init__(self, parent, entries):
            assert entries[0][0] == "146"

        def exec(self):
            return QDialog.DialogCode.Accepted

        def selected(self):
            return ["146"]

    monkeypatch.setattr(mw, "_ProfileCleanupDialog", FakeDialog)
    w._clean_profiles()
    assert not C.profiles_dir("146").exists()
    assert "Cleaned" in w.status.text()

    infos = []
    monkeypatch.setattr(QMessageBox, "information", lambda *a: infos.append(a))
    w._clean_profiles()
    assert infos and "No orphaned" in str(infos[0])
    w.close()


def _write_history(xdg_env, *lines):
    from tksteamlaunch import xdg as xdgmod

    path = xdgmod.log_file()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(lines), encoding="utf-8")
    return path


def test_played_column_shows_total_time(qt_app, xdg_env, monkeypatch):
    _write_history(xdg_env, "2026-10-03T10:00:00 appid=150 exit=0 dur=3700 cmd=/game\n")
    w = _main_window_with_game(qt_app, "150", monkeypatch)
    cell = w.table.item(0, 2)
    assert cell.text() == "1h 1m"
    assert "1 sessions" in cell.toolTip()
    w.close()


def test_played_column_sorts_by_seconds(qt_app, xdg_env, monkeypatch):
    from PySide6.QtCore import Qt

    from tksteamlaunch import config as C

    _write_history(
        xdg_env,
        "2026-10-03T10:00:00 appid=151 exit=0 dur=7200 cmd=/a\n",
        "2026-10-03T11:00:00 appid=152 exit=0 dur=60 cmd=/b\n",
    )
    for appid in ("151", "152", "153"):
        cfg = C.GameConfig()
        cfg.general.appid = appid
        C.save(cfg)
    w = _main_window_with_game(qt_app, "151", monkeypatch)
    w.table.sortByColumn(2, Qt.SortOrder.DescendingOrder)
    qt_app.processEvents()
    got = [w.table.item(r, 1).text() for r in range(w.table.rowCount())]
    assert got[0] == "151"  # 2h first
    assert got[-1] == "153"  # never played last
    w.close()


def test_history_clear(qt_app, xdg_env, monkeypatch):
    from PySide6.QtWidgets import QMessageBox

    from tksteamlaunch.gui.history_dialog import HistoryDialog

    path = _write_history(xdg_env, "2026-10-03T10:00:00 appid=150 exit=0 dur=60 cmd=/game\n")
    monkeypatch.setattr(QMessageBox, "question", lambda *a, **k: QMessageBox.StandardButton.No)
    dlg = HistoryDialog(None)
    assert dlg._table.rowCount() == 1
    dlg._clear()
    assert path.read_text() != ""  # No keeps the log
    monkeypatch.setattr(QMessageBox, "question", lambda *a, **k: QMessageBox.StandardButton.Yes)
    dlg._clear()
    assert path.read_text() == ""
    assert dlg._table.rowCount() == 0
    dlg.close()


def test_column_visibility_persists(qt_app, xdg_env, monkeypatch):
    w = _main_window_with_game(qt_app, "160", monkeypatch)
    header = w.table.horizontalHeader()
    assert not header.isSectionHidden(1)
    w._set_column_visible(1, False)
    assert header.isSectionHidden(1)
    w2 = _main_window_with_game(qt_app, "160", monkeypatch)
    assert w2.table.horizontalHeader().isSectionHidden(1)
    assert not w2.table.horizontalHeader().isSectionHidden(0)
    w.close()
    w2.close()


def test_header_menu_game_locked_and_reset(qt_app, xdg_env, monkeypatch):
    w = _main_window_with_game(qt_app, "161", monkeypatch)
    acts = {a.text(): a for a in w._build_header_menu().actions()}
    assert set(acts) == {"Game", "App ID", "Played", "ProtonDB", "", "Reset Columns"}
    assert acts["Game"].isChecked() and not acts["Game"].isEnabled()
    acts["App ID"].toggle()
    qt_app.processEvents()
    assert w.table.horizontalHeader().isSectionHidden(1)
    w._reset_columns()
    assert not w.table.horizontalHeader().isSectionHidden(1)
    from tksteamlaunch import config as C

    assert C.load_preferences().hidden_columns == ""
    assert C.load_preferences().column_order == ""
    w.close()


def test_reordered_columns_keep_actions_working(qt_app, xdg_env, monkeypatch):
    from PySide6.QtGui import QDesktopServices

    w = _main_window_with_game(qt_app, "162", monkeypatch)
    header = w.table.horizontalHeader()
    header.moveSection(header.visualIndex(3), 0)  # ProtonDB visually first
    qt_app.processEvents()
    from tksteamlaunch import config as C

    assert C.load_preferences().column_order.split(",")[0] == "3"
    tier = w.table.item(0, 3)  # logical index is stable
    opened = []
    monkeypatch.setattr(QDesktopServices, "openUrl", lambda url: opened.append(url.toString()))
    if tier is not None:
        w._on_double_click(tier)
        assert opened == ["https://www.protondb.com/app/162"]
    w.close()


def test_preferences_dialog_quick_launch(qt_app, xdg_env):
    from tksteamlaunch import config as C
    from tksteamlaunch.gui.preferences_dialog import PreferencesDialog

    prefs = PreferencesDialog(None)
    assert prefs.c_quick.isChecked() is True
    assert prefs.s_quick_count.isEnabled() is False  # tray off gates it
    prefs.c_tray.setChecked(True)
    assert prefs.s_quick_count.isEnabled() is True
    prefs.c_quick.setChecked(False)
    assert prefs.s_quick_count.isEnabled() is False
    prefs.c_quick.setChecked(True)
    prefs.s_quick_count.setValue(8)
    prefs.accept()
    back = C.load_preferences()
    assert (back.tray_quick_launch, back.tray_quick_count) == (True, 8)


def test_tray_recents_and_steam_launch(qt_app, xdg_env, monkeypatch):
    from PySide6.QtGui import QDesktopServices
    from PySide6.QtWidgets import QMenu

    _write_history(
        xdg_env,
        "2026-10-03T10:00:00 appid=170 exit=0 dur=60 cmd=/a\n",
        "2026-10-03T11:00:00 appid=171 exit=0 dur=120 cmd=/b\n",
    )
    w = _main_window_with_game(qt_app, "170", monkeypatch)
    recents = w._recent_games(1)
    assert [a for a, _, _ in recents] == ["171"]
    assert recents[0][2] == 120
    menu = QMenu(w)
    w._refresh_tray_menu(menu)
    labels = [a.text() for a in menu.actions() if a.text()]
    assert any("171" in label or "170" in label for label in labels)
    opened = []
    monkeypatch.setattr(
        QDesktopServices, "openUrl", lambda url: opened.append(url.toString()) or True
    )
    w._launch_steam("171")
    assert opened == ["steam://rungameid/171"]
    from PySide6.QtWidgets import QMessageBox

    warns = []
    monkeypatch.setattr(QDesktopServices, "openUrl", lambda url: False)
    monkeypatch.setattr(QMessageBox, "warning", lambda *a: warns.append(a))
    w._launch_steam("171")
    assert warns
    w.close()


def test_scan_library_adds_selected(qt_app, xdg_env, monkeypatch, tmp_path):
    import tksteamlaunch.gui.main_window as mw
    from tksteamlaunch import config as C

    sap = tmp_path / "steamapps"
    sap.mkdir()
    (sap / "appmanifest_180.acf").write_text('"AppState"\n{\n"appid" "180"\n"name" "S Game"\n}\n')
    monkeypatch.setenv("STEAM_ROOT", str(tmp_path))
    w = _main_window_with_game(qt_app, "181", monkeypatch)

    class FakeDialog:
        def __init__(self, parent, entries):
            assert entries == [("180", "S Game")]

        def exec(self):
            from PySide6.QtWidgets import QDialog

            return QDialog.DialogCode.Accepted

        def selected(self):
            return ["180"]

    monkeypatch.setattr(mw, "_ScanDialog", FakeDialog)
    w._scan_library()
    assert C.game_file("180").exists()
    assert "Added 1" in w.status.text()
    w.close()


def test_scan_library_empty_informs(qt_app, xdg_env, monkeypatch, tmp_path):
    from PySide6.QtWidgets import QMessageBox

    monkeypatch.setenv("STEAM_ROOT", str(tmp_path))
    w = _main_window_with_game(qt_app, "182", monkeypatch)
    infos = []
    monkeypatch.setattr(QMessageBox, "information", lambda *a: infos.append(a))
    w._scan_library()
    assert infos and "already configured" in str(infos[0])
    w.close()


def test_scan_dialog_selection(qt_app):
    from PySide6.QtCore import Qt

    import tksteamlaunch.gui.main_window as mw

    dlg = mw._ScanDialog(None, [("180", "S Game")])
    assert dlg.selected() == ["180"]
    dlg._table.item(0, 0).setCheckState(Qt.CheckState.Unchecked)
    assert dlg.selected() == []
    dlg.close()


def test_clear_shader_cache(qt_app, xdg_env, monkeypatch, tmp_path):
    from PySide6.QtWidgets import QMessageBox

    sap = tmp_path / "steamapps"
    (sap / "shadercache" / "183").mkdir(parents=True)
    (sap / "shadercache" / "183" / "fossilize.db").write_bytes(b"x" * 1024)
    monkeypatch.setenv("STEAM_ROOT", str(tmp_path))
    w = _main_window_with_game(qt_app, "183", monkeypatch)
    monkeypatch.setattr(QMessageBox, "question", lambda *a: QMessageBox.StandardButton.No)
    w._clear_shader_cache("183")
    assert (sap / "shadercache" / "183").exists()
    monkeypatch.setattr(QMessageBox, "question", lambda *a: QMessageBox.StandardButton.Yes)
    w._clear_shader_cache("183")
    assert not (sap / "shadercache" / "183").exists()
    assert "Cleared" in w.status.text()
    w._clear_shader_cache("184")  # missing: silent no-op
    w.close()


def test_newer_config_warns_on_open(qt_app, xdg_env, monkeypatch):
    from PySide6.QtWidgets import QMessageBox

    from tksteamlaunch import config as C
    from tksteamlaunch.gui.game_dialog import GameDialog

    cfg = C.GameConfig()
    cfg.general.appid = "195"
    C.save(cfg)
    C.game_file("195").write_text(
        C.game_file("195").read_text().replace("config_version = 1", "config_version = 99"),
        encoding="utf-8",
    )
    seen = []
    monkeypatch.setattr(
        QMessageBox, "warning", lambda *a, **k: seen.append(str(a[2]) if len(a) > 2 else "")
    )
    d = GameDialog(None, "195", "T")
    assert seen and "newer" in seen[0]
    d.close()


def test_app_icons_are_font_free():
    from pathlib import Path

    icons = Path(__file__).parent.parent / "src" / "tksteamlaunch" / "icons"
    for name in ("tksteamlaunch.svg", "tksteamlaunch-mono.svg"):
        text = (icons / name).read_text()
        assert "<text" not in text and "font-family" not in text
        assert text.index("<svg") == 0


def test_bundled_style_only_inside_appimage(monkeypatch):
    from tksteamlaunch.gui import app as appmod

    monkeypatch.delenv("APPIMAGE", raising=False)
    monkeypatch.delenv("QT_STYLE_OVERRIDE", raising=False)
    assert appmod.bundled_style() == ""
    monkeypatch.setenv("APPIMAGE", "/x/y.AppImage")
    assert appmod.bundled_style() == "Fusion"
    monkeypatch.setenv("QT_STYLE_OVERRIDE", "Windows")
    assert appmod.bundled_style() == ""


def test_clone_settings_to_game(qt_app, xdg_env, monkeypatch):
    from PySide6.QtWidgets import QInputDialog, QMessageBox

    from tksteamlaunch import config as C

    cfg = C.GameConfig()
    cfg.general.appid = "204"
    cfg.env.vars = {"A": "1"}
    C.save(cfg)
    C.save_profile("204", "p1", cfg)
    w = _main_window_with_game(qt_app, "209", monkeypatch)
    monkeypatch.setattr(QInputDialog, "getText", lambda *a, **k: ("205", True))
    w._clone_game_to("204")
    assert C.load("205").env.vars == {"A": "1"}
    assert C.load_profile("205", "p1").env.vars == {"A": "1"}
    assert "Cloned" in w.status.text()
    monkeypatch.setattr(QInputDialog, "getText", lambda *a, **k: ("204", True))
    infos = []
    monkeypatch.setattr(QMessageBox, "information", lambda *a: infos.append(a))
    w._clone_game_to("204")
    assert infos  # same source/target refused
    w.close()


def test_menu_shows_effective_profile_wrappers(qt_app, xdg_env, monkeypatch, tmp_path):
    import os

    from tksteamlaunch import config as C
    from tksteamlaunch.gui.menu_dialog import MenuDialog

    live = C.GameConfig()
    live.general.appid = "210"
    live.general.active_profile = "p1"
    C.save(live)
    prof = C.GameConfig()
    prof.general.appid = "210"
    prof.gamemode.feral_gamemode = True
    C.save_profile("210", "p1", prof)
    fake = tmp_path / "gamemoderun"
    fake.write_text("#!/bin/sh\nexit 0\n")
    fake.chmod(0o755)
    monkeypatch.setenv("PATH", f"{tmp_path}{os.pathsep}{os.environ['PATH']}")
    m = MenuDialog(None, "210", "Menu Game")
    assert "GameMode" in m._detail_lines()  # from the profile, not live
    m.close()


def test_history_clear_selected(qt_app, xdg_env, monkeypatch):
    from PySide6.QtWidgets import QMessageBox

    from tksteamlaunch.gui.history_dialog import HistoryDialog

    _write_history(
        xdg_env,
        "2026-10-03T10:00:00 appid=210 exit=0 dur=60 cmd=/a\n",
        "2026-10-03T11:00:00 appid=211 exit=0 dur=60 cmd=/b\n",
    )
    monkeypatch.setattr(QMessageBox, "question", lambda *a, **k: QMessageBox.StandardButton.Yes)
    dlg = HistoryDialog(None)
    assert dlg._table.rowCount() == 2
    dlg._table.selectRow(0)
    ask = dlg._appid_for_row(0)
    dlg._clear_selected()
    assert dlg._table.rowCount() == 1
    from tksteamlaunch import xdg as xdgmod

    rest = xdgmod.log_file().read_text()
    assert f"appid={ask} " not in rest
    dlg.close()


def test_main_menu_clear_history(qt_app, xdg_env, monkeypatch):
    from PySide6.QtWidgets import QMessageBox

    _write_history(xdg_env, "2026-10-03T10:00:00 appid=212 exit=0 dur=60 cmd=/a\n")
    w = _main_window_with_game(qt_app, "212", monkeypatch)
    monkeypatch.setattr(QMessageBox, "question", lambda *a, **k: QMessageBox.StandardButton.Yes)
    w._clear_game_history("212")
    from tksteamlaunch import xdg as xdgmod

    assert "appid=212" not in xdgmod.log_file().read_text()
    assert "Cleared 1" in w.status.text()
    w.close()


def test_clone_game_from_list(qt_app, xdg_env, monkeypatch, tmp_path):
    from PySide6.QtWidgets import QInputDialog

    from tksteamlaunch import config as C

    sap = tmp_path / "steamapps"
    sap.mkdir()
    (sap / "appmanifest_206.acf").write_text('"AppState"\n{\n"appid" "206"\n"name" "C Game"\n}\n')
    monkeypatch.setenv("STEAM_ROOT", str(tmp_path))
    cfg = C.GameConfig()
    cfg.general.appid = "204"
    C.save(cfg)
    w = _main_window_with_game(qt_app, "209", monkeypatch)
    picked = []
    monkeypatch.setattr(
        QInputDialog, "getItem", lambda *a, **k: picked.append(a[3]) or ("C Game [206]", True)
    )
    w._clone_game_to("204")
    assert picked and "C Game [206]" in picked[0]
    assert C.game_file("206").exists()
    w.close()


def test_edit_menu_uses_profile_timeout(qt_app, xdg_env, capsys):
    from PySide6.QtCore import QTimer
    from PySide6.QtWidgets import QApplication

    from tksteamlaunch import config as C
    from tksteamlaunch.gui import edit as editmod
    from tksteamlaunch.gui.menu_dialog import MenuDialog

    live = C.GameConfig()
    live.general.appid = "213"
    live.general.menu_timeout = 5
    live.general.active_profile = "p1"
    C.save(live)
    prof = C.GameConfig()
    prof.general.appid = "213"
    prof.general.menu_timeout = 30
    C.save_profile("213", "p1", prof)
    seen = []

    def inspect_modal():
        modal = QApplication.activeModalWidget()
        if isinstance(modal, MenuDialog):
            seen.append(modal._remaining)
            modal.reject()
        else:
            QTimer.singleShot(200, inspect_modal)

    QTimer.singleShot(400, inspect_modal)
    assert editmod.main(["--appid", "213", "--menu"]) == 0
    assert seen == [30]
    assert '"outcome": "cancelled"' in capsys.readouterr().out


def test_mode_picker_fills_in_background(qt_app, xdg_env, monkeypatch):
    from tksteamlaunch.backends import display as dispmod
    from tksteamlaunch.gui.game_dialog import GameDialog

    monkeypatch.setattr(dispmod, "offered_modes", lambda *a: [(3, "1920x1080@60", False)])
    d = GameDialog(None, "164", "T")
    assert _pump_until(qt_app, lambda: d.e_dmode.count() >= 2)
    assert "1920x1080@60" in [d.e_dmode.itemData(i) for i in range(d.e_dmode.count())]
    d.close()


def test_wedged_display_backend_never_blocks_open(qt_app, xdg_env, monkeypatch):
    import threading
    import time

    from tksteamlaunch.backends import display as dispmod
    from tksteamlaunch.gui.game_dialog import GameDialog

    gate = threading.Event()

    def stuck(*a):
        assert gate.wait(timeout=30)
        return []

    monkeypatch.setattr(dispmod, "offered_modes", stuck)
    start = time.monotonic()
    d = GameDialog(None, "166", "T")
    assert time.monotonic() - start < 10
    gate.set()  # release the worker before close so stop() joins cleanly
    d.close()


def test_dip_note_only_for_current_mode(qt_app, xdg_env, monkeypatch):
    from tksteamlaunch.backends import display as dispmod
    from tksteamlaunch.gui.game_dialog import GameDialog

    monkeypatch.setattr(
        dispmod,
        "offered_modes",
        lambda *a: [(2, "2560x1440@164.96", True), (3, "1920x1080@60", False)],
    )
    cfg = __import__("tksteamlaunch.config", fromlist=["x"]).GameConfig()
    cfg.general.appid = "167"
    cfg.display.mode = ""
    __import__("tksteamlaunch.config", fromlist=["x"]).save(cfg)
    d = GameDialog(None, "167", "T")
    assert _pump_until(qt_app, lambda: d.e_dmode.count() >= 2)
    assert d._dip_note.isHidden()
    assert d._dip_row.isHidden()
    d.e_dmode.setCurrentText("1920x1080@60")
    qt_app.processEvents()
    assert d._dip_note.isHidden()
    assert d._dip_row.isHidden()
    d.e_dmode.setCurrentText("2560x1440@164.96")
    qt_app.processEvents()
    assert not d._dip_note.isHidden()
    assert not d._dip_row.isHidden()
    d.close()


def test_dip_slider_roundtrip(qt_app, xdg_env):
    from tksteamlaunch import config as C
    from tksteamlaunch.gui.game_dialog import GameDialog

    cfg = C.GameConfig()
    cfg.general.appid = "171"
    C.save(cfg)
    d = GameDialog(None, "171", "T")
    assert (d.s_dip.minimum(), d.s_dip.maximum()) == (3, 15)
    assert d.s_dip.value() == 8 and d.l_dip.text() == "8 s"
    d.s_dip.setValue(6)
    assert d.l_dip.text() == "6 s"
    d._collect()
    assert d.cfg.display.dip_seconds == 6
    d.accept()
    assert C.load("171").display.dip_seconds == 6
    d.close()


def test_translations_load_pt_br(qt_app, monkeypatch):
    from PySide6.QtCore import QCoreApplication, QLocale

    from tksteamlaunch.gui import helpers as helpersmod

    monkeypatch.setattr(QLocale, "system", classmethod(lambda cls: QLocale("pt_BR")))
    app = qt_app
    assert helpersmod.install_translations(app) == "pt_BR"
    assert QCoreApplication.translate("MainWindow", "Games") == "Jogos"
    assert QCoreApplication.translate("GameDialog", "Save As...") == "Salvar como..."
    assert QCoreApplication.translate("MainWindow", "Nope") == "Nope"
    app.removeTranslator(helpersmod._translators.pop())


def test_translations_unknown_locale_loads_nothing(qt_app, monkeypatch):
    from PySide6.QtCore import QLocale

    from tksteamlaunch.gui import helpers as helpersmod

    monkeypatch.setattr(QLocale, "system", classmethod(lambda cls: QLocale("xx_YY")))
    assert helpersmod.install_translations(qt_app) == ""


def test_preferences_dialog_language(qt_app, xdg_env):
    from tksteamlaunch import config as C
    from tksteamlaunch.gui.preferences_dialog import PreferencesDialog

    prefs = PreferencesDialog(None)
    datas = [prefs.cb_lang.itemData(i) for i in range(prefs.cb_lang.count())]
    assert datas[0] == "system"
    assert "pt_BR" in datas
    prefs.cb_lang.setCurrentIndex(datas.index("pt_BR"))
    prefs.accept()
    assert C.load_preferences().language == "pt_BR"
    prefs.close()


def test_install_translations_explicit_override(qt_app, monkeypatch):
    from PySide6.QtCore import QCoreApplication, QLocale

    from tksteamlaunch.gui import helpers as helpersmod

    monkeypatch.setattr(QLocale, "system", classmethod(lambda cls: QLocale("pt_BR")))
    assert helpersmod.install_translations(qt_app, "en") == ""
    assert QCoreApplication.translate("MainWindow", "Games") == "Games"
    assert helpersmod.install_translations(qt_app, "pt_BR") == "pt_BR"
    assert QCoreApplication.translate("MainWindow", "Games") == "Jogos"
    qt_app.removeTranslator(helpersmod._translators.pop())


def test_preferred_language_falls_back(xdg_env, monkeypatch):
    from tksteamlaunch import config as C
    from tksteamlaunch.gui import helpers as helpersmod

    assert helpersmod.preferred_language() == "system"
    prefs = C.load_preferences()
    prefs.language = "pt_BR"
    C.save_preferences(prefs)
    assert helpersmod.preferred_language() == "pt_BR"
    monkeypatch.setattr(C, "load_preferences", lambda: 1 / 0)
    assert helpersmod.preferred_language() == ""
