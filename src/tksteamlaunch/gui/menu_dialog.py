"""Pre-launch menu dialog: Launch / Settings / Cancel.

Shown by the --menu flow (and show_menu configs). Settings opens the
regular game editor modally; coming back to the menu, Launch still
proceeds and Cancel still aborts. File writes only happen via Save
inside Settings or via the launcher after Launch.
"""

from __future__ import annotations

from PySide6.QtCore import QSize, Qt
from PySide6.QtGui import QPixmap
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
    ) -> None:
        from .. import artwork as artmod
        from .. import proton as protonmod

        super().__init__(parent)
        self.appid = appid
        self.name = name
        self.launch_requested = False
        self.setWindowTitle(f"TKSteamLaunch — {name or appid or 'game'}")
        self.setMinimumWidth(440)

        layout = QVBoxLayout(self)
        head = QHBoxLayout()
        icon_label = QLabel()
        pixmap = QPixmap(str(artmod.resolve_icon(appid))) if appid else QPixmap()
        if pixmap.isNull():
            icon_label.setPixmap(
                self.style().standardIcon(QStyle.StandardPixmap.SP_MediaPlay).pixmap(QSize(64, 64))
            )
        else:
            icon_label.setPixmap(
                pixmap.scaled(
                    QSize(64, 64),
                    Qt.AspectRatioMode.KeepAspectRatio,
                    Qt.TransformationMode.SmoothTransformation,
                )
            )
        head.addWidget(icon_label)
        info = QLabel(
            f"Game: {name or appid or '—'}\n"
            f"App ID: {appid or '—'}\n"
            f"Proton: {protonmod.tool_display(appid) if appid else '—'}"
        )
        info.setWordWrap(True)
        head.addWidget(info, stretch=1)
        layout.addLayout(head)

        btns = QDialogButtonBox()
        self.b_launch = btns.addButton("Launch", QDialogButtonBox.ButtonRole.AcceptRole)
        if can_launch:
            self.b_launch.setDefault(True)
        b_settings = btns.addButton("Settings...", QDialogButtonBox.ButtonRole.ActionRole)
        b_settings.clicked.connect(self._open_settings)
        btns.addButton(QDialogButtonBox.StandardButton.Cancel)
        btns.rejected.connect(self.reject)
        if not can_launch:
            self.b_launch.setEnabled(False)
            self.b_launch.setToolTip("No game command to run")
        self.b_launch.clicked.connect(self._on_launch)
        layout.addWidget(btns)

    def _on_launch(self) -> None:
        self.launch_requested = True
        self.accept()

    def _open_settings(self) -> None:
        from .game_dialog import GameDialog

        dlg = GameDialog(self, self.appid, self.name, launch_mode=False)
        dlg.exec()
