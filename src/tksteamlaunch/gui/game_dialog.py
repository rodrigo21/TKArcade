"""Game editor dialog with tabs. Also used for global defaults."""

from __future__ import annotations

import os
import shlex
import shutil

from PySide6.QtCore import Qt, QThread, Signal
from PySide6.QtGui import QFontDatabase
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QFrame,
    QGroupBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QSpinBox,
    QStyle,
    QTableWidget,
    QTableWidgetItem,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from .. import config as cfgmod
from .. import proton as protonmod
from .. import xdg
from ..backends import ludusavi as lu_backend
from ..backends import overlay as ov_backend
from ..backends import split_args
from ..config import NightlightProvider
from .helpers import open_path

_STATUS_COLORS_DARK = {"ok": "#7ee787", "warn": "#f47067", "note": "#e3b341"}
_STATUS_COLORS_LIGHT = {"ok": "#1a7f37", "warn": "#d1242f", "note": "#9a6700"}
_STATUS_MARKS = {"ok": "✓", "warn": "⚠", "note": "●"}


def _is_dark_theme(widget: QWidget) -> bool:
    """Detect a dark theme from the window background lightness."""
    try:
        return widget.palette().window().color().lightness() < 128
    except Exception:
        return False


def _binary_status(
    name: str, enabled: bool, skip_note: str = "skipped at launch"
) -> tuple[str, str]:
    """Return (kind, text); a missing binary is only an error when enabled."""
    path = shutil.which(name)
    if path:
        if enabled:
            return "ok", f"{name} — {path}"
        return "ok", f"{name} — {path} (off)"
    if enabled:
        return "warn", f"{name} not found in PATH — {skip_note}"
    return "note", f"{name} not installed (feature off)"


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


