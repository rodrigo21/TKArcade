"""Program preferences dialog (never per-game)."""

from __future__ import annotations

from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QVBoxLayout,
)

from .. import config as cfgmod


class PreferencesDialog(QDialog):
    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Preferences")
        self.resize(420, 280)
        self.prefs = cfgmod.load_preferences()

        layout = QVBoxLayout(self)
        form = QFormLayout()
        layout.addLayout(form)

        self.c_show_preview = QCheckBox("Show launch command preview")
        self.c_show_preview.setToolTip("Live preview box at the bottom of game dialogs.")
        self.c_show_preview.setChecked(self.prefs.show_preview)
        form.addRow("", self.c_show_preview)

        self.c_tray = QCheckBox("Enable status bar icon")
        self.c_tray.setToolTip("Keep TKSteamLaunch in the system tray.")
        self.c_tray.setChecked(self.prefs.tray_enable)
        self.c_tray.toggled.connect(self._update_tray_state)
        form.addRow("", self.c_tray)

        self.cb_tray_icon = QComboBox()
        self.cb_tray_icon.addItem("Normal", "normal")
        self.cb_tray_icon.addItem("Monochrome", "mono")
        self.cb_tray_icon.setCurrentIndex(0 if self.prefs.tray_icon == "normal" else 1)
        form.addRow("Tray icon style:", self.cb_tray_icon)

        self.c_minimize = QCheckBox("Minimize to tray")
        self.c_minimize.setChecked(self.prefs.minimize_to_tray)
        form.addRow("", self.c_minimize)

        self.c_close = QCheckBox("Close to tray")
        self.c_close.setChecked(self.prefs.close_to_tray)
        form.addRow("", self.c_close)

        self.c_quick = QCheckBox("Show recent games in tray menu")
        self.c_quick.setToolTip("Launch recent games through Steam (steam:// URL).")
        self.c_quick.setChecked(self.prefs.tray_quick_launch)
        self.c_quick.toggled.connect(self._update_tray_state)
        form.addRow("", self.c_quick)

        from PySide6.QtWidgets import QSpinBox

        self.s_quick_count = QSpinBox()
        self.s_quick_count.setRange(1, 10)
        self.s_quick_count.setValue(self.prefs.tray_quick_count)
        self.s_quick_count.setToolTip("How many recent games to list.")
        form.addRow("Recent games:", self.s_quick_count)
        self._update_tray_state()

        from PySide6.QtWidgets import QLineEdit

        self.e_sgdb = QLineEdit(self.prefs.sgdb_api_key)
        self.e_sgdb.setEchoMode(QLineEdit.EchoMode.Password)
        self.e_sgdb.setPlaceholderText("Free key from steamgriddb.com")
        self.e_sgdb.setToolTip("SteamGridDB API key for missing artwork fallback.")
        form.addRow("SteamGridDB key:", self.e_sgdb)

        btns = QDialogButtonBox(QDialogButtonBox.Save | QDialogButtonBox.Cancel)
        btns.accepted.connect(self.accept)
        btns.rejected.connect(self.reject)
        layout.addWidget(btns)

    def _update_tray_state(self) -> None:
        on = self.c_tray.isChecked()
        for widget in (self.cb_tray_icon, self.c_minimize, self.c_close):
            widget.setEnabled(on)
        self.s_quick_count.setEnabled(on and self.c_quick.isChecked())

    def accept(self) -> None:
        self.prefs.show_preview = self.c_show_preview.isChecked()
        self.prefs.tray_enable = self.c_tray.isChecked()
        self.prefs.tray_icon = str(self.cb_tray_icon.currentData() or "normal")
        self.prefs.minimize_to_tray = self.c_minimize.isChecked() and self.c_tray.isChecked()
        self.prefs.close_to_tray = self.c_close.isChecked() and self.c_tray.isChecked()
        self.prefs.sgdb_api_key = self.e_sgdb.text().strip()
        self.prefs.tray_quick_launch = self.c_quick.isChecked() and self.c_tray.isChecked()
        self.prefs.tray_quick_count = int(self.s_quick_count.value())
        cfgmod.save_preferences(self.prefs)
        super().accept()
