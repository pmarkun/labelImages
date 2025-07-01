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
from PyQt5.QtCore import Qt, QEvent
from PyQt5.QtGui import QPixmap, QFont, QPalette, QColor, QKeyEvent
from PyQt5.QtWidgets import (
    QAction,
    QApplication,
    QCheckBox,
    QComboBox,
    QFileDialog,
    QGridLayout,
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

DEFAULT_VIEWER_CONFIG = {
    "base_path": os.getcwd(),
    "labels": []
}


def load_config(path: str) -> dict:
    if not os.path.exists(path):
        with open(path, "w", encoding="utf-8") as f:
            yaml.safe_dump(DEFAULT_VIEWER_CONFIG, f)
    with open(path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f) or DEFAULT_VIEWER_CONFIG


def save_config(path: str, data: dict) -> None:
    with open(path, "w", encoding="utf-8") as f:
        yaml.safe_dump(data, f)


class ClickableLabel(QLabel):
    """A QLabel that can be clicked"""
    def __init__(self, parent=None, shoe_index=None, callback=None):
        super().__init__(parent)
        self.shoe_index = shoe_index
        self.callback = callback
    
    def mousePressEvent(self, event):
        if self.callback and self.shoe_index is not None:
            self.callback(event, self.shoe_index)
        super().mousePressEvent(event)


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
        self.undo_stack = []  # Para ctrl+z
        self.max_undo = 50   # Limite de undos
        self.has_unsaved_changes = False  # Track de mudanças não salvas

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
        open_json.setShortcut("Ctrl+O")
        
        save_json = QAction("💾 Salvar", self)
        save_json.triggered.connect(self.save_json)
        save_json.setShortcut("Ctrl+S")
        
        save_as_json = QAction("💾 Salvar Como...", self)
        save_as_json.triggered.connect(self.save_as_json)
        save_as_json.setShortcut("Ctrl+Shift+S")
        
        set_base = QAction("📁 Definir Base Path", self)
        set_base.triggered.connect(self.select_base_path)
        
        menu = self.menuBar().addMenu("Arquivo")
        if menu:
            menu.addAction(open_json)
            menu.addSeparator()
            menu.addAction(save_json)
            menu.addAction(save_as_json)
            menu.addSeparator()
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
        
        # Filter section
        filter_group = QGroupBox("Filtros")
        filter_layout = QVBoxLayout(filter_group)
        
        self.filter_unchecked_only = QCheckBox("Mostrar apenas dorsais sem imagens checadas")
        self.filter_unchecked_only.stateChanged.connect(self.on_filter_changed)
        filter_layout.addWidget(self.filter_unchecked_only)
        
        layout.addWidget(filter_group)
        
        # Tree widget
        self.tree = QTreeWidget()
        self.tree.setHeaderLabels(["Categoria / Dorsal / Nome"])
        self.tree.currentItemChanged.connect(self.on_item_selected)
        # Instala event filter para interceptar eventos de teclado
        self.tree.installEventFilter(self)
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
        thumb_layout = QVBoxLayout()
        self.thumb_label = QLabel()
        self.thumb_label.setAlignment(Qt.AlignCenter)
        self.thumb_label.setStyleSheet("border: 2px dashed #ddd; border-radius: 8px; padding: 20px; background-color: #f8f9fa;")
        self.thumb_label.setMinimumHeight(200)
        thumb_layout.addWidget(self.thumb_label)
        #layout.addWidget(thumb_group)
        
        # Runner and shoes section
        runner_group = QGroupBox("Corredor e Tênis")
        runner_layout = QHBoxLayout(runner_group)
        
        # Runner image
        runner_container = QVBoxLayout()
        
        self.runner_label = QLabel()
        self.runner_label.setAlignment(Qt.AlignCenter)
        self.runner_label.setStyleSheet("border: 2px dashed #ddd; border-radius: 8px; padding: 10px; background-color: #f8f9fa;")
        self.runner_label.setMinimumHeight(300)
        runner_container.addWidget(self.runner_label)
        
        # Shoes section
        shoes_container = QVBoxLayout()
        
        shoes_scroll = QScrollArea()
        shoes_scroll.setWidgetResizable(True)
        shoes_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        shoes_scroll.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        
        self.shoe_container = QWidget()
        self.shoe_box = QVBoxLayout(self.shoe_container)
        self.shoe_box.setSpacing(5)  # Reduce spacing to allow more room for shoes
        self.shoe_box.setContentsMargins(5, 5, 5, 5)  # Smaller margins
        shoes_scroll.setWidget(self.shoe_container)
        shoes_scroll.setMaximumWidth(300)
        shoes_scroll.setMinimumHeight(400)  # Ensure minimum height
        shoes_container.addWidget(shoes_scroll)
        
        runner_layout.addLayout(thumb_layout, 1)
        runner_layout.addLayout(runner_container, 2)
        runner_layout.addLayout(shoes_container, 2)
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
        self.bib_number.returnPressed.connect(self.on_bib_number_enter)
        bib_layout.addWidget(self.bib_number)
        
        # Bib category
        bib_layout.addWidget(QLabel("Categoria:"))
        self.bib_category = QComboBox()
        self.bib_category.activated.connect(self.on_category_selected)
        bib_layout.addWidget(self.bib_category)
        
        layout.addWidget(bib_group)
        
        # Brand selection group
        brand_group = QGroupBox("Marcas dos Tênis")
        brand_layout = QVBoxLayout(brand_group)
        
        # Create scrollable area for brands
        brand_scroll = QScrollArea()
        brand_scroll.setWidgetResizable(True)
        brand_scroll.setMinimumHeight(350)
        brand_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        
        self.brand_panel = QWidget()
        self.brand_layout = QGridLayout(self.brand_panel)
        self.brand_layout.setSpacing(5)
        self.brand_checks: List[QCheckBox] = []
        
        brand_scroll.setWidget(self.brand_panel)
        brand_layout.addWidget(brand_scroll)
        layout.addWidget(brand_group)
        
     
        # Keyboard shortcuts info
        shortcuts_group = QGroupBox("Atalhos de Teclado")
        shortcuts_layout = QVBoxLayout(shortcuts_group)
        
        # Dynamic shortcuts text based on config
        brand_shortcuts = ""
        config_labels = self.config.get("labels", [])
        if config_labels:
            brand_shortcuts = "<b>Marcas:</b><br>"
            for label_config in config_labels:
                if isinstance(label_config, dict):
                    key = label_config.get("key", "").upper()
                    label = label_config.get("label", "")
                    if key and label:
                        brand_shortcuts += f"<b>{key}</b> : {label}<br>"
            brand_shortcuts += "<br>"
        
        shortcuts_text = QLabel(f"""
        <b>Navegação:</b><br>
        ← → ↑ ↓ : Navegar<br>
        Enter : Salvar mudanças<br><br>
        
        <b>Edição:</b><br>
        <b>Del</b> : Remover imagem<br>
        <b>K</b> : Propagar dados e exportar crops de TODAS as imagens do mesmo dorsal<br>
        <b>C</b> : Marcar/desmarcar como checada<br>
        <b>Ctrl+Z</b> : Desfazer última alteração<br><br>
        
        {brand_shortcuts}
        <small>💡 Imagens checadas ficam protegidas contra edição</small>
        """)
        shortcuts_text.setStyleSheet("font-size: 11px; color: #666; padding: 5px;")
        shortcuts_text.setWordWrap(True)
        shortcuts_layout.addWidget(shortcuts_text)
        
        layout.addWidget(shortcuts_group)
        
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
            self.data = json.load(f)  # Limit to 1000 entries for performance
        
        # Limpa o stack de undo ao carregar novo arquivo
        self.undo_stack = []
        self.has_unsaved_changes = False
        
        self.collect_stats()
        self.populate_tree()
        self.show_entry(0)
        self.update_status_bar()
        self.update_window_title()

    def collect_stats(self) -> None:
        # Get brands from config first, then add any additional ones found in data
        config_labels = self.config.get("labels", [])
        brands = set()
        
        # Add brands from config
        for label_config in config_labels:
            if isinstance(label_config, dict) and "label" in label_config:
                brands.add(label_config["label"])
        
        # Add any additional brands found in the data
        cats = set()
        for item in self.data:
            for shoe in item.get("shoes", []):
                # Support both old and new format
                brand = shoe.get("new_label") or shoe.get("label") or shoe.get("classification_label")
                if brand:
                    brands.add(brand)
            
            # Support both old and new format for categories
            bib_cat = None
            run_data = item.get("run_data", {})
            if isinstance(run_data, dict):
                bib_cat = run_data.get("run_category")
            
            if bib_cat and bib_cat != "Not Identifiable":
                cats.add(bib_cat)
                
        self.brands = sorted(brands)
        self.bib_categories = sorted(cats)

        self.bib_category.clear()
        self.bib_category.addItems(self.bib_categories)

        # prepare brand checkboxes
        for chk in self.brand_checks:
            chk.deleteLater()
        self.brand_checks = []
        
        # Organiza as marcas em duas colunas
        for i, b in enumerate(self.brands):
            cb = QCheckBox(b)
            cb.stateChanged.connect(self.on_brand_changed_immediate)
            row = i // 2  # Linha
            col = i % 2   # Coluna (0 ou 1)
            self.brand_layout.addWidget(cb, row, col)
            self.brand_checks.append(cb)

    def populate_tree(self) -> None:
        self.tree.clear()
        cats = {}
        
        # Check if we should filter for unchecked only
        filter_unchecked_only = hasattr(self, 'filter_unchecked_only') and self.filter_unchecked_only.isChecked()
        
        for idx, item in enumerate(self.data):
            # Get category from run_data
            cat = "?"
            run_data = item.get("run_data", {})
            if isinstance(run_data, dict):
                cat = run_data.get("run_category", "?")
                if cat == "Not Identifiable":
                    cat = "?"
            
            # Get bib number from run_data
            bib_num = "?"
            if isinstance(run_data, dict):
                bib_num = run_data.get("bib_number", "?")
            
            # Apply filter: skip this bib if it has checked images and we're filtering for unchecked only
            if filter_unchecked_only and bib_num != "?" and self.bib_has_checked_images(str(bib_num)):
                continue
            
            is_checked = item.get("checked", False)
            
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
            
            # Adiciona ícone para imagens checadas
            # Support both old and new format for filename
            img_name = item.get("filename") or item.get("image_path", str(idx))
            if img_name != str(idx):
                # Extract just the filename part if it's a path
                img_name = os.path.basename(img_name)
            
            if is_checked:
                img_name = "✓ " + img_name
            
            img_node = QTreeWidgetItem(bib_node, [img_name])
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
        
        # Verifica se está checada
        is_checked = data_item.get('checked', False)
        
        # Support both old and new format for filename/image_path
        img_filename = data_item.get("filename") or data_item.get("image_path", "")
        img_path = os.path.join(self.config.get("base_path", ""), img_filename)
        try:
            img = Image.open(img_path)
        except Exception:
            print("Imagem não encontrada")
            return
        
        # Thumb of original - com indicador de status
        thumb_img = img.resize((150, int(150*img.height/img.width)))
        thumb_pixmap = self.pil_to_qpixmap(thumb_img)
        
        # Se está checada, adiciona uma borda verde
        if is_checked:
            self.thumb_label.setStyleSheet("border: 4px solid #28a745; border-radius: 8px; padding: 16px; background-color: #d4edda;")
        else:
            self.thumb_label.setStyleSheet("border: 2px dashed #ddd; border-radius: 8px; padding: 20px; background-color: #f8f9fa;")
        
        self.thumb_label.setPixmap(thumb_pixmap)
        
        # Runner crop - support both old and new format for bbox
        bbox = data_item.get("bbox") or data_item.get("person_bbox", [0, 0, img.width, img.height])
        runner = self.crop_image(img, bbox)
        # Calculate proportional resize to fit within a 300x400 box
        target_width, target_height = self.runner_label.width(), self.runner_label.height()
        width_ratio = target_width / runner.width * 0.95
        height_ratio = target_height / runner.height * 0.95
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
        
        shoes = data_item.get("shoes", [])
        num_shoes = len(shoes)
        
        # Get the actual available height from the scroll area parent
        # Use a more conservative and reliable approach
        container_height = self.shoe_container.height()  # Good default height for shoe display
        container_width = 270   # Fixed width based on scroll area max width
        
        # Set the container to use the full available height immediately
        self.shoe_container.setMinimumHeight(container_height)
        self.shoe_container.setMaximumHeight(container_height)
        
        # Calculate available space for each shoe
        if num_shoes > 0:
            # Reserve space for brand labels and margins (more conservative)
            label_height = 20  # Height for brand label
            widget_margins = 10  # Margins per shoe widget
            layout_spacing = self.shoe_box.spacing() * max(0, num_shoes - 1)  # Spacing between shoes
            total_reserved_height = num_shoes * (label_height + widget_margins) + layout_spacing + 30  # Extra margin
            
            # Calculate available height per shoe image
            available_height_per_shoe = max((container_height - total_reserved_height) / num_shoes, 40)
            available_width = container_width - 20  # Leave some margin
        else:
            available_height_per_shoe = 100
            available_width = 250
            
        for shoe in shoes:
            shoe_bbox = shoe.get("bbox")
            if shoe_bbox and len(shoe_bbox) >= 4:
                try:
                    crop = self.crop_image(img, shoe_bbox)
                    
                    # Calculate scaling to fit available space
                    height_ratio = available_height_per_shoe / crop.height if crop.height > 0 else 1
                    width_ratio = available_width / crop.width if crop.width > 0 else 1
                    
                    # Use the smaller ratio to maintain aspect ratio
                    shoe_ratio = min(height_ratio, width_ratio, 2.0)  # Allow up to 2x scaling
                    
                    # Ensure reasonable size bounds
                    shoe_ratio = max(shoe_ratio, 0.2)  # Minimum scale
                    shoe_ratio = min(shoe_ratio, 3.0)  # Maximum scale
                    
                    new_width = max(int(crop.width * shoe_ratio), 60)
                    new_height = max(int(crop.height * shoe_ratio), 40)
                    
                    shoe_img = crop.resize((new_width, new_height))
                    shoe_pixmap = self.pil_to_qpixmap(shoe_img)
                    
                    # Create a container for each shoe with label
                    shoe_widget = QWidget()
                    shoe_layout = QVBoxLayout(shoe_widget)
                    shoe_layout.setContentsMargins(5, 5, 5, 5)
                    
                    # Add brand label if available - support both old and new format
                    brand = shoe.get("new_label") or shoe.get("label") or shoe.get("classification_label", "")
                    if brand:
                        brand_lbl = QLabel(brand)
                        brand_lbl.setStyleSheet("font-size: 11px; color: #666; font-weight: bold;")
                        brand_lbl.setAlignment(Qt.AlignCenter)
                        shoe_layout.addWidget(brand_lbl)
                    
                    # Make the label clickable - store shoe index for removal
                    shoe_index = shoes.index(shoe)
                    lbl = ClickableLabel(shoe_index=shoe_index, callback=self.on_shoe_click)
                    lbl.setPixmap(shoe_pixmap)
                    lbl.setStyleSheet("border: 1px solid #ddd; border-radius: 4px; padding: 2px; cursor: pointer;")
                    lbl.setAlignment(Qt.AlignCenter)
                    
                    shoe_layout.addWidget(lbl)
                    
                    # Add stretch to center the image in its allocated space
                    shoe_layout.addStretch()
                    
                    # Set the widget to expand and fill allocated space
                    from PyQt5.QtWidgets import QSizePolicy
                    shoe_widget.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Expanding)
                    
                    self.shoe_box.addWidget(shoe_widget)
                except Exception as e:
                    print(f"Error processing shoe image: {e}")
    
        # Don't add stretch - we want shoes to fill the available space
        # self.shoe_box.addStretch()
        
        # Adjust container size to fit all shoes properly
        # self.adjust_shoe_container_size()

        # right panel data - desabilita se checado
        # Get bib number from run_data
        run_data = data_item.get("run_data", {})
        bib_number = ""
        if isinstance(run_data, dict):
            bib_number = str(run_data.get("bib_number", ""))
        
        # Temporarily disconnect signals to prevent triggering change handlers
        try:
            self.bib_number.returnPressed.disconnect()
        except:
            pass
        try:
            self.bib_category.activated.disconnect()
        except:
            pass
        for chk in self.brand_checks:
            try:
                chk.stateChanged.disconnect()
            except:
                pass
        
        self.bib_number.setText(bib_number)
        self.bib_number.setEnabled(not is_checked)
        
        # Get category from run_data
        cat = ""
        if isinstance(run_data, dict):
            cat = run_data.get("run_category", "")
        if cat and cat in self.bib_categories:
            self.bib_category.setCurrentText(cat)
        else:
            self.bib_category.setCurrentIndex(-1)
        self.bib_category.setEnabled(not is_checked)
        
        for chk in self.brand_checks:
            chk.setChecked(False)
            chk.setEnabled(not is_checked)
        
        # Support both old and new format for shoe brands
        brands_present = set()
        for shoe in data_item.get("shoes", []):
            brand = shoe.get("new_label") or shoe.get("label") or shoe.get("classification_label")
            if brand:
                brands_present.add(brand)
        
        for chk in self.brand_checks:
            if chk.text() in brands_present:
                chk.setChecked(True)
        
        # Reconnect signals
        self.bib_number.returnPressed.connect(self.on_bib_number_enter)
        self.bib_category.activated.connect(self.on_category_selected)
        for chk in self.brand_checks:
            chk.stateChanged.connect(self.on_brand_changed_immediate)

        # Atualiza status bar
        self.update_status_bar()

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

    def apply_changes(self, save_state: bool = True) -> None:
        if not self.data:
            return
        
        # Salva estado para undo antes de fazer mudanças (opcional)
        if save_state:
            self.save_state()
        
        item = self.data[self.current_index]
        
        # Handle run_data - always use run_data for bib number and category
        run_data = item.setdefault("run_data", {})
        
        # Update bib number and category in run_data
        run_data["bib_number"] = self.bib_number.text()
        cat = self.bib_category.currentText()
        if cat:
            run_data["run_category"] = cat
        
        # Handle shoes brands - update all shoes with selected brands
        checked_brands = [chk.text() for chk in self.brand_checks if chk.isChecked()]
        shoes = item.get("shoes", [])
        
        # Get current brands to detect changes for exporting crops
        old_brands = set()
        for shoe in shoes:
            if "classification_label" in shoe and shoe["classification_label"]:
                old_brands.add(shoe["classification_label"])
            elif "new_label" in shoe and shoe["new_label"]:
                old_brands.add(shoe["new_label"])
            elif "label" in shoe and shoe["label"]:
                old_brands.add(shoe["label"])
        
        # Clear all existing brands first
        for shoe in shoes:
            if "classification_label" in shoe:
                shoe["classification_label"] = ""
            elif "new_label" in shoe:
                shoe["new_label"] = ""
            elif "label" in shoe:
                shoe["label"] = ""
        
        # Apply selected brands to shoes (distribute evenly if multiple brands selected)
        if checked_brands and shoes:
            for idx, shoe in enumerate(shoes):
                # If only one brand selected, apply to all shoes
                if len(checked_brands) == 1:
                    brand = checked_brands[0]
                else:
                    # If multiple brands, cycle through them
                    brand = checked_brands[idx % len(checked_brands)]
                
                # Apply to the appropriate field based on what exists
                if "classification_label" in shoe:
                    shoe["classification_label"] = brand
                elif "new_label" in shoe:
                    shoe["new_label"] = brand
                else:
                    shoe["new_label"] = brand
        
        # Note: Export is now handled by the "K" key (keep_only_current_image method)
        
        self.data[self.current_index] = item
        self.mark_unsaved_changes()
        self.update_status_bar()

    def save_json(self) -> None:
        """Salva no arquivo atual"""
        if not self.json_path:
            self.save_as_json()
            return
        if not self.backup_done:
            shutil.copy(self.json_path, self.json_path + ".bak")
            self.backup_done = True
        with open(self.json_path, "w", encoding="utf-8") as f:
            json.dump(self.data, f, ensure_ascii=False, indent=2)
        self.has_unsaved_changes = False
        self.update_window_title()

    def save_as_json(self) -> None:
        """Salva com novo nome de arquivo"""
        if not self.data:
            return
        path, _ = QFileDialog.getSaveFileName(self, "Salvar JSON", filter="JSON Files (*.json)")
        if path:
            with open(path, "w", encoding="utf-8") as f:
                json.dump(self.data, f, ensure_ascii=False, indent=2)
            self.json_path = path
            self.backup_done = False  # Reset backup flag for new file
            self.has_unsaved_changes = False
            self.update_window_title()

    def update_window_title(self) -> None:
        """Atualiza o título da janela com indicador de mudanças"""
        title = "🏃 Runner Data Viewer"
        if self.json_path:
            filename = os.path.basename(self.json_path)
            title += f" - {filename}"
        if self.has_unsaved_changes:
            title += " *"
        self.setWindowTitle(title)

    def mark_unsaved_changes(self) -> None:
        """Marca que há mudanças não salvas"""
        if not self.has_unsaved_changes:
            self.has_unsaved_changes = True
            self.update_window_title()

    def on_item_selected(self, current: QTreeWidgetItem, previous: QTreeWidgetItem) -> None:
        """Handle tree item selection"""
        if current is None:
            return
        idx = current.data(0, Qt.UserRole)
        if isinstance(idx, int):
            self.show_entry(idx)

    # Undo functionality ------------------------------------------------
    def save_state(self) -> None:
        """Salva o estado atual para undo"""
        import copy
        state = {
            'data': copy.deepcopy(self.data),
            'current_index': self.current_index
        }
        self.undo_stack.append(state)
        if len(self.undo_stack) > self.max_undo:
            self.undo_stack.pop(0)
    
    def undo(self) -> None:
        """Desfaz a última alteração"""
        if not self.undo_stack:
            return
        state = self.undo_stack.pop()
        self.data = state['data']
        self.current_index = state['current_index']
        self.populate_tree()
        self.show_entry(self.current_index)
        self.save_json()
        self.update_status_bar()

    # Status and progress -----------------------------------------------
    def get_progress_stats(self) -> dict:
        """Calcula estatísticas de progresso"""
        total = len(self.data)
        checked = sum(1 for item in self.data if item.get('checked', False))
        return {
            'total': total,
            'checked': checked,
            'percentage': (checked / total * 100) if total > 0 else 0
        }

    def update_status_bar(self) -> None:
        """Atualiza a status bar com progresso"""
        stats = self.get_progress_stats()
        status_text = f"✓ Checadas: {stats['checked']} | Total: {stats['total']} | Progresso: {stats['percentage']:.1f}%"
        self.statusBar().showMessage(status_text)

    # Image management --------------------------------------------------
    def remove_current_image(self) -> None:
        """Remove a imagem atual (comando del)"""
        if not self.data:
            return
        
        # Salva estado para undo
        self.save_state()
        
        current_item = self.data[self.current_index]
        
        # Get bib number from run_data
        bib_number = ""
        run_data = current_item.get("run_data", {})
        if isinstance(run_data, dict):
            bib_number = str(run_data.get("bib_number", ""))
        
        # Remove a imagem
        self.data.pop(self.current_index)
        
        # Adjust current_index to select previous image (or keep same position if at beginning)
        if self.current_index > 0:
            self.current_index -= 1
        elif len(self.data) > 0:
            # If we were at index 0, stay at 0 (which now has the next image)
            self.current_index = 0
        else:
            # No more images
            self.current_index = -1
        
        self.populate_tree()
        if self.current_index >= 0 and self.current_index < len(self.data):
            self.show_entry(self.current_index)
            # Update tree selection to match current index
            self.select_tree_item_by_index(self.current_index)
        
        self.mark_unsaved_changes()
        self.update_status_bar()

    def remove_all_images_with_bib(self, bib_number) -> None:
        """Remove todas as imagens com um número de dorsal específico"""
        if not self.data or not bib_number:
            return
        
        # Salva estado para undo
        self.save_state()
        
        # Remove todas as imagens com o mesmo número de dorsal
        indices_to_remove = []
        for i, item in enumerate(self.data):
            # Get bib number from run_data
            item_bib_number = ""
            run_data = item.get("run_data", {})
            if isinstance(run_data, dict):
                item_bib_number = str(run_data.get("bib_number", ""))
            
            if item_bib_number == str(bib_number):
                indices_to_remove.append(i)
        
        if not indices_to_remove:
            return
        
        # Find the best new index (prefer previous image before the first removed one)
        first_removed_index = min(indices_to_remove)
        new_index = first_removed_index - 1 if first_removed_index > 0 else 0
        
        # Remove em ordem reversa para não afetar os índices
        for i in reversed(indices_to_remove):
            self.data.pop(i)
            # Adjust new_index if needed
            if i <= new_index:
                new_index = max(0, new_index - 1)
        
        # Update current index
        self.current_index = min(new_index, len(self.data) - 1) if self.data else -1
        
        self.populate_tree()
        if self.current_index >= 0:
            self.show_entry(self.current_index)
            # Update tree selection to match current index
            self.select_tree_item_by_index(self.current_index)
        
        self.mark_unsaved_changes()
        self.update_status_bar()

    def keep_only_current_image(self) -> None:
        """Mantém a imagem atual como master e atualiza todas as outras com o mesmo dorsal (comando k)"""
        if not self.data:
            return
        
        # Salva estado para undo
        self.save_state()
        
        current_item = self.data[self.current_index]
        
        # Get bib number from run_data
        bib_number = ""
        run_data = current_item.get("run_data", {})
        if isinstance(run_data, dict):
            bib_number = str(run_data.get("bib_number", ""))
        
        if not bib_number:
            return
        
        # Get current image's category and shoe brands to copy to others
        current_category = ""
        if isinstance(run_data, dict):
            current_category = run_data.get("run_category", "")
        
        # Get current shoe brands
        current_shoes = current_item.get("shoes", [])
        current_brands = []
        for shoe in current_shoes:
            brand = shoe.get("new_label") or shoe.get("label") or shoe.get("classification_label", "")
            if brand:
                current_brands.append(brand)
        
        # Mark current image as checked
        current_item['checked'] = True
        
        # Find and update all other images with the same bib number
        for i, item in enumerate(self.data):
            if i != self.current_index:
                # Get bib number from run_data
                item_bib_number = ""
                item_run_data = item.get("run_data", {})
                if isinstance(item_run_data, dict):
                    item_bib_number = str(item_run_data.get("bib_number", ""))
                
                if item_bib_number == bib_number:
                    # Uncheck this image
                    item['checked'] = False
                    
                    # Update category to match current image
                    if not isinstance(item_run_data, dict):
                        item["run_data"] = {}
                        item_run_data = item["run_data"]
                    item_run_data["run_category"] = current_category
                    
                    # Update shoe brands to match current image
                    item_shoes = item.get("shoes", [])
                    for idx, shoe in enumerate(item_shoes):
                        # Apply current brands cyclically if we have brands to apply
                        if current_brands:
                            brand_to_apply = current_brands[idx % len(current_brands)]
                            
                            # Apply to the appropriate field based on what exists
                            if "classification_label" in shoe:
                                shoe["classification_label"] = brand_to_apply
                            elif "new_label" in shoe:
                                shoe["new_label"] = brand_to_apply
                            else:
                                shoe["new_label"] = brand_to_apply
                        else:
                            # Clear brands if current image has no brands
                            if "classification_label" in shoe:
                                shoe["classification_label"] = ""
                            elif "new_label" in shoe:
                                shoe["new_label"] = ""
                            elif "label" in shoe:
                                shoe["label"] = ""
        
        # Export all shoes from the current (master) image after updating labels
        self.export_current_shoes()
        
        self.populate_tree()
        self.show_entry(self.current_index)
        # Ensure tree selection stays on current item
        self.select_tree_item_by_index(self.current_index)
        self.mark_unsaved_changes()
        self.update_status_bar()

    def toggle_checked(self) -> None:
        """Alterna o status de checado da imagem atual (comando c)"""
        if not self.data:
            return
        
        # Salva estado para undo
        self.save_state()
        
        current_item = self.data[self.current_index]
        current_checked = current_item.get('checked', False)
        current_item['checked'] = not current_checked
        
        self.mark_unsaved_changes()
        self.update_status_bar()
        
        # Atualiza a visualização para mostrar o status
        self.show_entry(self.current_index)

    def is_current_checked(self) -> bool:
        """Verifica se a imagem atual está checada"""
        if not self.data or self.current_index >= len(self.data):
            return False
        return self.data[self.current_index].get('checked', False)

    def eventFilter(self, source, event):
        """Intercepta eventos de teclado da tree widget para dar prioridade aos shortcuts"""
        if source == self.tree and event.type() == QEvent.Type.KeyPress:
            # Intercepta nossos shortcuts antes da tree widget processar
            key = event.key()
            modifiers = event.modifiers()
            key_text = event.text().lower()
            
            # Verifica se é um atalho de marca
            key_to_brand = self.get_key_to_brand_mapping()
            if key_text in key_to_brand:
                # Processa o atalho da marca no contexto da janela principal
                self.keyPressEvent(event)
                return True  # Bloqueia o evento para a tree widget
            
            # Nossos shortcuts personalizados
            if key == Qt.Key_C or key == Qt.Key_K or key == Qt.Key_Delete or \
               (modifiers == Qt.ControlModifier and key == Qt.Key_Z) or \
               key == Qt.Key_Return or key == Qt.Key_Enter:
                # Processa o evento no contexto da janela principal
                self.keyPressEvent(event)
                return True  # Bloqueia o evento para a tree widget
            
            # Para setas, permite navegação normal da tree mas também processa nossa lógica
            if key in (Qt.Key_Up, Qt.Key_Down, Qt.Key_Left, Qt.Key_Right):
                # Deixa a tree processar primeiro (para navegação visual)
                # Nosso keyPressEvent será chamado depois automaticamente
                return False
                
        # Para outros eventos, deixa processar normalmente
        return super().eventFilter(source, event)

    # navigation and editing -----------------------------------------------
    def keyPressEvent(self, event: QKeyEvent):
        if not self.data:
            return
            
        # Ctrl+Z para undo
        if event.modifiers() == Qt.ControlModifier and event.key() == Qt.Key_Z:
            self.undo()
            return
        
        # Verifica se é um atalho de marca primeiro
        key_text = event.text().lower()
        key_to_brand = self.get_key_to_brand_mapping()
        if key_text in key_to_brand:
            # Verifica se a imagem atual está checada (trava operações)
            is_checked = self.is_current_checked()
            if is_checked:
                QMessageBox.information(self, "Imagem Checada", f"Esta imagem está checada e não pode ser editada. Pressione 'C' para deschequear primeiro.")
                return
            self.set_brand_by_key(key_text)
            return
            
        # Verifica se a imagem atual está checada (trava operações destrutivas)
        is_checked = self.is_current_checked()
        
        # Del - remove imagem (só se não estiver checada)
        if event.key() == Qt.Key_Delete:
            if is_checked:
                QMessageBox.information(self, "Imagem Checada", "Esta imagem está checada e não pode ser removida. Pressione 'C' para deschequear primeiro.")
                return
            
            # Verifica se a seleção na tree é um número de dorsal
            current_tree_item = self.tree.currentItem()
            if current_tree_item:
                # Se é um item de nível de dorsal (tem filhos mas não tem índice de dados)
                if current_tree_item.childCount() > 0 and current_tree_item.data(0, Qt.UserRole) is None:
                    # É um número de dorsal, remove todas as imagens deste número
                    bib_number = current_tree_item.text(0)
                    self.remove_all_images_with_bib(bib_number)
                else:
                    # É uma imagem específica
                    self.remove_current_image()
            else:
                self.remove_current_image()
            return
            
        # K - manter apenas esta imagem para o número do dorsal (só se não estiver checada)
        if event.key() == Qt.Key_K:
            if is_checked:
                QMessageBox.information(self, "Imagem Checada", "Esta imagem está checada e não pode propagar suas informações. Pressione 'C' para deschequear primeiro.")
                return
            self.keep_only_current_image()
            return
            
        # C - toggle checked status
        if event.key() == Qt.Key_C:
            self.toggle_checked()
            return
            
        # Navegação
        if event.key() == Qt.Key_Right or event.key() == Qt.Key_Down:
            self.current_index = min(self.current_index + 1, len(self.data)-1)
            self.show_entry(self.current_index)
            return
        if event.key() == Qt.Key_Left or event.key() == Qt.Key_Up:
            self.current_index = max(self.current_index - 1, 0)
            self.show_entry(self.current_index)
            return
        if event.key() == Qt.Key_Return or event.key() == Qt.Key_Enter:
            if not is_checked:  # Só permite editar se não estiver checada
                self.apply_changes()
            else:
                QMessageBox.information(self, "Imagem Checada", "Esta imagem está checada e não pode ser editada. Pressione 'C' para deschequear primeiro.")
            return
        super().keyPressEvent(event)

    def closeEvent(self, event):
        """Handle application close event"""
        if self.has_unsaved_changes:
            reply = QMessageBox.question(
                self, 
                "Mudanças não salvas", 
                "Você tem mudanças não salvas. Deseja salvar antes de sair?",
                QMessageBox.Save | QMessageBox.Discard | QMessageBox.Cancel
            )
            
            if reply == QMessageBox.Save:
                self.save_json()
                event.accept()
            elif reply == QMessageBox.Discard:
                event.accept()
            else:  # Cancel
                event.ignore()
        else:
            event.accept()

    def select_tree_item_by_index(self, data_index: int) -> None:
        """Selects the tree item that corresponds to the given data index"""
        if data_index < 0 or data_index >= len(self.data):
            return
            
        def find_item_with_index(item: QTreeWidgetItem, target_index: int) -> QTreeWidgetItem:
            """Recursively search for tree item with specific data index"""
            # Check if this item has the target index
            item_index = item.data(0, Qt.UserRole)
            if item_index == target_index:
                return item
            
            # Search children
            for i in range(item.childCount()):
                child = item.child(i)
                if child:
                    result = find_item_with_index(child, target_index)
                    if result:
                        return result
            return None
        
        # Search through all top-level items
        for i in range(self.tree.topLevelItemCount()):
            top_item = self.tree.topLevelItem(i)
            if top_item:
                result = find_item_with_index(top_item, data_index)
                if result:
                    self.tree.setCurrentItem(result)
                    return

    def set_brand_by_key(self, key_char: str) -> None:
        """Define a marca baseada na tecla pressionada conforme configuração"""
        if not self.data:
            return
        
        # Encontra a label correspondente à tecla
        config_labels = self.config.get("labels", [])
        target_brand = None
        
        for label_config in config_labels:
            if isinstance(label_config, dict) and label_config.get("key") == key_char.lower():
                target_brand = label_config.get("label")
                break
        
        if not target_brand:
            return
        
        # Salva estado para undo
        self.save_state()
        
        # Desmarca todas as marcas
        for chk in self.brand_checks:
            chk.setChecked(False)
        
        # Marca apenas a marca selecionada
        for chk in self.brand_checks:
            if chk.text() == target_brand:
                chk.setChecked(True)
                break
        
        # Aplica as mudanças automaticamente (sem salvar estado novamente)
        self.apply_changes(save_state=False)
        
        # DON'T automatically check the image when using brand shortcuts
        # User can manually check with 'C' key if needed
        
        # Atualiza a visualização
        self.show_entry(self.current_index)
        
        # Atualiza a tree
        self.populate_tree()
        self.select_tree_item_by_index(self.current_index)
        
        self.mark_unsaved_changes()
        self.update_status_bar()

    def get_key_to_brand_mapping(self) -> dict:
        """Retorna um dicionário mapeando teclas para marcas"""
        config_labels = self.config.get("labels", [])
        mapping = {}
        
        for label_config in config_labels:
            if isinstance(label_config, dict):
                key = label_config.get("key", "").lower()
                label = label_config.get("label")
                if key and label:
                    mapping[key] = label
        
        return mapping

    # Change handlers ----------------------------------------
    def on_bib_number_enter(self) -> None:
        """Handle Enter key press in bib number field"""
        if not self.data or self.current_index >= len(self.data):
            return
        
        # Skip if image is checked (locked)
        if self.is_current_checked():
            return
        
        text = self.bib_number.text()
        item = self.data[self.current_index]
        
        # Ensure run_data exists and is a dict
        run_data = item.setdefault("run_data", {})
        
        # Update bib number in run_data
        run_data["bib_number"] = text
        
        self.mark_unsaved_changes()
        # Update tree to reflect changes
        self.populate_tree()
        self.select_tree_item_by_index(self.current_index)

    def on_category_selected(self, index: int) -> None:
        """Handle category selection from dropdown"""
        if not self.data or self.current_index >= len(self.data):
            return
        
        # Skip if image is checked (locked)
        if self.is_current_checked():
            return
        
        text = self.bib_category.currentText()
        if not text:  # Skip empty selections
            return
            
        item = self.data[self.current_index]
        
        # Ensure run_data exists and is a dict
        run_data = item.setdefault("run_data", {})
        
        # Update category in run_data
        run_data["run_category"] = text
        
        self.mark_unsaved_changes()
        # Update tree to reflect changes
        self.populate_tree()
        self.select_tree_item_by_index(self.current_index)

    def on_brand_changed_immediate(self) -> None:
        """Handle real-time changes to shoe brands (immediate for checkboxes)"""
        if not self.data or self.current_index >= len(self.data):
            return
        
        # Skip if image is checked (locked)
        if self.is_current_checked():
            return
        
        item = self.data[self.current_index]
        
        # Handle shoes brands - update all shoes with selected brands
        checked_brands = [chk.text() for chk in self.brand_checks if chk.isChecked()]
        shoes = item.get("shoes", [])
        
        # Clear all existing brands first
        for shoe in shoes:
            if "classification_label" in shoe:
                shoe["classification_label"] = ""
            elif "new_label" in shoe:
                shoe["new_label"] = ""
            elif "label" in shoe:
                shoe["label"] = ""
        
        # Apply selected brands to shoes (distribute evenly if multiple brands selected)
        if checked_brands and shoes:
            for idx, shoe in enumerate(shoes):
                # If only one brand selected, apply to all shoes
                if len(checked_brands) == 1:
                    brand = checked_brands[0]
                else:
                    # If multiple brands, cycle through them
                    brand = checked_brands[idx % len(checked_brands)]
                
                # Apply to the appropriate field based on what exists
                if "classification_label" in shoe:
                    shoe["classification_label"] = brand
                elif "new_label" in shoe:
                    shoe["new_label"] = brand
                else:
                    shoe["new_label"] = brand
        
        self.mark_unsaved_changes()
        # Refresh the shoe display to show updated brands
        self.show_entry(self.current_index)

    def adjust_shoe_container_size(self):
        """Adjust the shoe container size to fit all shoes without scroll bars"""
        if hasattr(self, 'shoe_container') and self.shoe_container:
            # Calculate the total height needed for all shoe widgets
            total_height = 0
            for i in range(self.shoe_box.count()):
                item = self.shoe_box.itemAt(i)
                if item and item.widget():
                    widget = item.widget()
                    # Get the size hint or actual size
                    try:
                        size_hint = widget.sizeHint()
                        if size_hint.isValid() and size_hint.height() > 0:
                            widget_height = size_hint.height()
                        else:
                            widget_height = 150  # Default fallback
                    except:
                        widget_height = 150  # Default fallback
                    total_height += widget_height
            
            # Add spacing between widgets
            spacing = self.shoe_box.spacing() * max(0, self.shoe_box.count() - 1)
            total_height += spacing + 20  # Extra margin
            
            # Set the container to the calculated size
            if total_height > 0:
                self.shoe_container.setFixedHeight(total_height)

    def export_shoe_crop(self, label, shoe_path):
        """Export a crop of the shoe to crops/[label]/[shoeimg]"""
        try:
            # Verificar se a imagem existe
            if not os.path.exists(shoe_path):
                print(f"Shoe image not found: {shoe_path}")
                return
            
            # Criar diretório de destino
            crops_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'crops', label)
            os.makedirs(crops_dir, exist_ok=True)
            
            # Nome do arquivo de destino
            shoe_filename = os.path.basename(shoe_path)
            dest_path = os.path.join(crops_dir, shoe_filename)
            
            # Copiar o arquivo
            import shutil
            shutil.copy2(shoe_path, dest_path)
            print(f"Exported shoe crop: {dest_path}")
            
        except Exception as e:
            print(f"Error exporting shoe crop: {e}")

    def export_current_shoes(self) -> None:
        """Export all shoes from ALL images with the same bib number to train/[label]/ folders"""
        if not self.data or self.current_index >= len(self.data):
            return
        
        current_item = self.data[self.current_index]
        
        # Get bib number from current image
        bib_number = ""
        run_data = current_item.get("run_data", {})
        if isinstance(run_data, dict):
            bib_number = str(run_data.get("bib_number", ""))
        
        if not bib_number:
            print("No bib number found for current image")
            return
        
        # Get output folder from config
        output_folder = self.config.get("output_folder", "train")
        
        # Find all images with the same bib number and export their shoes
        exported_count = 0
        for idx, item in enumerate(self.data):
            # Get bib number from this item
            item_bib_number = ""
            item_run_data = item.get("run_data", {})
            if isinstance(item_run_data, dict):
                item_bib_number = str(item_run_data.get("bib_number", ""))
            
            # Skip if not the same bib number
            if item_bib_number != bib_number:
                continue
            
            # Get the original image path
            img_filename = item.get("filename") or item.get("image_path", "")
            if not img_filename:
                print(f"No image filename found for item {idx}")
                continue
            
            img_path = os.path.join(self.config.get("base_path", ""), img_filename)
            if not os.path.exists(img_path):
                print(f"Original image not found: {img_path}")
                continue
            
            try:
                from PIL import Image
                img = Image.open(img_path)
            except Exception as e:
                print(f"Error opening image {img_path}: {e}")
                continue
            
            # Process each shoe in this image
            shoes = item.get("shoes", [])
            for i, shoe in enumerate(shoes):
                try:
                    # Get the brand/label for this shoe
                    brand = shoe.get("new_label") or shoe.get("label") or shoe.get("classification_label", "")
                    if not brand:
                        print(f"No brand found for shoe {i} in image {idx}")
                        continue
                    
                    # Get the bounding box
                    shoe_bbox = shoe.get("bbox")
                    if not shoe_bbox or len(shoe_bbox) < 4:
                        print(f"No valid bbox found for shoe {i} in image {idx}")
                        continue
                    
                    # Crop the shoe from the original image using existing method
                    shoe_crop = self.crop_image(img, shoe_bbox)
                    
                    # Create output directory structure: train/[brand]/
                    brand_dir = os.path.join(output_folder, brand)
                    os.makedirs(brand_dir, exist_ok=True)
                    
                    # Generate output filename with image index to avoid duplicates
                    base_name = os.path.splitext(os.path.basename(img_filename))[0]
                    shoe_filename = f"crop_{base_name}_img{idx}_shoe_{i}.jpg"
                    output_path = os.path.join(brand_dir, shoe_filename)
                    
                    # Save the cropped shoe
                    shoe_crop.save(output_path, "JPEG", quality=95)
                    print(f"Exported shoe crop: {output_path}")
                    exported_count += 1
                    
                except Exception as e:
                    print(f"Error exporting shoe {i} from image {idx}: {e}")
        
        print(f"Exported {exported_count} shoe crops for bib number {bib_number}")

    def on_shoe_click(self, event, shoe_index):
        """Handle clicking on a shoe image to remove it"""
        from PyQt5.QtWidgets import QMessageBox
        
        if not self.data or self.current_index >= len(self.data):
            return
            
        current_item = self.data[self.current_index]
        shoes = current_item.get("shoes", [])
        
        if shoe_index >= len(shoes):
            return
            
        shoe = shoes[shoe_index]
        brand = shoe.get("new_label") or shoe.get("label") or shoe.get("classification_label", "Unknown")
        
        # Show confirmation dialog
        reply = QMessageBox.question(
            self, 
            'Remove Shoe', 
            f'Are you sure you want to remove this {brand} shoe from the image?',
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No
        )
        
        if reply == QMessageBox.Yes:
            # Save state for undo
            self.save_state()
            
            # Remove the shoe from the data
            shoes.pop(shoe_index)
            current_item["shoes"] = shoes
            
            # Mark as having unsaved changes
            self.mark_unsaved_changes()
            
            # Refresh the display
            self.show_entry(self.current_index)
            self.populate_tree()
            self.select_tree_item_by_index(self.current_index)

    def on_filter_changed(self) -> None:
        """Handle filter checkbox changes"""
        if self.data:
            self.populate_tree()

    def bib_has_checked_images(self, bib_number: str) -> bool:
        """Check if a bib number has any checked images"""
        for item in self.data:
            # Get bib number from run_data
            item_run_data = item.get("run_data", {})
            if isinstance(item_run_data, dict):
                item_bib_number = str(item_run_data.get("bib_number", ""))
                if item_bib_number == bib_number and item.get("checked", False):
                    return True
        return False

def main() -> None:
    app = QApplication(sys.argv)
    viewer = RunnerViewer()
    viewer.show()
    sys.exit(app.exec_())


if __name__ == "__main__":
    main()
