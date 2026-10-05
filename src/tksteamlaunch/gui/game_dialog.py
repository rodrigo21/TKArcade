"""Game editor dialog with tabs. Also used for global defaults."""

from __future__ import annotations

import copy
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
    QSlider,
    QSpinBox,
    QStyle,
    QTableWidget,
    QTableWidgetItem,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from .. import config as cfgmod
from .. import gpu as gpumod
from .. import presets as presetsmod
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
    from PySide6.QtCore import QCoreApplication

    def tr(s: str) -> str:
        return QCoreApplication.translate("GameDialog", s)

    path = shutil.which(name)
    if path:
        if enabled:
            return "ok", tr(f"{name} — {path}")
        return "ok", tr(f"{name} — {path} (off)")
    if enabled:
        return "warn", tr(f"{name} not found in PATH — {skip_note}")
    return "note", tr(f"{name} not installed (feature off)")


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


def _scroll_page(page: QWidget) -> QWidget:
    """Wrap a tab page so small windows can scroll instead of clipping."""
    from PySide6.QtWidgets import QScrollArea

    scroll = QScrollArea()
    scroll.setWidgetResizable(True)
    scroll.setFrameShape(QFrame.Shape.NoFrame)
    scroll.setWidget(page)
    return scroll


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


class _DisplayModesWorker(QThread):
    """Query offered display modes off the UI thread (kscreen can wedge)."""

    done = Signal(int, list)

    def __init__(self, provider: str, output: str, run: int, parent=None) -> None:
        super().__init__(parent)
        self._provider = provider
        self._output = output
        self._run = run

    def run(self) -> None:
        try:
            from ..backends import display as dispmod

            modes = dispmod.offered_modes(self._provider, self._output)
        except Exception:
            modes = []
        if not self.isInterruptionRequested():
            self.done.emit(self._run, modes)


