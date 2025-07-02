"""
Tree widget management for the Runner Viewer application.
"""
from typing import List, Dict, Any, Optional
from PyQt5.QtCore import Qt, QObject, pyqtSignal
from PyQt5.QtWidgets import QTreeWidget, QTreeWidgetItem
from core.models import DataCache, get_position_from_bib


class TreeManager(QObject):
    """Manages the tree widget operations and data display."""
    
    # Signals
    item_expanded = pyqtSignal(object)  # QTreeWidgetItem
    
    def __init__(self, tree_widget: QTreeWidget):
        super().__init__()
        self.tree = tree_widget
        self.data: List[Dict[str, Any]] = []
        self.cache = DataCache()
        self._expansion_connected = False
    
    def set_data(self, data: List[Dict[str, Any]]) -> None:
        """Set the data and rebuild cache."""
        self.data = data
        self.cache.build_cache(data)
    
    def populate_tree(self, selected_category: Optional[str] = None, selected_gender: Optional[str] = None, filter_unchecked_only: bool = False, restore_expansion: Optional[Dict[str, bool]] = None) -> None:
        """Populate the tree with bib numbers and images."""
        self.tree.clear()
        
        if selected_category == "Todas as categorias":
            selected_category = None
        
        if selected_gender == "Todos os gêneros":
            selected_gender = None
        
        # Get relevant cache entries for the selected category and gender
        relevant_bibs = []
        for cache_key, cache_data in self.cache.bib_cache.items():
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
            if filter_unchecked_only and bib_number != "?" and self._bib_has_checked_images(str(bib_number)):
                continue
            
            relevant_bibs.append(cache_data)
        
        # Sort by position (numeric value of bib number) using the 'position' field
        relevant_bibs.sort(key=lambda x: get_position_from_bib(x['position']))
        
        # Create tree nodes
        for cache_data in relevant_bibs:
            bib_number = cache_data['bib_number']
            position = get_position_from_bib(cache_data['position'])
            gender = cache_data["gender"]
            
            # Create the bib node with format [Position]. [Gender] ([Bib Number])
            if position == 999999:
                bib_text = f"?. {gender} ({bib_number})"
            else:
                bib_text = f"{position}. {gender} ({bib_number})"
            
            bib_node = QTreeWidgetItem(self.tree, [bib_text])
            
            # Store the best image index as the bib node's data
            bib_node.setData(0, Qt.UserRole, cache_data['index'])
            
            # Mark that this node needs to load children when expanded
            bib_node.setData(1, Qt.UserRole, {
                'bib_number': bib_number, 
                'category': selected_category, 
                'loaded': False
            })
            
            # Add a dummy child so the expansion triangle appears
            dummy_child = QTreeWidgetItem(bib_node, ["Carregando..."])
        
        # Connect the tree expansion signal to load children on demand
        if not self._expansion_connected:
            self.tree.itemExpanded.connect(self._on_tree_item_expanded)
            self._expansion_connected = True
        
        # Restore expansion state if provided, otherwise keep collapsed
        if restore_expansion:
            self.restore_expansion_state(restore_expansion)
        else:
            self.tree.collapseAll()
    
    def _on_tree_item_expanded(self, item: QTreeWidgetItem) -> None:
        """Load children when a bib node is expanded."""
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
        for idx, data_item in enumerate(self.data):
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
                import os
                img_name = os.path.basename(img_name)
            
            if is_checked:
                img_name = "✓ " + img_name
            
            img_node = QTreeWidgetItem(item, [img_name])
            img_node.setData(0, Qt.UserRole, idx)
        
        # Mark as loaded
        item_data['loaded'] = True
        item.setData(1, Qt.UserRole, item_data)
        
        # Emit signal for external handling
        self.item_expanded.emit(item)
    
    def select_tree_item_by_index(self, data_index: int) -> None:
        """Selects the tree item that corresponds to the given data index."""
        if data_index < 0 or data_index >= len(self.data):
            return
        
        def find_item_with_index(item: QTreeWidgetItem, target_index: int) -> Optional[QTreeWidgetItem]:
            """Recursively search for tree item with specific data index."""
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
        else:
            # No next item found, stay on current or go to last available
            if self.tree.topLevelItemCount() > 0:
                last_item = self.tree.topLevelItem(self.tree.topLevelItemCount() - 1)
                if last_item:
                    self.tree.setCurrentItem(last_item)
    
    def _bib_has_checked_images(self, bib_number: str) -> bool:
        """Check if a bib number has any checked images."""
        for item in self.data:
            run_data = item.get("run_data", {})
            if isinstance(run_data, dict):
                item_bib_number = str(run_data.get("bib_number", ""))
                if item_bib_number == bib_number and item.get("checked", False):
                    return True
        return False
    
    def get_expansion_state(self) -> Dict[str, bool]:
        """Get the current expansion state of all bib nodes."""
        expansion_state = {}
        for i in range(self.tree.topLevelItemCount()):
            bib_item = self.tree.topLevelItem(i)
            if bib_item:
                bib_text = bib_item.text(0)
                expansion_state[bib_text] = bib_item.isExpanded()
        return expansion_state
    
    def restore_expansion_state(self, expansion_state: Dict[str, bool]) -> None:
        """Restore the expansion state of bib nodes."""
        for i in range(self.tree.topLevelItemCount()):
            bib_item = self.tree.topLevelItem(i)
            if bib_item:
                bib_text = bib_item.text(0)
                if bib_text in expansion_state and expansion_state[bib_text]:
                    bib_item.setExpanded(True)
    
    def get_selected_item_info(self) -> Optional[Dict[str, Any]]:
        """Get information about the currently selected item."""
        current_item = self.tree.currentItem()
        if not current_item:
            return None
        
        # Check if it's a child item (image)
        parent = current_item.parent()
        if parent:
            return {
                'type': 'image',
                'bib_text': parent.text(0),
                'image_name': current_item.text(0),
                'data_index': current_item.data(0, Qt.UserRole)
            }
        else:
            return {
                'type': 'bib',
                'bib_text': current_item.text(0),
                'data_index': current_item.data(0, Qt.UserRole)
            }
    
    def select_next_item_after_deletion(self, deleted_item_info: Dict[str, Any], expansion_state: Dict[str, bool]) -> None:
        """Select the next appropriate item after deletion, maintaining expansion state."""
        # First restore expansion state
        self.restore_expansion_state(expansion_state)
        
        if deleted_item_info['type'] == 'image':
            # If we deleted an image, try to select next image in same bib
            bib_text = deleted_item_info['bib_text']
            bib_item = self._find_bib_item_by_text(bib_text)
            
            if bib_item:
                # Ensure the bib item is expanded if it was before
                if bib_text in expansion_state and expansion_state[bib_text]:
                    bib_item.setExpanded(True)
                
                if bib_item.childCount() > 0:
                    # Select first child image
                    first_child = bib_item.child(0)
                    if first_child:
                        self.tree.setCurrentItem(first_child)
                        return
                else:
                    # If no children, select the bib item itself
                    self.tree.setCurrentItem(bib_item)
                    return
        elif deleted_item_info['type'] == 'bib':
            # If we deleted a whole bib, find the next bib item
            for i in range(self.tree.topLevelItemCount()):
                item = self.tree.topLevelItem(i)
                if item:
                    self.tree.setCurrentItem(item)
                    # Restore expansion for this item if it was expanded
                    item_text = item.text(0)
                    if item_text in expansion_state and expansion_state[item_text]:
                        item.setExpanded(True)
                    return
        
        # Fallback: select next available item
        self.select_next_tree_item()
    
    def _find_bib_item_by_text(self, bib_text: str) -> Optional[QTreeWidgetItem]:
        """Find a bib item by its text."""
        for i in range(self.tree.topLevelItemCount()):
            item = self.tree.topLevelItem(i)
            if item and item.text(0) == bib_text:
                return item
        return None
