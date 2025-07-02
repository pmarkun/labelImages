"""
Data models and structures for the Runner Viewer application.
"""
from typing import Dict, List, Any, Optional
from dataclasses import dataclass


@dataclass
class Shoe:
    """Represents a shoe detection in an image."""
    bbox: List[int]
    confidence: float = 0.0
    label: str = ""
    new_label: str = ""
    classification_label: str = ""
    
    def get_brand(self) -> str:
        """Get the brand/label for this shoe, checking all possible fields."""
        return self.new_label or self.label or self.classification_label or ""
    
    def set_brand(self, brand: str) -> None:
        """Set the brand/label for this shoe."""
        if hasattr(self, 'classification_label'):
            self.classification_label = brand
        elif hasattr(self, 'new_label'):
            self.new_label = brand
        else:
            self.new_label = brand


@dataclass
class RunData:
    """Represents runner/bib information."""
    bib_number: str = ""
    run_category: str = ""


@dataclass
class ImageData:
    """Represents an image with associated runner and shoe data."""
    filename: str = ""
    image_path: str = ""
    bbox: Optional[List[int]] = None
    person_bbox: Optional[List[int]] = None
    shoes: Optional[List[Dict[str, Any]]] = None
    run_data: Optional[Dict[str, Any]] = None
    checked: bool = False
    
    def __post_init__(self):
        if self.shoes is None:
            self.shoes = []
        if self.run_data is None:
            self.run_data = {}
    
    def get_filename(self) -> str:
        """Get the filename, supporting both old and new formats."""
        return self.filename or self.image_path or ""
    
    def get_bib_number(self) -> str:
        """Get the bib number from run_data."""
        if isinstance(self.run_data, dict):
            return str(self.run_data.get("bib_number", ""))
        return ""
    
    def get_category(self) -> str:
        """Get the category from run_data."""
        if isinstance(self.run_data, dict):
            category = self.run_data.get("run_category", "")
            return "?" if category == "Not Identifiable" else category
        return ""
    
    def get_bbox(self) -> List[int]:
        """Get the bounding box, supporting both old and new formats."""
        return self.bbox or self.person_bbox or [0, 0, 0, 0]


class DataCache:
    """Cache for optimizing data access and tree population."""
    
    def __init__(self):
        self.bib_cache: Dict[str, Dict[str, Any]] = {}
    
    def build_cache(self, data: List[Dict[str, Any]]) -> None:
        """Build cache of best images per bib number for performance."""
        self.bib_cache = {}
        
        for idx, item in enumerate(data):
            # Get bib number from run_data
            bib_number = ""
            run_data = item.get("run_data", {})
            if isinstance(run_data, dict):
                bib_number = str(run_data.get("bib_number", ""))
            
            if not bib_number:
                continue
                
            # Get category
            category = ""
            if isinstance(run_data, dict):
                category = run_data.get("run_category", "")
                if category == "Not Identifiable":
                    category = "?"

            # Get position from position
            position = run_data.get("position", "")
            gender = run_data.get("gender", "Desconhecido")
            # Calculate total confidence for shoes in this image
            total_confidence = 0
            shoes = item.get("shoes", [])
            for shoe in shoes:
                confidence = shoe.get("confidence", 0)
                if isinstance(confidence, (int, float)):
                    total_confidence += confidence
            
            # Create cache key
            cache_key = f"{bib_number}|{category}|{gender}"
            
            # Check if this is the best image for this bib/category combination
            if cache_key not in self.bib_cache or total_confidence > self.bib_cache[cache_key]['confidence']:
                self.bib_cache[cache_key] = {
                    'image': item,
                    'index': idx,
                    'confidence': total_confidence,
                    'bib_number': bib_number,
                    'category': category,
                    'position': position,
                    'gender' : gender,
                }
    
    def get_best_image_for_bib(self, bib_number: str, category=None) -> Dict[str, Any]:
        """Get the best image for a given bib number and category."""
        cache_key = f"{bib_number}|{category or ''}"
        return self.bib_cache.get(cache_key, {
            'image': None,
            'index': -1,
            'confidence': -1
        })
    
    def get_all_bib_numbers_for_category(self, category=None) -> List[str]:
        """Get all unique bib numbers for a given category, sorted by position."""
        bib_numbers = set()
        
        for cache_key, cache_data in self.bib_cache.items():
            item_category = cache_data['category']
            bib_number = cache_data['bib_number']
            
            # Skip if doesn't match category filter
            if category and category != "Todas as categorias" and item_category != category:
                continue
            
            bib_numbers.add(bib_number)
        
        # Sort by position (numeric value of bib number)
        return sorted(bib_numbers, key=lambda x: get_position_from_bib(x))


def get_position_from_bib(bib_number: str) -> int:
    """Calculate position based on bib number sorting."""
    if not bib_number or bib_number == "?":
        return 999999  # Put unknown bibs at the end
    
    try:
        return int(bib_number)
    except ValueError:
        return 999999
