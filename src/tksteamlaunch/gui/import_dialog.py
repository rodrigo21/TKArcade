"""Import entry points: TKSteamLaunch exports or SteamTinkerLaunch configs."""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
)

from .. import config as cfgmod
from .. import stl_import as sti


class ImportChooserDialog(QDialog):
    """Pick an import source. Returns 1 (export file) or 2 (STL)."""

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle(self.tr("Import Configurations"))
        layout = QVBoxLayout(self)
        layout.addWidget(QLabel(self.tr("Import configurations from:")))
        row = QHBoxLayout()
        b_export = QPushButton(self.tr("TKSteamLaunch Export..."))
        b_export.setToolTip(self.tr("A tarball created by Export..."))
        b_export.clicked.connect(lambda: self.done(1))
        b_stl = QPushButton(self.tr("SteamTinkerLaunch..."))
        b_stl.setToolTip(self.tr("Per-game configs as a steamtinkerlaunch profile"))
        b_stl.clicked.connect(lambda: self.done(2))
        row.addWidget(b_export)
        row.addWidget(b_stl)
        layout.addLayout(row)
        btns = QDialogButtonBox(QDialogButtonBox.Cancel)
        btns.rejected.connect(self.reject)
        layout.addWidget(btns)


def usage_notice(imported: list[str], skipped: list[str]) -> str:
    """Explain where imports landed. Pure function (tested)."""
    from PySide6.QtCore import QCoreApplication

    tr = lambda s: QCoreApplication.translate("import_dialog", s)  # noqa: E731
    lines = []
    if imported:
        lines.append(tr("Imported as the 'steamtinkerlaunch' profile (live config untouched):"))
        lines += [f"  • {appid}" for appid in imported]
        lines.append(tr("Open the game, pick the profile in the Profile row to try it."))
    if skipped:
        lines.append(tr("Skipped (no STL config found):"))
        lines += [f"  • {appid}" for appid in skipped]
    return "\n".join(lines)


class StlImportDialog(QDialog):
    """Table of configured games that also have an STL config."""

    def __init__(self, parent, games: list[tuple[str, str]]) -> None:
        super().__init__(parent)
        self.setWindowTitle(self.tr("Import from SteamTinkerLaunch"))
        self.resize(520, 380)
        self._games = sorted(games, key=lambda g: g[1].lower())
        layout = QVBoxLayout(self)
        if not self._games:
            layout.addWidget(QLabel(self.tr("No configured game has an STL config.")))
        self.table = QTableWidget(len(self._games), 3)
        self.table.setHorizontalHeaderLabels(
            [self.tr("Import"), self.tr("Game"), self.tr("App ID")]
        )
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QTableWidget.SelectionMode.ExtendedSelection)
        for row, (appid, name) in enumerate(self._games):
            check = QTableWidgetItem()
            check.setFlags(check.flags() | Qt.ItemFlag.ItemIsUserCheckable)
            check.setCheckState(Qt.CheckState.Checked)
            self.table.setItem(row, 0, check)
            self.table.setItem(row, 1, QTableWidgetItem(name))
            self.table.setItem(row, 2, QTableWidgetItem(appid))
        self.table.resizeColumnsToContents()
        layout.addWidget(self.table, stretch=1)
        row = QHBoxLayout()
        b_all = QPushButton(self.tr("Select All"))
        b_all.clicked.connect(lambda: self._set_all(Qt.CheckState.Checked))
        b_none = QPushButton(self.tr("Select None"))
        b_none.clicked.connect(lambda: self._set_all(Qt.CheckState.Unchecked))
        b_import = QPushButton(self.tr("Import from SteamTinkerLaunch"))
        b_import.setDefault(True)
        b_import.clicked.connect(self._do_import)
        row.addWidget(b_all)
        row.addWidget(b_none)
        row.addStretch(1)
        row.addWidget(b_import)
        layout.addLayout(row)

    def _set_all(self, state: Qt.CheckState) -> None:
        for row in range(self.table.rowCount()):
            item = self.table.item(row, 0)
            if item is not None:
                item.setCheckState(state)

    def _checked_appids(self) -> list[str]:
        out = []
        for row in range(self.table.rowCount()):
            item = self.table.item(row, 0)
            name_item = self.table.item(row, 1)
            if item is not None and item.checkState() == Qt.CheckState.Checked:
                appid_item = self.table.item(row, 2)
                if appid_item is not None:
                    out.append(appid_item.text())
                elif name_item is not None:
                    out.append(name_item.text())
        return out

    def _do_import(self) -> None:
        imported, skipped = [], []
        reports: dict[str, list[str]] = {}
        for appid in self._checked_appids():
            raw = sti.parse_stl_conf(sti.stl_config_dir() / "gamecfgs" / "id" / f"{appid}.conf")
            if not raw:
                skipped.append(appid)
                continue
            cfg, report = sti.map_to_gameconfig(appid, raw)
            try:
                cfgmod.save_profile(appid, sti.PROFILE_NAME, cfg)
            except Exception as e:
                skipped.append(appid)
                reports[appid] = [f"save failed: {e}"]
                continue
            imported.append(appid)
            if report:
                reports[appid] = report
        text = usage_notice(imported, skipped)
        details = "\n".join(f"{a}: {'; '.join(r)}" for a, r in reports.items() if r)
        if details:
            text += "\n\n" + self.tr("Notes:") + "\n" + details
        QMessageBox.information(self, "TKSteamLaunch", text or self.tr("Nothing selected."))
        self.accept()
