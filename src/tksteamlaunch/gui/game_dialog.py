"""Game editor dialog with tabs. Also used for global defaults."""
from __future__ import annotations

import shutil

from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QSpinBox,
    QTabWidget,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from .. import config as cfgmod
from .. import xdg
from ..backends import overlay as ov_backend
from .helpers import open_path


def _env_to_text(vars: dict[str, str]) -> str:
    return "\n".join(f"{k}={v}" for k, v in vars.items())


def _text_to_env(text: str) -> dict[str, str]:
    out: dict[str, str] = {}
    for line in text.splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        k = k.strip()
        if k:
            out[k] = v
    return out


class BulkEnvDialog(QDialog):
    """Bulk-edit environment variables as KEY=VALUE text."""

    def __init__(self, parent, text: str) -> None:
        super().__init__(parent)
        self.setWindowTitle("Bulk Edit Environment Variables")
        self.resize(480, 360)
        layout = QVBoxLayout(self)
        layout.addWidget(QLabel("One VARIABLE=value per line; lines starting with # are ignored."))
        self.edit = QPlainTextEdit(text)
        self.edit.setPlaceholderText("ONE=1\nTWO=2")
        layout.addWidget(self.edit, stretch=1)
        btns = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        btns.accepted.connect(self.accept)
        btns.rejected.connect(self.reject)
        layout.addWidget(btns)

    def text(self) -> str:
        return self.edit.toPlainText()


