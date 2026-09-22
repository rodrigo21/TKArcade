"""Game editor dialog with tabs."""
from __future__ import annotations

import shutil

from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QLabel,
    QLineEdit,
    QPlainTextEdit,
    QSpinBox,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from .. import config as cfgmod


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


class GameDialog(QDialog):
    def __init__(self, parent, appid: str) -> None:
        super().__init__(parent)
        self.setWindowTitle(f"Game {appid}")
        self.resize(640, 520)
        self.cfg = cfgmod.load(appid)

        layout = QVBoxLayout(self)
        tabs = QTabWidget()
        layout.addWidget(tabs, stretch=1)

        # --- General ---
        g = QWidget()
        gf = QFormLayout(g)
        self.e_appid = QLineEdit(self.cfg.general.appid)
        self.e_appid.setReadOnly(True)
        self.e_exe = QLineEdit(self.cfg.general.custom_executable)
        self.e_exe.setPlaceholderText("/.../game.exe (swap inside the Proton prefix)")
        gf.addRow("AppID:", self.e_appid)
        gf.addRow("Custom exe:", self.e_exe)
        self.e_env = QPlainTextEdit(_env_to_text(self.cfg.env.vars))
        self.e_env.setPlaceholderText("KEY=VALUE (one per line)")
        gf.addRow("Env vars:", self.e_env)
        tabs.addTab(g, "General/Env")

        # --- Pre/Post ---
        pp = QWidget()
        pf = QFormLayout(pp)
        self.e_pre = QLineEdit(self.cfg.pre_post.pre_command)
        self.e_pre_args = QLineEdit(" ".join(self.cfg.pre_post.pre_args))
        self.e_post = QLineEdit(self.cfg.pre_post.post_command)
        self.e_post_args = QLineEdit(" ".join(self.cfg.pre_post.post_args))
        self.s_timeout = QSpinBox()
        self.s_timeout.setRange(1, 3600)
        self.s_timeout.setValue(self.cfg.pre_post.timeout)
        self.c_shell = QCheckBox("run in shell (bash -c)")
        self.c_shell.setChecked(self.cfg.pre_post.run_in_shell)
        pf.addRow("Pre command:", self.e_pre)
        pf.addRow("Pre args:", self.e_pre_args)
        pf.addRow("Post command:", self.e_post)
        pf.addRow("Post args:", self.e_post_args)
        pf.addRow("Timeout (s):", self.s_timeout)
        pf.addRow("", self.c_shell)
        tabs.addTab(pp, "Pre/Post")

        # --- Performance ---
        perf = QWidget()
        ff = QFormLayout(perf)
        self.c_feral = QCheckBox("gamemoderun (Feral GameMode)")
        self.c_feral.setChecked(self.cfg.gamemode.feral_gamemode)
        self.c_cachy = QCheckBox("game-performance (CachyOS)")
        self.c_cachy.setChecked(self.cfg.gamemode.cachyos_game_performance)
        ff.addRow("", self.c_feral)
        ff.addRow("", self.c_cachy)
        ff.addRow(QLabel(self._which_hint()))
        tabs.addTab(perf, "Performance")

        # --- Overlay ---
        ov = QWidget()
        of = QFormLayout(ov)
        self.c_gs = QCheckBox("gamescope")
        self.c_gs.setChecked(self.cfg.gamescope.enable)
        self.e_gs_args = QLineEdit(self.cfg.gamescope.args)
        self.e_gs_args.setPlaceholderText("-f -H 1080 -r 144")
        self.c_mh = QCheckBox("mangohud")
        self.c_mh.setChecked(self.cfg.mangohud.enable)
        self.e_mh_args = QLineEdit(self.cfg.mangohud.args)
        of.addRow("", self.c_gs)
        of.addRow("gamescope args:", self.e_gs_args)
        of.addRow("", self.c_mh)
        of.addRow("mangohud args:", self.e_mh_args)
        tabs.addTab(ov, "Gamescope/MangoHud")

        # --- Ludusavi ---
        lu = QWidget()
        lf = QFormLayout(lu)
        self.c_lu_enable = QCheckBox("Enable ludusavi for this game")
        self.c_lu_enable.setChecked(self.cfg.ludusavi.enable)
        self.c_lu_enable.toggled.connect(self._update_lu_state)
        self.c_restore = QCheckBox("Restore before launch")
        self.c_restore.setChecked(self.cfg.ludusavi.restore)
        self.c_restore.setToolTip("Unchecked = --no-restore")
        self.c_backup = QCheckBox("Backup after exit")
        self.c_backup.setChecked(self.cfg.ludusavi.backup)
        self.c_backup.setToolTip("Unchecked = --no-backup")
        self.e_luname = QLineEdit(self.cfg.ludusavi.name_override)
        self.e_luname.setPlaceholderText("empty = --infer steam")
        self.c_lugui = QCheckBox("Use --gui notifications")
        self.c_lugui.setChecked(self.cfg.ludusavi.use_gui)
        self.c_lugui.setToolTip("With --gui you can decline restore/backup per session")
        lf.addRow("", self.c_lu_enable)
        lf.addRow("", self.c_restore)
        lf.addRow("", self.c_backup)
        lf.addRow("Alt. name:", self.e_luname)
        lf.addRow("", self.c_lugui)
        self.l_lu_note = QLabel("With --gui, restore/backup can be declined per session.")
        lf.addRow(self.l_lu_note)
        lf.addRow(QLabel(self._ludusavi_hint()))
        tabs.addTab(lu, "Ludusavi")
        self._update_lu_state()

        # --- Nightlight ---
        nl = QWidget()
        nf = QFormLayout(nl)
        self.c_nl = QCheckBox("disable during the game (restored afterwards)")
        self.c_nl.setChecked(self.cfg.nightlight.disable_during_game)
        self.cb_nl = QComboBox()
        self.cb_nl.addItems(["auto", "kde", "gnome", "off"])
        self.cb_nl.setCurrentText(self.cfg.nightlight.provider or "auto")
        nf.addRow("", self.c_nl)
        nf.addRow("Provider:", self.cb_nl)
        tabs.addTab(nl, "Night Light")

        btns = QDialogButtonBox(QDialogButtonBox.Save | QDialogButtonBox.Cancel)
        btns.accepted.connect(self.accept)
        btns.rejected.connect(self.reject)
        layout.addWidget(btns)

    def _update_lu_state(self) -> None:
        on = self.c_lu_enable.isChecked()
        for w in (self.c_restore, self.c_backup, self.e_luname,
                  self.c_lugui, self.l_lu_note):
            w.setEnabled(on)

    def _which_hint(self) -> str:
        parts = []
        for b in ("gamemoderun", "game-performance", "gamescope", "mangohud"):
            parts.append(f"{b}: {'OK' if shutil.which(b) else 'missing'}")
        return "  ·  ".join(parts)

    def _ludusavi_hint(self) -> str:
        exe = shutil.which("ludusavi")
        if not exe:
            return "ludusavi: missing in PATH"
        if "/flatpak/" in exe or "flatpak" in exe:
            return f"ludusavi: {exe} (Flatpak: prefer standalone)"
        return f"ludusavi: {exe}"

    def accept(self) -> None:
        import shlex

        self.cfg.general.custom_executable = self.e_exe.text().strip()
        self.cfg.env.vars = _text_to_env(self.e_env.toPlainText())
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
        self.cfg.ludusavi.enable = self.c_lu_enable.isChecked()
        self.cfg.ludusavi.restore = self.c_restore.isChecked()
        self.cfg.ludusavi.backup = self.c_backup.isChecked()
        self.cfg.ludusavi.name_override = self.e_luname.text().strip()
        self.cfg.ludusavi.use_gui = self.c_lugui.isChecked()
        self.cfg.nightlight.disable_during_game = self.c_nl.isChecked()
        self.cfg.nightlight.provider = self.cb_nl.currentText()
        cfgmod.save(self.cfg)
        super().accept()
