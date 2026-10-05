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
        self.setWindowTitle(self.tr("Preferences"))
        self.resize(420, 280)
        self.prefs = cfgmod.load_preferences()

        layout = QVBoxLayout(self)
        form = QFormLayout()
        layout.addLayout(form)

        self.c_show_preview = QCheckBox(self.tr("Show launch command preview"))
        self.c_show_preview.setToolTip(self.tr("Live preview box at the bottom of game dialogs."))
        self.c_show_preview.setChecked(self.prefs.show_preview)
        form.addRow("", self.c_show_preview)

        self.c_tray = QCheckBox(self.tr("Enable status bar icon"))
        self.c_tray.setToolTip(self.tr("Keep TKSteamLaunch in the system tray."))
        self.c_tray.setChecked(self.prefs.tray_enable)
        self.c_tray.toggled.connect(self._update_tray_state)
        form.addRow("", self.c_tray)

        self.cb_tray_icon = QComboBox()
        self.cb_tray_icon.addItem(self.tr("Normal"), "normal")
        self.cb_tray_icon.addItem(self.tr("Monochrome"), "mono")
        self.cb_tray_icon.setCurrentIndex(0 if self.prefs.tray_icon == "normal" else 1)
        form.addRow(self.tr("Tray icon style:"), self.cb_tray_icon)

        self.c_minimize = QCheckBox(self.tr("Minimize to tray"))
        self.c_minimize.setChecked(self.prefs.minimize_to_tray)
        form.addRow("", self.c_minimize)

        self.c_close = QCheckBox(self.tr("Close to tray"))
        self.c_close.setChecked(self.prefs.close_to_tray)
        form.addRow("", self.c_close)

        self.c_quick = QCheckBox(self.tr("Show recent games in tray menu"))
        self.c_quick.setToolTip(self.tr("Launch recent games through Steam (steam:// URL)."))
        self.c_quick.setChecked(self.prefs.tray_quick_launch)
        self.c_quick.toggled.connect(self._update_tray_state)
        form.addRow("", self.c_quick)

        from PySide6.QtWidgets import QSpinBox

        self.s_quick_count = QSpinBox()
        self.s_quick_count.setRange(1, 10)
        self.s_quick_count.setValue(self.prefs.tray_quick_count)
        self.s_quick_count.setToolTip(self.tr("How many recent games to list."))
        form.addRow(self.tr("Recent games:"), self.s_quick_count)
        self._update_tray_state()

        from PySide6.QtWidgets import QLineEdit

        self.e_sgdb = QLineEdit(self.prefs.sgdb_api_key)
        self.e_sgdb.setEchoMode(QLineEdit.EchoMode.Password)
        self.e_sgdb.setPlaceholderText(self.tr("Free key from steamgriddb.com"))
        self.e_sgdb.setToolTip(self.tr("SteamGridDB API key for missing artwork fallback."))
        form.addRow(self.tr("SteamGridDB key:"), self.e_sgdb)

        from .helpers import available_languages

        self.cb_lang = QComboBox()
        self.cb_lang.addItem(self.tr("System default"), "system")
        for code, label in available_languages():
            self.cb_lang.addItem(label, code)
        idx = self.cb_lang.findData(self.prefs.language or "system")
        self.cb_lang.setCurrentIndex(max(idx, 0))
        self.cb_lang.setToolTip(self.tr("Takes effect on restart."))
        form.addRow(self.tr("Language:"), self.cb_lang)

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
        self.prefs.language = str(self.cb_lang.currentData() or "system")
        cfgmod.save_preferences(self.prefs)
        super().accept()