class _CoverageWorker(QThread):
    """Run the (potentially slow) Ludusavi coverage check off the UI thread."""

    done = Signal(str, str)

    def __init__(self, appid: str, name_override: str, parent=None) -> None:
        super().__init__(parent)
        self._appid = appid
        self._override = name_override

    def run(self) -> None:
        try:
            status, detail = lu_backend.check_coverage(self._appid, self._override)
        except Exception as e:  # never kill the dialog from the worker
            status, detail = "unavailable", f"coverage check failed: {e}"
        if not self.isInterruptionRequested():
            self.done.emit(status, detail)


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
    def __init__(
        self,
        parent,
        appid: str = "",
        name: str = "",
        defaults_mode: bool = False,
        launch_mode: bool = False,
        can_launch: bool = True,
    ) -> None:
        super().__init__(parent)
        self.defaults_mode = defaults_mode
        self.launch_mode = launch_mode and not defaults_mode
        self.can_launch = can_launch
        self.launch_requested = False
        self._skip_save = False
        self._orig_tips: dict = {}
        self._cov_thread: _CoverageWorker | None = None
        self._cov_run = 0
        self.appid = appid
        if defaults_mode:
            self.setWindowTitle("Global Defaults")
            self.cfg = cfgmod.load_defaults()
        else:
            self.setWindowTitle(
                f"Game Settings — {name} ({appid})" if name else f"Game Settings ({appid})"
            )
            if cfgmod.game_file(appid).exists():
                self.cfg = cfgmod.load(appid)
            else:
                # New game: start from a snapshot of the global defaults.
                self.cfg = cfgmod.load_defaults()
                self.cfg.general.appid = appid
        self.resize(680, 640)
        self._dark = _is_dark_theme(self)
        self._status_labels: dict[str, QLabel] = {}
        self._active_profile = ""

        layout = QVBoxLayout(self)
        if defaults_mode:
            layout.addWidget(QLabel("Template for new games. Existing games keep their own copy."))

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
        if not defaults_mode:
            self.e_runtime = QLineEdit()
            self.e_runtime.setReadOnly(True)
            self.e_runtime.setToolTip("Proton tool and version from your Steam config (read-only).")
            gf.addRow("Detected Runtime:", self.e_runtime)
        self.e_exe = QLineEdit()
        self.e_exe.setPlaceholderText("Optional replacement executable for this game")
        gf.addRow("Custom Executable:", self.e_exe)
        self.e_prefix = QLineEdit()
        self.e_prefix.setPlaceholderText("e.g. zink-run")
        self.e_prefix.setToolTip(
            "Command prefix wrapping the game directly, inside MangoHud, "
            "GameMode, Gamescope and Ludusavi."
        )
        gf.addRow("Custom Command Prefix:", self.e_prefix)
        self.e_prefix.textChanged.connect(self._update_prefix_status)
        self.c_show_menu = QCheckBox("Show menu before launch")
        self.c_show_menu.setToolTip(
            "Show the pre-launch menu (Launch / Settings / Cancel) "
            "on every Steam start. Also forced by the --menu flag."
        )
        gf.addRow("", self.c_show_menu)
        self.c_notify = QCheckBox("Notify on launch")
        self.c_notify.setToolTip("Show a transient summary notification when the game starts.")
        gf.addRow("", self.c_notify)
        self.c_inhibit = QCheckBox("Inhibit idle suspend while playing")
        self.c_inhibit.setToolTip(
            "Holds a logind idle lock during the session. Sleep lock is not "
            "included (needs privileges)."
        )
        gf.addRow("", self.c_inhibit)
        if not defaults_mode:
            self.cb_profile = QComboBox()
            self.cb_profile.setToolTip("Switching loads the profile (Save writes it).")
            self.cb_profile.currentIndexChanged.connect(self._on_profile_switch)
            b_prof_save = QPushButton("Save As...")
            b_prof_save.clicked.connect(self._on_profile_save)
            b_prof_delete = QPushButton("Delete")
            b_prof_delete.clicked.connect(self._on_profile_delete)
            prof_row = QWidget()
            prof_layout = QHBoxLayout(prof_row)
            prof_layout.setContentsMargins(0, 0, 0, 0)
            prof_layout.addWidget(self.cb_profile, stretch=1)
            prof_layout.addWidget(b_prof_save)
            prof_layout.addWidget(b_prof_delete)
            gf.addRow("Profile:", prof_row)
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
        b_preset = QPushButton("Add Preset...")
        b_preset.setToolTip("Merge a curated env preset (only missing keys).")
        b_preset.clicked.connect(self._add_env_preset)
        env_btns.addWidget(b_add)
        env_btns.addWidget(b_del)
        env_btns.addWidget(b_bulk)
        env_btns.addWidget(b_preset)
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
            self.c_protonlog = QCheckBox("Capture Proton log (disk-heavy)")
            self.c_protonlog.setToolTip("Sets PROTON_LOG=1 with a per-game log dir (Proton only).")
            self.b_protonlog = QPushButton("Open")
            self.b_protonlog.clicked.connect(self._open_proton_log)
            proton_row = QWidget()
            proton_layout = QHBoxLayout(proton_row)
            proton_layout.setContentsMargins(0, 0, 0, 0)
            proton_layout.addWidget(self.c_protonlog, stretch=1)
            proton_layout.addWidget(self.b_protonlog)
            gf.addRow("", proton_row)
            self.cb_winedebug = QComboBox()
            self.cb_winedebug.addItem("Off", "")
            self.cb_winedebug.addItem("Quiet (-all)", "-all")
            self.cb_winedebug.addItem("Errors (+err)", "+err")
            self.cb_winedebug.addItem("Warnings (+warn,+err)", "+warn,+err")
            self.cb_winedebug.setToolTip("Sets WINEDEBUG for Wine/Proton output.")
            gf.addRow("Wine Debug:", self.cb_winedebug)
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

        # --- Performance: system + display/overlay sections ---
        perf = QWidget()
        perf_layout = QVBoxLayout(perf)
        perf_layout.setContentsMargins(0, 0, 0, 0)
        sys_box = QGroupBox("System")
        ff = QFormLayout(sys_box)
        self.c_feral = QCheckBox("Enable Feral GameMode (gamemoderun)")
        self.c_feral.setToolTip(
            "Optimizes CPU and GPU governors while the game runs. "
            "Mutually exclusive with CachyOS game-performance."
        )
        self.c_cachy = QCheckBox("Enable CachyOS game-performance")
        self.c_cachy.setToolTip(
            "Applies the CachyOS gaming performance profile. "
            "Mutually exclusive with Feral GameMode."
        )
        self.l_feral_pad = QLabel()
        self.l_cachy_pad = QLabel()
        self.c_feral.toggled.connect(self._on_gamemode_exclusive)
        self.c_cachy.toggled.connect(self._on_gamemode_exclusive)
        ff.addRow(self.l_feral_pad, self.c_feral)
        ff.addRow(self.l_cachy_pad, self.c_cachy)
        perf_layout.addWidget(sys_box)

        gs_box = QGroupBox("Gamescope")
        gf = QFormLayout(gs_box)
        self.c_gs = QCheckBox("Enable Gamescope")
        self.e_gs_args = QLineEdit()
        self.e_gs_args.setPlaceholderText("-f -H 1080 -r 144")
        self.l_gs_args = QLabel("Gamescope Options:")
        self.l_gs_args.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        gs_args_row = QWidget()
        gs_args_layout = QHBoxLayout(gs_args_row)
        gs_args_layout.setContentsMargins(0, 0, 0, 0)
        b_gs_preset = QPushButton("Preset...")
        b_gs_preset.setToolTip("Fill in a starter Gamescope option set.")
        b_gs_preset.clicked.connect(self._apply_gamescope_preset)
        gs_args_layout.addWidget(self.e_gs_args, stretch=1)
        gs_args_layout.addWidget(b_gs_preset)
        gf.addRow("", self.c_gs)
        gf.addRow(self.l_gs_args, gs_args_row)
        perf_layout.addWidget(gs_box)
        mh_box = QGroupBox("MangoHud")
        mf = QFormLayout(mh_box)
        self.c_mh = QCheckBox("Enable MangoHud")
        self.e_mh_args = QLineEdit()
        self.l_mh_args = QLabel("MangoHud Options:")
        self.l_mh_args.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        self.cb_mh_conf = QComboBox()
        self.cb_mh_conf.setToolTip("Sets MANGOHUD_CONFIGFILE for the game.")
        self.l_mh_conf = QLabel("MangoHud Configuration:")
        self.l_mh_conf.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        mh_conf_row = QWidget()
        mh_conf_layout = QHBoxLayout(mh_conf_row)
        mh_conf_layout.setContentsMargins(0, 0, 0, 0)
        b_mh_new = QPushButton("New Configuration...")
        b_mh_new.clicked.connect(self._new_mangohud_config)
        mh_conf_layout.addWidget(self.cb_mh_conf, stretch=1)
        mh_conf_layout.addWidget(b_mh_new)
        mf.addRow("", self.c_mh)
        mf.addRow(self.l_mh_args, self.e_mh_args)
        mf.addRow(self.l_mh_conf, mh_conf_row)
        perf_layout.addWidget(mh_box)
        perf_layout.addStretch(1)
        tabs.addTab(perf, "Performance")

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
        self.c_lugui.setToolTip(
            "With prompts enabled, restore and backup can be declined per session."
        )
        lf.addRow("", self.c_lu_enable)
        lf.addRow("", self.c_restore)
        lf.addRow("", self.c_backup)
        lf.addRow("Game Name Override:", self.e_luname)
        lf.addRow("", self.c_lugui)
        self.l_lu_note = QLabel(
            "With prompts enabled, restore and backup can be declined per session."
        )
        self.l_lu_note.setWordWrap(True)
        lf.addRow(self.l_lu_note)
        if not defaults_mode:
            self.b_coverage = QPushButton("Check Coverage...")
            self.b_coverage.setToolTip(
                "Check whether Ludusavi has a manifest entry and local saves."
            )
            self.b_coverage.clicked.connect(self._check_coverage)
            cov_row = QWidget()
            cov_layout = QHBoxLayout(cov_row)
            cov_layout.setContentsMargins(0, 0, 0, 0)
            cov_layout.addWidget(self.b_coverage)
            cov_layout.addStretch(1)
            lf.addRow("Coverage:", cov_row)
        tabs.addTab(lu, "Ludusavi")

        # --- Night Light ---
        nl = QWidget()
        nf = QFormLayout(nl)
        self.c_nl = QCheckBox("Disable while the game is running (restored on exit)")
        self.cb_nl = QComboBox()
        self.cb_nl.addItem("Automatic", NightlightProvider.AUTO)
        self.cb_nl.addItem("Plasma", NightlightProvider.PLASMA)
        self.cb_nl.addItem("GNOME", NightlightProvider.GNOME)
        self.cb_nl.addItem("Disabled", NightlightProvider.OFF)
        nf.addRow("", self.c_nl)
        nf.addRow("Provider:", self.cb_nl)
        tabs.addTab(nl, "Night Light")

        pt = QWidget()
        pf = QFormLayout(pt)
        self.c_fresh = QCheckBox("Delete prefix before launch (fresh start)")
        self.c_fresh.setToolTip(
            "Deletes the compatdata prefix so Steam recreates it. WIPES saves "
            "inside the prefix — rely on cloud or Ludusavi backups!"
        )
        pf.addRow("", self.c_fresh)
        self.e_verbs = QLineEdit()
        self.e_verbs.setPlaceholderText("dotnet48 vcrun2022 (space-separated)")
        self.e_verbs.setToolTip("Winetricks verbs installed via protontricks before launch.")
        pf.addRow("Winetricks Verbs:", self.e_verbs)
        tabs.addTab(pt, "Proton")

        if not defaults_mode:
            notes = QWidget()
            notes_layout = QVBoxLayout(notes)
            notes_layout.setContentsMargins(0, 0, 0, 0)
            self.e_notes = QPlainTextEdit()
            self.e_notes.setPlaceholderText(
                "Free-form notes, e.g. works with GE-Proton, disable FSR in menus."
            )
            notes_layout.addWidget(self.e_notes)
            tabs.addTab(notes, "Notes")

        for box in (
            self.c_feral,
            self.c_cachy,
            self.c_gs,
            self.c_mh,
            self.c_lu_enable,
        ):
            box.toggled.connect(self._on_feature_toggled)

        status_keys = [
            "custom_prefix",
            "gamemoderun",
            "game-performance",
            "gamescope",
            "mangohud",
            "ludusavi",
        ]
        if not defaults_mode:
            # per-game only: Steam launch options need an AppID.
            status_keys.append("steam-options")
        layout.addWidget(self._status_box("Dependency Status", status_keys))

        if defaults_mode:
            btns = QDialogButtonBox(QDialogButtonBox.Save | QDialogButtonBox.Cancel)
            b_factory = QPushButton("Reset to Factory Defaults")
            b_factory.clicked.connect(self._on_reset_factory)
            btns.addButton(b_factory, QDialogButtonBox.ResetRole)
        else:
            btns = QDialogButtonBox()
            if self.launch_mode and self.can_launch:
                b_launch = QPushButton("Launch")
                b_launch.setIcon(self.style().standardIcon(QStyle.StandardPixmap.SP_MediaPlay))
                b_launch.setToolTip(
                    "Discard unsaved changes and launch with the saved configuration."
                )
                b_launch.clicked.connect(self._on_launch_without_save)
                btns.addButton(b_launch, QDialogButtonBox.ButtonRole.AcceptRole)
            btns.addButton(QDialogButtonBox.StandardButton.Save)
            if self.launch_mode and self.can_launch:
                b_save_launch = QPushButton("Save && Launch")
                b_save_launch.setIcon(
                    self.style().standardIcon(QStyle.StandardPixmap.SP_DialogApplyButton)
                )
                b_save_launch.setDefault(True)
                b_save_launch.clicked.connect(self._on_save_and_launch)
                btns.addButton(b_save_launch, QDialogButtonBox.ButtonRole.AcceptRole)
            b_reset = btns.addButton(
                "Reset to Global Defaults", QDialogButtonBox.ButtonRole.ResetRole
            )
            b_reset.clicked.connect(self._on_reset)
            btns.addButton(QDialogButtonBox.StandardButton.Cancel)
        if self._show_preview_box():
            preview_group = QGroupBox("Launch Command Preview")
            self._preview_group = preview_group
            preview_layout = QVBoxLayout(preview_group)
            preview_layout.setContentsMargins(4, 4, 4, 4)
            self._preview_edit = QPlainTextEdit()
            self._preview_edit.setReadOnly(True)
            font = QFontDatabase.systemFont(QFontDatabase.FixedFont)
            self._preview_edit.setFont(font)
            metrics = self._preview_edit.fontMetrics()
            self._preview_edit.setFixedHeight(metrics.lineSpacing() * 4 + 12)
            preview_layout.addWidget(self._preview_edit)
            preview_foot = QHBoxLayout()
            preview_foot.addStretch(1)
            b_refresh = QPushButton("Refresh")
            b_refresh.setToolTip("Rebuild the preview from the current fields.")
            b_refresh.clicked.connect(self._refresh_preview)
            preview_foot.addWidget(b_refresh)
            preview_layout.addLayout(preview_foot)
            layout.addWidget(preview_group)
        else:
            self._preview_edit = None
            self._preview_group = None
        btns.accepted.connect(self.accept)
        btns.rejected.connect(self.reject)
        layout.addWidget(btns)

        self._align_label_widths(
            self.l_feral_pad,
            self.l_cachy_pad,
            self.l_gs_args,
            self.l_mh_args,
            self.l_mh_conf,
        )
        self._populate()
        self._wire_preview()
        tabs.currentChanged.connect(self._refresh_preview)
        self._refresh_preview()

    def _populate(self) -> None:
        self._populating = True
        try:
            self._populate_fields()
        finally:
            self._populating = False
            self._refresh_statuses()

    def _populate_fields(self) -> None:
        c = self.cfg
        self.cb_gametype.setCurrentText(c.general.game_type or "auto")
        if not self.defaults_mode:
            self.e_runtime.setText(self._detect_runtime_text())
        self.e_exe.setText(c.general.custom_executable)
        self.e_prefix.setText(c.general.custom_prefix)
        self.c_show_menu.setChecked(c.general.show_menu)
        self.c_notify.setChecked(c.notifications.notify_on_launch)
        self.c_inhibit.setChecked(c.session.inhibit_idle)
        if not self.defaults_mode:
            self.c_protonlog.setChecked(c.debug.proton_log)
            idx = self.cb_winedebug.findData(c.debug.winedebug or "")
            self.cb_winedebug.setCurrentIndex(max(idx, 0))
        if not self.defaults_mode:
            self._refresh_profiles()
        self._set_env_table(c.env.vars)
        if not self.defaults_mode:
            log_path = str(xdg.game_log_file(self.appid))
            self.e_log.setText(log_path)
            self.b_log.setEnabled(os.path.exists(log_path))
        self.e_pre.setText(c.pre_post.pre_command)
        self.e_pre_args.setText(" ".join(c.pre_post.pre_args))
        self.e_post.setText(c.pre_post.post_command)
        self.e_post_args.setText(" ".join(c.pre_post.post_args))
        self.s_timeout.setValue(c.pre_post.timeout)
        self.c_shell.setChecked(c.pre_post.run_in_shell)
        self.c_feral.setChecked(c.gamemode.feral_gamemode)
        self.c_cachy.setChecked(c.gamemode.cachyos_game_performance)
        if self.c_feral.isChecked() and self.c_cachy.isChecked():
            # same rule as the launcher backend: Feral wins on conflict.
            self.c_cachy.setChecked(False)
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
        idx = self.cb_nl.findData(c.nightlight.provider or "auto")
        self.cb_nl.setCurrentIndex(max(idx, 0))
        self.c_fresh.setChecked(c.proton.fresh_prefix)
        self.e_verbs.setText(" ".join(c.proton.winetricks_verbs))
        if not self.defaults_mode:
            self.e_notes.setPlainText(c.notes.text)
        self._apply_binary_availability()

    def _detect_runtime_text(self) -> str:
        """Read-only Proton tool/version from the Steam config, if mapped."""
        if self.defaults_mode or not self.appid:
            return ""
        if (self.cfg.general.game_type or "auto") == "native":
            return "Native (no Proton)"
        return protonmod.tool_display(self.appid)

    def _refresh_profiles(self) -> None:
        self.cb_profile.blockSignals(True)
        try:
            self.cb_profile.clear()
            for name in cfgmod.list_profiles(self.appid):
                self.cb_profile.addItem(name, name)
            idx = self.cb_profile.findData(self._active_profile)
            self.cb_profile.setCurrentIndex(idx)
        finally:
            self.cb_profile.blockSignals(False)

    def _on_profile_switch(self) -> None:
        name = str(self.cb_profile.currentData() or "")
        if not name:
            return
        self._active_profile = name
        self.cfg = cfgmod.load_profile(self.appid, name)
        self.cfg.general.appid = self.appid
        self._populate()

    def _on_profile_save(self) -> None:
        from PySide6.QtWidgets import QInputDialog

        name, ok = QInputDialog.getText(self, "Save Profile", "Profile name:")
        if not ok or not name.strip():
            return
        self._collect()
        cfgmod.save_profile(self.appid, name.strip(), self.cfg)
        self._active_profile = name.strip()
        self._refresh_profiles()

    def _on_profile_delete(self) -> None:
        name = str(self.cb_profile.currentData() or "")
        if not name:
            return
        cfgmod.delete_profile(self.appid, name)
        if self._active_profile == name:
            self._active_profile = ""
        self._refresh_profiles()

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

    def _add_env_preset(self) -> None:
        from PySide6.QtWidgets import QInputDialog

        from .. import presets as presetsmod

        names = sorted(presetsmod.ENV_PRESETS)
        name, ok = QInputDialog.getItem(self, "Add Env Preset", "Preset:", names, 0, False)
        if not ok or not name:
            return
        vars = self._table_to_env()
        added = presetsmod.apply_preset(vars, name)
        self._set_env_table(vars)
        if not added:
            QMessageBox.information(
                self,
                "TKSteamLaunch",
                f"Preset '{name}': all keys already present.",
            )

    def _apply_gamescope_preset(self) -> None:
        from PySide6.QtWidgets import QInputDialog

        names = sorted(ov_backend.GAMESCOPE_PRESETS)
        name, ok = QInputDialog.getItem(self, "Gamescope Preset", "Preset:", names, 0, False)
        if ok and name:
            self.e_gs_args.setText(ov_backend.GAMESCOPE_PRESETS[name])

    def _refresh_mangohud_configs(self) -> None:
        current = self.cfg.mangohud.config_file
        self.cb_mh_conf.clear()
        self.cb_mh_conf.addItem("Default (MangoHud.conf)", "")
        for name in ov_backend.list_mangohud_configs():
            if name == ov_backend.DEFAULT_MANGOHUD_CONF:
                continue
            self.cb_mh_conf.addItem(name, name)
        idx = self.cb_mh_conf.findData(current)
        self.cb_mh_conf.setCurrentIndex(max(idx, 0))

    def _new_mangohud_config(self) -> None:
        from PySide6.QtWidgets import QInputDialog

        name, ok = QInputDialog.getText(self, "New MangoHud Configuration", "File name:")
        if not ok or not name.strip():
            return
        choices = {
            "Copy of MangoHud.conf": "default",
            "Minimal overlay": "minimal",
            "FPS limiter overlay": "fps-cap",
            "Full metrics overlay": "full",
            "Empty file": "empty",
        }
        label, ok = QInputDialog.getItem(
            self,
            "New MangoHud Configuration",
            "Start from:",
            list(choices),
            0,
            False,
        )
        if not ok:
            return
        path, source, error = ov_backend.create_mangohud_config(
            name.strip(), template=choices[label]
        )
        if error:
            QMessageBox.warning(self, "TKSteamLaunch", error)
            return
        if source == "exists":
            QMessageBox.information(self, "TKSteamLaunch", f"{path.name} already exists.")
        self._refresh_mangohud_configs()
        idx = self.cb_mh_conf.findData(path.name)
        if idx >= 0:
            self.cb_mh_conf.setCurrentIndex(idx)
        if not open_path(str(path)):
            QMessageBox.warning(self, "TKSteamLaunch", f"Could not open {path}.")

    def _open_log(self) -> None:
        if not open_path(self.e_log.text()):
            QMessageBox.warning(self, "TKSteamLaunch", "Could not open the log file.")

    def _open_proton_log(self) -> None:
        from ..launcher import proton_log_dir

        if not open_path(str(proton_log_dir(self.appid))):
            QMessageBox.warning(self, "TKSteamLaunch", "Could not open the Proton log folder.")

    def _on_reset_factory(self) -> None:
        # In-memory only: the file changes on Save, Cancel discards everything.
        self.cfg = cfgmod.GameConfig()
        self._populate()

    def reject(self) -> None:
        self._stop_coverage_worker()
        super().reject()

    def _on_reset(self) -> None:
        # In-memory only: the file changes on Save, Cancel discards everything.
        self._cov_run += 1  # invalidate any in-flight coverage result
        self.cfg = cfgmod.load_defaults()
        self.cfg.general.appid = self.appid
        self._active_profile = ""
        self._populate()

    def _on_save_and_launch(self) -> None:
        self.launch_requested = True
        self.accept()

    def _show_preview_box(self) -> bool:
        try:
            return bool(cfgmod.load_preferences().show_preview)
        except Exception:
            return True

    def _refresh_preview(self) -> None:
        if self._preview_edit is None:
            return
        self._collect()
        try:
            from ..launcher import build_final_command

            cmd, _env, warnings = build_final_command(self.cfg, ["%command%"])
        except Exception as e:  # never break the dialog on preview
            self._preview_edit.setPlainText(f"(preview unavailable: {e})")
            return
        lines = [shlex.join(cmd) if cmd else "(empty command)"]
        lines += [f"# warning: {w}" for w in warnings]
        self._preview_edit.setPlainText("\n".join(lines))

    def _wire_preview(self) -> None:
        from PySide6.QtWidgets import (
            QCheckBox,
            QComboBox,
            QLineEdit,
            QPlainTextEdit,
            QSpinBox,
            QTableWidget,
        )

        for widget in self.findChildren(QLineEdit):
            widget.textChanged.connect(self._refresh_preview)
        for widget in self.findChildren(QPlainTextEdit):
            if widget is not self._preview_edit:
                widget.textChanged.connect(self._refresh_preview)
        for widget in self.findChildren(QCheckBox):
            widget.toggled.connect(self._refresh_preview)
        for widget in self.findChildren(QComboBox):
            widget.currentIndexChanged.connect(self._refresh_preview)
        for widget in self.findChildren(QSpinBox):
            widget.valueChanged.connect(self._refresh_preview)
        for widget in self.findChildren(QTableWidget):
            widget.cellChanged.connect(self._refresh_preview)
            widget.model().rowsInserted.connect(self._refresh_preview)
            widget.model().rowsRemoved.connect(self._refresh_preview)

    def _update_lu_state(self) -> None:
        on = self.c_lu_enable.isChecked()
        for w in (self.c_restore, self.c_backup, self.e_luname, self.c_lugui, self.l_lu_note):
            w.setEnabled(on)

    def _check_coverage(self) -> None:
        from PySide6.QtCore import Qt
        from PySide6.QtWidgets import QApplication

        if self._cov_thread is not None and self._cov_thread.isRunning():
            return
        self._collect()
        self._cov_run += 1
        run = self._cov_run
        self.b_coverage.setEnabled(False)
        QApplication.setOverrideCursor(Qt.CursorShape.WaitCursor)
        worker = _CoverageWorker(self.appid, self.cfg.ludusavi.name_override, parent=self)
        worker.done.connect(lambda status, detail: self._on_coverage_done(run, status, detail))
        worker.finished.connect(worker.deleteLater)
        self._cov_thread = worker
        worker.start()

    def _on_coverage_done(self, run: int, status: str, detail: str) -> None:
        from PySide6.QtWidgets import QApplication

        # Drop our reference: finished() will deleteLater() the worker.
        self._cov_thread = None
        QApplication.restoreOverrideCursor()
        if hasattr(self, "b_coverage"):
            self.b_coverage.setEnabled(True)
        if run != self._cov_run:
            return  # stale result (e.g. config was reset mid-run)
        messages = {
            "covered": f"Ludusavi covers this game.\n{detail}",
            "no-local-saves": f"Manifest entry exists, but no saves found.\n{detail}",
            "no-entry": (
                "No manifest entry for this game.\n"
                "Add a custom game entry in Ludusavi to enable backups."
            ),
            "unavailable": f"Could not check coverage:\n{detail}",
        }
        QMessageBox.information(self, "TKSteamLaunch", messages.get(status, detail))

    @staticmethod
    def _align_label_widths(*labels: QLabel) -> None:
        """Equalize label widths so fields in separate form layouts align.

        Runtime-measured via sizeHint: safe across fonts, DPI and themes.
        """
        width = 0
        for label in labels:
            width = max(width, label.sizeHint().width())
        for label in labels:
            label.setMinimumWidth(width)

    def _status_box(self, title: str, keys: list[str]) -> QWidget:
        """Full-width log-like box holding per-binary status lines."""
        box = QGroupBox(title)
        outer = QVBoxLayout(box)
        outer.setContentsMargins(4, 4, 4, 4)
        frame = QFrame()
        frame.setFrameShape(QFrame.Shape.StyledPanel)
        frame.setFrameShadow(QFrame.Shadow.Sunken)
        inner = QVBoxLayout(frame)
        inner.setContentsMargins(8, 6, 8, 6)
        for key in keys:
            label = QLabel()
            label.setTextFormat(Qt.TextFormat.RichText)
            label.setWordWrap(True)
            inner.addWidget(label)
            self._status_labels[key] = label
        outer.addWidget(frame)
        return box

    def _render_status(self, kind: str, text: str) -> str:
        import html

        colors = _STATUS_COLORS_DARK if self._dark else _STATUS_COLORS_LIGHT
        mark = _STATUS_MARKS.get(kind, "●")
        color = colors.get(kind, colors["note"])
        return f'<span style="color:{color}; font-weight:bold;">{mark}</span> {html.escape(text)}'

    def _set_status(self, key: str, kind: str, text: str) -> None:
        label = self._status_labels.get(key)
        if label is not None:
            label.setText(self._render_status(kind, text))

    def _refresh_statuses(self) -> None:
        feral_on = self.c_feral.isChecked()
        cachy_on = self.c_cachy.isChecked()
        # Mutually exclusive: hide the sidelined backend (Feral wins).
        self._status_labels["gamemoderun"].setVisible(not cachy_on)
        self._status_labels["game-performance"].setVisible(not feral_on)
        self._set_status(
            "gamemoderun",
            *_binary_status("gamemoderun", feral_on),
        )
        self._set_status(
            "game-performance",
            *_binary_status("game-performance", cachy_on),
        )
        self._set_status("gamescope", *_binary_status("gamescope", self.c_gs.isChecked()))
        self._set_status("mangohud", *_binary_status("mangohud", self.c_mh.isChecked()))
        self._refresh_ludusavi_status()
        self._update_prefix_status()
        self._refresh_steam_status()

    def _refresh_steam_status(self) -> None:
        from .. import steam as steammod

        if self.defaults_mode or not self.appid:
            self._set_status("steam-options", "note", "Steam options: n/a for global defaults")
            return
        status, detail = steammod.launch_options_status(self.appid)
        kinds = {"ok": "ok", "missing": "warn", "unknown": "note"}
        self._set_status("steam-options", kinds.get(status, "note"), detail)

    def _on_feature_toggled(self, _checked: bool = False) -> None:
        self._refresh_statuses()

    def _apply_binary_availability(self) -> None:
        """Disable tool toggles whose binaries are missing (unchecking them).

        Dead-on-arrival options cannot be (re-)enabled; the launcher would
        skip them with a warning anyway. Idempotent across repopulates.
        """
        tools = {
            self.c_feral: "gamemoderun",
            self.c_cachy: "game-performance",
            self.c_gs: "gamescope",
            self.c_mh: "mangohud",
            self.c_lu_enable: "ludusavi",
        }
        for checkbox, binary in tools.items():
            self._orig_tips.setdefault(checkbox, checkbox.toolTip())
            if shutil.which(binary):
                checkbox.setEnabled(True)
                checkbox.setToolTip(self._orig_tips[checkbox])
            else:
                checkbox.setChecked(False)
                checkbox.setEnabled(False)
                checkbox.setToolTip(f"{binary} not installed — option skipped at launch.")
        self._update_lu_state()

    def _on_gamemode_exclusive(self, _checked: bool = False) -> None:
        if getattr(self, "_populating", False):
            return
        sender = self.sender()
        if sender is self.c_feral and self.c_feral.isChecked():
            self.c_cachy.setChecked(False)
        elif sender is self.c_cachy and self.c_cachy.isChecked():
            self.c_feral.setChecked(False)

    def _refresh_ludusavi_status(self) -> None:
        on = self.c_lu_enable.isChecked()
        exe = shutil.which("ludusavi")
        if exe and ("/flatpak/" in exe or "flatpak" in exe):
            self._set_status(
                "ludusavi",
                "note",
                f"ludusavi via Flatpak ({exe}) — may not see Proton prefixes",
            )
        else:
            self._set_status("ludusavi", *_binary_status("ludusavi", on))

    def _update_prefix_status(self) -> None:
        prefix = self.e_prefix.text().strip()
        if not prefix:
            self._set_status("custom_prefix", "ok", "No custom prefix — game launches directly")
            return
        parts = split_args(prefix)
        if not parts:
            return
        self._set_status(
            "custom_prefix",
            *_binary_status(parts[0], True, skip_note="launch will fail"),
        )

    def _collect(self) -> None:
        self.cfg.general.game_type = self.cb_gametype.currentText()
        self.cfg.general.custom_executable = self.e_exe.text().strip()
        self.cfg.general.custom_prefix = self.e_prefix.text().strip()
        self.cfg.general.show_menu = self.c_show_menu.isChecked()
        self.cfg.notifications.notify_on_launch = self.c_notify.isChecked()
        self.cfg.session.inhibit_idle = self.c_inhibit.isChecked()
        self.cfg.proton.fresh_prefix = self.c_fresh.isChecked()
        self.cfg.proton.winetricks_verbs = split_args(self.e_verbs.text())
        self.cfg.env.vars = self._table_to_env()
        self.cfg.pre_post.pre_command = self.e_pre.text().strip()
        self.cfg.pre_post.pre_args = split_args(self.e_pre_args.text())
        self.cfg.pre_post.post_command = self.e_post.text().strip()
        self.cfg.pre_post.post_args = split_args(self.e_post_args.text())
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
        self.cfg.nightlight.provider = str(self.cb_nl.currentData() or "auto")
        if not self.defaults_mode:
            self.cfg.notes.text = self.e_notes.toPlainText()
            self.cfg.debug.proton_log = self.c_protonlog.isChecked()
            self.cfg.debug.winedebug = str(self.cb_winedebug.currentData() or "")

    def _stop_coverage_worker(self) -> None:
        worker, self._cov_thread = self._cov_thread, None
        self._cov_run += 1  # invalidate any result still queued
        if worker is not None and worker.isRunning():
            worker.requestInterruption()
            worker.wait(3000)
            if worker.isRunning():
                worker.terminate()
                worker.wait(2000)
        from PySide6.QtWidgets import QApplication

        QApplication.restoreOverrideCursor()

    def _on_launch_without_save(self) -> None:
        self.launch_requested = True
        self._skip_save = True
        self.accept()

    def accept(self) -> None:
        self._stop_coverage_worker()
        if not self._skip_save:
            self._collect()
            if self.defaults_mode:
                cfgmod.save_defaults(self.cfg)
            else:
                cfgmod.save(self.cfg)
        super().accept()
