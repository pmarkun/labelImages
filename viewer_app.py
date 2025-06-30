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
import io

import yaml
from PIL import Image
from PIL import ImageQt
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QPixmap, QFont, QPalette, QColor, QKeyEvent
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
    QFrame,
    QScrollArea,
    QGroupBox,
    QPushButton,
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
        self.setWindowTitle("🏃 Runner Data Viewer")
        self.setup_styling()
        self.setMinimumSize(800, 600)
        self.config_path = os.path.join(os.getcwd(), "viewer_config.yaml")
        self.config = load_config(self.config_path)
        self.json_path = ""
        self.data: List[dict] = []
        self.current_index = 0
        self.brands: List[str] = []
        self.bib_categories: List[str] = []
        self.backup_done = False

        # Setup UI
        self.setup_ui()

        # Menu
        self.setup_menu()

    def setup_styling(self) -> None:
        """Apply modern styling to the application"""

        app = QApplication.instance()

        self.setStyleSheet("""
            QMainWindow {
                background-color: #f8f9fa;
                color: #333;
            }
            QTreeWidget {
                background-color: white;
                border: 1px solid #ddd;
                border-radius: 8px;
                padding: 5px;
                font-size: 13px;
            }
            QTreeWidget::item {
                padding: 4px;
                border-bottom: 1px solid #f0f0f0;
            }
            QTreeWidget::item:selected {
                background-color: #007acc;
                color: white;
            }
            QLabel {
                color: #333;
                font-size: 13px;
            }
            QGroupBox {
                font-weight: bold;
                border: 2px solid #ddd;
                border-radius: 8px;
                margin: 10px 0px;
                padding-top: 10px;
                background-color: white;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 5px 0 5px;
                color: #007acc;
                font-size: 14px;
            }
            QLineEdit, QComboBox {
                border: 2px solid #ddd;
                border-radius: 6px;
                padding: 8px;
                font-size: 13px;
                background-color: white;
            }
            QLineEdit:focus, QComboBox:focus {
                border-color: #007acc;
            }
            QCheckBox {
                spacing: 8px;
                font-size: 12px;
                padding: 4px;
            }
            QCheckBox::indicator {
                width: 18px;
                height: 18px;
            }
            QCheckBox::indicator:unchecked {
                border: 2px solid #ddd;
                border-radius: 3px;
                background-color: white;
            }
            QCheckBox::indicator:checked {
                border: 2px solid #007acc;
                border-radius: 3px;
                background-color: #007acc;
            }
            QPushButton {
                background-color: #007acc;
                color: white;
                border: none;
                border-radius: 6px;
                padding: 10px 20px;
                font-size: 13px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #005fa3;
            }
            QPushButton:pressed {
                background-color: #004578;
            }
            QSplitter::handle {
                background-color: #ddd;
                width: 3px;
            }
            QScrollArea {
                border: 1px solid #ddd;
                border-radius: 8px;
                background-color: white;
            }
        """)

    def setup_menu(self) -> None:
        """Setup the application menu"""
        open_json = QAction("📂 Abrir JSON", self)
        open_json.triggered.connect(self.load_json)
        set_base = QAction("📁 Definir Base Path", self)
        set_base.triggered.connect(self.select_base_path)
        
        menu = self.menuBar().addMenu("Arquivo")
        if menu:
            menu.addAction(open_json)
            menu.addAction(set_base)

    def setup_ui(self) -> None:
        """Setup the main user interface"""
        # Create main splitter
        main_splitter = QSplitter(Qt.Horizontal)
        
        # Left panel - Tree view
        left_panel = self.create_left_panel()
        
        # Center panel - Image display
        center_panel = self.create_center_panel()
        
        # Right panel - Details and controls
        right_panel = self.create_right_panel()
        
        main_splitter.addWidget(left_panel)
        main_splitter.addWidget(center_panel)
        main_splitter.addWidget(right_panel)
        
        # Set splitter proportions
        main_splitter.setStretchFactor(0, 2)  # Left panel
        main_splitter.setStretchFactor(1, 3)  # Center panel (larger)
        main_splitter.setStretchFactor(2, 1)  # Right panel
        
        self.setCentralWidget(main_splitter)
        
    def create_left_panel(self) -> QWidget:
        """Create the left panel with tree view"""
        panel = QWidget()
        layout = QVBoxLayout(panel)
        layout.setSpacing(10)
        layout.setContentsMargins(10, 10, 10, 10)
        
        # Header
        header = QLabel("📁 Navegação")
        header.setStyleSheet("font-size: 16px; font-weight: bold; color: #007acc; margin-bottom: 10px;")
        layout.addWidget(header)
        
        # Tree widget
        self.tree = QTreeWidget()
        self.tree.setHeaderLabels(["Categoria / Dorsal / Nome"])
        self.tree.currentItemChanged.connect(self.on_item_selected)
        layout.addWidget(self.tree)
        
        return panel
        
    def create_center_panel(self) -> QWidget:
        """Create the center panel with image displays"""
        panel = QWidget()
        layout = QVBoxLayout(panel)
        layout.setSpacing(15)
        layout.setContentsMargins(10, 10, 10, 10)
        
        # Header
        header = QLabel("🖼️ Visualização de Imagens")
        header.setStyleSheet("font-size: 16px; font-weight: bold; color: #007acc; margin-bottom: 10px;")
        layout.addWidget(header)
        
        # Original image thumbnail
        thumb_group = QGroupBox("Imagem Original")
        thumb_layout = QVBoxLayout(thumb_group)
        self.thumb_label = QLabel()
        self.thumb_label.setAlignment(Qt.AlignCenter)
        self.thumb_label.setStyleSheet("border: 2px dashed #ddd; border-radius: 8px; padding: 20px; background-color: #f8f9fa;")
        self.thumb_label.setMinimumHeight(200)
        thumb_layout.addWidget(self.thumb_label)
        layout.addWidget(thumb_group)
        
        # Runner and shoes section
        runner_group = QGroupBox("Corredor e Tênis")
        runner_layout = QHBoxLayout(runner_group)
        
        # Runner image
        runner_container = QVBoxLayout()
        runner_label_header = QLabel("👤 Corredor")
        runner_label_header.setStyleSheet("font-weight: bold; color: #666; margin-bottom: 5px;")
        runner_container.addWidget(runner_label_header)
        
        self.runner_label = QLabel()
        self.runner_label.setAlignment(Qt.AlignCenter)
        self.runner_label.setStyleSheet("border: 2px dashed #ddd; border-radius: 8px; padding: 10px; background-color: #f8f9fa;")
        self.runner_label.setMinimumHeight(300)
        runner_container.addWidget(self.runner_label)
        
        # Shoes section
        shoes_container = QVBoxLayout()
        shoes_label_header = QLabel("👟 Tênis")
        shoes_label_header.setStyleSheet("font-weight: bold; color: #666; margin-bottom: 5px;")
        shoes_container.addWidget(shoes_label_header)
        
        shoes_scroll = QScrollArea()
        shoes_scroll.setWidgetResizable(True)
        shoes_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        shoes_scroll.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        
        self.shoe_container = QWidget()
        self.shoe_box = QVBoxLayout(self.shoe_container)
        self.shoe_box.setSpacing(10)
        shoes_scroll.setWidget(self.shoe_container)
        shoes_scroll.setMaximumWidth(150)
        shoes_container.addWidget(shoes_scroll)
        
        runner_layout.addLayout(runner_container, 2)
        runner_layout.addLayout(shoes_container, 1)
        layout.addWidget(runner_group)
        
        return panel
        
    def create_right_panel(self) -> QWidget:
        """Create the right panel with details and controls"""
        panel = QWidget()
        layout = QVBoxLayout(panel)
        layout.setSpacing(15)
        layout.setContentsMargins(10, 10, 10, 10)
        
        # Header
        header = QLabel("⚙️ Detalhes e Edição")
        header.setStyleSheet("font-size: 16px; font-weight: bold; color: #007acc; margin-bottom: 10px;")
        layout.addWidget(header)
        
        # Bib information group
        bib_group = QGroupBox("Informações do Dorsal")
        bib_layout = QVBoxLayout(bib_group)
        
        # Bib number
        bib_layout.addWidget(QLabel("Número do Dorsal:"))
        self.bib_number = QLineEdit()
        self.bib_number.setPlaceholderText("Digite o número...")
        bib_layout.addWidget(self.bib_number)
        
        # Bib category
        bib_layout.addWidget(QLabel("Categoria:"))
        self.bib_category = QComboBox()
        bib_layout.addWidget(self.bib_category)
        
        layout.addWidget(bib_group)
        
        # Brand selection group
        brand_group = QGroupBox("Marcas dos Tênis")
        brand_layout = QVBoxLayout(brand_group)
        
        # Create scrollable area for brands
        brand_scroll = QScrollArea()
        brand_scroll.setWidgetResizable(True)
        brand_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        
        self.brand_panel = QWidget()
        self.brand_layout = QVBoxLayout(self.brand_panel)
        self.brand_layout.setSpacing(5)
        self.brand_checks: List[QCheckBox] = []
        
        brand_scroll.setWidget(self.brand_panel)
        brand_layout.addWidget(brand_scroll)
        layout.addWidget(brand_group)
        
        # Action buttons
        button_group = QGroupBox("Ações")
        button_layout = QVBoxLayout(button_group)
        
        save_btn = QPushButton("💾 Salvar Alterações")
        save_btn.clicked.connect(self.apply_changes)
        button_layout.addWidget(save_btn)
        
        layout.addWidget(button_group)
        
        # Add stretch to push everything to top
        layout.addStretch()
        
        return panel

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
            self.data = json.load(f)[0:1000]  # Limit to 1000 entries for performance
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
        
        for b in self.brands:
            cb = QCheckBox(b)
            self.brand_layout.addWidget(cb)
            self.brand_checks.append(cb)

    def populate_tree(self) -> None:
        self.tree.clear()
        cats = {}
        for idx, item in enumerate(self.data):
            cat = item.get("bib", {}).get("category", "?")
            bib_num = item.get("bib", {}).get("number", "?")
            cat_node = cats.get(cat)
            if not cat_node:
                cat_node = QTreeWidgetItem(self.tree, [cat])
                cats[cat] = cat_node
            bib_node = None
            # search if bib child exists
            for i in range(cat_node.childCount()):
                child = cat_node.child(i)
                if child and child.text(0) == str(bib_num):
                    bib_node = child
                    break
            if bib_node is None:
                bib_node = QTreeWidgetItem(cat_node, [str(bib_num)])
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
        data_item = self.data[index]
        img_path = os.path.join(self.config.get("base_path", ""), data_item["filename"])
        try:
            img = Image.open(img_path)
        except Exception:
            self.thumb_label.setText("Imagem não encontrada")
            return
        
        # Thumb of original
        thumb_img = img.resize((150, int(150*img.height/img.width)))
        thumb_pixmap = self.pil_to_qpixmap(thumb_img)
        self.thumb_label.setPixmap(thumb_pixmap)
        
        # Runner crop
        bbox = data_item.get("bbox", [0, 0, img.width, img.height])
        runner = self.crop_image(img, bbox)
        # Calculate proportional resize to fit within a 300x400 box
        target_width, target_height = 300, 400
        width_ratio = target_width / runner.width
        height_ratio = target_height / runner.height
        # Use the smaller ratio to ensure image fits in both dimensions
        scale_ratio = min(width_ratio, height_ratio)
        runner_img = runner.resize((int(runner.width * scale_ratio), int(runner.height * scale_ratio)))
        runner_pixmap = self.pil_to_qpixmap(runner_img)
        self.runner_label.setPixmap(runner_pixmap)

        # shoes
        for i in reversed(range(self.shoe_box.count())):
            layout_item = self.shoe_box.itemAt(i)
            if layout_item:
                w = layout_item.widget()
                if w:
                    w.deleteLater()
        
        for shoe in data_item.get("shoes", []):
            shoe_bbox = shoe.get("bbox")
            if shoe_bbox and len(shoe_bbox) >= 4:
                x1, y1, x2, y2 = shoe_bbox
                runner_bbox = data_item.get("bbox", [0, 0, img.width, img.height])
                if len(runner_bbox) >= 4:
                    x1 = runner_bbox[0] + x1
                    y1 = runner_bbox[1] + y1
                    x2 = runner_bbox[0] + x2
                    y2 = runner_bbox[1] + y2
                    sbbox = [x1, y1, x2, y2]
                    try:
                        crop = self.crop_image(img, sbbox)
                        shoe_img = crop.resize((120, int(120*crop.height/crop.width)))
                        shoe_pixmap = self.pil_to_qpixmap(shoe_img)
                        
                        # Create a container for each shoe with label
                        shoe_widget = QWidget()
                        shoe_layout = QVBoxLayout(shoe_widget)
                        shoe_layout.setContentsMargins(5, 5, 5, 5)
                        
                        lbl = QLabel()
                        lbl.setPixmap(shoe_pixmap)
                        lbl.setStyleSheet("border: 1px solid #ddd; border-radius: 4px; padding: 2px;")
                        
                        # Add brand label if available
                        brand = shoe.get("new_label") or shoe.get("label", "")
                        if brand:
                            brand_lbl = QLabel(brand)
                            brand_lbl.setStyleSheet("font-size: 11px; color: #666; font-weight: bold;")
                            brand_lbl.setAlignment(Qt.AlignCenter)
                            shoe_layout.addWidget(brand_lbl)
                        
                        shoe_layout.addWidget(lbl)
                        self.shoe_box.addWidget(shoe_widget)
                    except Exception as e:
                        print(f"Error processing shoe image: {e}")
        
        self.shoe_box.addStretch()

        # right panel data
        self.bib_number.setText(str(data_item.get("bib", {}).get("number", "")))
        cat = data_item.get("bib", {}).get("category")
        if cat and cat in self.bib_categories:
            self.bib_category.setCurrentText(cat)
        else:
            self.bib_category.setCurrentIndex(-1)
        for chk in self.brand_checks:
            chk.setChecked(False)
        brands_present = {shoe.get("new_label") or shoe.get("label") for shoe in data_item.get("shoes", [])}
        for chk in self.brand_checks:
            if chk.text() in brands_present:
                chk.setChecked(True)

    def pil_to_qpixmap(self, pil_image):
        """Convert PIL Image to QPixmap"""
        # Convert PIL image to bytes
        byte_array = io.BytesIO()
        pil_image.save(byte_array, format='PNG')
        byte_array.seek(0)
        
        # Load QPixmap from bytes
        pixmap = QPixmap()
        pixmap.loadFromData(byte_array.getvalue())
        return pixmap

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
    def keyPressEvent(self, event: QKeyEvent):
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
