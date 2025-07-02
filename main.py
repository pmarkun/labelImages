"""
Main application controller for the Runner Viewer application.
"""
import os
import sys
import copy
from typing import List, Dict, Any, Optional
from PyQt5.QtCore import QEvent, QObject, Qt, QTimer
from PyQt5.QtGui import QKeyEvent
from PyQt5.QtWidgets import QApplication, QCheckBox, QTreeWidgetItem, QMessageBox

from ui.main_window import RunnerViewerMainWindow
from ui.tree_widget import TreeManager
from ui.hybrid_image_display import HybridImageDisplayManager
from ui.image_display import ExportManager
from ui.export_dialog import ExportDialog
from core.data_manager import DataManager
from utils.config import load_config, save_config
from utils.image_utils import clear_image_cache


DEFAULT_VIEWER_CONFIG = {
    "base_path": os.getcwd(),
    "labels": []
}


class RunnerViewerApp(QObject):
    """Main application controller for the Runner Viewer."""
    
    def __init__(self):
        super().__init__()
        
        # Initialize config
        self.config_path = os.path.join(os.getcwd(), "viewer_config.yaml")
        self.config = load_config(self.config_path)
        if not self.config:
            self.config = DEFAULT_VIEWER_CONFIG
            save_config(self.config_path, self.config)
        
        # Initialize data
        self.json_path = ""
        self.current_index = 0
        self.brands: List[str] = []
        self.bib_categories: List[str] = []
        self.genders: List[str] = []
        self.backup_done = False
        self.has_unsaved_changes = False
        
        # Initialize components
        self.data_manager = DataManager()
        self.main_window = RunnerViewerMainWindow()
        self.tree_manager = TreeManager(self.main_window.get_tree_widget())
        self.image_display = HybridImageDisplayManager(
            self.main_window.get_thumb_label(),
            self.main_window.get_runner_label(),
            self.main_window.get_shoe_container(),
            self.main_window.get_shoe_layout()
        )
        self.export_manager = None  # Will be initialized when data is loaded
        
        # Connect signals
        self._connect_signals()
        
        # Set up event filter for tree widget
        self.main_window.get_tree_widget().installEventFilter(self)
        
        # Set shoe click callback
        self.image_display.set_shoe_click_callback(self._on_shoe_click)
        
        # Setup filter debouncing
        self._filter_timer = QTimer()
        self._filter_timer.setSingleShot(True)
        self._filter_timer.timeout.connect(self._perform_filter_update)
        self._filter_timer.setInterval(150)  # 150ms delay
    
    def _connect_signals(self) -> None:
        """Connect all UI signals to their handlers."""
        # Main window signals
        self.main_window.json_load_requested.connect(self.load_json)
        self.main_window.json_save_requested.connect(self.save_json)
        self.main_window.json_save_as_requested.connect(self.save_as_json)
        self.main_window.base_path_change_requested.connect(self.select_base_path)
        self.main_window.export_requested.connect(self.open_export_dialog)
        
        # Left panel signals
        self.main_window.left_panel.filter_changed.connect(self.on_filter_changed)
        self.main_window.left_panel.item_selected.connect(self.on_item_selected)
        
        # Right panel signals
        self.main_window.right_panel.bib_number_entered.connect(self.on_bib_number_enter)
        self.main_window.right_panel.category_selected.connect(self.on_category_selected)
        self.main_window.right_panel.brand_changed.connect(self.on_brand_changed_immediate)
        
        # Tree manager signals
        self.tree_manager.item_expanded.connect(self._on_tree_item_expanded)
    
    def show(self) -> None:
        """Show the main window."""
        self.main_window.show()
    
    def load_json(self, path: str) -> None:
        """Load JSON data file."""
        try:
            self.json_path = path
            
            # Clear image caches before loading new data
            clear_image_cache()
            self.image_display.clear_cache()
            
            self.data_manager.load_json(path)
            
            # Clear undo stack and reset flags
            self.has_unsaved_changes = False
            
            # Initialize export manager
            self.export_manager = ExportManager(
                self.data_manager.data,
                self.config.get("base_path", ""),
                self.config.get("output_folder", "train")
            )
            
            # Collect statistics and setup UI
            self.collect_stats()
            self.populate_tree()
            self.show_entry(0)
            self.update_status_bar()
            self.update_window_title()
            
        except Exception as e:
            QMessageBox.critical(self.main_window, "Error", f"Failed to load JSON file: {e}")
    
    def save_json(self) -> None:
        """Save to current file."""
        if not self.json_path:
            self.save_as_json()
            return
        
        try:
            if not self.backup_done:
                import shutil
                shutil.copy(self.json_path, self.json_path + ".bak")
                self.backup_done = True
            
            self.data_manager.save_json(self.json_path, backup=False)
            self.has_unsaved_changes = False
            self.update_window_title()
            
        except Exception as e:
            QMessageBox.critical(self.main_window, "Error", f"Failed to save JSON file: {e}")
    
    def save_as_json(self) -> None:
        """Save with new filename."""
        if not self.data_manager.data:
            return
        
        from PyQt5.QtWidgets import QFileDialog
        path, _ = QFileDialog.getSaveFileName(self.main_window, "Salvar JSON", filter="JSON Files (*.json)")
        if path:
            try:
                self.data_manager.save_json(path, backup=False)
                self.json_path = path
                self.backup_done = False
                self.has_unsaved_changes = False
                self.update_window_title()
                
            except Exception as e:
                QMessageBox.critical(self.main_window, "Error", f"Failed to save JSON file: {e}")
    
    def select_base_path(self) -> None:
        """Select base path for images."""
        from PyQt5.QtWidgets import QFileDialog
        folder = QFileDialog.getExistingDirectory(
            self.main_window, 
            "Base de Imagens", 
            self.config.get("base_path", "")
        )
        if folder:
            self.config["base_path"] = folder
            save_config(self.config_path, self.config)
            if self.json_path:
                # Save expansion state before repopulating
                expansion_state = self.tree_manager.get_expansion_state()
                
                # Repopulate tree with expansion state preserved
                self.tree_manager.set_data(self.data_manager.data)
                selected_category = self.main_window.get_category_filter().currentText()
                selected_gender = self.main_window.get_gender_filter().currentText()
                filter_unchecked_only = self.main_window.get_filter_unchecked_only().isChecked()
                self.tree_manager.populate_tree(selected_category, selected_gender, filter_unchecked_only, expansion_state)
                
                self.show_entry(0)
    
    def open_export_dialog(self) -> None:
        """Open the export dialog for data export with various options."""
        if not self.data_manager.data:
            QMessageBox.information(
                self.main_window, 
                "Nenhum Dados", 
                "Não há dados carregados para exportar."
            )
            return
        
        # Create and show the export dialog with correct parameters
        dialog = ExportDialog(
            self.data_manager.data, 
            self.config.get("base_path", ""), 
            self.main_window
        )
        
        # Show the dialog
        dialog.exec_()

    def collect_stats(self) -> None:
        """Collect brands and categories from data."""
        config_labels = self.config.get("labels", [])
        self.brands, self.bib_categories, self.genders = self.data_manager.collect_stats(config_labels)
        
        # Update UI components
        self._update_category_filter()
        self._update_bib_category_combo()
        self._setup_brand_checkboxes()
        self._setup_shortcuts_info()
    
    def _update_category_filter(self) -> None:
        """Update the category filter dropdown."""
        category_filter = self.main_window.get_category_filter()
        category_filter.clear()
        category_filter.addItem("Todas as categorias")
        category_filter.addItems(self.bib_categories)
    
    def _update_bib_category_combo(self) -> None:
        """Update the bib category dropdown."""
        bib_category = self.main_window.get_bib_category_field()
        bib_category.clear()
        bib_category.addItems(self.bib_categories)
    
    def _setup_brand_checkboxes(self) -> None:
        """Setup brand checkboxes."""
        self.main_window.right_panel.setup_brand_checkboxes(self.brands)
    
    def _setup_shortcuts_info(self) -> None:
        """Setup keyboard shortcuts information."""
        config_labels = self.config.get("labels", [])
        self.main_window.right_panel.setup_shortcuts_info(config_labels)
    
    def populate_tree(self) -> None:
        """Populate the tree widget."""
        self.tree_manager.set_data(self.data_manager.data)
        
        selected_category = self.main_window.get_category_filter().currentText()
        selected_gender = self.main_window.get_gender_filter().currentText()
        filter_unchecked_only = self.main_window.get_filter_unchecked_only().isChecked()
        
        self.tree_manager.populate_tree(selected_category, selected_gender, filter_unchecked_only)
    
    def show_entry(self, index: int) -> None:
        """Display entry using FastImageDisplayManager."""
        if not self.data_manager.data:
            return
        
        index = max(0, min(index, len(self.data_manager.data)-1))
        self.current_index = index
        data_item = self.data_manager.data[index]
        
        # Use FastImageDisplayManager to display the image
        base_path = self.config.get("base_path", "")
        self.image_display.display_image(data_item, base_path)
        
        # Preload nearby images for faster navigation
        self._preload_nearby_images(index)
        
        # Update right panel data
        self._update_right_panel_data(data_item)
        
        # Update status bar
        self.update_status_bar()
    
    def _preload_nearby_images(self, current_index: int):
        """Preload images around current index for faster navigation."""
        if not self.data_manager.data:
            return
        
        # Get nearby items (5 before and 5 after)
        start_idx = max(0, current_index - 5)
        end_idx = min(len(self.data_manager.data), current_index + 6)
        
        nearby_items = []
        for i in range(start_idx, end_idx):
            if i != current_index:  # Don't preload current image
                nearby_items.append(self.data_manager.data[i])
        
        base_path = self.config.get("base_path", "")
        self.image_display.preload_images(nearby_items, base_path)
    
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
        bib_number_field = self.main_window.get_bib_number_field()
        bib_number_field.setText(bib_number)
        bib_number_field.setEnabled(not is_checked)
        
        bib_category_field = self.main_window.get_bib_category_field()
        if category and category in self.bib_categories:
            bib_category_field.setCurrentText(category)
        else:
            bib_category_field.setCurrentIndex(-1)
        bib_category_field.setEnabled(not is_checked)
        
        # Update brand checkboxes
        brand_checks = self.main_window.get_brand_checks()
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
            self.main_window.right_panel.bib_number_entered.disconnect()
        except:
            pass
        try:
            self.main_window.right_panel.category_selected.disconnect()
        except:
            pass
        try:
            self.main_window.right_panel.brand_changed.disconnect()
        except:
            pass
    
    def _reconnect_right_panel_signals(self) -> None:
        """Reconnect right panel signals."""
        self.main_window.right_panel.bib_number_entered.connect(self.on_bib_number_enter)
        self.main_window.right_panel.category_selected.connect(self.on_category_selected)
        self.main_window.right_panel.brand_changed.connect(self.on_brand_changed_immediate)
    
    def update_status_bar(self) -> None:
        """Update the status bar with progress."""
        stats = self.data_manager.get_progress_stats()
        self.main_window.update_status_bar(
            int(stats['checked']), 
            int(stats['total']), 
            stats['percentage']
        )
    
    def update_window_title(self) -> None:
        """Update the window title."""
        self.main_window.update_window_title(self.json_path, self.has_unsaved_changes)
    
    def mark_unsaved_changes(self) -> None:
        """Mark that there are unsaved changes."""
        if not self.has_unsaved_changes:
            self.has_unsaved_changes = True
            self.update_window_title()
    
    # Event handlers
    def on_filter_changed(self) -> None:
        """Handle filter changes with debouncing."""
        # Use timer to debounce filter changes
        self._filter_timer.start()
    
    def _perform_filter_update(self) -> None:
        """Perform the actual filter update after debouncing."""
        if self.data_manager.data:
            # Note: For filter changes, we intentionally don't preserve expansion
            # because the user is changing what's displayed, so collapsing makes sense
            self.populate_tree()
            # Select first item if available
            tree = self.main_window.get_tree_widget()
            if tree.topLevelItemCount() > 0:
                first_item = tree.topLevelItem(0)
                if first_item:
                    tree.setCurrentItem(first_item)
                    self.on_item_selected(first_item, None)
    
    def on_item_selected(self, current: QTreeWidgetItem, previous=None) -> None:
        """Handle tree item selection."""
        if current is None:
            return
        idx = current.data(0, Qt.UserRole)
        if isinstance(idx, int):
            self.show_entry(idx)
    
    def on_bib_number_enter(self) -> None:
        """Handle Enter key in bib number field."""
        if not self.data_manager.data or self.current_index >= len(self.data_manager.data):
            return
        
        if self._is_current_checked():
            return
        
        # Save expansion state
        expansion_state = self.tree_manager.get_expansion_state()
        
        bib_text = self.main_window.get_bib_number_field().text()
        
        # Save state for undo
        self.data_manager.save_state(self.current_index)
        
        # Update data
        item = self.data_manager.data[self.current_index]
        run_data = item.setdefault("run_data", {})
        run_data["bib_number"] = bib_text
        
        self.mark_unsaved_changes()
        
        # Repopulate tree with expansion state preserved
        self.tree_manager.set_data(self.data_manager.data)
        selected_category = self.main_window.get_category_filter().currentText()
        selected_gender = self.main_window.get_gender_filter().currentText()
        filter_unchecked_only = self.main_window.get_filter_unchecked_only().isChecked()
        self.tree_manager.populate_tree(selected_category, selected_gender, filter_unchecked_only, expansion_state)
        
        self.tree_manager.select_next_tree_item()
    
    def on_category_selected(self, index: int) -> None:
        """Handle category selection."""
        if not self.data_manager.data or self.current_index >= len(self.data_manager.data):
            return
        
        if self._is_current_checked():
            return
        
        # Save expansion state
        expansion_state = self.tree_manager.get_expansion_state()
        
        category_text = self.main_window.get_bib_category_field().currentText()
        if not category_text:
            return
        
        # Save state for undo
        self.data_manager.save_state(self.current_index)
        
        # Update data
        item = self.data_manager.data[self.current_index]
        run_data = item.setdefault("run_data", {})
        run_data["run_category"] = category_text
        
        self.mark_unsaved_changes()
        
        # Repopulate tree with expansion state preserved
        self.tree_manager.set_data(self.data_manager.data)
        selected_category = self.main_window.get_category_filter().currentText()
        selected_gender = self.main_window.get_gender_filter().currentText()
        filter_unchecked_only = self.main_window.get_filter_unchecked_only().isChecked()
        self.tree_manager.populate_tree(selected_category, selected_gender, filter_unchecked_only, expansion_state)
        
        self.tree_manager.select_next_tree_item()
    
    def on_brand_changed_immediate(self) -> None:
        """Handle immediate brand changes."""
        if not self.data_manager.data or self.current_index >= len(self.data_manager.data):
            return
        
        if self._is_current_checked():
            return
        
        # Get checked brands
        checked_brands = [
            chk.text() for chk in self.main_window.get_brand_checks() 
            if chk.isChecked()
        ]
        
        # Save state for undo
        self.data_manager.save_state(self.current_index)
        
        # Update data
        self.data_manager.update_image_data(
            self.current_index, 
            self.main_window.get_bib_number_field().text(),
            self.main_window.get_bib_category_field().currentText(),
            checked_brands
        )
        
        self.mark_unsaved_changes()
        self.show_entry(self.current_index)  # Refresh display
    
    def _on_tree_item_expanded(self, item: QTreeWidgetItem) -> None:
        """Handle tree item expansion."""
        # Tree manager handles the expansion logic
        pass
    
    def _on_shoe_click(self, event, shoe_index: int) -> None:
        """Handle shoe click for removal."""
        if not self.data_manager.data or self.current_index >= len(self.data_manager.data):
            return
        
        current_item = self.data_manager.data[self.current_index]
        
        def save_state():
            self.data_manager.save_state(self.current_index)
        
        def mark_unsaved():
            self.mark_unsaved_changes()
        
        def refresh_display():
            # Save expansion state before refreshing
            expansion_state = self.tree_manager.get_expansion_state()
            
            self.show_entry(self.current_index)
            
            # Repopulate tree with expansion state preserved
            self.tree_manager.set_data(self.data_manager.data)
            selected_category = self.main_window.get_category_filter().currentText()
            selected_gender = self.main_window.get_gender_filter().currentText()
            filter_unchecked_only = self.main_window.get_filter_unchecked_only().isChecked()
            self.tree_manager.populate_tree(selected_category, selected_gender, filter_unchecked_only, expansion_state)
            
            self.tree_manager.select_tree_item_by_index(self.current_index)
        
        if self.export_manager:
            self.export_manager.on_shoe_click(
                event, shoe_index, current_item, self.current_index,
                save_state, mark_unsaved, refresh_display
            )
    
    def _is_current_checked(self) -> bool:
        """Check if current image is checked."""
        if not self.data_manager.data or self.current_index >= len(self.data_manager.data):
            return False
        return self.data_manager.data[self.current_index].get('checked', False)
    
    # Keyboard handling
    def eventFilter(self, source, event):
        """Handle keyboard events."""
        tree = self.main_window.get_tree_widget()
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
        """Handle key press events."""
        if not self.data_manager.data:
            return
        
        # Ctrl+Z for undo
        if event.modifiers() == Qt.ControlModifier and event.key() == Qt.Key_Z:
            self._undo()
            return
        
        # Brand shortcuts
        key_text = event.text().lower()
        key_to_brand = self._get_key_to_brand_mapping()
        if key_text in key_to_brand:
            if self._is_current_checked():
                self.main_window.show_protected_image_message()
                return
            self._set_brand_by_key(key_text)
            return
        
        is_checked = self._is_current_checked()
        
        # Delete key
        if event.key() == Qt.Key_Delete:
            if is_checked:
                self.main_window.show_protected_image_message()
                return
            
            current_tree_item = self.main_window.get_tree_widget().currentItem()
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
                self.main_window.show_protected_image_message()
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
                self.main_window.show_protected_image_message()
            return
    
    def _undo(self) -> None:
        """Undo last change."""
        # Save expansion state before undo
        expansion_state = self.tree_manager.get_expansion_state()
        
        state = self.data_manager.undo()
        if state:
            self.current_index = state['current_index']
            
            # Repopulate tree with expansion state preserved
            self.tree_manager.set_data(self.data_manager.data)
            selected_category = self.main_window.get_category_filter().currentText()
            selected_gender = self.main_window.get_gender_filter().currentText()
            filter_unchecked_only = self.main_window.get_filter_unchecked_only().isChecked()
            self.tree_manager.populate_tree(selected_category, selected_gender, filter_unchecked_only, expansion_state)
            
            self.show_entry(self.current_index)
            self.save_json()
            self.update_status_bar()
    
    def _remove_current_image(self) -> None:
        """Remove current image."""
        # Save current state and expansion
        selected_item_info = self.tree_manager.get_selected_item_info()
        expansion_state = self.tree_manager.get_expansion_state()
        
        self.data_manager.save_state(self.current_index)
        new_index = self.data_manager.remove_image(self.current_index)
        self.current_index = new_index
        
        # Repopulate tree with expansion state restored
        self.tree_manager.set_data(self.data_manager.data)
        selected_category = self.main_window.get_category_filter().currentText()
        selected_gender = self.main_window.get_gender_filter().currentText()
        filter_unchecked_only = self.main_window.get_filter_unchecked_only().isChecked()
        self.tree_manager.populate_tree(selected_category, selected_gender, filter_unchecked_only, expansion_state)
        
        # Select appropriate next item
        if selected_item_info:
            self.tree_manager.select_next_item_after_deletion(selected_item_info, expansion_state)
        else:
            self.tree_manager.select_next_tree_item()
        
        self.mark_unsaved_changes()
        self.update_status_bar()
    
    def _remove_all_images_with_bib(self, bib_number: str) -> None:
        """Remove all images with specific bib number."""
        # Save current state and expansion
        selected_item_info = self.tree_manager.get_selected_item_info()
        expansion_state = self.tree_manager.get_expansion_state()
        
        self.data_manager.save_state(self.current_index)
        new_index = self.data_manager.remove_all_images_with_bib(bib_number)
        self.current_index = new_index
        
        # Repopulate tree with expansion state restored
        self.tree_manager.set_data(self.data_manager.data)
        selected_category = self.main_window.get_category_filter().currentText()
        selected_gender = self.main_window.get_gender_filter().currentText()
        filter_unchecked_only = self.main_window.get_filter_unchecked_only().isChecked()
        self.tree_manager.populate_tree(selected_category, selected_gender, filter_unchecked_only, expansion_state)
        
        # Select appropriate next item
        if selected_item_info:
            self.tree_manager.select_next_item_after_deletion(selected_item_info, expansion_state)
        else:
            self.tree_manager.select_next_tree_item()
        
        self.mark_unsaved_changes()
        self.update_status_bar()
    
    def _keep_only_current_image(self) -> None:
        """Keep current image as master and propagate data."""
        # Save expansion state
        expansion_state = self.tree_manager.get_expansion_state()
        
        self.data_manager.save_state(self.current_index)
        self.data_manager.propagate_data_to_same_bib(self.current_index)
        
        # Note: Export functionality moved to manual export dialog (Tools > Export)
        # No longer automatically exports when K is pressed
        
        # Repopulate tree with expansion state preserved
        self.tree_manager.set_data(self.data_manager.data)
        selected_category = self.main_window.get_category_filter().currentText()
        selected_gender = self.main_window.get_gender_filter().currentText()
        filter_unchecked_only = self.main_window.get_filter_unchecked_only().isChecked()
        self.tree_manager.populate_tree(selected_category, selected_gender, filter_unchecked_only, expansion_state)
        
        self.show_entry(self.current_index)
        self.tree_manager.select_tree_item_by_index(self.current_index)
        self.mark_unsaved_changes()
        self.update_status_bar()
    
    def _toggle_checked(self) -> None:
        """Toggle checked status."""
        self.data_manager.save_state(self.current_index)
        new_status = self.data_manager.toggle_checked(self.current_index)
        
        self.mark_unsaved_changes()
        self.update_status_bar()
        self.show_entry(self.current_index)  # Refresh display
    
    def _apply_changes(self) -> None:
        """Apply current changes."""
        if self._is_current_checked():
            return
        
        # Save expansion state and current selection
        expansion_state = self.tree_manager.get_expansion_state()
        current_selection_info = self.tree_manager.get_selected_item_info()
        
        bib_number = self.main_window.get_bib_number_field().text()
        category = self.main_window.get_bib_category_field().currentText()
        checked_brands = [
            chk.text() for chk in self.main_window.get_brand_checks() 
            if chk.isChecked()
        ]
        
        self.data_manager.save_state(self.current_index)
        self.data_manager.update_image_data(self.current_index, bib_number, category, checked_brands)
        
        self.mark_unsaved_changes()
        self.update_status_bar()
        
        # Repopulate tree with expansion state preserved
        self.tree_manager.set_data(self.data_manager.data)
        selected_category = self.main_window.get_category_filter().currentText()
        selected_gender = self.main_window.get_gender_filter().currentText()
        filter_unchecked_only = self.main_window.get_filter_unchecked_only().isChecked()
        self.tree_manager.populate_tree(selected_category, selected_gender, filter_unchecked_only, expansion_state)
        
        # Try to select the same item or the next appropriate one
        if current_selection_info:
            # For shortcuts, we want to stay on the current item if possible
            self.tree_manager.select_tree_item_by_index(self.current_index)
        else:
            self.tree_manager.select_next_tree_item()
    
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
        
        # Save expansion state and current selection
        expansion_state = self.tree_manager.get_expansion_state()
        
        # Update brand checkboxes
        brand_checks = self.main_window.get_brand_checks()
        for chk in brand_checks:
            chk.setChecked(chk.text() == target_brand)
        
        # Apply changes directly to maintain position
        bib_number = self.main_window.get_bib_number_field().text()
        category = self.main_window.get_bib_category_field().currentText()
        checked_brands = [target_brand]  # Only the shortcut brand is selected
        
        self.data_manager.save_state(self.current_index)
        self.data_manager.update_image_data(self.current_index, bib_number, category, checked_brands)
        
        self.mark_unsaved_changes()
        self.update_status_bar()
        
        # Repopulate tree with expansion state preserved
        self.tree_manager.set_data(self.data_manager.data)
        selected_category = self.main_window.get_category_filter().currentText()
        selected_gender = self.main_window.get_gender_filter().currentText()
        filter_unchecked_only = self.main_window.get_filter_unchecked_only().isChecked()
        self.tree_manager.populate_tree(selected_category, selected_gender, filter_unchecked_only, expansion_state)
        
        # Stay on the current item (don't advance to next)
        self.tree_manager.select_tree_item_by_index(self.current_index)
    
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
    
    def closeEvent(self, event):
        """Handle application close."""
        if self.has_unsaved_changes:
            choice = self.main_window.show_unsaved_changes_dialog()
            if choice == "save":
                self.save_json()
                event.accept()
            elif choice == "discard":
                event.accept()
            else:  # cancel
                event.ignore()
        else:
            event.accept()


def main():
    """Main entry point."""
    app = QApplication(sys.argv)
    viewer = RunnerViewerApp()
    viewer.show()
    
    # Handle close event
    app.lastWindowClosed.connect(app.quit)
    
    sys.exit(app.exec_())


if __name__ == "__main__":
    main()
