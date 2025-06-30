# -*- coding: utf-8 -*-
"""Qt application for browsing and editing runner data described in a JSON file.

The application expects a JSON file with the structure shown in the user request
and a configuration YAML file named ``viewer_config.yaml`` placed in the same
folder as this script. The configuration currently stores only ``base_path``
which is joined with the ``filename`` field of the JSON entries to locate the
images on disk.
"""

import json
import os
import shutil
import sys
from typing import List

import yaml
from PIL import Image, ImageQt
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QPixmap
from PyQt5.QtWidgets import (
    QAction,
    QApplication,
    QCheckBox,
    QComboBox,
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMessageBox,
    QSplitter,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
    QWidget,
)

DEFAULT_VIEWER_CONFIG = {"base_path": os.getcwd()}


def load_config(path: str) -> dict:
    if not os.path.exists(path):
        with open(path, "w", encoding="utf-8") as f:
            yaml.safe_dump(DEFAULT_VIEWER_CONFIG, f)
    with open(path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f) or DEFAULT_VIEWER_CONFIG


def save_config(path: str, data: dict) -> None:
    with open(path, "w", encoding="utf-8") as f:
        yaml.safe_dump(data, f)


class RunnerViewer(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("JSON Runner Viewer")
        self.resize(1200, 800)

        self.config_path = os.path.join(os.getcwd(), "viewer_config.yaml")
        self.config = load_config(self.config_path)
        self.json_path = ""
        self.data: List[dict] = []
        self.current_index = 0
        self.brands: List[str] = []
        self.bib_categories: List[str] = []
        self.backup_done = False

        # UI
        self.tree = QTreeWidget()
        self.tree.setHeaderLabels(["Categoria/Bib/Nome"])
        self.tree.currentItemChanged.connect(self.on_item_selected)

        self.thumb_label = QLabel(alignment=Qt.AlignCenter)
        self.runner_label = QLabel(alignment=Qt.AlignCenter)
        self.shoe_box = QVBoxLayout()
        self.shoe_container = QWidget()
        self.shoe_container.setLayout(self.shoe_box)

        middle = QWidget()
        mid_layout = QVBoxLayout(middle)
        mid_layout.addWidget(self.thumb_label)
        middle_runner = QHBoxLayout()
        middle_runner.addWidget(self.runner_label)
        middle_runner.addWidget(self.shoe_container)
        mid_layout.addLayout(middle_runner)

        # Right panel with details
        self.full_image = QLabel(alignment=Qt.AlignCenter)
        self.bib_number = QLineEdit()
        self.bib_category = QComboBox()
        self.brand_checks: List[QCheckBox] = []
        self.brand_panel = QWidget()
        self.brand_layout = QHBoxLayout(self.brand_panel)

        right = QWidget()
        right_layout = QVBoxLayout(right)
        right_layout.addWidget(self.full_image)
        right_layout.addWidget(QLabel("Número:"))
        right_layout.addWidget(self.bib_number)
        right_layout.addWidget(QLabel("Categoria:"))
        right_layout.addWidget(self.bib_category)
        right_layout.addWidget(QLabel("Marca do Tênis:"))
        right_layout.addWidget(self.brand_panel)
        right_layout.addStretch()

        splitter = QSplitter()
        splitter.addWidget(self.tree)
        splitter.addWidget(middle)
        splitter.addWidget(right)
        splitter.setStretchFactor(1, 1)
        self.setCentralWidget(splitter)

        # Menu
        open_json = QAction("Abrir JSON", self)
        open_json.triggered.connect(self.load_json)
        set_base = QAction("Definir Base Path", self)
        set_base.triggered.connect(self.select_base_path)
        menu = self.menuBar().addMenu("Arquivo")
        menu.addAction(open_json)
        menu.addAction(set_base)

    # Utility ---------------------------------------------------------------
    def select_base_path(self) -> None:
        folder = QFileDialog.getExistingDirectory(self, "Base de Imagens", self.config.get("base_path", ""))
        if folder:
            self.config["base_path"] = folder
            save_config(self.config_path, self.config)
            if self.json_path:
                self.populate_tree()
                self.show_entry(0)

    def load_json(self) -> None:
        path, _ = QFileDialog.getOpenFileName(self, "JSON", filter="JSON Files (*.json)")
        if not path:
            return
        self.json_path = path
        with open(path, "r", encoding="utf-8") as f:
            self.data = json.load(f)
        self.collect_stats()
        self.populate_tree()
        self.show_entry(0)

    def collect_stats(self) -> None:
        brands = set()
        cats = set()
        for item in self.data:
            for shoe in item.get("shoes", []):
                brand = shoe.get("new_label") or shoe.get("label")
                if brand:
                    brands.add(brand)
            bib_cat = item.get("bib", {}).get("category")
            if bib_cat:
                cats.add(bib_cat)
        self.brands = sorted(brands)
        self.bib_categories = sorted(cats)

        self.bib_category.clear()
        self.bib_category.addItems(self.bib_categories)

        # prepare brand checkboxes
        for chk in self.brand_checks:
            chk.deleteLater()
        self.brand_checks = []
        self.brand_layout.addStretch()  # ensure layout not empty
        for b in self.brands:
            cb = QCheckBox(b)
            self.brand_layout.addWidget(cb)
            self.brand_checks.append(cb)

    def populate_tree(self) -> None:
        self.tree.clear()
        cats = {}
        for idx, item in enumerate(self.data):
            cat = item.get("category", "?")
            bib_num = item.get("bib", {}).get("number", "?")
            cat_node = cats.get(cat)
            if not cat_node:
                cat_node = QTreeWidgetItem(self.tree, [cat])
                cats[cat] = cat_node
            bib_node = None
            # search if bib child exists
            for i in range(cat_node.childCount()):
                if cat_node.child(i).text(0) == bib_num:
                    bib_node = cat_node.child(i)
                    break
            if bib_node is None:
                bib_node = QTreeWidgetItem(cat_node, [bib_num])
            img_node = QTreeWidgetItem(bib_node, [item.get("filename", str(idx))])
            img_node.setData(0, Qt.UserRole, idx)
        self.tree.expandAll()

    def crop_image(self, img: Image.Image, box: List[int]) -> Image.Image:
        left, top, right, bottom = box
        return img.crop((left, top, right, bottom))

    def show_entry(self, index: int) -> None:
        if not self.data:
            return
        index = max(0, min(index, len(self.data)-1))
        self.current_index = index
        item = self.data[index]
        img_path = os.path.join(self.config.get("base_path", ""), item["filename"])
        try:
            img = Image.open(img_path)
        except Exception:
            self.thumb_label.setText("Imagem não encontrada")
            return
        # Thumb of original
        thumb = ImageQt.ImageQt(img.resize((200, int(200*img.height/img.width))))
        self.thumb_label.setPixmap(QPixmap.fromImage(thumb))
        # Runner crop
        bbox = item.get("bbox", [0, 0, img.width, img.height])
        runner = self.crop_image(img, bbox)
        rimg = ImageQt.ImageQt(runner.resize((300, int(300*runner.height/runner.width))))
        self.runner_label.setPixmap(QPixmap.fromImage(rimg))

        # shoes
        for i in reversed(range(self.shoe_box.count())):
            w = self.shoe_box.itemAt(i).widget()
            if w:
                w.deleteLater()
        for shoe in item.get("shoes", []):
            sbbox = shoe.get("bbox")
            if sbbox:
                crop = self.crop_image(img, sbbox)
                simg = ImageQt.ImageQt(crop.resize((120, int(120*crop.height/crop.width))))
                lbl = QLabel()
                lbl.setPixmap(QPixmap.fromImage(simg))
                self.shoe_box.addWidget(lbl)
        self.shoe_box.addStretch()

        # right panel data
        self.full_image.setPixmap(QPixmap.fromImage(rimg))
        self.bib_number.setText(str(item.get("bib", {}).get("number", "")))
        cat = item.get("bib", {}).get("category")
        if cat and cat in self.bib_categories:
            self.bib_category.setCurrentText(cat)
        else:
            self.bib_category.setCurrentIndex(-1)
        for chk in self.brand_checks:
            chk.setChecked(False)
        brands_present = {shoe.get("new_label") or shoe.get("label") for shoe in item.get("shoes", [])}
        for chk in self.brand_checks:
            if chk.text() in brands_present:
                chk.setChecked(True)

    def apply_changes(self) -> None:
        if not self.data:
            return
        item = self.data[self.current_index]
        # bib
        item.setdefault("bib", {})
        item["bib"]["number"] = self.bib_number.text()
        cat = self.bib_category.currentText()
        if cat:
            item["bib"]["category"] = cat
        # shoes brands
        checked = [chk.text() for chk in self.brand_checks if chk.isChecked()]
        shoes = item.get("shoes", [])
        for idx, brand in enumerate(checked):
            if idx < len(shoes):
                shoes[idx]["new_label"] = brand
        self.data[self.current_index] = item
        self.save_json()

    def save_json(self) -> None:
        if not self.json_path:
            return
        if not self.backup_done:
            shutil.copy(self.json_path, self.json_path + ".bak")
            self.backup_done = True
        with open(self.json_path, "w", encoding="utf-8") as f:
            json.dump(self.data, f, ensure_ascii=False, indent=2)

    def on_item_selected(self, current: QTreeWidgetItem) -> None:
        if current is None:
            return
        idx = current.data(0, Qt.UserRole)
        if isinstance(idx, int):
            self.show_entry(idx)

    # navigation and editing -----------------------------------------------
    def keyPressEvent(self, event):
        if not self.data:
            return
        if event.key() == Qt.Key_Delete:
            reply = QMessageBox.question(self, "Remover", "Remover imagem?", QMessageBox.Yes | QMessageBox.No)
            if reply == QMessageBox.Yes:
                self.data.pop(self.current_index)
                self.populate_tree()
                new_index = min(self.current_index, len(self.data)-1)
                if new_index >= 0:
                    self.show_entry(new_index)
                    self.save_json()
            return
        if event.key() == Qt.Key_Right or event.key() == Qt.Key_Down:
            self.current_index = min(self.current_index + 1, len(self.data)-1)
            self.show_entry(self.current_index)
            return
        if event.key() == Qt.Key_Left or event.key() == Qt.Key_Up:
            self.current_index = max(self.current_index - 1, 0)
            self.show_entry(self.current_index)
            return
        if event.key() == Qt.Key_Return or event.key() == Qt.Key_Enter:
            self.apply_changes()
            return
        super().keyPressEvent(event)


def main() -> None:
    app = QApplication(sys.argv)
    viewer = RunnerViewer()
    viewer.show()
    sys.exit(app.exec_())


if __name__ == "__main__":
    main()
