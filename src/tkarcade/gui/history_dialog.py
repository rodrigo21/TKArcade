"""Session history dialog (reads the global launcher.log)."""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QHeaderView,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
)

from .. import history as histmod
from .. import steam as steammod
from .. import xdg
from ..backends.notify import format_duration


class HistoryDialog(QDialog):
    def __init__(self, parent) -> None:
        super().__init__(parent)
        self.setWindowTitle(self.tr("Session History"))
        self.resize(640, 400)
        layout = QVBoxLayout(self)
        table = QTableWidget(0, 5)
        table.setHorizontalHeaderLabels(
            [
                self.tr("Game"),
                self.tr("Last played"),
                self.tr("Sessions"),
                self.tr("Total time"),
                self.tr("Failures"),
            ]
        )
        table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        table.setEditTriggers(QTableWidget.NoEditTriggers)
        self._table = table
        layout.addWidget(table)
        self._reload()
        btns = QDialogButtonBox(QDialogButtonBox.Close)
        btns.rejected.connect(self.reject)
        clear = btns.addButton(
            self.tr("Clear History..."), QDialogButtonBox.ButtonRole.DestructiveRole
        )
        clear.clicked.connect(self._clear)
        clear_sel = btns.addButton(
            self.tr("Clear Selected"), QDialogButtonBox.ButtonRole.ActionRole
        )
        clear_sel.clicked.connect(self._clear_selected)
        layout.addWidget(btns)

    def _reload(self) -> None:
        """Rebuild the table from the current log file."""
        table = self._table
        names = {a: n for a, n in steammod.list_games()}
        stats = histmod.summarize(histmod.parse_log(xdg.log_file()))
        rows = sorted(stats.values(), key=lambda s: s.last, reverse=True)
        table.setRowCount(len(rows))
        for row, s in enumerate(rows):
            name_item = QTableWidgetItem(names.get(s.appid, s.appid))
            name_item.setData(Qt.ItemDataRole.UserRole, s.appid)
            table.setItem(row, 0, name_item)
            table.setItem(row, 1, QTableWidgetItem(s.last.replace("T", " ")))
            table.setItem(row, 2, QTableWidgetItem(str(s.runs)))
            table.setItem(row, 3, QTableWidgetItem(format_duration(s.total_dur)))
            table.setItem(row, 4, QTableWidgetItem(str(s.fails)))

    def _appid_for_row(self, row: int) -> str:
        item = self._table.item(row, 0)
        return str((item.data(Qt.ItemDataRole.UserRole) if item else "") or "")

    def _clear_selected(self) -> None:
        """Drop history of the selected rows after confirmation."""
        from PySide6.QtWidgets import QMessageBox

        rows = sorted({i.row() for i in self._table.selectedItems()})
        appids = []
        for row in rows:
            appid = self._appid_for_row(row)
            if appid and appid not in appids:
                appids.append(appid)
        if not appids:
            return
        answer = QMessageBox.question(
            self,
            "TKArcade",
            self.tr(f"Clear history for {len(appids)} game(s)? This cannot be undone."),
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if answer != QMessageBox.StandardButton.Yes:
            return
        for appid in appids:
            try:
                histmod.clear_appid(xdg.log_file(), appid)
            except Exception as e:
                QMessageBox.warning(self, "TKArcade", f"{appid}: {e}")
                return
        self._reload()

    def _clear(self) -> None:
        """Truncate the session log after confirmation, then refresh."""
        from PySide6.QtWidgets import QMessageBox

        answer = QMessageBox.question(
            self,
            "TKArcade",
            self.tr("Clear all session history? This cannot be undone."),
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if answer != QMessageBox.StandardButton.Yes:
            return
        try:
            xdg.log_file().write_text("", encoding="utf-8")
        except OSError as e:
            QMessageBox.warning(self, "TKArcade", self.tr(f"Could not clear history: {e}"))
            return
        self._reload()
