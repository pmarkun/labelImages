"""
Data models and structures for the Runner Viewer application (new format only).
"""
from typing import Dict, List, Any


class DataCache:
    """Cache for optimizing data access and tree population (new format only)."""

    def __init__(self):
        self.bib_cache: Dict[str, Dict[str, Any]] = {}
        self.index_map: Dict[int, List[str]] = {}

    # ------------------------------------------------------------------
    # internal helpers
    # ------------------------------------------------------------------
    def _compute_cache_entry(self, participant: Dict[str, Any], index: int) -> tuple:
        """Compute cache key and entry for a participant."""
        bib_number = str(participant.get("bib_number", ""))
        if not bib_number:
            return None, None

        category = participant.get("run_category", "")
        if category == "Not Identifiable":
            category = "?"

        gender = participant.get("gender", "Desconhecido")

        # Check if participant has valid images
        has_valid_image = False
        runners = participant.get("runners_found", [])
        for runner in runners:
            img_path = runner.get("image") or runner.get("image_path")
            if img_path:
                has_valid_image = True
                break

        # Confidence over shoes in first runner
        total_confidence = 0
        if runners:
            for shoe in runners[0].get("shoes", []):
                confidence = shoe.get("confidence", 0)
                if isinstance(confidence, (int, float)):
                    total_confidence += confidence

        cache_key = f"{bib_number}|{category}|{gender}"
        position = participant.get("position", "?")
        entry = {
            'participant': participant,
            'index': index,
            'confidence': total_confidence,
            'bib_number': bib_number,
            'category': category,
            'gender': gender,
            'position': position,
            'has_valid_image': has_valid_image,
        }
        return cache_key, entry
    
    def build_cache(self, data: List[Dict[str, Any]]) -> None:
        """Build cache of best participants per bib number for performance (new format only)."""
        self.bib_cache = {}
        self.index_map = {}
        for idx, participant in enumerate(data):
            cache_key, entry = self._compute_cache_entry(participant, idx)
            if not cache_key:
                continue
            existing = self.bib_cache.get(cache_key)
            if existing is None or entry['confidence'] > existing['confidence']:
                if existing is not None:
                    old_idx = existing['index']
                    if old_idx in self.index_map and cache_key in self.index_map[old_idx]:
                        self.index_map[old_idx].remove(cache_key)
                self.bib_cache[cache_key] = entry
                self.index_map.setdefault(idx, []).append(cache_key)
    
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

    # ------------------------------------------------------------------
    # incremental update methods for better performance
    # ------------------------------------------------------------------
    def update_participant(self, participant: Dict[str, Any], index: int) -> None:
        """Update cache entry for a single participant."""
        cache_key, entry = self._compute_cache_entry(participant, index)
        if not cache_key:
            return

        # remove existing mapping for this index
        if index in self.index_map:
            for key in list(self.index_map[index]):
                existing = self.bib_cache.get(key)
                if existing and existing['index'] == index:
                    del self.bib_cache[key]
            self.index_map[index] = []

        existing = self.bib_cache.get(cache_key)
        if existing is None or entry['confidence'] >= existing['confidence']:
            if existing is not None:
                old_idx = existing['index']
                if old_idx in self.index_map and cache_key in self.index_map[old_idx]:
                    self.index_map[old_idx].remove(cache_key)
            self.bib_cache[cache_key] = entry
            self.index_map.setdefault(index, []).append(cache_key)

    def remove_indices(self, removed: List[int], data: List[Dict[str, Any]]) -> None:
        """Remove participants at given indices and update cache."""
        if not removed:
            return

        removed_set = set(removed)

        # Identify keys affected and remove them
        keys_to_recalc = set()
        for idx in sorted(removed_set):
            keys = self.index_map.pop(idx, [])
            for key in keys:
                entry = self.bib_cache.get(key)
                if entry and entry['index'] == idx:
                    del self.bib_cache[key]
                    keys_to_recalc.add(key)

        # Shift indices after removal
        def shifted(i):
            shift = sum(1 for r in removed_set if i > r)
            return i - shift

        new_index_map: Dict[int, List[str]] = {}
        for i, keys in self.index_map.items():
            new_i = shifted(i)
            new_index_map.setdefault(new_i, []).extend(keys)
            for key in keys:
                entry = self.bib_cache.get(key)
                if entry and entry['index'] == i:
                    entry['index'] = new_i
        self.index_map = new_index_map

        # Recalculate removed bibs
        for key in keys_to_recalc:
            bib_number, category, gender = key.split('|')
            best_entry = None
            best_idx = -1
            best_conf = -1
            for idx, participant in enumerate(data):
                if str(participant.get("bib_number", "")) != bib_number:
                    continue
                item_category = participant.get("run_category", "")
                if item_category == "Not Identifiable":
                    item_category = "?"
                if item_category != category:
                    continue
                if participant.get("gender", "Desconhecido") != gender:
                    continue
                cache_key2, entry2 = self._compute_cache_entry(participant, idx)
                if entry2 and entry2['confidence'] > best_conf:
                    best_conf = entry2['confidence']
                    best_entry = entry2
                    best_idx = idx
            if best_entry is not None:
                self.bib_cache[key] = best_entry
                self.index_map.setdefault(best_idx, []).append(key)

def get_position_from_bib(bib_number: str) -> int:
    """Calculate position based on bib number sorting."""
    if not bib_number or bib_number == "?":
        return 999999  # Put unknown bibs at the end
    try:
        return int(bib_number)
    except ValueError:
        return 999999
