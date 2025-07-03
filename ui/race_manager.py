from typing import List
from datetime import datetime
from PyQt5.QtCore import Qt, pyqtSignal
from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QTableWidget, QTableWidgetItem,
    QPushButton, QFileDialog, QLineEdit, QLabel, QDateEdit
)

from db.db_manager import DBManager


class RaceManagerWindow(QWidget):
    race_selected = pyqtSignal(int)

    def __init__(self, db_manager: DBManager):
        super().__init__()
        self.db = db_manager
        self.setWindowTitle("Bases Importadas")
        self.resize(600, 400)
        self._setup_ui()
        self.refresh()

    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)

        self.table = QTableWidget()
        self.table.setColumnCount(5)
        self.table.setHorizontalHeaderLabels([
            "Nome", "Data", "Corredores", "Imagens", "Categorias"
        ])
        self.table.cellDoubleClicked.connect(self._open_selected)
        layout.addWidget(self.table)

        btn_row = QHBoxLayout()
        self.delete_btn = QPushButton("Deletar")
        self.delete_btn.clicked.connect(self._delete_selected)
        btn_row.addWidget(self.delete_btn)

        self.export_json_btn = QPushButton("Exportar JSON")
        self.export_json_btn.clicked.connect(self._export_json)
        btn_row.addWidget(self.export_json_btn)

        self.export_csv_btn = QPushButton("Exportar CSV")
        self.export_csv_btn.clicked.connect(self._export_csv)
        btn_row.addWidget(self.export_csv_btn)

        layout.addLayout(btn_row)

        # Add new race section
        form_row = QHBoxLayout()
        self.name_edit = QLineEdit()
        self.name_edit.setPlaceholderText("Nome da Prova")
        form_row.addWidget(self.name_edit)

        self.loc_edit = QLineEdit()
        self.loc_edit.setPlaceholderText("Local")
        form_row.addWidget(self.loc_edit)

        self.date_edit = QDateEdit()
        self.date_edit.setCalendarPopup(True)
        self.date_edit.setDate(datetime.now())
        form_row.addWidget(self.date_edit)

        self.json_path = QLineEdit()
        self.json_path.setPlaceholderText("JSON...")
        form_row.addWidget(self.json_path)
        browse = QPushButton("Selecionar")
        browse.clicked.connect(self._select_json)
        form_row.addWidget(browse)

        add_btn = QPushButton("Adicionar")
        add_btn.clicked.connect(self._add_race)
        form_row.addWidget(add_btn)

        layout.addLayout(form_row)

    def refresh(self) -> None:
        races = self.db.list_races()
        self.table.setRowCount(len(races))
        for row, race in enumerate(races):
            self.table.setItem(row, 0, QTableWidgetItem(race["name"]))
            self.table.setItem(row, 1, QTableWidgetItem(race["date"]))
            self.table.setItem(row, 2, QTableWidgetItem(str(race["num_participants"])))
            self.table.setItem(row, 3, QTableWidgetItem(str(race["num_images"])))
            self.table.setItem(row, 4, QTableWidgetItem(race["categories"]))
            # store id in row data
            self.table.setRowHeight(row, 20)
            self.table.item(row,0).setData(Qt.UserRole, race["id"])

    def _selected_race_id(self) -> int:
        row = self.table.currentRow()
        if row < 0:
            return -1
        item = self.table.item(row, 0)
        return item.data(Qt.UserRole)

    def _delete_selected(self) -> None:
        rid = self._selected_race_id()
        if rid is None or rid == -1:
            return
        self.db.delete_race(rid)
        self.refresh()

    def _open_selected(self, row: int, column: int) -> None:
        item = self.table.item(row, 0)
        rid = item.data(Qt.UserRole)
        if rid:
            self.race_selected.emit(rid)

    def _export_json(self) -> None:
        rid = self._selected_race_id()
        if rid == -1:
            return
        path, _ = QFileDialog.getSaveFileName(self, "Exportar JSON", filter="JSON (*.json)")
        if path:
            self.db.export_race_to_json(rid, path)

    def _export_csv(self) -> None:
        rid = self._selected_race_id()
        if rid == -1:
            return
        path, _ = QFileDialog.getSaveFileName(self, "Exportar CSV", filter="CSV (*.csv)")
        if path:
            self.db.export_race_to_csv(rid, path)

    def _select_json(self) -> None:
        path, _ = QFileDialog.getOpenFileName(self, "JSON", filter="JSON (*.json)")
        if path:
            self.json_path.setText(path)

    def _add_race(self) -> None:
        path = self.json_path.text()
        if not path:
            return
        name = self.name_edit.text() or "Prova"
        location = self.loc_edit.text()
        date = self.date_edit.date().toPyDate()
        self.db.add_race(name, location, date, path)
        self.name_edit.clear()
        self.loc_edit.clear()
        self.json_path.clear()
        self.refresh()
