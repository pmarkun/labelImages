"""
Data management and business logic for the Runner Viewer application (new format only).
"""
import json
import shutil
import copy
import csv
from typing import List, Dict, Any, Set
from .models import DataCache


class DataManager:
    """Manages the application data and operations (new format only)."""
    
    def __init__(self):
        self.data: List[Dict[str, Any]] = []
        self.cache = DataCache()
        self.undo_stack: List[Dict[str, Any]] = []
        self.max_undo = 50
    
    def load_json(self, file_path: str) -> None:
        """Load data from JSON file (new format only)."""
        with open(file_path, "r", encoding="utf-8") as f:
            self.data = json.load(f)
        self.cache.build_cache(self.data)
        self.undo_stack = []

    def load_data(self, data: List[Dict[str, Any]]) -> None:
        """Load data directly from a list of dictionaries."""
        self.data = list(data)
        self.cache.build_cache(self.data)
        self.undo_stack = []
    
    def save_json(self, file_path: str, backup: bool = True) -> None:
        """Save data to JSON file."""
        if backup:
            shutil.copy(file_path, file_path + ".bak")
        with open(file_path, "w", encoding="utf-8") as f:
            json.dump(self.data, f, ensure_ascii=False, indent=2)
    
    def collect_stats(self, config_labels: List[Dict[str, Any]]) -> tuple:
        """Collect brands, categories and genders from new-format data."""
        brands = set()
        cats = set()
        genders = set()
        for label_config in config_labels:
            if isinstance(label_config, dict) and "label" in label_config:
                brands.add(label_config["label"])
        for participant in self.data:
            # Categories and genders from participant-level fields
            cat = participant.get("run_category")
            if cat and cat != "Not Identifiable":
                cats.add(cat)
            gender = participant.get("gender")
            if gender:
                genders.add(gender)
            # Brands from runners_found
            for runner in participant.get("runners_found", []):
                for shoe in runner.get("shoes", []):
                    brand = shoe.get("new_label") or shoe.get("label") or shoe.get("classification_label")
                    if brand:
                        brands.add(brand)
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
        """Calculate progress statistics (participants checked)."""
        total = len(self.data)
        checked = sum(1 for item in self.data if item.get('checked', False))
        return {
            'total': total,
            'checked': checked,
            'percentage': (checked / total * 100) if total > 0 else 0
        }
    
    def remove_participant(self, index: int) -> int:
        """Remove participant at index and return new current index."""
        if 0 <= index < len(self.data):
            self.data.pop(index)
            self.cache.build_cache(self.data)
            if index > 0:
                return index - 1
            elif len(self.data) > 0:
                return 0
            else:
                return -1
        return index
    
    def remove_all_with_bib(self, bib_number: str) -> int:
        """Remove all participants with specific bib number and return new current index."""
        indices_to_remove = [i for i, p in enumerate(self.data) if str(p.get("bib_number", "")) == str(bib_number)]
        if not indices_to_remove:
            return -1
        first_removed_index = min(indices_to_remove)
        new_index = first_removed_index - 1 if first_removed_index > 0 else 0
        for i in reversed(indices_to_remove):
            self.data.pop(i)
            if i <= new_index:
                new_index = max(0, new_index - 1)
        self.cache.build_cache(self.data)
        return min(new_index, len(self.data) - 1) if self.data else -1
    
    def update_participant_data(self, index: int, bib_number: str, category: str, checked_brands: List[str]) -> None:
        """Update participant data with new information (new format only)."""
        if not (0 <= index < len(self.data)):
            return
        participant = self.data[index]
        participant["bib_number"] = bib_number
        if category:
            participant["run_category"] = category
        # Update brands in first runner's shoes (if any)
        runners = participant.get("runners_found", [])
        if runners:
            shoes = runners[0].get("shoes", [])
            # Clear existing brands
            for shoe in shoes:
                for key in ("classification_label", "new_label", "label"):
                    if key in shoe:
                        shoe[key] = ""
            # Apply new brands
            if checked_brands and shoes:
                for idx, shoe in enumerate(shoes):
                    brand = checked_brands[0] if len(checked_brands) == 1 else checked_brands[idx % len(checked_brands)]
                    if "classification_label" in shoe:
                        shoe["classification_label"] = brand
                    elif "new_label" in shoe:
                        shoe["new_label"] = brand
                    else:
                        shoe["new_label"] = brand
        self.cache.build_cache(self.data)
    
    def propagate_data_to_same_bib(self, current_index: int) -> None:
        """Propagate current participant data to all with same bib number (new format only)."""
        if not (0 <= current_index < len(self.data)):
            return
        current = self.data[current_index]
        bib_number = str(current.get("bib_number", ""))
        if not bib_number:
            return
        current_category = current.get("run_category", "")
        runners = current.get("runners_found", [])
        current_brands = []
        if runners:
            for shoe in runners[0].get("shoes", []):
                brand = shoe.get("new_label") or shoe.get("label") or shoe.get("classification_label", "")
                if brand:
                    current_brands.append(brand)
        current['checked'] = True
        for i, participant in enumerate(self.data):
            if i != current_index and str(participant.get("bib_number", "")) == bib_number:
                participant['checked'] = False
                participant["run_category"] = current_category
                runners2 = participant.get("runners_found", [])
                if runners2:
                    shoes2 = runners2[0].get("shoes", [])
                    for idx, shoe in enumerate(shoes2):
                        if current_brands:
                            brand_to_apply = current_brands[idx % len(current_brands)]
                            if "classification_label" in shoe:
                                shoe["classification_label"] = brand_to_apply
                            elif "new_label" in shoe:
                                shoe["new_label"] = brand_to_apply
                            else:
                                shoe["new_label"] = brand_to_apply
                        else:
                            for key in ("classification_label", "new_label", "label"):
                                if key in shoe:
                                    shoe[key] = ""
        self.cache.build_cache(self.data)
    
    def toggle_checked(self, index: int) -> bool:
        """Toggle checked status of participant and return new status."""
        if not (0 <= index < len(self.data)):
            return False
        current = self.data[index]
        current_checked = current.get('checked', False)
        current['checked'] = not current_checked
        return not current_checked
    
    def bib_has_checked(self, bib_number: str) -> bool:
        """Check if a bib number has any checked participants."""
        for participant in self.data:
            if str(participant.get("bib_number", "")) == bib_number and participant.get("checked", False):
                return True
        return False

    def export_simplified_csv(self, file_path: str) -> int:
        """Export a simplified CSV with key runner information."""
        headers = ["bib", "position", "gender", "run_category", "shoe_brand", "confidence"]
        exported = 0

        with open(file_path, "w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow(headers)

            for participant in self.data:
                bib = str(participant.get("bib_number", ""))
                position = participant.get("position", "")
                gender = participant.get("gender", "")
                run_category = participant.get("run_category", "")
                checked = participant.get("checked", False)

                # Gather all shoes from all runners
                shoes = []
                for runner in participant.get("runners_found", []):
                    shoes.extend(runner.get("shoes", []))

                brand_scores: Dict[str, float] = {}
                for shoe in shoes:
                    brand = shoe.get("classification_label") or shoe.get("new_label") or shoe.get("label")
                    if not brand:
                        continue
                    conf = shoe.get("classification_confidence", 0)
                    if isinstance(conf, (int, float)):
                        brand_scores[brand] = brand_scores.get(brand, 0) + conf

                brand = ""
                confidence = 0.0

                if checked and brand_scores:
                    # When checked, assume all shoes labeled consistently
                    first_shoe = shoes[0] if shoes else {}
                    brand = first_shoe.get("classification_label") or first_shoe.get("new_label") or first_shoe.get("label") or ""
                    confidence = 1.0
                elif brand_scores:
                    brand = max(brand_scores, key=brand_scores.get)
                    confidence = brand_scores[brand]

                if confidence >= 0.95:
                    writer.writerow([bib, position, gender, run_category, brand, f"{confidence:.2f}"])
                    exported += 1

        return exported
