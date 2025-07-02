#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Modularized Runner Data Viewer Application

This refactored version splits the original monolithic viewer_app.py into:
- core/: Business logic, data models, and data management
- ui/: User interface components and widgets  
- utils/: Configuration and utility functions

The architecture follows separation of concerns with clear module boundaries.
"""

import json
import os
import shutil
import sys
import copy
from typing import List, Dict, Any
import io

import yaml
from PIL import Image
from PyQt5.QtCore import Qt, QEvent
from PyQt5.QtGui import QPixmap, QFont, QPalette, QColor, QKeyEvent
from PyQt5.QtWidgets import (
    QAction, QApplication, QCheckBox, QComboBox, QFileDialog, QGridLayout,
    QHBoxLayout, QLabel, QLineEdit, QMainWindow, QMessageBox, QSplitter,
    QTreeWidget, QTreeWidgetItem, QVBoxLayout, QWidget, QFrame,
    QScrollArea, QGroupBox, QPushButton, QSizePolicy
)

# Import modular components
from core.data_manager import DataManager
from core.models import DataCache, get_position_from_bib
from ui.widgets import ClickableLabel
from utils.config import load_config, save_config
from utils.image_utils import crop_image, pil_to_qpixmap

# Default configuration
DEFAULT_VIEWER_CONFIG = {
    "base_path": os.getcwd(),
    "labels": []
}


class RunnerViewer(QMainWindow):
    """Main application class for the Runner Viewer."""
    
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("🏃 Runner Data Viewer")
        self.setup_styling()
        self.setMinimumSize(800, 600)
        
        # Configuration
        self.config_path = os.path.join(os.getcwd(), "viewer_config.yaml")
        self.config = load_config(self.config_path)
        if not self.config:
            self.config = DEFAULT_VIEWER_CONFIG
            save_config(self.config_path, self.config)
        
        # Data management
        self.data_manager = DataManager()
        self.json_path = ""
        self.current_index = 0
        self.brands: List[str] = []
        self.bib_categories: List[str] = []
        self.backup_done = False
        self.has_unsaved_changes = False
        
        # UI setup
        self.setup_ui()
        self.setup_menu()
        
        # Cache for performance
        self.bib_cache = {}
        self._expansion_connected = False

    def setup_styling(self) -> None:
        """Apply modern styling to the application"""
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
        
        # Category filter
        filter_layout.addWidget(QLabel("Categoria:"))
        self.category_filter = QComboBox()
        self.category_filter.addItem("Todas as categorias")
        self.category_filter.activated.connect(self.on_filter_changed)
        filter_layout.addWidget(self.category_filter)
        
        self.filter_unchecked_only = QCheckBox("Mostrar apenas dorsais sem imagens checadas")
        self.filter_unchecked_only.stateChanged.connect(self.on_filter_changed)
        filter_layout.addWidget(self.filter_unchecked_only)
        
        layout.addWidget(filter_group)
        
        # Tree widget
        self.tree = QTreeWidget()
        self.tree.setHeaderLabels(["Categoria / Dorsal / Nome"])
        self.tree.currentItemChanged.connect(self.on_item_selected)
        # Install event filter for keyboard events
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
        self.shoe_box.setSpacing(5)
        self.shoe_box.setContentsMargins(5, 5, 5, 5)
        shoes_scroll.setWidget(self.shoe_container)
        shoes_scroll.setMaximumWidth(300)
        shoes_scroll.setMinimumHeight(400)
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
        
        # Add stretch to push everything to top
        layout.addStretch()
        
        return panel

    # Data operations using the new data manager
    def load_json(self) -> None:
        """Load JSON data file using the data manager."""
        path, _ = QFileDialog.getOpenFileName(self, "JSON", filter="JSON Files (*.json)")
        if not path:
            return
        
        try:
            self.json_path = path
            self.data_manager.load_json(path)
            
            # Clear undo stack and reset state
            self.has_unsaved_changes = False
            
            self.collect_stats()
            self.populate_tree()
            self.show_entry(0)
            self.update_status_bar()
            self.update_window_title()
            
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to load JSON: {e}")

    def collect_stats(self) -> None:
        """Collect brands and categories using the data manager."""
        config_labels = self.config.get("labels", [])
        self.brands, self.bib_categories = self.data_manager.collect_stats(config_labels)

        # Update UI components
        self.bib_category.clear()
        self.bib_category.addItems(self.bib_categories)
        
        # Update category filter
        self.category_filter.clear()
        self.category_filter.addItem("Todas as categorias")
        self.category_filter.addItems(self.bib_categories)

        # Setup brand checkboxes
        for chk in self.brand_checks:
            chk.deleteLater()
        self.brand_checks = []
        
        # Organize brands in two columns
        for i, b in enumerate(self.brands):
            cb = QCheckBox(b)
            cb.stateChanged.connect(self.on_brand_changed_immediate)
            row = i // 2
            col = i % 2
            self.brand_layout.addWidget(cb, row, col)
            self.brand_checks.append(cb)

    def populate_tree(self) -> None:
        """Populate tree using the new cache system."""
        self.tree.clear()
        
        # Get selected category filter
        selected_category = self.category_filter.currentText()
        if selected_category == "Todas as categorias":
            selected_category = None
        
        # Check if we should filter for unchecked only
        filter_unchecked_only = self.filter_unchecked_only.isChecked()
        
        # Get relevant cache entries for the selected category
        relevant_bibs = []
        cache = self.data_manager.cache
        
        for cache_key, cache_data in cache.bib_cache.items():
            bib_number = cache_data['bib_number']
            category = cache_data['category']
            
            # Skip if doesn't match category filter
            if selected_category and category != selected_category:
                continue
            
            # Apply filter: skip this bib if it has checked images and we're filtering for unchecked only
            if filter_unchecked_only and bib_number != "?" and self.data_manager.bib_has_checked_images(str(bib_number)):
                continue
            
            relevant_bibs.append(cache_data)
        
        # Sort by position (numeric value of bib number)
        relevant_bibs.sort(key=lambda x: get_position_from_bib(x['position']))
        
        # Create tree nodes
        for cache_data in relevant_bibs:
            bib_number = cache_data['bib_number']
            
            position = get_position_from_bib(cache_data['position'])
            gender = cache_data["gender"]

            # Create the bib node with format [Position]. [Bib Number]
            if position == 999999:
                bib_text = f"?. {gender} ({bib_number})"
            else:
                bib_text = f"{position}. {gender} ({bib_number})"
            
            bib_node = QTreeWidgetItem(self.tree, [bib_text])
            
            # Store the best image index as the bib node's data
            bib_node.setData(0, Qt.UserRole, cache_data['index'])
            
            # Mark that this node needs to load children when expanded
            bib_node.setData(1, Qt.UserRole, {'bib_number': bib_number, 'category': selected_category, 'loaded': False})
            
            # Add a dummy child so the expansion triangle appears
            dummy_child = QTreeWidgetItem(bib_node, ["Carregando..."])
            
        # Connect the tree expansion signal to load children on demand
        if not self._expansion_connected:
            self.tree.itemExpanded.connect(self.on_tree_item_expanded)
            self._expansion_connected = True
        
        # Keep tree collapsed by default
        self.tree.collapseAll()

    def show_entry(self, index: int) -> None:
        """Display entry using new image utilities."""
        if not self.data_manager.data:
            return
        
        index = max(0, min(index, len(self.data_manager.data)-1))
        self.current_index = index
        data_item = self.data_manager.data[index]
        
        # Check if checked
        is_checked = data_item.get('checked', False)
        
        # Get image path
        img_filename = data_item.get("filename") or data_item.get("image_path", "")
        img_path = os.path.join(self.config.get("base_path", ""), img_filename)
        
        try:
            img = Image.open(img_path)
        except Exception:
            print("Imagem não encontrada")
            return
        
        # Display thumbnail with status indicator
        thumb_img = img.resize((150, int(150*img.height/img.width)))
        thumb_pixmap = pil_to_qpixmap(thumb_img)
        
        if is_checked:
            self.thumb_label.setStyleSheet("border: 4px solid #28a745; border-radius: 8px; padding: 16px; background-color: #d4edda;")
        else:
            self.thumb_label.setStyleSheet("border: 2px dashed #ddd; border-radius: 8px; padding: 20px; background-color: #f8f9fa;")
        
        self.thumb_label.setPixmap(thumb_pixmap)
        
        # Display runner crop
        bbox = data_item.get("bbox") or data_item.get("person_bbox", [0, 0, img.width, img.height])
        runner = crop_image(img, bbox)
        target_width, target_height = self.runner_label.width(), self.runner_label.height()
        width_ratio = target_width / runner.width * 0.95
        height_ratio = target_height / runner.height * 0.95
        scale_ratio = min(width_ratio, height_ratio)
        runner_img = runner.resize((int(runner.width * scale_ratio), int(runner.height * scale_ratio)))
        runner_pixmap = pil_to_qpixmap(runner_img)
        self.runner_label.setPixmap(runner_pixmap)

        # Display shoes
        self._display_shoes(img, data_item)
        
        # Update right panel data
        self._update_right_panel_data(data_item)
        
        # Update status bar
        self.update_status_bar()

    def _display_shoes(self, img: Image.Image, data_item: Dict[str, Any]) -> None:
        """Display shoes using the new system."""
        # Clear existing shoes
        for i in reversed(range(self.shoe_box.count())):
            layout_item = self.shoe_box.itemAt(i)
            if layout_item:
                w = layout_item.widget()
                if w:
                    w.deleteLater()
        
        shoes = data_item.get("shoes", [])
        num_shoes = len(shoes)
        
        if num_shoes == 0:
            return
        
        # Calculate container dimensions
        container_height = self.shoe_container.height()
        container_width = 270
        
        self.shoe_container.setMinimumHeight(container_height)
        self.shoe_container.setMaximumHeight(container_height)
        
        # Calculate available space per shoe
        label_height = 20
        widget_margins = 10
        layout_spacing = self.shoe_box.spacing() * max(0, num_shoes - 1)
        total_reserved_height = num_shoes * (label_height + widget_margins) + layout_spacing + 30
        
        available_height_per_shoe = max((container_height - total_reserved_height) / num_shoes, 40)
        available_width = container_width - 20
        
        # Display each shoe
        for shoe_index, shoe in enumerate(shoes):
            shoe_bbox = shoe.get("bbox")
            if shoe_bbox and len(shoe_bbox) >= 4:
                try:
                    crop = crop_image(img, shoe_bbox)
                    
                    # Calculate scaling
                    height_ratio = available_height_per_shoe / crop.height if crop.height > 0 else 1
                    width_ratio = available_width / crop.width if crop.width > 0 else 1
                    shoe_ratio = min(height_ratio, width_ratio, 2.0)
                    shoe_ratio = max(shoe_ratio, 0.2)
                    shoe_ratio = min(shoe_ratio, 3.0)
                    
                    new_width = max(int(crop.width * shoe_ratio), 60)
                    new_height = max(int(crop.height * shoe_ratio), 40)
                    
                    shoe_img = crop.resize((new_width, new_height))
                    shoe_pixmap = pil_to_qpixmap(shoe_img)
                    
                    # Create shoe widget container
                    shoe_widget = QWidget()
                    shoe_layout = QVBoxLayout(shoe_widget)
                    shoe_layout.setContentsMargins(5, 5, 5, 5)
                    
                    # Add brand label
                    brand = shoe.get("new_label") or shoe.get("label") or shoe.get("classification_label", "")
                    if brand:
                        brand_lbl = QLabel(brand)
                        brand_lbl.setStyleSheet("font-size: 11px; color: #666; font-weight: bold;")
                        brand_lbl.setAlignment(Qt.AlignCenter)
                        shoe_layout.addWidget(brand_lbl)
                    
                    # Create clickable shoe label
                    lbl = ClickableLabel(shoe_index=shoe_index, callback=self.on_shoe_click)
                    lbl.setPixmap(shoe_pixmap)
                    lbl.setStyleSheet("border: 1px solid #ddd; border-radius: 4px; padding: 2px; cursor: pointer;")
                    lbl.setAlignment(Qt.AlignCenter)
                    
                    shoe_layout.addWidget(lbl)
                    shoe_layout.addStretch()
                    
                    shoe_widget.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Expanding)
                    self.shoe_box.addWidget(shoe_widget)
                    
                except Exception as e:
                    print(f"Error processing shoe image: {e}")

    def _update_right_panel_data(self, data_item: Dict[str, Any]) -> None:
        """Update the right panel with current data."""
        is_checked = data_item.get('checked', False)
        
        # Get bib number and category
        run_data = data_item.get("run_data", {})
        bib_number = ""
        category = ""
        if isinstance(run_data, dict):
            bib_number = str(run_data.get("bib_number", ""))
            category = run_data.get("run_category", "")
        
        # Temporarily disconnect signals
        self._disconnect_right_panel_signals()
        
        # Update fields
        self.bib_number.setText(bib_number)
        self.bib_number.setEnabled(not is_checked)
        
        if category and category in self.bib_categories:
            self.bib_category.setCurrentText(category)
        else:
            self.bib_category.setCurrentIndex(-1)
        self.bib_category.setEnabled(not is_checked)
        
        # Update brand checkboxes
        for chk in self.brand_checks:
            chk.setChecked(False)
            chk.setEnabled(not is_checked)
        
        # Get current shoe brands
        brands_present = set()
        for shoe in data_item.get("shoes", []):
            brand = shoe.get("new_label") or shoe.get("label") or shoe.get("classification_label")
            if brand:
                brands_present.add(brand)
        
        for chk in self.brand_checks:
            if chk.text() in brands_present:
                chk.setChecked(True)
        
        # Reconnect signals
        self._reconnect_right_panel_signals()

    def _disconnect_right_panel_signals(self) -> None:
        """Temporarily disconnect right panel signals."""
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

    def _reconnect_right_panel_signals(self) -> None:
        """Reconnect right panel signals."""
        self.bib_number.returnPressed.connect(self.on_bib_number_enter)
        self.bib_category.activated.connect(self.on_category_selected)
        for chk in self.brand_checks:
            chk.stateChanged.connect(self.on_brand_changed_immediate)

    # Save operations using data manager
    def save_json(self) -> None:
        """Save using the data manager."""
        if not self.json_path:
            self.save_as_json()
            return
        
        try:
            if not self.backup_done:
                shutil.copy(self.json_path, self.json_path + ".bak")
                self.backup_done = True
            
            self.data_manager.save_json(self.json_path, backup=False)
            self.has_unsaved_changes = False
            self.update_window_title()
            
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to save: {e}")

    def save_as_json(self) -> None:
        """Save as new file using the data manager."""
        if not self.data_manager.data:
            return
        
        path, _ = QFileDialog.getSaveFileName(self, "Salvar JSON", filter="JSON Files (*.json)")
        if path:
            try:
                self.data_manager.save_json(path, backup=False)
                self.json_path = path
                self.backup_done = False
                self.has_unsaved_changes = False
                self.update_window_title()
                
            except Exception as e:
                QMessageBox.critical(self, "Error", f"Failed to save: {e}")

    def update_status_bar(self) -> None:
        """Update status bar using data manager stats."""
        stats = self.data_manager.get_progress_stats()
        status_text = f"✓ Checadas: {int(stats['checked'])} | Total: {int(stats['total'])} | Progresso: {stats['percentage']:.1f}%"
        self.statusBar().showMessage(status_text)

    def update_window_title(self) -> None:
        """Update window title with file info and unsaved changes indicator."""
        title = "🏃 Runner Data Viewer"
        if self.json_path:
            filename = os.path.basename(self.json_path)
            title += f" - {filename}"
        if self.has_unsaved_changes:
            title += " *"
        self.setWindowTitle(title)

    def mark_unsaved_changes(self) -> None:
        """Mark that there are unsaved changes."""
        if not self.has_unsaved_changes:
            self.has_unsaved_changes = True
            self.update_window_title()

    # Event handlers
    def on_item_selected(self, current: QTreeWidgetItem, previous=None) -> None:
        """Handle tree item selection."""
        if current is None:
            return
        idx = current.data(0, Qt.UserRole)
        if isinstance(idx, int):
            self.show_entry(idx)

    def on_filter_changed(self) -> None:
        """Handle filter changes."""
        if self.data_manager.data:
            self.populate_tree()
            # Select first item if available
            if self.tree.topLevelItemCount() > 0:
                first_item = self.tree.topLevelItem(0)
                if first_item:
                    self.tree.setCurrentItem(first_item)
                    self.on_item_selected(first_item, None)

    def on_bib_number_enter(self) -> None:
        """Handle Enter key in bib number field using data manager."""
        if not self.data_manager.data or self.current_index >= len(self.data_manager.data):
            return
        
        if self._is_current_checked():
            return
        
        bib_text = self.bib_number.text()
        
        # Save state for undo
        self.data_manager.save_state(self.current_index)
        
        # Update data
        item = self.data_manager.data[self.current_index]
        run_data = item.setdefault("run_data", {})
        run_data["bib_number"] = bib_text
        
        self.mark_unsaved_changes()
        self.populate_tree()
        self.select_next_tree_item()

    def on_category_selected(self, index: int) -> None:
        """Handle category selection using data manager."""
        if not self.data_manager.data or self.current_index >= len(self.data_manager.data):
            return
        
        if self._is_current_checked():
            return
        
        category_text = self.bib_category.currentText()
        if not category_text:
            return
        
        # Save state for undo
        self.data_manager.save_state(self.current_index)
        
        # Update data
        item = self.data_manager.data[self.current_index]
        run_data = item.setdefault("run_data", {})
        run_data["run_category"] = category_text
        
        self.mark_unsaved_changes()
        self.populate_tree()
        self.select_next_tree_item()

    def on_brand_changed_immediate(self) -> None:
        """Handle immediate brand changes using data manager."""
        if not self.data_manager.data or self.current_index >= len(self.data_manager.data):
            return
        
        if self._is_current_checked():
            return
        
        # Get checked brands
        checked_brands = [chk.text() for chk in self.brand_checks if chk.isChecked()]
        
        # Save state for undo
        self.data_manager.save_state(self.current_index)
        
        # Update data using data manager
        self.data_manager.update_image_data(
            self.current_index, 
            self.bib_number.text(),
            self.bib_category.currentText(),
            checked_brands
        )
        
        self.mark_unsaved_changes()
        self.show_entry(self.current_index)  # Refresh display

    def on_tree_item_expanded(self, item: QTreeWidgetItem) -> None:
        """Load children when a bib node is expanded"""
        # Check if this item needs to load children
        item_data = item.data(1, Qt.UserRole)
        if not isinstance(item_data, dict) or item_data.get('loaded', True):
            return
        
        bib_number = item_data.get('bib_number')
        category = item_data.get('category')
        
        if not bib_number:
            return
        
        # Remove the dummy child
        item.takeChildren()
        
        # Find all images for this bib number
        images_for_bib = []
        for idx, data_item in enumerate(self.data_manager.data):
            # Get bib number from run_data
            item_bib_number = ""
            run_data = data_item.get("run_data", {})
            if isinstance(run_data, dict):
                item_bib_number = str(run_data.get("bib_number", ""))
            
            # Get category
            item_category = ""
            if isinstance(run_data, dict):
                item_category = run_data.get("run_category", "")
                if item_category == "Not Identifiable":
                    item_category = "?"
            
            # Skip if doesn't match bib number or category filter
            if item_bib_number != bib_number:
                continue
            if category and category != "?" and item_category != category:
                continue
            
            images_for_bib.append((idx, data_item))
        
        # Add child nodes for each image
        for idx, data_item in images_for_bib:
            is_checked = data_item.get("checked", False)
            
            # Support both old and new format for filename
            img_name = data_item.get("filename") or data_item.get("image_path", str(idx))
            if img_name != str(idx):
                # Extract just the filename part if it's a path
                img_name = os.path.basename(img_name)
            
            if is_checked:
                img_name = "✓ " + img_name
            
            img_node = QTreeWidgetItem(item, [img_name])
            img_node.setData(0, Qt.UserRole, idx)
        
        # Mark as loaded
        item_data['loaded'] = True
        item.setData(1, Qt.UserRole, item_data)

    def on_shoe_click(self, event, shoe_index: int) -> None:
        """Handle shoe click for removal."""
        if not self.data_manager.data or self.current_index >= len(self.data_manager.data):
            return
            
        current_item = self.data_manager.data[self.current_index]
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
            self.data_manager.save_state(self.current_index)
            
            # Remove the shoe from the data
            shoes.pop(shoe_index)
            current_item["shoes"] = shoes
            
            # Mark as having unsaved changes
            self.mark_unsaved_changes()
            
            # Refresh the display
            self.show_entry(self.current_index)
            self.populate_tree()
            self.select_tree_item_by_index(self.current_index)

    def select_base_path(self) -> None:
        """Select base path for images."""
        folder = QFileDialog.getExistingDirectory(self, "Base de Imagens", self.config.get("base_path", ""))
        if folder:
            self.config["base_path"] = folder
            save_config(self.config_path, self.config)
            if self.json_path:
                self.populate_tree()
                self.show_entry(0)

    def select_tree_item_by_index(self, data_index: int) -> None:
        """Select tree item by data index."""
        if data_index < 0 or data_index >= len(self.data_manager.data):
            return
            
        def find_item_with_index(item: QTreeWidgetItem, target_index: int):
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
        
        # Search through all top-level items (bib nodes)
        for i in range(self.tree.topLevelItemCount()):
            bib_item = self.tree.topLevelItem(i)
            if bib_item:
                # Check if this bib node itself has the target index (best image)
                if bib_item.data(0, Qt.UserRole) == data_index:
                    self.tree.setCurrentItem(bib_item)
                    return
                
                # Search in children (if expanded)
                result = find_item_with_index(bib_item, data_index)
                if result:
                    # Expand the parent if needed
                    if not bib_item.isExpanded():
                        bib_item.setExpanded(True)
                    self.tree.setCurrentItem(result)
                    return

    def select_next_tree_item(self) -> None:
        """Select the next item in the tree after current operations."""
        current_item = self.tree.currentItem()
        if not current_item:
            # If no current item, select the first one
            if self.tree.topLevelItemCount() > 0:
                first_item = self.tree.topLevelItem(0)
                if first_item:
                    self.tree.setCurrentItem(first_item)
                    self.on_item_selected(first_item, None)
            return
        
        # Try to find the next item
        next_item = None
        
        # If current item has children and is expanded, go to first child
        if current_item.childCount() > 0 and current_item.isExpanded():
            next_item = current_item.child(0)
        else:
            # Look for next sibling or go up to parent's next sibling
            parent = current_item.parent()
            if parent:
                # We're in a child, find next sibling or parent's next sibling
                current_index = parent.indexOfChild(current_item)
                if current_index + 1 < parent.childCount():
                    next_item = parent.child(current_index + 1)
                else:
                    # No more siblings, find parent's next sibling
                    parent_index = self.tree.indexOfTopLevelItem(parent)
                    if parent_index + 1 < self.tree.topLevelItemCount():
                        next_item = self.tree.topLevelItem(parent_index + 1)
            else:
                # We're at top level, find next top level item
                current_index = self.tree.indexOfTopLevelItem(current_item)
                if current_index + 1 < self.tree.topLevelItemCount():
                    next_item = self.tree.topLevelItem(current_index + 1)
        
        # If we found a next item, select it
        if next_item:
            self.tree.setCurrentItem(next_item)
            # Trigger selection to update display
            self.on_item_selected(next_item, current_item)
        else:
            # No next item found, stay on current or go to last available
            if self.tree.topLevelItemCount() > 0:
                last_item = self.tree.topLevelItem(self.tree.topLevelItemCount() - 1)
                if last_item:
                    self.tree.setCurrentItem(last_item)
                    self.on_item_selected(last_item, current_item)

    def _is_current_checked(self) -> bool:
        """Check if current image is checked."""
        if not self.data_manager.data or self.current_index >= len(self.data_manager.data):
            return False
        return self.data_manager.data[self.current_index].get('checked', False)

    # Keyboard handling (simplified for now, could be moved to a separate handler)
    def eventFilter(self, source, event):
        """Handle keyboard events for the tree widget."""
        if source == self.tree and event.type() == QEvent.KeyPress:
            key = event.key()
            modifiers = event.modifiers()
            key_text = event.text().lower()
            
            # Check for brand shortcuts
            key_to_brand = self._get_key_to_brand_mapping()
            if key_text in key_to_brand:
                self.keyPressEvent(event)
                return True
            
            # Custom shortcuts
            if key == Qt.Key_C or key == Qt.Key_K or key == Qt.Key_Delete or \
               (modifiers == Qt.ControlModifier and key == Qt.Key_Z) or \
               key == Qt.Key_Return or key == Qt.Key_Enter:
                self.keyPressEvent(event)
                return True
            
            # Allow arrow key navigation
            if key in (Qt.Key_Up, Qt.Key_Down, Qt.Key_Left, Qt.Key_Right):
                return False
        
        return super().eventFilter(source, event)

    def keyPressEvent(self, event: QKeyEvent):
        """Handle key press events using the data manager."""
        if not self.data_manager.data:
            return
        
        # Ctrl+Z for undo
        if event.modifiers() == Qt.ControlModifier and event.key() == Qt.Key_Z:
            state = self.data_manager.undo()
            if state:
                self.current_index = state['current_index']
                self.populate_tree()
                self.show_entry(self.current_index)
                self.save_json()
                self.update_status_bar()
            return
        
        # Brand shortcuts
        key_text = event.text().lower()
        key_to_brand = self._get_key_to_brand_mapping()
        if key_text in key_to_brand:
            if self._is_current_checked():
                QMessageBox.information(self, "Imagem Checada", "Esta imagem está checada e não pode ser editada. Pressione 'C' para deschequear primeiro.")
                return
            self._set_brand_by_key(key_text)
            return
        
        is_checked = self._is_current_checked()
        
        # Delete key
        if event.key() == Qt.Key_Delete:
            if is_checked:
                QMessageBox.information(self, "Imagem Checada", "Esta imagem está checada e não pode ser removida. Pressione 'C' para deschequear primeiro.")
                return
            
            current_tree_item = self.tree.currentItem()
            if current_tree_item:
                if current_tree_item.childCount() > 0 and current_tree_item.data(0, Qt.UserRole) is None:
                    # Remove all images with this bib number
                    bib_number = current_tree_item.text(0)
                    self._remove_all_images_with_bib(bib_number)
                else:
                    # Remove current image
                    self._remove_current_image()
            else:
                self._remove_current_image()
            return
        
        # K key - propagate data
        if event.key() == Qt.Key_K:
            if is_checked:
                QMessageBox.information(self, "Imagem Checada", "Esta imagem está checada e não pode propagar suas informações. Pressione 'C' para deschequear primeiro.")
                return
            self._keep_only_current_image()
            return
        
        # C key - toggle checked
        if event.key() == Qt.Key_C:
            self._toggle_checked()
            return
        
        # Navigation
        if event.key() == Qt.Key_Right or event.key() == Qt.Key_Down:
            self.current_index = min(self.current_index + 1, len(self.data_manager.data) - 1)
            self.show_entry(self.current_index)
            return
        if event.key() == Qt.Key_Left or event.key() == Qt.Key_Up:
            self.current_index = max(self.current_index - 1, 0)
            self.show_entry(self.current_index)
            return
        if event.key() == Qt.Key_Return or event.key() == Qt.Key_Enter:
            if not is_checked:
                self._apply_changes()
            else:
                QMessageBox.information(self, "Imagem Checada", "Esta imagem está checada e não pode ser editada. Pressione 'C' para deschequear primeiro.")
            return

    def _remove_current_image(self) -> None:
        """Remove current image using data manager."""
        self.data_manager.save_state(self.current_index)
        new_index = self.data_manager.remove_image(self.current_index)
        self.current_index = new_index
        
        self.populate_tree()
        self.select_next_tree_item()
        self.mark_unsaved_changes()
        self.update_status_bar()

    def _remove_all_images_with_bib(self, bib_number: str) -> None:
        """Remove all images with specific bib number using data manager."""
        self.data_manager.save_state(self.current_index)
        new_index = self.data_manager.remove_all_images_with_bib(bib_number)
        self.current_index = new_index
        
        self.populate_tree()
        self.select_next_tree_item()
        self.mark_unsaved_changes()
        self.update_status_bar()

    def _keep_only_current_image(self) -> None:
        """Keep current image as master and propagate data using data manager."""
        self.data_manager.save_state(self.current_index)
        self.data_manager.propagate_data_to_same_bib(self.current_index)
        
        # Export shoes for this bib number
        current_item = self.data_manager.data[self.current_index]
        run_data = current_item.get("run_data", {})
        if isinstance(run_data, dict):
            bib_number = str(run_data.get("bib_number", ""))
            if bib_number:
                self._export_shoes_for_bib(bib_number)
        
        self.populate_tree()
        self.show_entry(self.current_index)
        self.select_tree_item_by_index(self.current_index)
        self.mark_unsaved_changes()
        self.update_status_bar()

    def _toggle_checked(self) -> None:
        """Toggle checked status using data manager."""
        self.data_manager.save_state(self.current_index)
        new_status = self.data_manager.toggle_checked(self.current_index)
        
        self.mark_unsaved_changes()
        self.update_status_bar()
        self.show_entry(self.current_index)  # Refresh display

    def _apply_changes(self) -> None:
        """Apply current changes using data manager."""
        if self._is_current_checked():
            return
        
        bib_number = self.bib_number.text()
        category = self.bib_category.currentText()
        checked_brands = [chk.text() for chk in self.brand_checks if chk.isChecked()]
        
        self.data_manager.save_state(self.current_index)
        self.data_manager.update_image_data(self.current_index, bib_number, category, checked_brands)
        
        self.mark_unsaved_changes()
        self.update_status_bar()
        self.populate_tree()
        self.select_next_tree_item()

    def _set_brand_by_key(self, key_char: str) -> None:
        """Set brand based on key shortcut."""
        config_labels = self.config.get("labels", [])
        target_brand = None
        
        for label_config in config_labels:
            if isinstance(label_config, dict) and label_config.get("key") == key_char.lower():
                target_brand = label_config.get("label")
                break
        
        if not target_brand:
            return
        
        # Update brand checkboxes
        for chk in self.brand_checks:
            chk.setChecked(chk.text() == target_brand)
        
        # Apply changes
        self._apply_changes()

    def _get_key_to_brand_mapping(self) -> Dict[str, str]:
        """Get key to brand mapping from config."""
        config_labels = self.config.get("labels", [])
        mapping = {}
        
        for label_config in config_labels:
            if isinstance(label_config, dict):
                key = label_config.get("key", "").lower()
                label = label_config.get("label")
                if key and label:
                    mapping[key] = label
        
        return mapping

    def _export_shoes_for_bib(self, bib_number: str) -> int:
        """Export all shoes for images with the same bib number."""
        if not bib_number:
            return 0
        
        output_folder = self.config.get("output_folder", "train")
        base_path = self.config.get("base_path", "")
        exported_count = 0
        
        for idx, item in enumerate(self.data_manager.data):
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
                continue
            
            img_path = os.path.join(base_path, img_filename)
            if not os.path.exists(img_path):
                continue
            
            try:
                img = Image.open(img_path)
            except Exception:
                continue
            
            # Process each shoe in this image
            shoes = item.get("shoes", [])
            for i, shoe in enumerate(shoes):
                try:
                    # Get the brand/label for this shoe
                    brand = shoe.get("new_label") or shoe.get("label") or shoe.get("classification_label", "")
                    if not brand:
                        continue
                    
                    # Get the bounding box
                    shoe_bbox = shoe.get("bbox")
                    if not shoe_bbox or len(shoe_bbox) < 4:
                        continue
                    
                    # Crop the shoe
                    shoe_crop = crop_image(img, shoe_bbox)
                    
                    # Create output directory
                    brand_dir = os.path.join(output_folder, brand)
                    os.makedirs(brand_dir, exist_ok=True)
                    
                    # Generate output filename
                    base_name = os.path.splitext(os.path.basename(img_filename))[0]
                    shoe_filename = f"crop_{base_name}_img{idx}_shoe_{i}.jpg"
                    output_path = os.path.join(brand_dir, shoe_filename)
                    
                    # Save the cropped shoe
                    shoe_crop.save(output_path, "JPEG", quality=95)
                    exported_count += 1
                    
                except Exception as e:
                    print(f"Error exporting shoe {i} from image {idx}: {e}")
        
        print(f"Exported {exported_count} shoe crops for bib number {bib_number}")
        return exported_count

    def closeEvent(self, event):
        """Handle application close event."""
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


def main() -> None:
    """Main entry point for the refactored application."""
    app = QApplication(sys.argv)
    viewer = RunnerViewer()
    viewer.show()
    sys.exit(app.exec_())


if __name__ == "__main__":
    main()