class BulkEnvDialog(QDialog):
    """Bulk-edit environment variables as KEY=VALUE text."""

    def __init__(self, parent, text: str) -> None:
        super().__init__(parent)
        self.setWindowTitle(self.tr("Bulk Edit Environment Variables"))
        self.resize(480, 360)
        layout = QVBoxLayout(self)
        layout.addWidget(
            QLabel(self.tr("One VARIABLE=value per line; lines starting with # are ignored."))
        )
        self.edit = QPlainTextEdit(text)
        self.edit.setPlaceholderText(self.tr("ONE=1\nTWO=2"))
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
        self._dmode_thread: _DisplayModesWorker | None = None
        self._dmode_run = 0
        self.appid = appid
        if defaults_mode:
            self.setWindowTitle(self.tr("Global Defaults"))
            try:
                self.cfg = cfgmod.load_defaults()
            except OSError as e:
                self.cfg = cfgmod.GameConfig()
                self._load_warning = self.tr(
                    f"The defaults file could not be read: {e}\nShowing built-in defaults instead."
                )
            else:
                err = cfgmod.toml_error(xdg.defaults_file())
                self._load_warning = (
                    self.tr(
                        f"The defaults file could not be read (invalid TOML): {err}\n"
                        "Showing built-in defaults instead."
                    )
                    if err
                    else None
                )
        else:
            self.setWindowTitle(
                self.tr(f"Game Settings — {name} ({appid})")
                if name
                else self.tr(f"Game Settings ({appid})")
            )
            self.cfg, self._load_warning = cfgmod.load_with_warning(appid)
        self._dark = _is_dark_theme(self)
        self._status_labels: dict[str, QLabel] = {}
        saved_profile = "" if defaults_mode else self.cfg.general.active_profile
        if saved_profile and saved_profile not in cfgmod.list_profiles(appid):
            saved_profile = ""
        self._active_profile = saved_profile
        if saved_profile:
            # Open directly into the persisted profile content, not live.
            err = self._read_profile(saved_profile)
            if err:
                self._load_warning = self.tr(
                    f'The profile "{saved_profile}" could not be read: {err}\n'
                    "Showing defaults for it instead."
                )
        self._profile_names: set[str] = (
            set(cfgmod.list_profiles(appid)) if not defaults_mode else set()
        )
        from .helpers import apply_default_size

        apply_default_size(self, fallback=(680, 640))

        layout = QVBoxLayout(self)
        if defaults_mode:
            layout.addWidget(
                QLabel(self.tr("Template for new games. Existing games keep their own copy."))
            )

        tabs = QTabWidget()
        layout.addWidget(tabs, stretch=1)
        self._tabs = tabs

        # --- General ---
        g = QWidget()
        gf = QFormLayout(g)
        if not defaults_mode:
            self.e_appid = QLineEdit(self.cfg.general.appid)
            self.e_appid.setReadOnly(True)
            gf.addRow(self.tr("Steam App ID:"), self.e_appid)
        self.cb_gametype = QComboBox()
        self.cb_gametype.addItem(self.tr("Automatic"), "auto")
        self.cb_gametype.addItem(self.tr("Proton"), "proton")
        self.cb_gametype.addItem(self.tr("Native Linux"), "native")
        self.cb_gametype.setToolTip(self.tr("Auto detects Proton versus native Linux games."))
        gf.addRow(self.tr("Game Type:"), self.cb_gametype)
        if not defaults_mode:
            self.e_runtime = QLineEdit()
            self.e_runtime.setReadOnly(True)
            self.e_runtime.setToolTip(
                self.tr("Proton tool and version from your Steam config (read-only).")
            )
            gf.addRow(self.tr("Detected Runtime:"), self.e_runtime)
        self.e_exe = QLineEdit()
        self.e_exe.setPlaceholderText(self.tr("Optional replacement executable for this game"))
        gf.addRow(self.tr("Custom Executable:"), self.e_exe)
        self.e_prefix = QLineEdit()
        self.e_prefix.setPlaceholderText(self.tr("e.g. zink-run"))
        self.e_prefix.setToolTip(
            self.tr(
                "Command prefix wrapping the game directly, inside MangoHud, "
                "GameMode, Gamescope and Ludusavi."
            )
        )
        gf.addRow(self.tr("Custom Command Prefix:"), self.e_prefix)
        self.e_prefix.textChanged.connect(self._update_prefix_status)
        self.c_show_menu = QCheckBox(self.tr("Show menu before launch"))
        self.c_show_menu.setToolTip(
            self.tr(
                "Show the pre-launch menu (Launch / Settings / Cancel) "
                "on every Steam start. Also forced by the --menu flag."
            )
        )
        gf.addRow("", self.c_show_menu)
        self.s_menu_timeout = QSpinBox()
        self.s_menu_timeout.setRange(0, 600)
        self.s_menu_timeout.setToolTip(
            self.tr("Auto-launch countdown in seconds (0 = wait forever).")
        )
        gf.addRow(self.tr("Menu Timeout (seconds):"), self.s_menu_timeout)
        if not defaults_mode:
            self.cb_profile = QComboBox()
            self.cb_profile.setToolTip(self.tr("Switching loads the profile (Save writes it)."))
            self.cb_profile.currentIndexChanged.connect(self._on_profile_switch)
            b_prof_save = QPushButton(self.tr("Save As..."))
            b_prof_save.clicked.connect(self._on_profile_save)
            b_prof_clone = QPushButton(self.tr("Clone..."))
            b_prof_clone.setToolTip(
                self.tr("Copy the selected profile (or live config) to a new name.")
            )
            b_prof_clone.clicked.connect(self._on_profile_clone)
            b_prof_delete = QPushButton(self.tr("Delete"))
            b_prof_delete.clicked.connect(self._on_profile_delete)
            prof_row = QWidget()
            prof_layout = QHBoxLayout(prof_row)
            prof_layout.setContentsMargins(0, 0, 0, 0)
            prof_layout.addWidget(self.cb_profile, stretch=1)
            prof_layout.addWidget(b_prof_save)
            prof_layout.addWidget(b_prof_clone)
            prof_layout.addWidget(b_prof_delete)
            gf.addRow(self.tr("Profile:"), prof_row)
        if not defaults_mode:
            log_row = QWidget()
            log_layout = QHBoxLayout(log_row)
            log_layout.setContentsMargins(0, 0, 0, 0)
            self.e_log = QLineEdit()
            self.e_log.setReadOnly(True)
            self.b_log = QPushButton(self.tr("Open"))
            self.b_log.clicked.connect(self._open_log)
            log_layout.addWidget(self.e_log, stretch=1)
            log_layout.addWidget(self.b_log)
            gf.addRow(self.tr("Log File:"), log_row)
        tabs.addTab(_scroll_page(g), self.tr("General"))

        # --- Environment ---
        env_page = QWidget()
        env_page_layout = QVBoxLayout(env_page)
        env_page_layout.setContentsMargins(4, 4, 4, 4)
        env_box = QWidget()
        env_layout = QVBoxLayout(env_box)
        env_layout.setContentsMargins(0, 0, 0, 0)
        self.t_env = QTableWidget(0, 2)
        self.t_env.setHorizontalHeaderLabels([self.tr("Variable"), self.tr("Value")])
        self.t_env.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        env_layout.addWidget(self.t_env)
        env_btns = QHBoxLayout()
        b_add = QPushButton(self.tr("Add"))
        b_add.clicked.connect(lambda: self.t_env.insertRow(self.t_env.rowCount()))
        b_del = QPushButton(self.tr("Remove"))
        b_del.clicked.connect(self._remove_env_row)
        b_bulk = QPushButton(self.tr("Bulk Edit..."))
        b_bulk.clicked.connect(self._bulk_edit_env)
        b_preset = QPushButton(self.tr("Add Preset..."))
        b_preset.setToolTip(self.tr("Merge a curated env preset (only missing keys)."))
        b_preset.clicked.connect(self._add_env_preset)
        env_btns.addWidget(b_add)
        env_btns.addWidget(b_del)
        env_btns.addWidget(b_bulk)
        env_btns.addWidget(b_preset)
        env_btns.addStretch(1)
        env_layout.addLayout(env_btns)
        env_page_layout.addWidget(QLabel(self.tr("Per-game environment variables:")))
        env_page_layout.addWidget(env_box, stretch=1)
        env_scroll = _scroll_page(env_page)
        tabs.addTab(env_scroll, self.tr("Environment"))

        # --- Pre/Post Commands ---
        pp = QWidget()
        pf = QFormLayout(pp)
        self.e_pre = QLineEdit()
        self.e_pre_args = QLineEdit()
        self.e_post = QLineEdit()
        self.e_post_args = QLineEdit()
        self.s_timeout = QSpinBox()
        self.s_timeout.setRange(1, 3600)
        self.c_shell = QCheckBox(self.tr("Run in shell (bash -c)"))
        pf.addRow(self.tr("Pre-Launch Command:"), self.e_pre)
        pf.addRow(self.tr("Pre-Launch Arguments:"), self.e_pre_args)
        pf.addRow(self.tr("Post-Exit Command:"), self.e_post)
        pf.addRow(self.tr("Post-Exit Arguments:"), self.e_post_args)
        pf.addRow(self.tr("Timeout (seconds):"), self.s_timeout)
        pf.addRow("", self.c_shell)
        pp_scroll = _scroll_page(pp)
        tabs.addTab(pp_scroll, self.tr("Pre/Post Commands"))

        # --- Performance: system + display/overlay sections ---
        perf = QWidget()
        perf_layout = QVBoxLayout(perf)
        perf_layout.setContentsMargins(0, 0, 0, 0)
        sys_box = QGroupBox(self.tr("System"))
        ff = QFormLayout(sys_box)
        self.c_feral = QCheckBox(self.tr("Enable Feral GameMode (gamemoderun)"))
        self.c_feral.setToolTip(
            self.tr(
                "Optimizes CPU and GPU governors while the game runs. "
                "Mutually exclusive with CachyOS game-performance."
            )
        )
        self.c_cachy = QCheckBox(self.tr("Enable CachyOS game-performance"))
        self.c_cachy.setToolTip(
            self.tr(
                "Applies the CachyOS gaming performance profile. "
                "Mutually exclusive with Feral GameMode."
            )
        )
        self.l_feral_pad = QLabel()
        self.l_cachy_pad = QLabel()
        self.c_feral.toggled.connect(self._on_gamemode_exclusive)
        self.c_cachy.toggled.connect(self._on_gamemode_exclusive)
        ff.addRow(self.l_feral_pad, self.c_feral)
        ff.addRow(self.l_cachy_pad, self.c_cachy)
        perf_layout.addWidget(sys_box)

        perf_layout.addStretch(1)
        tabs.addTab(_scroll_page(perf), self.tr("Performance"))

        # --- Display (image pipeline) ---
        disp = QWidget()
        disp_layout = QVBoxLayout(disp)
        disp_layout.setContentsMargins(4, 4, 4, 4)
        dm_box = QGroupBox(self.tr("Display Mode"))
        df = QFormLayout(dm_box)
        self.e_dout = QLineEdit()
        self.e_dout.setPlaceholderText(self.tr("auto = current output"))
        self.e_dout.setToolTip(
            self.tr("Output name (e.g. DP-3); empty follows the current output.")
        )
        df.addRow(self.tr("Output:"), self.e_dout)
        self.e_dmode = QComboBox()
        self.e_dmode.setEditable(True)
        self.e_dmode.setPlaceholderText(self.tr("e.g. 1920x1080@60, empty = off"))
        self.e_dmode.setToolTip(
            self.tr(
                "Resolution (and refresh rate) while the game runs; restored on exit. "
                "Type any mode or pick a detected one."
            )
        )
        b_dmodes = QPushButton(self.tr("Refresh"))
        b_dmodes.setToolTip(
            self.tr(
                "List the output's detected modes (runs a backend query). "
                "Manual entry always works."
            )
        )
        b_dmodes.clicked.connect(self._refresh_display_modes)
        dmode_row = QWidget()
        dmode_layout = QHBoxLayout(dmode_row)
        dmode_layout.setContentsMargins(0, 0, 0, 0)
        dmode_layout.addWidget(self.e_dmode, stretch=1)
        dmode_layout.addWidget(b_dmodes)
        df.addRow(self.tr("Mode:"), dmode_row)
        self.cb_dprov = QComboBox()
        for value, label in (
            ("auto", self.tr("Automatic")),
            ("plasma", self.tr("Plasma")),
            ("gnome", self.tr("GNOME")),
            ("wlroots", self.tr("wlroots")),
            ("x11", self.tr("X11")),
            ("off", self.tr("Disabled")),
        ):
            self.cb_dprov.addItem(label, value)
        self.cb_dprov.setToolTip(
            self.tr("Display backend. GNOME and wlroots compositors land in phase 2.")
        )
        df.addRow(self.tr("Provider:"), self.cb_dprov)
        self.s_dip = QSlider(Qt.Orientation.Horizontal)
        self.s_dip.setRange(3, 15)
        self.s_dip.setSingleStep(1)
        self.s_dip.setTickPosition(QSlider.TickPosition.TicksBelow)
        self.s_dip.setTickInterval(3)
        self.s_dip.setToolTip(self.tr("Seconds on the dip mode before returning."))
        self.l_dip = QLabel("")
        self.s_dip.valueChanged.connect(lambda v: self.l_dip.setText(self.tr(f"{v} s")))
        dip_row = QWidget()
        dip_row.setObjectName("dip_row")
        dip_layout = QHBoxLayout(dip_row)
        dip_layout.setContentsMargins(0, 0, 0, 0)
        dip_layout.addWidget(self.s_dip, stretch=1)
        dip_layout.addWidget(self.l_dip)
        df.addRow(self.tr("Dip delay:"), dip_row)
        self._dip_row = dip_row
        self._dip_row.setVisible(False)
        dm_note = QLabel(
            self.tr("Same mode as current: dips down and back first (VRAM workaround).")
        )
        dm_note.setObjectName("dip_note")
        dm_note.setVisible(False)
        df.addRow("", dm_note)
        self._dip_note = dm_note
        self._dmode_current: str | None = None
        disp_layout.addWidget(dm_box)
        gs_box = QGroupBox(self.tr("Gamescope"))
        gf = QFormLayout(gs_box)
        self.c_gs = QCheckBox(self.tr("Enable Gamescope"))
        self.e_gs_args = QLineEdit()
        self.e_gs_args.setPlaceholderText(self.tr("-f -H 1080 -r 144"))
        self.l_gs_args = QLabel(self.tr("Gamescope Options:"))
        self.l_gs_args.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        gs_args_row = QWidget()
        gs_args_layout = QHBoxLayout(gs_args_row)
        gs_args_layout.setContentsMargins(0, 0, 0, 0)
        b_gs_preset = QPushButton(self.tr("Preset..."))
        b_gs_preset.setToolTip(self.tr("Fill in a starter Gamescope option set."))
        b_gs_preset.clicked.connect(self._apply_gamescope_preset)
        gs_args_layout.addWidget(self.e_gs_args, stretch=1)
        gs_args_layout.addWidget(b_gs_preset)
        gf.addRow("", self.c_gs)
        gf.addRow(self.l_gs_args, gs_args_row)
        disp_layout.addWidget(gs_box)
        mh_box = QGroupBox(self.tr("MangoHud"))
        mf = QFormLayout(mh_box)
        self.c_mh = QCheckBox(self.tr("Enable MangoHud"))
        self.e_mh_args = QLineEdit()
        self.l_mh_args = QLabel(self.tr("MangoHud Options:"))
        self.l_mh_args.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        self.cb_mh_conf = QComboBox()
        self.cb_mh_conf.setToolTip(self.tr("Sets MANGOHUD_CONFIGFILE for the game."))
        self.l_mh_conf = QLabel(self.tr("MangoHud Configuration:"))
        self.l_mh_conf.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        mh_conf_row = QWidget()
        mh_conf_layout = QHBoxLayout(mh_conf_row)
        mh_conf_layout.setContentsMargins(0, 0, 0, 0)
        b_mh_new = QPushButton(self.tr("New Configuration..."))
        b_mh_new.clicked.connect(self._new_mangohud_config)
        mh_conf_layout.addWidget(self.cb_mh_conf, stretch=1)
        mh_conf_layout.addWidget(b_mh_new)
        mf.addRow("", self.c_mh)
        mf.addRow(self.l_mh_args, self.e_mh_args)
        mf.addRow(self.l_mh_conf, mh_conf_row)
        disp_layout.addWidget(mh_box)
        rt_box = QGroupBox(self.tr("RT Upscaler"))
        rf = QFormLayout(rt_box)
        self.c_rt = QCheckBox(self.tr("Enable RT Upscaler (linux-rt-upscaler)"))
        self.c_rt.setToolTip(
            self.tr("SRCNN upscaling for X11/XWayland windows; forces PROTON_ENABLE_WAYLAND=0.")
        )
        self.e_rt_args = QLineEdit()
        self.e_rt_args.setPlaceholderText(self.tr("-m 4x24 (see upscale --help-all)"))
        self.l_rt_args = QLabel(self.tr("Upscaler Options:"))
        self.l_rt_args.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        rf.addRow("", self.c_rt)
        rf.addRow(self.l_rt_args, self.e_rt_args)
        disp_layout.addWidget(rt_box)
        disp_layout.addStretch(1)
        tabs.addTab(_scroll_page(disp), self.tr("Display"))

        # --- Ludusavi ---
        lu = QWidget()
        lf = QFormLayout(lu)
        self.c_lu_enable = QCheckBox(self.tr("Enable Ludusavi for this game"))
        self.c_lu_enable.toggled.connect(self._update_lu_state)
        self.c_restore = QCheckBox(self.tr("Restore backup before launch"))
        self.c_restore.setToolTip(self.tr("Unchecked = --no-restore"))
        self.c_backup = QCheckBox(self.tr("Back up after exit"))
        self.c_backup.setToolTip(self.tr("Unchecked = --no-backup"))
        self.e_luname = QLineEdit()
        self.e_luname.setPlaceholderText(self.tr("Leave empty to detect the game from Steam"))
        self.c_lugui = QCheckBox(self.tr("Show Prompts (--gui)"))
        self.c_lugui.setToolTip(
            self.tr("With prompts enabled, restore and backup can be declined per session.")
        )
        lf.addRow("", self.c_lu_enable)
        lf.addRow("", self.c_restore)
        lf.addRow("", self.c_backup)
        lf.addRow(self.tr("Game Name Override:"), self.e_luname)
        lf.addRow("", self.c_lugui)
        self.l_lu_note = QLabel(
            self.tr("With prompts enabled, restore and backup can be declined per session.")
        )
        self.l_lu_note.setWordWrap(True)
        lf.addRow(self.l_lu_note)
        if not defaults_mode:
            self.b_coverage = QPushButton(self.tr("Check Coverage..."))
            self.b_coverage.setToolTip(
                self.tr("Check whether Ludusavi has a manifest entry and local saves.")
            )
            self.b_coverage.clicked.connect(self._check_coverage)
            cov_row = QWidget()
            cov_layout = QHBoxLayout(cov_row)
            cov_layout.setContentsMargins(0, 0, 0, 0)
            cov_layout.addWidget(self.b_coverage)
            cov_layout.addStretch(1)
            lf.addRow(self.tr("Coverage:"), cov_row)
        tabs.addTab(_scroll_page(lu), self.tr("Ludusavi"))

        # --- System (desktop integration) ---
        nl = QWidget()
        nl_layout = QVBoxLayout(nl)
        nl_layout.setContentsMargins(4, 4, 4, 4)
        notif_box = QGroupBox(self.tr("Notifications"))
        nff = QFormLayout(notif_box)
        self.c_notify = QCheckBox(self.tr("Notify on launch"))
        self.c_notify.setToolTip(
            self.tr("Show a transient summary notification when the game starts.")
        )
        nff.addRow("", self.c_notify)
        nl_layout.addWidget(notif_box)
        idle_box = QGroupBox(self.tr("Idle Suspend"))
        iff = QFormLayout(idle_box)
        self.c_inhibit = QCheckBox(self.tr("Inhibit idle suspend while playing"))
        self.c_inhibit.setToolTip(
            self.tr(
                "Holds a logind idle lock during the session. Sleep lock is not "
                "included (needs privileges)."
            )
        )
        iff.addRow("", self.c_inhibit)
        nl_layout.addWidget(idle_box)
        nlight_box = QGroupBox(self.tr("Night Light"))
        nlf = QFormLayout(nlight_box)
        self.c_nl = QCheckBox(
            self.tr("Disable night light while the game is running (restored on exit)")
        )
        self.cb_nl = QComboBox()
        self.cb_nl.addItem(self.tr("Automatic"), NightlightProvider.AUTO)
        self.cb_nl.addItem(self.tr("Plasma"), NightlightProvider.PLASMA)
        self.cb_nl.addItem(self.tr("GNOME"), NightlightProvider.GNOME)
        self.cb_nl.addItem(self.tr("Disabled"), NightlightProvider.OFF)
        nlf.addRow("", self.c_nl)
        nlf.addRow(self.tr("Provider:"), self.cb_nl)
        nl_layout.addWidget(nlight_box)
        nl_layout.addStretch(1)
        tabs.addTab(_scroll_page(nl), self.tr("System"))

        pt = QWidget()
        pf = QFormLayout(pt)
        self.c_fresh = QCheckBox(self.tr("Delete prefix before launch (fresh start)"))
        self.c_fresh.setToolTip(
            self.tr(
                "Deletes the compatdata prefix so Steam recreates it. WIPES saves "
                "inside the prefix — rely on cloud or Ludusavi backups!"
            )
        )
        pf.addRow("", self.c_fresh)
        self.e_verbs = QLineEdit()
        self.e_verbs.setPlaceholderText(self.tr("dotnet48 vcrun2022 (space-separated)"))
        self.e_verbs.setToolTip(
            self.tr("Winetricks verbs installed via protontricks before launch.")
        )
        pf.addRow(self.tr("Winetricks Verbs:"), self.e_verbs)
        if not defaults_mode:
            self.c_protonlog = QCheckBox(self.tr("Capture Proton log (disk-heavy)"))
            self.c_protonlog.setToolTip(
                self.tr("Sets PROTON_LOG=1 with a per-game log dir (Proton only).")
            )
            self.b_protonlog = QPushButton(self.tr("Open"))
            self.b_protonlog.clicked.connect(self._open_proton_log)
            proton_row = QWidget()
            proton_layout = QHBoxLayout(proton_row)
            proton_layout.setContentsMargins(0, 0, 0, 0)
            proton_layout.addWidget(self.c_protonlog, stretch=1)
            proton_layout.addWidget(self.b_protonlog)
            pf.addRow("", proton_row)
            self.cb_winedebug = QComboBox()
            self.cb_winedebug.addItem(self.tr("Off"), "")
            self.cb_winedebug.addItem(self.tr("Quiet (-all)"), "-all")
            self.cb_winedebug.addItem(self.tr("Errors (+err)"), "+err")
            self.cb_winedebug.addItem(self.tr("Warnings (+warn,+err)"), "+warn,+err")
            self.cb_winedebug.setToolTip(self.tr("Sets WINEDEBUG for Wine/Proton output."))
            pf.addRow(self.tr("Wine Debug:"), self.cb_winedebug)
        pt_scroll = _scroll_page(pt)
        tabs.addTab(pt_scroll, self.tr("Wine / Proton"))

        if not defaults_mode:
            notes = QWidget()
            notes_layout = QVBoxLayout(notes)
            notes_layout.setContentsMargins(0, 0, 0, 0)
            self.e_notes = QPlainTextEdit()
            self.e_notes.setPlaceholderText(
                self.tr("Free-form notes, e.g. works with GE-Proton, disable FSR in menus.")
            )
            notes_layout.addWidget(self.e_notes)
            tabs.addTab(_scroll_page(notes), self.tr("Notes"))

        for box in (
            self.c_feral,
            self.c_cachy,
            self.c_gs,
            self.c_mh,
            self.c_rt,
            self.c_lu_enable,
        ):
            box.toggled.connect(self._on_feature_toggled)

        status_keys = [
            "custom_prefix",
            "custom_exe",
            "pre_hook",
            "post_hook",
            "gamemoderun",
            "game-performance",
            "gamescope",
            "mangohud",
            "rt-upscale",
            "ludusavi",
        ]
        if not defaults_mode:
            # per-game only: Steam launch options need an AppID.
            status_keys.append("steam-options")
        layout.addWidget(self._status_box(self.tr("Dependency Status"), status_keys))

        if defaults_mode:
            btns = QDialogButtonBox(QDialogButtonBox.Save | QDialogButtonBox.Cancel)
            b_factory = QPushButton(self.tr("Reset to Factory Defaults"))
            b_factory.clicked.connect(self._on_reset_factory)
            btns.addButton(b_factory, QDialogButtonBox.ResetRole)
        else:
            btns = QDialogButtonBox()
            if self.launch_mode and self.can_launch:
                b_launch = QPushButton(self.tr("Launch"))
                b_launch.setIcon(self.style().standardIcon(QStyle.StandardPixmap.SP_MediaPlay))
                b_launch.setToolTip(
                    self.tr("Discard unsaved changes and launch with the saved configuration.")
                )
                b_launch.clicked.connect(self._on_launch_without_save)
                btns.addButton(b_launch, QDialogButtonBox.ButtonRole.AcceptRole)
            btns.addButton(QDialogButtonBox.StandardButton.Save)
            if self.launch_mode and self.can_launch:
                b_save_launch = QPushButton(self.tr("Save && Launch"))
                b_save_launch.setIcon(
                    self.style().standardIcon(QStyle.StandardPixmap.SP_DialogApplyButton)
                )
                b_save_launch.setDefault(True)
                b_save_launch.clicked.connect(self._on_save_and_launch)
                btns.addButton(b_save_launch, QDialogButtonBox.ButtonRole.AcceptRole)
            b_reset = btns.addButton(
                self.tr("Reset to Global Defaults"), QDialogButtonBox.ButtonRole.ResetRole
            )
            b_reset.clicked.connect(self._on_reset)
            b_diff = btns.addButton(
                self.tr("Diff vs Defaults"), QDialogButtonBox.ButtonRole.HelpRole
            )
            b_diff.clicked.connect(self._show_diff)
            btns.addButton(QDialogButtonBox.StandardButton.Cancel)
        if self._show_preview_box():
            preview_group = QGroupBox(self.tr("Launch Command Preview"))
            preview_group.setCheckable(True)
            preview_group.setChecked(True)
            self._preview_group = preview_group
            preview_layout = QVBoxLayout(preview_group)
            preview_layout.setContentsMargins(4, 4, 4, 4)
            self._preview_edit = QPlainTextEdit()
            self._preview_edit.setReadOnly(True)
            font = QFontDatabase.systemFont(QFontDatabase.FixedFont)
            self._preview_edit.setFont(font)
            metrics = self._preview_edit.fontMetrics()
            self._preview_edit.setFixedHeight(metrics.lineSpacing() * 3 + 12)
            preview_layout.addWidget(self._preview_edit)
            preview_foot_box = QWidget()
            preview_foot = QHBoxLayout(preview_foot_box)
            preview_foot.setContentsMargins(0, 0, 0, 0)
            preview_foot.addStretch(1)
            b_refresh = QPushButton(self.tr("Refresh"))
            b_refresh.setToolTip(self.tr("Rebuild the preview from the current fields."))
            b_refresh.clicked.connect(self._refresh_preview)
            preview_foot.addWidget(b_refresh)
            preview_layout.addWidget(preview_foot_box)
            preview_group.toggled.connect(self._preview_edit.setVisible)
            preview_group.toggled.connect(preview_foot_box.setVisible)
            layout.addWidget(preview_group)
        else:
            self._preview_edit = None
            self._preview_group = None
        btns.accepted.connect(self.accept)
        btns.rejected.connect(self.reject)
        self.wrappers_summary = QLabel()
        self.wrappers_summary.setObjectName("wrappers_summary")
        self.wrappers_summary.setWordWrap(True)
        self.wrappers_summary.setToolTip(
            self.tr("Wrappers enabled by the current fields (same order as launch).")
        )
        foot = QHBoxLayout()
        foot.addWidget(self.wrappers_summary, stretch=1)
        layout.addLayout(foot)
        layout.addWidget(btns)

        self._align_label_widths(
            self.l_feral_pad,
            self.l_cachy_pad,
            self.l_gs_args,
            self.l_mh_args,
            self.l_mh_conf,
            self.l_rt_args,
        )
        self._populate()
        self._wire_preview()
        self.e_exe.textChanged.connect(self._refresh_hook_statuses)
        self.e_pre.textChanged.connect(self._refresh_hook_statuses)
        self.e_post.textChanged.connect(self._refresh_hook_statuses)
        self.e_dmode.currentTextChanged.connect(lambda _t: self._update_dip_ui())
        tabs.currentChanged.connect(self._refresh_preview)
        self._show_load_warning()
        self._refresh_display_modes()

    def _populate(self) -> None:
        self._populating = True
        try:
            self._populate_fields()
        finally:
            self._populating = False
            self._refresh_statuses()
        self._clean = copy.deepcopy(self.cfg)
        # Explicit refresh: widget signals fired mid-populate must not
        # collect (see _refresh_preview), so no incidental refresh happens.
        self._refresh_preview()

    def _populate_fields(self) -> None:
        c = self.cfg
        idx = self.cb_gametype.findData(c.general.game_type or "auto")
        self.cb_gametype.setCurrentIndex(max(idx, 0))
        if not self.defaults_mode:
            self.e_runtime.setText(self._detect_runtime_text())
        self.e_exe.setText(c.general.custom_executable)
        self.e_prefix.setText(c.general.custom_prefix)
        self.c_show_menu.setChecked(c.general.show_menu)
        self.s_menu_timeout.setValue(c.general.menu_timeout)
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
        self.e_dout.setText(c.display.output)
        self.e_dmode.setCurrentText(c.display.mode)
        idx = self.cb_dprov.findData(c.display.provider or "auto")
        self.cb_dprov.setCurrentIndex(max(idx, 0))
        self.s_dip.setValue(min(15, max(3, c.display.dip_seconds)))
        self.l_dip.setText(self.tr(f"{self.s_dip.value()} s"))
        self.c_mh.setChecked(c.mangohud.enable)
        self.e_mh_args.setText(c.mangohud.args)
        self._refresh_mangohud_configs()
        self.c_rt.setChecked(c.rtupscale.enable)
        self.e_rt_args.setText(c.rtupscale.args)
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
            return self.tr("Native (no Proton)")
        return protonmod.tool_display(self.appid)

    def focusInEvent(self, event) -> None:
        super().focusInEvent(event)
        if self.defaults_mode:
            return
        current = set(cfgmod.list_profiles(self.appid))
        if current != self._profile_names:
            self._profile_names = current
            if self._active_profile not in current:
                self._active_profile = ""
            self._refresh_profiles()

    def _refresh_profiles(self) -> None:
        self.cb_profile.blockSignals(True)
        try:
            self.cb_profile.clear()
            self.cb_profile.addItem(self.tr("(Game Defaults)"), "")
            names = cfgmod.list_profiles(self.appid)
            for name in names:
                self.cb_profile.addItem(name, name)
            idx = self.cb_profile.findData(self._active_profile)
            self.cb_profile.setCurrentIndex(idx)
            self._profile_names = set(names)
        finally:
            self.cb_profile.blockSignals(False)

    def _load_live(self) -> None:
        """Load the saved game settings (or defaults for a new game).

        Never raises on disk errors: _load_warning carries the fallback
        notice for _show_load_warning.
        """
        self.cfg, self._load_warning = cfgmod.load_with_warning(self.appid)

    def _show_load_warning(self) -> None:
        """Surface a config-fallback warning after (re)populating, if any."""
        if self._load_warning:
            QMessageBox.warning(self, "TKSteamLaunch", self._load_warning)

    def _save_active(self) -> None:
        """Collect widgets and persist to the active source.

        Profile active: the profile file carries the edits and the live
        file keeps only the selection, so Game Defaults stays pristine.
        Defaults active (or defaults mode): the live file (or the
        defaults template) carries the edits.
        """
        self._collect()
        if self.defaults_mode:
            cfgmod.save_defaults(self.cfg)
        elif self._active_profile:
            cfgmod.save_profile(self.appid, self._active_profile, self.cfg)
            live, _warn = cfgmod.load_with_warning(self.appid)
            live.general.active_profile = self._active_profile
            cfgmod.save(live)
        else:
            cfgmod.save(self.cfg)

    def _confirm_discard_changes(self) -> bool:
        """Save/Discard/Cancel prompt for unsaved edits. True = proceed."""
        if not self._is_dirty():
            return True
        box = QMessageBox(self)
        box.setWindowTitle("TKSteamLaunch")
        box.setText(self.tr("You have unsaved changes. Save them before switching?"))
        box.setStandardButtons(
            QMessageBox.StandardButton.Save
            | QMessageBox.StandardButton.Discard
            | QMessageBox.StandardButton.Cancel
        )
        box.setDefaultButton(QMessageBox.StandardButton.Save)
        answer = box.exec()
        if answer == QMessageBox.StandardButton.Save:
            self._save_active()
            return True
        return answer == QMessageBox.StandardButton.Discard

    def _read_profile(self, name: str) -> str | None:
        """Load a profile into self.cfg; return problem text or None."""
        try:
            self.cfg = cfgmod.load_profile(self.appid, name)
            self.cfg.general.appid = self.appid
        except OSError as e:
            return f"unreadable: {e}"
        except cfgmod.ConfigVersionError as e:
            return str(e)
        return cfgmod.toml_error(cfgmod.profile_file(self.appid, name))

    def _on_profile_switch(self) -> None:
        name = str(self.cb_profile.currentData() or "")
        if name == self._active_profile:
            return
        if not self._confirm_discard_changes():
            self._refresh_profiles()
            return
        self._active_profile = name
        if name:
            err = self._read_profile(name)
            self._load_warning = (
                self.tr(
                    f'The profile "{name}" could not be read: {err}\n'
                    "Showing defaults for it instead."
                )
                if err
                else None
            )
        else:
            self._load_live()
        self._populate()
        self._show_load_warning()

    def _on_profile_save(self) -> None:
        from PySide6.QtWidgets import QInputDialog

        name, ok = QInputDialog.getText(self, self.tr("Save Profile"), self.tr("Profile name:"))
        if not ok or not name.strip():
            return
        self._collect()
        cfgmod.save_profile(self.appid, name.strip(), self.cfg)
        self._active_profile = name.strip()
        self._refresh_profiles()

    def _on_profile_clone(self) -> None:
        from PySide6.QtWidgets import QInputDialog, QMessageBox

        self._refresh_profiles()
        src = str(self.cb_profile.currentData() or "")
        if src:
            try:
                cfg = cfgmod.load_profile(self.appid, src)
            except (OSError, cfgmod.ConfigVersionError) as e:
                QMessageBox.warning(
                    self, "TKSteamLaunch", self.tr(f'Profile "{src}" could not be read: {e}')
                )
                return
        else:
            go = QMessageBox.question(
                self,
                "TKSteamLaunch",
                self.tr("No profile selected — clone the current (live) settings?"),
            )
            if go != QMessageBox.StandardButton.Yes:
                return
            self._collect()
            cfg = self.cfg
        name, ok = QInputDialog.getText(
            self,
            self.tr("Clone Profile"),
            self.tr("New profile name:"),
            text=f"{src or 'live'} copy",
        )
        if not ok or not name.strip():
            return
        cfgmod.save_profile(self.appid, name.strip(), cfg)
        self._active_profile = name.strip()
        self._refresh_profiles()

    def _on_profile_delete(self) -> None:
        name = str(self.cb_profile.currentData() or "")
        if not name:
            return
        cfgmod.delete_profile(self.appid, name)
        if self._active_profile == name:
            if not self._confirm_discard_changes():
                self._refresh_profiles()
                return
            self._active_profile = ""
            self._load_live()
            self._populate()
            self._show_load_warning()
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

        names = sorted(presetsmod.PRESETS)
        labels = {n: self._preset_label(n, presetsmod.PRESETS[n]) for n in names}
        label, ok = QInputDialog.getItem(
            self,
            self.tr("Add Env Preset"),
            self.tr("Preset:"),
            [labels[n] for n in names],
            0,
            False,
        )
        if not ok or not label:
            return
        name = next(n for n in names if labels[n] == label)
        preset = presetsmod.PRESETS[name]
        mismatch = self._preset_mismatch(preset)
        if mismatch:
            answer = QMessageBox.question(
                self,
                "TKSteamLaunch",
                self.tr(f"Preset '{name}' is for {mismatch}.\nApply anyway?"),
            )
            if answer != QMessageBox.StandardButton.Yes:
                return
        vars = self._table_to_env()
        added = presetsmod.apply_preset(vars, name)
        self._set_env_table(vars)
        if not added:
            QMessageBox.information(
                self, "TKSteamLaunch", self.tr(f"Preset '{name}': all keys already present.")
            )

    @staticmethod
    def _preset_label(name: str, preset) -> str:
        tags = []
        if preset.drivers:
            tags.append("/".join(preset.drivers))
        if preset.proton:
            tags.append("/".join(preset.proton))
        if tags:
            return f"{name} [{'/'.join(tags)}]"
        return name

    def _preset_mismatch(self, preset) -> str:
        """Describe why a preset may not apply here, or '' when it fits."""
        if preset.drivers:
            vendors = gpumod.detect_vendors()
            if vendors and not (set(preset.drivers) & vendors):
                return "/".join(preset.drivers) + " GPUs"
        if preset.proton and not self.defaults_mode and self.appid:
            tool = protonmod.compat_tool_name(self.appid) or ""
            if tool and protonmod.flavor(tool) not in preset.proton:
                return "/".join(preset.proton) + " Proton"
        return ""

    def _apply_gamescope_preset(self) -> None:
        from PySide6.QtWidgets import QInputDialog

        names = sorted(ov_backend.GAMESCOPE_PRESETS)
        name, ok = QInputDialog.getItem(
            self, self.tr("Gamescope Preset"), self.tr("Preset:"), names, 0, False
        )
        if ok and name:
            self.e_gs_args.setText(ov_backend.GAMESCOPE_PRESETS[name])

    def _refresh_mangohud_configs(self) -> None:
        current = self.cfg.mangohud.config_file
        self.cb_mh_conf.clear()
        self.cb_mh_conf.addItem(self.tr("Default (MangoHud.conf)"), "")
        for name in ov_backend.list_mangohud_configs():
            if name == ov_backend.DEFAULT_MANGOHUD_CONF:
                continue
            self.cb_mh_conf.addItem(name, name)
        idx = self.cb_mh_conf.findData(current)
        self.cb_mh_conf.setCurrentIndex(max(idx, 0))

    def _new_mangohud_config(self) -> None:
        from PySide6.QtWidgets import QInputDialog

        name, ok = QInputDialog.getText(
            self, self.tr("New MangoHud Configuration"), self.tr("File name:")
        )
        if not ok or not name.strip():
            return
        choices = {
            self.tr("Copy of MangoHud.conf"): "default",
            self.tr("Minimal overlay"): "minimal",
            self.tr("FPS limiter overlay"): "fps-cap",
            self.tr("Full metrics overlay"): "full",
            self.tr("Empty file"): "empty",
        }
        label, ok = QInputDialog.getItem(
            self,
            self.tr("New MangoHud Configuration"),
            self.tr("Start from:"),
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
            QMessageBox.information(self, "TKSteamLaunch", self.tr(f"{path.name} already exists."))
        self._refresh_mangohud_configs()
        idx = self.cb_mh_conf.findData(path.name)
        if idx >= 0:
            self.cb_mh_conf.setCurrentIndex(idx)
        if not open_path(str(path)):
            QMessageBox.warning(self, "TKSteamLaunch", self.tr(f"Could not open {path}."))

    def _open_log(self) -> None:
        if not open_path(self.e_log.text()):
            QMessageBox.warning(self, "TKSteamLaunch", self.tr("Could not open the log file."))

    def _open_proton_log(self) -> None:
        from ..launcher import proton_log_dir

        if not open_path(str(proton_log_dir(self.appid))):
            QMessageBox.warning(
                self, "TKSteamLaunch", self.tr("Could not open the Proton log folder.")
            )

    def _on_reset_factory(self) -> None:
        # In-memory only: the file changes on Save, Cancel discards everything.
        self.cfg = cfgmod.GameConfig()
        self._populate()

    def reject(self) -> None:
        self._stop_coverage_worker()
        self._stop_dmode_worker()
        super().reject()

    def closeEvent(self, event) -> None:
        # close() bypasses reject(): stop workers here too, never
        # destroy a running QThread (aborts) at teardown.
        self._stop_coverage_worker()
        self._stop_dmode_worker()
        super().closeEvent(event)

    def _on_reset(self) -> None:
        """Reset the game to the Global Defaults template, persisting now.

        Unlike other edits, Reset writes the live file immediately: a
        staged reset that Cancel silently discards proved too easy to
        mistake for applied. Profiles are never touched. Cancel leaves
        widgets and files exactly as they were.
        """
        if self._active_profile:
            detail = self.tr(
                f'Unsaved changes to profile "{self._active_profile}" will be '
                "discarded (the saved profile is kept)."
            )
        elif self._is_dirty():
            detail = self.tr("Unsaved changes will be discarded.")
        else:
            detail = self.tr("This overwrites the saved game config.")
        answer = QMessageBox.question(
            self,
            "TKSteamLaunch",
            self.tr("Reset this game to the Global Defaults template now?\n") + detail,
            QMessageBox.StandardButton.Reset | QMessageBox.StandardButton.Cancel,
            QMessageBox.StandardButton.Cancel,
        )
        if answer != QMessageBox.StandardButton.Reset:
            return
        self._cov_run += 1  # invalidate any in-flight coverage result
        self.cfg = cfgmod.load_defaults()
        self.cfg.general.appid = self.appid
        self._active_profile = ""
        self._load_warning = None
        self._populate()
        self._refresh_profiles()
        cfgmod.save(self.cfg)

    def _show_diff(self) -> None:
        self._collect()
        diff = cfgmod.diff_vs_defaults(self.cfg)
        dlg = QDialog(self)
        dlg.setWindowTitle(self.tr("Differences from Global Defaults"))
        dlg.resize(640, 480)
        layout = QVBoxLayout(dlg)
        edit = QPlainTextEdit(diff or self.tr("(no differences)"))
        edit.setReadOnly(True)
        edit.setFont(QFontDatabase.systemFont(QFontDatabase.FixedFont))
        layout.addWidget(edit)
        btns = QDialogButtonBox(QDialogButtonBox.Close)
        btns.rejected.connect(dlg.reject)
        layout.addWidget(btns)
        dlg.exec()

    def _on_save_and_launch(self) -> None:
        self.launch_requested = True
        self.accept()

    def _show_preview_box(self) -> bool:
        try:
            return bool(cfgmod.load_preferences().show_preview)
        except Exception:
            return True

    def _refresh_display_modes(self) -> None:
        """(Re)query offered modes in the background; manual entry always works."""
        self._dmode_run += 1
        run = self._dmode_run
        worker = _DisplayModesWorker(
            str(self.cb_dprov.currentData() or "auto"),
            self.e_dout.text().strip(),
            run,
            parent=self,
        )
        worker.done.connect(self._on_display_modes)
        worker.finished.connect(worker.deleteLater)
        self._dmode_thread = worker
        worker.start()

    def _on_display_modes(self, run: int, modes: list) -> None:
        self._dmode_thread = None
        if run != self._dmode_run:
            return  # stale result (e.g. output changed mid-query)
        current = self.e_dmode.currentData() or self.e_dmode.currentText()
        self._dmode_current = None
        self.e_dmode.blockSignals(True)
        try:
            self.e_dmode.clear()
            self.e_dmode.addItem("")
            for entry in modes:
                # Tolerate legacy plain-string items; never blow up in the
                # event loop on a malformed worker result.
                if isinstance(entry, str):
                    num, text, is_current = None, entry, False
                else:
                    num, text, is_current = entry
                if is_current:
                    self._dmode_current = text
                if num is None:
                    self.e_dmode.addItem(text, text)
                elif is_current:
                    self.e_dmode.addItem(f"{num}: {text} ★", text)
                else:
                    self.e_dmode.addItem(f"{num}: {text}", text)
        finally:
            self.e_dmode.blockSignals(False)
        self.e_dmode.setCurrentText(str(current or ""))
        self._update_dip_ui()

    def _update_dip_ui(self) -> None:
        """Show dip note + slider only when requesting the current mode."""
        from ..backends import display as dispmod

        value = str(self.e_dmode.currentData() or self.e_dmode.currentText() or "").strip()
        show = False
        if value and self._dmode_current:
            want = dispmod.parse_mode(value)
            cur = dispmod.parse_mode(self._dmode_current)
            show = (
                want is not None
                and cur is not None
                and want[0] == cur[0]
                and want[1] == cur[1]
                and (want[2] is None or abs(want[2] - cur[2]) < 1.0)
            )
        self._dip_note.setVisible(show)
        self._dip_row.setVisible(show)

    def _refresh_preview(self) -> None:
        # Never collect mid-populate: later fields still hold stale widget
        # values, so collecting now would clobber cfg and the populate
        # would copy the stale values back ("reset changes nothing").
        if getattr(self, "_populating", False):
            return
        self._collect()
        try:
            from ..launcher import active_wrappers, build_final_command

            wrappers = active_wrappers(self.cfg)
        except Exception:
            wrappers = []
        if wrappers:
            self.wrappers_summary.setText(self.tr(f"Will launch with: {' · '.join(wrappers)}"))
        else:
            self.wrappers_summary.setText(self.tr("No wrappers enabled"))
        if self._preview_edit is None:
            return
        try:
            cmd, _env, warnings = build_final_command(self.cfg, ["%command%"])
        except Exception as e:  # never break the dialog on preview
            self._preview_edit.setPlainText(self.tr(f"(preview unavailable: {e})"))
            return
        lines = [shlex.join(cmd) if cmd else self.tr("(empty command)")]
        lines += [self.tr(f"# warning: {w}") for w in warnings]
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
            "covered": self.tr(f"Ludusavi covers this game.\n{detail}"),
            "no-local-saves": self.tr(f"Manifest entry exists, but no saves found.\n{detail}"),
            "no-entry": self.tr(
                "No manifest entry for this game.\n"
                "Add a custom game entry in Ludusavi to enable backups."
            ),
            "unavailable": self.tr(f"Could not check coverage:\n{detail}"),
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
        """Two-column box holding per-binary status lines."""
        from PySide6.QtWidgets import QGridLayout

        box = QGroupBox(title)
        outer = QVBoxLayout(box)
        outer.setContentsMargins(4, 4, 4, 4)
        frame = QFrame()
        frame.setFrameShape(QFrame.Shape.StyledPanel)
        frame.setFrameShadow(QFrame.Shadow.Sunken)
        inner = QGridLayout(frame)
        inner.setContentsMargins(8, 6, 8, 6)
        self._status_grid = inner
        self._status_grid = inner
        for i, key in enumerate(keys):
            label = QLabel()
            label.setTextFormat(Qt.TextFormat.RichText)
            label.setWordWrap(True)
            label.linkActivated.connect(self._on_status_link)
            inner.addWidget(label, i // 2, i % 2)
            self._status_labels[key] = label
        outer.addWidget(frame)
        return box

    def _reflow_status_grid(self) -> None:
        """Pack visible labels first so blanks always land at the end."""
        grid = getattr(self, "_status_grid", None)
        if grid is None:
            return
        order = [
            "custom_prefix",
            "custom_exe",
            "pre_hook",
            "post_hook",
            "gamemoderun",
            "game-performance",
            "gamescope",
            "mangohud",
            "rt-upscale",
            "ludusavi",
            "steam-options",
        ]
        visible = [
            self._status_labels[k]
            for k in order
            if k in self._status_labels and not self._status_labels[k].isHidden()
        ]
        for label in list(self._status_labels.values()):
            grid.removeWidget(label)
        for i, label in enumerate(visible):
            grid.addWidget(label, i // 2, i % 2)

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

    def _on_status_link(self, target: str) -> None:
        """Open-folder links inside status lines (never break the dialog)."""
        try:
            open_path(target)
        except Exception:
            pass

    def _set_status_link(self, key: str, kind: str, text: str, link_dir: str) -> None:
        """Status line with an Open-folder link; the dir itself is escaped."""
        import html

        label = self._status_labels.get(key)
        if label is None:
            return
        colors = _STATUS_COLORS_DARK if self._dark else _STATUS_COLORS_LIGHT
        mark = _STATUS_MARKS.get(kind, "●")
        color = colors.get(kind, colors["note"])
        label.setText(
            f'<span style="color:{color}; font-weight:bold;">{mark}</span> '
            f'{html.escape(text)} (<a href="{html.escape(link_dir)}">{self.tr("Open folder")}</a>)'
        )
        label.setVisible(True)

    def _refresh_hook_statuses(self) -> None:
        """Live custom-exe/hook path checks with actionable Open-folder links."""
        for key, field in (
            ("custom_exe", self.e_exe),
            ("pre_hook", self.e_pre),
            ("post_hook", self.e_post),
        ):
            label = self._status_labels.get(key)
            if label is None:
                continue
            command = field.text().strip()
            if not command:
                label.setVisible(False)
                continue
            try:
                first = shlex.split(command, posix=True)[0]
            except (ValueError, IndexError):
                first = command.split(maxsplit=1)[0]
            if os.path.exists(os.path.expanduser(first)) or shutil.which(first):
                label.setVisible(True)
                self._set_status(key, "ok", self.tr(f"{key.replace('_', '-')}: {first}"))
                continue
            parent = os.path.dirname(os.path.expanduser(first)) or "."
            label.setVisible(True)
            if os.path.isdir(parent):
                self._set_status_link(
                    key, "warn", self.tr(f"{key.replace('_', '-')} not found: {first}"), parent
                )
            else:
                self._set_status(
                    key, "warn", self.tr(f"{key.replace('_', '-')} not found: {first}")
                )
        self._reflow_status_grid()

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
        self._set_status("rt-upscale", *_binary_status("upscale", self.c_rt.isChecked()))
        self._refresh_ludusavi_status()
        self._update_prefix_status()
        self._refresh_hook_statuses()
        self._refresh_steam_status()
        self._reflow_status_grid()

    def _refresh_steam_status(self) -> None:
        from .. import steam as steammod

        if self.defaults_mode or not self.appid:
            self._set_status(
                "steam-options", "note", self.tr("Steam options: n/a for global defaults")
            )
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
                checkbox.setToolTip(self.tr(f"{binary} not installed — option skipped at launch."))
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
                self.tr(f"ludusavi via Flatpak ({exe}) — may not see Proton prefixes"),
            )
        else:
            self._set_status("ludusavi", *_binary_status("ludusavi", on))

    def _update_prefix_status(self) -> None:
        prefix = self.e_prefix.text().strip()
        if not prefix:
            self._set_status(
                "custom_prefix", "ok", self.tr("No custom prefix — game launches directly")
            )
            return
        parts = split_args(prefix)
        if not parts:
            return
        self._set_status(
            "custom_prefix",
            *_binary_status(parts[0], True, skip_note=self.tr("launch will fail")),
        )

    def _collect_into(self, cfg) -> None:
        cfg.general.game_type = str(self.cb_gametype.currentData() or "auto")
        cfg.general.custom_executable = self.e_exe.text().strip()
        cfg.general.custom_prefix = self.e_prefix.text().strip()
        cfg.general.show_menu = self.c_show_menu.isChecked()
        if not self.defaults_mode:
            cfg.general.active_profile = self._active_profile
        cfg.general.menu_timeout = int(self.s_menu_timeout.value())
        cfg.notifications.notify_on_launch = self.c_notify.isChecked()
        cfg.session.inhibit_idle = self.c_inhibit.isChecked()
        cfg.proton.fresh_prefix = self.c_fresh.isChecked()
        cfg.proton.winetricks_verbs = split_args(self.e_verbs.text())
        cfg.env.vars = self._table_to_env()
        cfg.pre_post.pre_command = self.e_pre.text().strip()
        cfg.pre_post.pre_args = split_args(self.e_pre_args.text())
        cfg.pre_post.post_command = self.e_post.text().strip()
        cfg.pre_post.post_args = split_args(self.e_post_args.text())
        cfg.pre_post.timeout = int(self.s_timeout.value())
        cfg.pre_post.run_in_shell = bool(self.c_shell.isChecked())
        cfg.gamemode.feral_gamemode = self.c_feral.isChecked()
        cfg.gamemode.cachyos_game_performance = self.c_cachy.isChecked()
        cfg.gamescope.enable = self.c_gs.isChecked()
        cfg.gamescope.args = self.e_gs_args.text().strip()
        cfg.display.output = self.e_dout.text().strip()
        cfg.display.mode = str(
            self.e_dmode.currentData() or self.e_dmode.currentText() or ""
        ).strip()
        cfg.display.provider = str(self.cb_dprov.currentData() or "auto")
        cfg.display.dip_seconds = int(self.s_dip.value())
        cfg.mangohud.enable = self.c_mh.isChecked()
        cfg.mangohud.args = self.e_mh_args.text().strip()
        cfg.mangohud.config_file = str(self.cb_mh_conf.currentData() or "")
        cfg.rtupscale.enable = self.c_rt.isChecked()
        cfg.rtupscale.args = self.e_rt_args.text().strip()
        cfg.ludusavi.enable = self.c_lu_enable.isChecked()
        cfg.ludusavi.restore = self.c_restore.isChecked()
        cfg.ludusavi.backup = self.c_backup.isChecked()
        cfg.ludusavi.name_override = self.e_luname.text().strip()
        cfg.ludusavi.use_gui = self.c_lugui.isChecked()
        cfg.nightlight.disable_during_game = self.c_nl.isChecked()
        cfg.nightlight.provider = str(self.cb_nl.currentData() or "auto")
        if not self.defaults_mode:
            cfg.notes.text = self.e_notes.toPlainText()
            cfg.debug.proton_log = self.c_protonlog.isChecked()
            cfg.debug.winedebug = str(self.cb_winedebug.currentData() or "")

    def _collect(self) -> None:
        self._collect_into(self.cfg)

    def _is_dirty(self) -> bool:
        """True when the widgets differ from the last populated state."""
        if getattr(self, "_clean", None) is None:
            return False
        probe = copy.deepcopy(self._clean)
        self._collect_into(probe)
        # Selection memory is not a user edit: profiles strip it on save.
        probe.general.active_profile = self._clean.general.active_profile
        return cfgmod.to_toml_dict(probe) != cfgmod.to_toml_dict(self._clean)

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

    def _stop_dmode_worker(self) -> None:
        # Never destroy a running QThread (aborts): same stop-and-wait
        # discipline as the coverage worker.
        worker, self._dmode_thread = self._dmode_thread, None
        self._dmode_run += 1  # invalidate any result still queued
        if worker is not None and worker.isRunning():
            worker.requestInterruption()
            worker.wait(3000)
            if worker.isRunning():
                worker.terminate()
                worker.wait(2000)

    def _on_launch_without_save(self) -> None:
        self.launch_requested = True
        self._skip_save = True
        self.accept()

    def accept(self) -> None:
        self._stop_coverage_worker()
        self._stop_dmode_worker()
        if not self._skip_save:
            self._save_active()
        super().accept()
