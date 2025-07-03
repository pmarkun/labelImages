"""
Data models and structures for the Runner Viewer application (new format only).
"""
from typing import Dict, List, Any


class DataCache:
    """Cache for optimizing data access and tree population (new format only)."""
    def __init__(self):
        self.bib_cache: Dict[str, Dict[str, Any]] = {}
    
    def build_cache(self, data: List[Dict[str, Any]]) -> None:
        """Build cache of best participants per bib number for performance (new format only)."""
        self.bib_cache = {}
        for idx, participant in enumerate(data):
            bib_number = str(participant.get("bib_number", ""))
            if not bib_number:
                continue
            category = participant.get("run_category", "")
            if category == "Not Identifiable":
                category = "?"
            gender = participant.get("gender", "Desconhecido")
            
            # Check if this participant has valid images
            has_valid_image = False
            runners = participant.get("runners_found", [])
            for runner in runners:
                img_path = runner.get("image") or runner.get("image_path")
                if img_path:
                    has_valid_image = True
                    break
            
            # Confidence: sum over shoes in first runner (if any)
            total_confidence = 0
            if runners:
                for shoe in runners[0].get("shoes", []):
                    confidence = shoe.get("confidence", 0)
                    if isinstance(confidence, (int, float)):
                        total_confidence += confidence
            cache_key = f"{bib_number}|{category}|{gender}"
            position = participant.get("position", "?")
            if cache_key not in self.bib_cache or total_confidence > self.bib_cache[cache_key]['confidence']:
                self.bib_cache[cache_key] = {
                    'participant': participant,
                    'index': idx,
                    'confidence': total_confidence,
                    'bib_number': bib_number,
                    'category': category,
                    'gender': gender,
                    'position': position,
                    'has_valid_image': has_valid_image,
                }
    
    def get_best_participant_for_bib(self, bib_number: str, category=None, gender=None) -> Dict[str, Any]:
        """Get the best participant for a given bib number, category, and gender."""
        category = category or ""
        gender = gender or ""
        cache_key = f"{bib_number}|{category}|{gender}"
        return self.bib_cache.get(cache_key, {
            'participant': None,
            'index': -1,
            'confidence': -1
        })
    
    def get_all_bib_numbers_for_category(self, category=None) -> List[str]:
        """Get all unique bib numbers for a given category, sorted numerically."""
        bib_numbers = set()
        for cache_key, cache_data in self.bib_cache.items():
            item_category = cache_data['category']
            bib_number = cache_data['bib_number']
            if category and category != "Todas as categorias" and item_category != category:
                continue
            bib_numbers.add(bib_number)
        return sorted(bib_numbers, key=lambda x: get_position_from_bib(x))

def get_position_from_bib(bib_number: str) -> int:
    """Calculate position based on bib number sorting."""
    if not bib_number or bib_number == "?":
        return 999999  # Put unknown bibs at the end
    try:
        return int(bib_number)
    except ValueError:
        return 999999
