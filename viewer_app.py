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
from ui.main_window import RunnerViewerMainWindow
from ui.config_dialog import ConfigurationDialog
from ui.widgets import ClickableLabel
from ui.image_display import ImageDisplayManager
from utils.config import load_config, save_config
from utils.image_utils import crop_image, pil_to_qpixmap, draw_bounding_boxes

# Default configuration
DEFAULT_VIEWER_CONFIG = {
    "base_path": os.getcwd(),
    "labels": [],
    "chest_plate_confidence_threshold": 0.5,
    "shoes_confidence_threshold": 0.5
}


class RunnerViewer(RunnerViewerMainWindow):
    """Main application class for the Runner Viewer."""
    
    def __init__(self) -> None:
        super().__init__()
        
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
        self.genders: List[str] = []
        self.backup_done = False
        self.has_unsaved_changes = False
        
        # Cache for performance
        self.bib_cache = {}
        self._expansion_connected = False
        
        # Initialize image display manager
        self.image_display = ImageDisplayManager(
            self.get_thumb_label(),
            self.get_runner_label(),
            self.get_shoe_container(),
            self.get_shoe_layout()
        )
        self.image_display.set_shoe_click_callback(self.on_shoe_click)
        
        # Connect UI signals to handlers
        self.connect_signals()
        
        # Install event filter for keyboard events
        self.get_tree_widget().installEventFilter(self)

    def connect_signals(self) -> None:
        """Connect UI signals to their handlers."""
        # Main window signals
        self.json_load_requested.connect(self.load_json_file)
        self.json_save_requested.connect(self.save_json)
        self.json_save_as_requested.connect(self.save_as_json)
        self.base_path_change_requested.connect(self.select_base_path)
        self.configuration_requested.connect(self.open_configuration_dialog)
        
        # Panel signals
        self.left_panel.filter_changed.connect(self.on_filter_changed)
        self.left_panel.item_selected.connect(self.on_item_selected)
        
        self.right_panel.bib_number_entered.connect(self.on_bib_number_enter)
        self.right_panel.category_selected.connect(self.on_category_selected)
        self.right_panel.brand_changed.connect(self.on_brand_changed_immediate)

    # Data operations using the new data manager
    def load_json_file(self, path: str) -> None:
        """Load JSON data file using the data manager."""
        try:
            self.json_path = path
            
            # Get current thresholds from config
            chest_plate_threshold = self.config.get('chest_plate_confidence_threshold', 0.5)
            shoes_threshold = self.config.get('shoes_confidence_threshold', 0.5)
            
            self.data_manager.load_json(path, chest_plate_threshold, shoes_threshold)
            
            # Clear undo stack and reset state
            self.has_unsaved_changes = False
            
            self.collect_stats()
            self.populate_tree()
            self.show_entry(0)
            self.update_status_bar()
            self.update_window_title(self.json_path, self.has_unsaved_changes)
            
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to load JSON: {e}")

    def collect_stats(self) -> None:
        """Collect brands, categories and genders using the data manager."""
        config_labels = self.config.get("labels", [])
        self.brands, self.bib_categories, self.genders = self.data_manager.collect_stats(config_labels)

        # Update UI components
        bib_category = self.get_bib_category_field()
        bib_category.clear()
        bib_category.addItems(self.bib_categories)
        
        # Update category filter
        category_filter = self.get_category_filter()
        category_filter.clear()
        category_filter.addItem("Todas as categorias")
        category_filter.addItems(self.bib_categories)

        # Update gender filter
        gender_filter = self.get_gender_filter()
        gender_filter.clear()
        gender_filter.addItem("Todos os gêneros")
        gender_filter.addItems(self.genders)

        # Setup brand checkboxes using the right panel
        self.right_panel.setup_brand_checkboxes(self.brands)
        
        # Setup shortcuts info
        self.right_panel.setup_shortcuts_info(config_labels)

    def populate_tree(self) -> None:
        """Populate tree using the new cache system."""
        tree = self.get_tree_widget()
        tree.clear()
        
        # Get selected category filter
        category_filter = self.get_category_filter()
        selected_category = category_filter.currentText()
        if selected_category == "Todas as categorias":
            selected_category = None
        
        # Get selected gender filter
        gender_filter = self.get_gender_filter()
        selected_gender = gender_filter.currentText()
        if selected_gender == "Todos os gêneros":
            selected_gender = None
        
        # Check if we should filter for unchecked only
        filter_unchecked_only = self.get_filter_unchecked_only().isChecked()
        
        # Get relevant cache entries for the selected category and gender
        relevant_bibs = []
        cache = self.data_manager.cache
        
        for cache_key, cache_data in cache.bib_cache.items():
            bib_number = cache_data['bib_number']
            category = cache_data['category']
            gender = cache_data['gender']
            
            # Skip if doesn't match category filter
            if selected_category and category != selected_category:
                continue
            
            # Skip if doesn't match gender filter
            if selected_gender and gender != selected_gender:
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
            
            bib_node = QTreeWidgetItem(tree, [bib_text])
            
            # Store the best image index as the bib node's data
            bib_node.setData(0, Qt.UserRole, cache_data['index'])
            
            # Mark that this node needs to load children when expanded
            bib_node.setData(1, Qt.UserRole, {'bib_number': bib_number, 'category': selected_category, 'loaded': False})
            
            # Add a dummy child so the expansion triangle appears
            dummy_child = QTreeWidgetItem(bib_node, ["Carregando..."])
            
        # Connect the tree expansion signal to load children on demand
        if not self._expansion_connected:
            tree.itemExpanded.connect(self.on_tree_item_expanded)
            self._expansion_connected = True
        
        # Keep tree collapsed by default
        tree.collapseAll()

    def show_entry(self, index: int) -> None:
        """Display entry using ImageDisplayManager."""
        if not self.data_manager.data:
            return
        
        index = max(0, min(index, len(self.data_manager.data)-1))
        self.current_index = index
        data_item = self.data_manager.data[index]
        
        # Use ImageDisplayManager to display the image
        base_path = self.config.get("base_path", "")
        self.image_display.display_image(data_item, base_path)
        
        # Update right panel data
        self._update_right_panel_data(data_item)
        
        # Update status bar
        self.update_status_bar()

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
        bib_number_field = self.get_bib_number_field()
        bib_number_field.setText(bib_number)
        bib_number_field.setEnabled(not is_checked)
        
        bib_category_field = self.get_bib_category_field()
        if category and category in self.bib_categories:
            bib_category_field.setCurrentText(category)
        else:
            bib_category_field.setCurrentIndex(-1)
        bib_category_field.setEnabled(not is_checked)
        
        # Update brand checkboxes
        brand_checks = self.get_brand_checks()
        for chk in brand_checks:
            chk.setChecked(False)
            chk.setEnabled(not is_checked)
        
        # Get current shoe brands
        brands_present = set()
        for shoe in data_item.get("shoes", []):
            brand = shoe.get("new_label") or shoe.get("label") or shoe.get("classification_label")
            if brand:
                brands_present.add(brand)
        
        for chk in brand_checks:
            if chk.text() in brands_present:
                chk.setChecked(True)
        
        # Reconnect signals
        self._reconnect_right_panel_signals()

    def _disconnect_right_panel_signals(self) -> None:
        """Temporarily disconnect right panel signals."""
        try:
            self.right_panel.bib_number_entered.disconnect()
        except:
            pass
        try:
            self.right_panel.category_selected.disconnect()
        except:
            pass
        try:
            self.right_panel.brand_changed.disconnect()
        except:
            pass

    def _reconnect_right_panel_signals(self) -> None:
        """Reconnect right panel signals."""
        self.right_panel.bib_number_entered.connect(self.on_bib_number_enter)
        self.right_panel.category_selected.connect(self.on_category_selected)
        self.right_panel.brand_changed.connect(self.on_brand_changed_immediate)

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
            super().update_window_title(self.json_path, self.has_unsaved_changes)
            
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
                super().update_window_title(self.json_path, self.has_unsaved_changes)
                
            except Exception as e:
                QMessageBox.critical(self, "Error", f"Failed to save: {e}")

    def update_status_bar(self) -> None:
        """Update status bar using data manager stats."""
        stats = self.data_manager.get_progress_stats()
        super().update_status_bar(int(stats['checked']), int(stats['total']), stats['percentage'])

    def mark_unsaved_changes(self) -> None:
        """Mark that there are unsaved changes."""
        if not self.has_unsaved_changes:
            self.has_unsaved_changes = True
            super().update_window_title(self.json_path, self.has_unsaved_changes)

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
            tree = self.get_tree_widget()
            if tree.topLevelItemCount() > 0:
                first_item = tree.topLevelItem(0)
                if first_item:
                    tree.setCurrentItem(first_item)
                    self.on_item_selected(first_item, None)

    def on_bib_number_enter(self) -> None:
        """Handle Enter key in bib number field using data manager."""
        if not self.data_manager.data or self.current_index >= len(self.data_manager.data):
            return
        
        if self._is_current_checked():
            return
        
        bib_number_field = self.get_bib_number_field()
        bib_text = bib_number_field.text()
        
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
        
        bib_category_field = self.get_bib_category_field()
        category_text = bib_category_field.currentText()
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
        brand_checks = self.get_brand_checks()
        checked_brands = [chk.text() for chk in brand_checks if chk.isChecked()]
        
        # Save state for undo
        self.data_manager.save_state(self.current_index)
        
        # Update data using data manager
        bib_number_field = self.get_bib_number_field()
        bib_category_field = self.get_bib_category_field()
        self.data_manager.update_image_data(
            self.current_index, 
            bib_number_field.text(),
            bib_category_field.currentText(),
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
        
        tree = self.get_tree_widget()
            
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
        for i in range(tree.topLevelItemCount()):
            bib_item = tree.topLevelItem(i)
            if bib_item:
                # Check if this bib node itself has the target index (best image)
                if bib_item.data(0, Qt.UserRole) == data_index:
                    tree.setCurrentItem(bib_item)
                    return
                
                # Search in children (if expanded)
                result = find_item_with_index(bib_item, data_index)
                if result:
                    # Expand the parent if needed
                    if not bib_item.isExpanded():
                        bib_item.setExpanded(True)
                    tree.setCurrentItem(result)
                    return

    def select_next_tree_item(self) -> None:
        """Select the next item in the tree after current operations."""
        tree = self.get_tree_widget()
        current_item = tree.currentItem()
        if not current_item:
            # If no current item, select the first one
            if tree.topLevelItemCount() > 0:
                first_item = tree.topLevelItem(0)
                if first_item:
                    tree.setCurrentItem(first_item)
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
                    parent_index = tree.indexOfTopLevelItem(parent)
                    if parent_index + 1 < tree.topLevelItemCount():
                        next_item = tree.topLevelItem(parent_index + 1)
            else:
                # We're at top level, find next top level item
                current_index = tree.indexOfTopLevelItem(current_item)
                if current_index + 1 < tree.topLevelItemCount():
                    next_item = tree.topLevelItem(current_index + 1)
        
        # If we found a next item, select it
        if next_item:
            tree.setCurrentItem(next_item)
            # Trigger selection to update display
            self.on_item_selected(next_item, current_item)
        else:
            # No next item found, stay on current or go to last available
            if tree.topLevelItemCount() > 0:
                last_item = tree.topLevelItem(tree.topLevelItemCount() - 1)
                if last_item:
                    tree.setCurrentItem(last_item)
                    self.on_item_selected(last_item, current_item)

    def _is_current_checked(self) -> bool:
        """Check if current image is checked."""
        if not self.data_manager.data or self.current_index >= len(self.data_manager.data):
            return False
        return self.data_manager.data[self.current_index].get('checked', False)

    # Keyboard handling (simplified for now, could be moved to a separate handler)
    def eventFilter(self, source, event):
        """Handle keyboard events for the tree widget."""
        tree = self.get_tree_widget()
        if source == tree and event.type() == QEvent.KeyPress:
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
            
            current_tree_item = self.get_tree_widget().currentItem()
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
            choice = super().show_unsaved_changes_dialog()
            
            if choice == "save":
                self.save_json()
                event.accept()
            elif choice == "discard":
                event.accept()
            else:  # cancel
                event.ignore()
        else:
            event.accept()

    def open_configuration_dialog(self) -> None:
        """Open the configuration dialog to adjust settings."""
        # Store original thresholds to detect changes
        original_chest_threshold = self.config.get('chest_plate_confidence_threshold', 0.5)
        original_shoes_threshold = self.config.get('shoes_confidence_threshold', 0.5)
        
        # Create and show the configuration dialog
        dialog = ConfigurationDialog(self.config, self)
        if dialog.exec_() == dialog.Accepted:
            # Get the updated configuration
            updated_config = dialog.get_updated_config()
            
            # Check if thresholds changed
            new_chest_threshold = updated_config.get('chest_plate_confidence_threshold', 0.5)
            new_shoes_threshold = updated_config.get('shoes_confidence_threshold', 0.5)
            
            thresholds_changed = (
                original_chest_threshold != new_chest_threshold or 
                original_shoes_threshold != new_shoes_threshold
            )
            
            # Update the current configuration
            self.config.update(updated_config)
            
            # Save the configuration to YAML file
            try:
                save_config(self.config_path, self.config)
                
                # If thresholds changed and we have data loaded, reload it
                if thresholds_changed and self.json_path and self.data_manager.data:
                    reply = QMessageBox.question(
                        self,
                        "Recarregar Dados",
                        "Os thresholds de confiança foram alterados. Deseja recarregar os dados "
                        "para aplicar os novos filtros?",
                        QMessageBox.Yes | QMessageBox.No
                    )
                    
                    if reply == QMessageBox.Yes:
                        # Save current state before reloading
                        current_item = self.get_tree_widget().currentItem()
                        current_index = 0
                        if current_item:
                            current_index = current_item.data(0, Qt.UserRole) or 0
                        
                        # Reload data with new thresholds
                        self.data_manager.reload_with_thresholds(
                            self.json_path, new_chest_threshold, new_shoes_threshold
                        )
                        
                        # Refresh UI
                        self.collect_stats()
                        self.populate_tree()
                        
                        # Try to restore previous selection or go to first item
                        if current_index < len(self.data_manager.data):
                            self.show_entry(current_index)
                        else:
                            self.show_entry(0)
                        
                        self.update_status_bar()
                        QMessageBox.information(
                            self,
                            "Dados Recarregados",
                            f"Dados recarregados com os novos thresholds:\n"
                            f"• Placa de Peito: {new_chest_threshold:.2f}\n"
                            f"• Tênis: {new_shoes_threshold:.2f}"
                        )
                        
                self.mark_unsaved_changes()  # Mark as having changes that might affect display
                
            except Exception as e:
                QMessageBox.critical(
                    self, 
                    "Erro ao Salvar Configuração", 
                    f"Não foi possível salvar a configuração: {e}"
                )


def main() -> None:
    """Main entry point for the refactored application."""
    app = QApplication(sys.argv)
    viewer = RunnerViewer()
    viewer.show()
    sys.exit(app.exec_())


if __name__ == "__main__":
    main()
