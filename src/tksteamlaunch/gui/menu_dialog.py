"""Pre-launch menu dialog: Launch / Settings / Cancel.

Shown by the --menu flow (and show_menu configs). Settings opens the
regular game editor modally; coming back to the menu, Launch still
proceeds and Cancel still aborts. File writes only happen via Save
inside Settings or via the launcher after Launch.
"""

from __future__ import annotations

from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QLabel,
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
        super().__init__(parent)
        self.appid = appid
        self.launch_requested = False
        title = f"TKSteamLaunch — {name} ({appid})" if name else f"TKSteamLaunch ({appid})"
        self.setWindowTitle(title)

        layout = QVBoxLayout(self)
        info = QLabel(f"Game: {name or appid}\nApp ID: {appid or '—'}")
        layout.addWidget(info)

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

        dlg = GameDialog(self, self.appid, "", launch_mode=False)
        dlg.exec()
