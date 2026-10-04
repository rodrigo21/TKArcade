"""Pre-launch menu dialog: Launch / Settings / Cancel.

Shown by the --menu flow (and show_menu configs). Settings opens the
regular game editor modally; coming back to the menu, Launch still
proceeds and Cancel still aborts. File writes only happen via Save
inside Settings or via the launcher after Launch.
"""

from __future__ import annotations

from PySide6.QtCore import QSize, Qt, QTimer
from PySide6.QtGui import QIcon, QPixmap
from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QHBoxLayout,
    QLabel,
    QStyle,
    QVBoxLayout,
)


class MenuDialog(QDialog):
    def __init__(
        self,
        parent,
        appid: str = "",
        name: str = "",
        can_launch: bool = True,
        timeout: int = 0,
    ) -> None:
        from .. import artwork as artmod
        from .. import proton as protonmod

        super().__init__(parent)
        self.appid = appid
        self.name = name
        self.launch_requested = False
        self._remaining = max(0, int(timeout or 0))
        self.setWindowTitle(f"TKSteamLaunch — {name or appid or 'game'}")
        self.setMinimumWidth(480)

        layout = QVBoxLayout(self)
        head = QHBoxLayout()
        icon_label = QLabel()
        pixmap = QPixmap(str(artmod.resolve_icon(appid, landscape=True))) if appid else QPixmap()
        if pixmap.isNull():
            icon_label.setPixmap(
                self.style().standardIcon(QStyle.StandardPixmap.SP_MediaPlay).pixmap(QSize(96, 96))
            )
        else:
            icon_label.setPixmap(
                pixmap.scaled(
                    QSize(96, 64),
                    Qt.AspectRatioMode.KeepAspectRatio,
                    Qt.TransformationMode.SmoothTransformation,
                )
            )
        head.addWidget(icon_label)
        info_lines = [f"{name} ({appid})" if name and appid else (name or appid or "—")]
        info_lines.append(f"Proton: {protonmod.tool_display(appid) if appid else '—'}")
        extra = self._detail_lines()
        if extra:
            info_lines.append(extra)
        self._count_label = QLabel()
        self._count_label.setVisible(False)
        info = QLabel("\n".join(info_lines))
        info.setWordWrap(True)
        head.addWidget(info, stretch=1)
        layout.addLayout(head)
        layout.addWidget(self._count_label)

        btns = QDialogButtonBox()
        btns.setCenterButtons(True)
        self.b_launch = btns.addButton("Launch", QDialogButtonBox.ButtonRole.AcceptRole)
        self.b_launch.setIcon(self.style().standardIcon(QStyle.StandardPixmap.SP_MediaPlay))
        if can_launch:
            self.b_launch.setDefault(True)
        b_settings = btns.addButton("Settings...", QDialogButtonBox.ButtonRole.ActionRole)
        b_settings.setIcon(QIcon.fromTheme("configure"))
        if b_settings.icon().isNull():
            b_settings.setIcon(self.style().standardIcon(QStyle.StandardPixmap.SP_DialogOpenButton))
        b_settings.clicked.connect(self._open_settings)
        btns.addButton(QDialogButtonBox.StandardButton.Cancel)
        btns.rejected.connect(self.reject)
        if not can_launch:
            self.b_launch.setEnabled(False)
            self.b_launch.setToolTip("No game command to run")
        self.b_launch.clicked.connect(self._on_launch)
        layout.addWidget(btns)

        self._timer = QTimer(self)
        self._timer.setInterval(1000)
        self._timer.timeout.connect(self._tick)
        if self._remaining > 0 and can_launch:
            self._update_countdown()
            self._timer.start()

    def _detail_lines(self) -> str:
        """Playtime + active wrappers, both instant and local."""
        from .. import config as cfgmod
        from .. import history as histmod
        from .. import xdg
        from ..backends import notify as notify_backend
        from ..launcher import active_wrappers

        parts = []
        try:
            sessions = histmod.parse_log(xdg.log_file())
            stats = histmod.summarize(sessions).get(self.appid or "")
            if stats is not None and stats.runs:
                parts.append(
                    f"Played {notify_backend.format_duration(stats.total_dur)} "
                    f"over {stats.runs} session(s)"
                )
        except Exception:
            pass
        try:
            if self.appid:
                wrappers = active_wrappers(cfgmod.load_effective(self.appid))
                if wrappers:
                    parts.append(" · ".join(wrappers))
        except Exception:
            pass
        return "\n".join(parts)

    def _update_countdown(self) -> None:
        self._count_label.setVisible(self._remaining > 0)
        self._count_label.setText(f"Launching in {self._remaining}…" if self._remaining > 0 else "")

    def _tick(self) -> None:
        self._remaining -= 1
        if self._remaining <= 0:
            self._timer.stop()
            self._on_launch()
            return
        self._update_countdown()

    def _stop_countdown(self) -> None:
        self._timer.stop()
        self._remaining = 0
        self._update_countdown()

    def _on_launch(self) -> None:
        self._stop_countdown()
        self.launch_requested = True
        self.accept()

    def _open_settings(self) -> None:
        from .game_dialog import GameDialog

        self._stop_countdown()
        dlg = GameDialog(self, self.appid, self.name, launch_mode=False)
        dlg.exec()

    def reject(self) -> None:
        self._stop_countdown()
        super().reject()
