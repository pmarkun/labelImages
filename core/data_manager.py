"""
Data management and business logic for the Runner Viewer application.
"""
import json
import shutil
import copy
from typing import List, Dict, Any, Set
from .models import DataCache, get_position_from_bib


class DataManager:
    """Manages the application data and operations."""
    
    def __init__(self):
        self.data: List[Dict[str, Any]] = []
        self.cache = DataCache()
        self.undo_stack: List[Dict[str, Any]] = []
        self.max_undo = 50
        
    def load_json(self, file_path: str, chest_plate_threshold: float = 0.5, shoes_threshold: float = 0.5) -> None:
        """Load data from JSON file and apply confidence thresholds."""
        with open(file_path, "r", encoding="utf-8") as f:
            raw_data = json.load(f)
        
        # Apply thresholds to filter data
        self.data = self._apply_confidence_filters(raw_data, chest_plate_threshold, shoes_threshold)
        self.cache.build_cache(self.data)
        self.undo_stack = []
    
    def save_json(self, file_path: str, backup: bool = True) -> None:
        """Save data to JSON file."""
        if backup:
            shutil.copy(file_path, file_path + ".bak")
        
        with open(file_path, "w", encoding="utf-8") as f:
            json.dump(self.data, f, ensure_ascii=False, indent=2)
    
    def collect_stats(self, config_labels: List[Dict[str, Any]]) -> tuple:
        """Collect brands, categories and genders from data."""
        brands = set()
        cats = set()
        genders = set()
        
        # Add brands from config
        for label_config in config_labels:
            if isinstance(label_config, dict) and "label" in label_config:
                brands.add(label_config["label"])
        
        # Add brands, categories and genders from data
        for item in self.data:
            for shoe in item.get("shoes", []):
                brand = shoe.get("new_label") or shoe.get("label") or shoe.get("classification_label")
                if brand:
                    brands.add(brand)
            
            run_data = item.get("run_data", {})
            if isinstance(run_data, dict):
                bib_cat = run_data.get("run_category")
                if bib_cat and bib_cat != "Not Identifiable":
                    cats.add(bib_cat)
                
                gender = run_data.get("gender")
                if gender:
                    genders.add(gender)
        
        self.cache.build_cache(self.data)
        return sorted(brands), sorted(cats), sorted(genders)
    
    def save_state(self, current_index: int) -> None:
        """Save current state for undo functionality."""
        state = {
            'data': copy.deepcopy(self.data),
            'current_index': current_index
        }
        self.undo_stack.append(state)
        if len(self.undo_stack) > self.max_undo:
            self.undo_stack.pop(0)
    
    def undo(self) -> Dict[str, Any]:
        """Undo last change and return the restored state."""
        if not self.undo_stack:
            return {}
        
        state = self.undo_stack.pop()
        self.data = state['data']
        self.cache.build_cache(self.data)
        return state
    
    def get_progress_stats(self) -> Dict[str, float]:
        """Calculate progress statistics."""
        total = len(self.data)
        checked = sum(1 for item in self.data if item.get('checked', False))
        return {
            'total': total,
            'checked': checked,
            'percentage': (checked / total * 100) if total > 0 else 0
        }
    
    def remove_image(self, index: int) -> int:
        """Remove image at index and return new current index."""
        if 0 <= index < len(self.data):
            self.data.pop(index)
            self.cache.build_cache(self.data)
            
            # Adjust index
            if index > 0:
                return index - 1
            elif len(self.data) > 0:
                return 0
            else:
                return -1
        return index
    
    def remove_all_images_with_bib(self, bib_number: str) -> int:
        """Remove all images with specific bib number and return new current index."""
        indices_to_remove = []
        
        for i, item in enumerate(self.data):
            item_bib_number = ""
            run_data = item.get("run_data", {})
            if isinstance(run_data, dict):
                item_bib_number = str(run_data.get("bib_number", ""))
            
            if item_bib_number == str(bib_number):
                indices_to_remove.append(i)
        
        if not indices_to_remove:
            return -1
        
        # Find the best new index
        first_removed_index = min(indices_to_remove)
        new_index = first_removed_index - 1 if first_removed_index > 0 else 0
        
        # Remove in reverse order
        for i in reversed(indices_to_remove):
            self.data.pop(i)
            if i <= new_index:
                new_index = max(0, new_index - 1)
        
        self.cache.build_cache(self.data)
        return min(new_index, len(self.data) - 1) if self.data else -1
    
    def update_image_data(self, index: int, bib_number: str, category: str, 
                         checked_brands: List[str]) -> None:
        """Update image data with new information."""
        if not (0 <= index < len(self.data)):
            return
        
        item = self.data[index]
        
        # Update run_data
        run_data = item.setdefault("run_data", {})
        run_data["bib_number"] = bib_number
        if category:
            run_data["run_category"] = category
        
        # Update shoe brands
        shoes = item.get("shoes", [])
        
        # Clear existing brands
        for shoe in shoes:
            if "classification_label" in shoe:
                shoe["classification_label"] = ""
            elif "new_label" in shoe:
                shoe["new_label"] = ""
            elif "label" in shoe:
                shoe["label"] = ""
        
        # Apply new brands
        if checked_brands and shoes:
            for idx, shoe in enumerate(shoes):
                if len(checked_brands) == 1:
                    brand = checked_brands[0]
                else:
                    brand = checked_brands[idx % len(checked_brands)]
                
                if "classification_label" in shoe:
                    shoe["classification_label"] = brand
                elif "new_label" in shoe:
                    shoe["new_label"] = brand
                else:
                    shoe["new_label"] = brand
        
        self.cache.build_cache(self.data)
    
    def propagate_data_to_same_bib(self, current_index: int) -> None:
        """Propagate current image data to all images with same bib number."""
        if not (0 <= current_index < len(self.data)):
            return
        
        current_item = self.data[current_index]
        
        # Get current image's data
        run_data = current_item.get("run_data", {})
        if not isinstance(run_data, dict):
            return
        
        bib_number = str(run_data.get("bib_number", ""))
        if not bib_number:
            return
        
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
        
        # Update all other images with same bib number
        for i, item in enumerate(self.data):
            if i != current_index:
                item_run_data = item.get("run_data", {})
                if isinstance(item_run_data, dict):
                    item_bib_number = str(item_run_data.get("bib_number", ""))
                    
                    if item_bib_number == bib_number:
                        # Uncheck and update
                        item['checked'] = False
                        item_run_data["run_category"] = current_category
                        
                        # Update shoe brands
                        item_shoes = item.get("shoes", [])
                        for idx, shoe in enumerate(item_shoes):
                            if current_brands:
                                brand_to_apply = current_brands[idx % len(current_brands)]
                                
                                if "classification_label" in shoe:
                                    shoe["classification_label"] = brand_to_apply
                                elif "new_label" in shoe:
                                    shoe["new_label"] = brand_to_apply
                                else:
                                    shoe["new_label"] = brand_to_apply
                            else:
                                # Clear brands if current has none
                                if "classification_label" in shoe:
                                    shoe["classification_label"] = ""
                                elif "new_label" in shoe:
                                    shoe["new_label"] = ""
                                elif "label" in shoe:
                                    shoe["label"] = ""
        
        self.cache.build_cache(self.data)
    
    def toggle_checked(self, index: int) -> bool:
        """Toggle checked status of image and return new status."""
        if not (0 <= index < len(self.data)):
            return False
        
        current_item = self.data[index]
        current_checked = current_item.get('checked', False)
        current_item['checked'] = not current_checked
        return not current_checked
    
    def bib_has_checked_images(self, bib_number: str) -> bool:
        """Check if a bib number has any checked images."""
        for item in self.data:
            run_data = item.get("run_data", {})
            if isinstance(run_data, dict):
                item_bib_number = str(run_data.get("bib_number", ""))
                if item_bib_number == bib_number and item.get("checked", False):
                    return True
        return False
    
    def _apply_confidence_filters(self, raw_data: List[Dict[str, Any]], 
                                 chest_plate_threshold: float, 
                                 shoes_threshold: float) -> List[Dict[str, Any]]:
        """Apply confidence thresholds to filter data."""
        filtered_data = []
        
        for item in raw_data:
            # Create a copy of the item to avoid modifying original data
            filtered_item = copy.deepcopy(item)
            
            # Filter shoes based on detection and classification confidence
            if "shoes" in filtered_item:
                filtered_shoes = []
                for shoe in filtered_item["shoes"]:
                    classification_conf = shoe.get("classification_confidence", 0.0)
                    
                    # Keep shoe if both detection and classification confidence meet threshold
                    if classification_conf >= shoes_threshold:
                        filtered_shoes.append(shoe)
                
                filtered_item["shoes"] = filtered_shoes
            
            # Filter bib/chest plate data based on confidence
            if "bib" in filtered_item.get('run_data', {}) and isinstance(filtered_item.get("run_data",{}).get('bib'), dict):
                bib_conf = filtered_item["bib"].get("confidence", 0.0)
                
                # Remove bib data if confidence is below threshold
                if bib_conf < chest_plate_threshold:
                    filtered_item["bib"] = {}
            
            # Only include items that have at least one shoe or valid bib data
            has_valid_shoes = len(filtered_item.get("shoes", [])) > 0
            has_valid_bib = bool(filtered_item.get("bib", {}))
            
            if has_valid_shoes or has_valid_bib:
                filtered_data.append(filtered_item)
        
        return filtered_data
    
    def reload_with_thresholds(self, file_path: str, chest_plate_threshold: float, shoes_threshold: float) -> None:
        """Reload data with new confidence thresholds."""
        self.load_json(file_path, chest_plate_threshold, shoes_threshold)