class GameDialog(QDialog):
    def __init__(self, parent, appid: str = "", name: str = "", defaults_mode: bool = False) -> None:
        super().__init__(parent)
        self.defaults_mode = defaults_mode
        self.appid = appid
        if defaults_mode:
            self.setWindowTitle("Global Defaults")
            self.cfg = cfgmod.load_defaults()
        else:
            self.setWindowTitle(f"Game Settings — {name} ({appid})" if name else f"Game Settings ({appid})")
            self.cfg = cfgmod.load(appid)
        self.resize(680, 560)

        layout = QVBoxLayout(self)
        if defaults_mode:
            layout.addWidget(QLabel("These settings apply to all games unless overridden per game."))

        tabs = QTabWidget()
        layout.addWidget(tabs, stretch=1)

        # --- General ---
        g = QWidget()
        gf = QFormLayout(g)
        if not defaults_mode:
            self.e_appid = QLineEdit(self.cfg.general.appid)
            self.e_appid.setReadOnly(True)
            gf.addRow("Steam App ID:", self.e_appid)
        self.cb_gametype = QComboBox()
        self.cb_gametype.addItems(["auto", "proton", "native"])
        self.cb_gametype.setToolTip("Auto detects Proton versus native Linux games.")
        gf.addRow("Game Type:", self.cb_gametype)
        self.e_exe = QLineEdit()
        self.e_exe.setPlaceholderText("Optional replacement executable for this game")
        gf.addRow("Custom Executable:", self.e_exe)
        env_box = QWidget()
        env_layout = QVBoxLayout(env_box)
        env_layout.setContentsMargins(0, 0, 0, 0)
        self.t_env = QTableWidget(0, 2)
        self.t_env.setHorizontalHeaderLabels(["Variable", "Value"])
        self.t_env.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        env_layout.addWidget(self.t_env)
        env_btns = QHBoxLayout()
        b_add = QPushButton("Add")
        b_add.clicked.connect(lambda: self.t_env.insertRow(self.t_env.rowCount()))
        b_del = QPushButton("Remove")
        b_del.clicked.connect(self._remove_env_row)
        b_bulk = QPushButton("Bulk Edit...")
        b_bulk.clicked.connect(self._bulk_edit_env)
        env_btns.addWidget(b_add)
        env_btns.addWidget(b_del)
        env_btns.addWidget(b_bulk)
        env_btns.addStretch(1)
        env_layout.addLayout(env_btns)
        gf.addRow("Environment Variables:", env_box)
        if not defaults_mode:
            log_row = QWidget()
            log_layout = QHBoxLayout(log_row)
            log_layout.setContentsMargins(0, 0, 0, 0)
            self.e_log = QLineEdit()
            self.e_log.setReadOnly(True)
            self.b_log = QPushButton("Open")
            self.b_log.clicked.connect(self._open_log)
            log_layout.addWidget(self.e_log, stretch=1)
            log_layout.addWidget(self.b_log)
            gf.addRow("Log File:", log_row)
        tabs.addTab(g, "General")

        # --- Pre/Post Commands ---
        pp = QWidget()
        pf = QFormLayout(pp)
        self.e_pre = QLineEdit()
        self.e_pre_args = QLineEdit()
        self.e_post = QLineEdit()
        self.e_post_args = QLineEdit()
        self.s_timeout = QSpinBox()
        self.s_timeout.setRange(1, 3600)
        self.c_shell = QCheckBox("Run in shell (bash -c)")
        pf.addRow("Pre-Launch Command:", self.e_pre)
        pf.addRow("Pre-Launch Arguments:", self.e_pre_args)
        pf.addRow("Post-Exit Command:", self.e_post)
        pf.addRow("Post-Exit Arguments:", self.e_post_args)
        pf.addRow("Timeout (seconds):", self.s_timeout)
        pf.addRow("", self.c_shell)
        tabs.addTab(pp, "Pre/Post Commands")

        # --- Performance ---
        perf = QWidget()
        ff = QFormLayout(perf)
        self.c_feral = QCheckBox("Enable Feral GameMode (gamemoderun)")
        self.c_feral.setToolTip("Optimizes CPU and GPU governors while the game runs.")
        self.c_cachy = QCheckBox("Enable CachyOS game-performance")
        self.c_cachy.setToolTip("Applies the CachyOS gaming performance profile.")
        ff.addRow("", self.c_feral)
        ff.addRow("", self.c_cachy)
        ff.addRow(QLabel(self._which_hint()))
        tabs.addTab(perf, "Performance")

        # --- Gamescope & MangoHud ---
        ov = QWidget()
        of = QFormLayout(ov)
        self.c_gs = QCheckBox("Enable Gamescope")
        self.e_gs_args = QLineEdit()
        self.e_gs_args.setPlaceholderText("-f -H 1080 -r 144")
        self.c_mh = QCheckBox("Enable MangoHud")
        self.e_mh_args = QLineEdit()
        self.cb_mh_conf = QComboBox()
        self.cb_mh_conf.setToolTip("Sets MANGOHUD_CONFIGFILE for the game.")
        mh_conf_row = QWidget()
        mh_conf_layout = QHBoxLayout(mh_conf_row)
        mh_conf_layout.setContentsMargins(0, 0, 0, 0)
        b_mh_new = QPushButton("New Configuration...")
        b_mh_new.clicked.connect(self._new_mangohud_config)
        mh_conf_layout.addWidget(self.cb_mh_conf, stretch=1)
        mh_conf_layout.addWidget(b_mh_new)
        of.addRow("", self.c_gs)
        of.addRow("Gamescope Options:", self.e_gs_args)
        of.addRow("", self.c_mh)
        of.addRow("MangoHud Options:", self.e_mh_args)
        of.addRow("MangoHud Configuration:", mh_conf_row)
        tabs.addTab(ov, "Gamescope & MangoHud")

        # --- Ludusavi ---
        lu = QWidget()
        lf = QFormLayout(lu)
        self.c_lu_enable = QCheckBox("Enable Ludusavi for this game")
        self.c_lu_enable.toggled.connect(self._update_lu_state)
        self.c_restore = QCheckBox("Restore backup before launch")
        self.c_restore.setToolTip("Unchecked = --no-restore")
        self.c_backup = QCheckBox("Back up after exit")
        self.c_backup.setToolTip("Unchecked = --no-backup")
        self.e_luname = QLineEdit()
        self.e_luname.setPlaceholderText("Leave empty to detect the game from Steam")
        self.c_lugui = QCheckBox("Show Prompts (--gui)")
        self.c_lugui.setToolTip("With prompts enabled, restore and backup can be declined per session.")
        lf.addRow("", self.c_lu_enable)
        lf.addRow("", self.c_restore)
        lf.addRow("", self.c_backup)
        lf.addRow("Game Name Override:", self.e_luname)
        lf.addRow("", self.c_lugui)
        self.l_lu_note = QLabel("With prompts enabled, restore and backup can be declined per session.")
        self.l_lu_note.setWordWrap(True)
        lf.addRow(self.l_lu_note)
        lf.addRow(QLabel(self._ludusavi_hint()))
        tabs.addTab(lu, "Ludusavi")

        # --- Night Light ---
        nl = QWidget()
        nf = QFormLayout(nl)
        self.c_nl = QCheckBox("Disable while the game is running (restored on exit)")
        self.cb_nl = QComboBox()
        self.cb_nl.addItems(["auto", "kde", "gnome", "off"])
        nf.addRow("", self.c_nl)
        nf.addRow("Provider:", self.cb_nl)
        tabs.addTab(nl, "Night Light")

        if defaults_mode:
            btns = QDialogButtonBox(QDialogButtonBox.Save | QDialogButtonBox.Cancel)
        else:
            btns = QDialogButtonBox(
                QDialogButtonBox.Save | QDialogButtonBox.Cancel | QDialogButtonBox.Reset
            )
            btns.button(QDialogButtonBox.Reset).setText("Reset to Global Defaults")
            btns.button(QDialogButtonBox.Reset).clicked.connect(self._on_reset)
        btns.accepted.connect(self.accept)
        btns.rejected.connect(self.reject)
        layout.addWidget(btns)

        self._populate()

    def _populate(self) -> None:
        c = self.cfg
        self.cb_gametype.setCurrentText(c.general.game_type or "auto")
        self.e_exe.setText(c.general.custom_executable)
        self._set_env_table(c.env.vars)
        if not self.defaults_mode:
            log_path = str(xdg.game_log_file(self.appid))
            self.e_log.setText(log_path)
            import os

            self.b_log.setEnabled(os.path.exists(log_path))
        self.e_pre.setText(c.pre_post.pre_command)
        self.e_pre_args.setText(" ".join(c.pre_post.pre_args))
        self.e_post.setText(c.pre_post.post_command)
        self.e_post_args.setText(" ".join(c.pre_post.post_args))
        self.s_timeout.setValue(c.pre_post.timeout)
        self.c_shell.setChecked(c.pre_post.run_in_shell)
        self.c_feral.setChecked(c.gamemode.feral_gamemode)
        self.c_cachy.setChecked(c.gamemode.cachyos_game_performance)
        self.c_gs.setChecked(c.gamescope.enable)
        self.e_gs_args.setText(c.gamescope.args)
        self.c_mh.setChecked(c.mangohud.enable)
        self.e_mh_args.setText(c.mangohud.args)
        self._refresh_mangohud_configs()
        self.c_lu_enable.setChecked(c.ludusavi.enable)
        self.c_restore.setChecked(c.ludusavi.restore)
        self.c_backup.setChecked(c.ludusavi.backup)
        self.e_luname.setText(c.ludusavi.name_override)
        self.c_lugui.setChecked(c.ludusavi.use_gui)
        self._update_lu_state()
        self.c_nl.setChecked(c.nightlight.disable_during_game)
        self.cb_nl.setCurrentText(c.nightlight.provider or "auto")

    def _set_env_table(self, vars: dict[str, str]) -> None:
        self.t_env.setRowCount(0)
        for k, v in vars.items():
            row = self.t_env.rowCount()
            self.t_env.insertRow(row)
            self.t_env.setItem(row, 0, QTableWidgetItem(k))
            self.t_env.setItem(row, 1, QTableWidgetItem(v))

    def _table_to_env(self) -> dict[str, str]:
        out: dict[str, str] = {}
        for row in range(self.t_env.rowCount()):
            ki = self.t_env.item(row, 0)
            vi = self.t_env.item(row, 1)
            k = (ki.text() if ki else "").strip()
            if k:
                out[k] = vi.text() if vi else ""
        return out

    def _remove_env_row(self) -> None:
        row = self.t_env.currentRow()
        if row >= 0:
            self.t_env.removeRow(row)

    def _bulk_edit_env(self) -> None:
        dlg = BulkEnvDialog(self, _env_to_text(self._table_to_env()))
        if dlg.exec():
            self._set_env_table(_text_to_env(dlg.text()))

    def _refresh_mangohud_configs(self) -> None:
        current = self.cfg.mangohud.config_file
        self.cb_mh_conf.clear()
        self.cb_mh_conf.addItem("Default (MangoHud.conf)", "")
        for name in ov_backend.list_mangohud_configs():
            if name == ov_backend.DEFAULT_MANGOHUD_CONF:
                continue
            self.cb_mh_conf.addItem(name, name)
        idx = self.cb_mh_conf.findData(current)
        self.cb_mh_conf.setCurrentIndex(idx if idx >= 0 else 0)

    def _new_mangohud_config(self) -> None:
        from PySide6.QtWidgets import QInputDialog

        d = ov_backend.mangohud_config_dir()
        try:
            d.mkdir(parents=True, exist_ok=True)
        except Exception as e:  # noqa: BLE001
            QMessageBox.warning(self, "TKSteamLaunch", f"Could not create {d}: {e}")
            return
        name, ok = QInputDialog.getText(self, "New MangoHud Configuration", "File name:")
        if not ok or not name.strip():
            return
        name = name.strip()
        if not name.endswith(".conf"):
            name += ".conf"
        path = d / name
        if path.exists():
            QMessageBox.information(self, "TKSteamLaunch", f"{name} already exists.")
        else:
            try:
                path.write_text("# MangoHud configuration\n", encoding="utf-8")
            except Exception as e:  # noqa: BLE001
                QMessageBox.warning(self, "TKSteamLaunch", f"Could not write {path}: {e}")
                return
        self._refresh_mangohud_configs()
        idx = self.cb_mh_conf.findData(name)
        if idx >= 0:
            self.cb_mh_conf.setCurrentIndex(idx)
        if not open_path(str(path)):
            QMessageBox.warning(self, "TKSteamLaunch", f"Could not open {path}.")

    def _open_log(self) -> None:
        if not open_path(self.e_log.text()):
            QMessageBox.warning(self, "TKSteamLaunch", "Could not open the log file.")

    def _on_reset(self) -> None:
        r = QMessageBox.question(
            self, "TKSteamLaunch",
            "Delete all per-game settings and use the global defaults instead?",
        )
        if r != QMessageBox.StandardButton.Yes:
            return
        cfgmod.reset_game_to_defaults(self.appid)
        self.cfg = cfgmod.load(self.appid)
        self._populate()

    def _update_lu_state(self) -> None:
        on = self.c_lu_enable.isChecked()
        for w in (self.c_restore, self.c_backup, self.e_luname,
                  self.c_lugui, self.l_lu_note):
            w.setEnabled(on)

    def _which_hint(self) -> str:
        found, missing = [], []
        for b in ("gamemoderun", "game-performance", "gamescope", "mangohud"):
            (found if shutil.which(b) else missing).append(b)
        parts = []
        if found:
            parts.append("Found: " + ", ".join(found))
        if missing:
            parts.append("Missing: " + ", ".join(missing))
        return " · ".join(parts) if parts else ""

    def _ludusavi_hint(self) -> str:
        exe = shutil.which("ludusavi")
        if not exe:
            return "Ludusavi: not found in PATH"
        if "/flatpak/" in exe or "flatpak" in exe:
            return f"Ludusavi: {exe} (Flatpak: prefer standalone)"
        return f"Ludusavi: {exe}"

    def _collect(self) -> None:
        import shlex

        self.cfg.general.game_type = self.cb_gametype.currentText()
        self.cfg.general.custom_executable = self.e_exe.text().strip()
        self.cfg.env.vars = self._table_to_env()
        self.cfg.pre_post.pre_command = self.e_pre.text().strip()
        self.cfg.pre_post.pre_args = shlex.split(self.e_pre_args.text()) if self.e_pre_args.text().strip() else []
        self.cfg.pre_post.post_command = self.e_post.text().strip()
        self.cfg.pre_post.post_args = shlex.split(self.e_post_args.text()) if self.e_post_args.text().strip() else []
        self.cfg.pre_post.timeout = int(self.s_timeout.value())
        self.cfg.pre_post.run_in_shell = bool(self.c_shell.isChecked())
        self.cfg.gamemode.feral_gamemode = self.c_feral.isChecked()
        self.cfg.gamemode.cachyos_game_performance = self.c_cachy.isChecked()
        self.cfg.gamescope.enable = self.c_gs.isChecked()
        self.cfg.gamescope.args = self.e_gs_args.text().strip()
        self.cfg.mangohud.enable = self.c_mh.isChecked()
        self.cfg.mangohud.args = self.e_mh_args.text().strip()
        self.cfg.mangohud.config_file = str(self.cb_mh_conf.currentData() or "")
        self.cfg.ludusavi.enable = self.c_lu_enable.isChecked()
        self.cfg.ludusavi.restore = self.c_restore.isChecked()
        self.cfg.ludusavi.backup = self.c_backup.isChecked()
        self.cfg.ludusavi.name_override = self.e_luname.text().strip()
        self.cfg.ludusavi.use_gui = self.c_lugui.isChecked()
        self.cfg.nightlight.disable_during_game = self.c_nl.isChecked()
        self.cfg.nightlight.provider = self.cb_nl.currentText()

    def accept(self) -> None:
        self._collect()
        if self.defaults_mode:
            cfgmod.save_defaults(self.cfg)
        else:
            cfgmod.save(self.cfg)
        super().accept()
