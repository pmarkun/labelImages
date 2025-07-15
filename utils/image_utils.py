"""
Image processing utilities.
"""
import io
import hashlib
from functools import lru_cache
from typing import List, Dict, Any, Tuple, Optional
from PIL import Image, ImageDraw, ImageFont
from PyQt5.QtGui import QPixmap

BOUNDING_BOX_WIDTH = 6  # Width of the bounding box lines

# Global cache for processed images
_image_cache = {}
_processed_image_cache = {}

def clear_image_cache():
    """Clear the global image cache."""
    global _image_cache, _processed_image_cache
    _image_cache.clear()
    _processed_image_cache.clear()

def get_cache_key(img_path: str, modification_time: Optional[float] = None) -> str:
    """Generate a cache key for an image."""
    if modification_time is not None:
        return f"{img_path}_{modification_time}"
    return img_path

def load_image_cached(img_path: str) -> Image.Image:
    """Load an image with caching and EXIF orientation correction."""
    global _image_cache
    
    try:
        import os
        mtime = os.path.getmtime(img_path)
        cache_key = get_cache_key(img_path, mtime)
        
        if cache_key in _image_cache:
            return _image_cache[cache_key]
        
        img = Image.open(img_path)
        # Apply EXIF orientation correction
        img = correct_exif(img)
        
        # Keep cache size reasonable
        if len(_image_cache) > 50:
            # Remove oldest entries
            keys_to_remove = list(_image_cache.keys())[:10]
            for key in keys_to_remove:
                del _image_cache[key]
        
        _image_cache[cache_key] = img
        return img
    except Exception:
        # Fallback without cache
        img = Image.open(img_path)
        return correct_exif(img)

def crop_image(img: Image.Image, box: List[int]) -> Image.Image:
    """Crop an image using the provided bounding box."""
    left, top, right, bottom = box
    return img.crop((left, top, right, bottom))


@lru_cache(maxsize=128)
def get_font():
    """Get font with caching."""
    try:
        return ImageFont.truetype("arial.ttf", 20)
    except:
        try:
            return ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 20)
        except:
            return ImageFont.load_default()


def draw_bounding_boxes(img: Image.Image, data_item: Dict[str, Any]) -> Image.Image:
    """Draw bounding boxes on the image for person, bib, and shoes."""
    global _processed_image_cache
    
    # Create cache key based on image hash and bounding box data
    img_bytes = img.tobytes()
    bbox_str = str(data_item.get("bib", {})) + str(data_item.get("shoes", []))
    cache_key = hashlib.md5(img_bytes + bbox_str.encode()).hexdigest()
    
    if cache_key in _processed_image_cache:
        return _processed_image_cache[cache_key]
    
    # Create a copy of the image to draw on
    img_copy = img.copy()
    draw = ImageDraw.Draw(img_copy)
    
    # Get cached font
    font = get_font()
    
    # Draw bib bounding box (blue)
    bib_data = data_item.get("bib", {})
    if isinstance(bib_data, dict) and "bbox" in bib_data:
        bib_bbox = bib_data["bbox"]
        if len(bib_bbox) >= 4:
            left, top, right, bottom = bib_bbox
            draw.rectangle([left, top, right, bottom], outline="blue", width=BOUNDING_BOX_WIDTH)
            run_data = data_item.get("run_data", {})
            if isinstance(run_data, dict):
                bib_number = run_data.get("bib_number", "")
                confidence = bib_data.get("confidence", 0.0)
                draw.text((left, top - 25), f'{bib_number} ({confidence:.2f})', fill="blue", font=font)
    
    # Draw shoe bounding boxes (red)
    shoes = data_item.get("shoes", [])
    for i, shoe in enumerate(shoes):
        shoe_bbox = shoe.get("bbox")
        if shoe_bbox and len(shoe_bbox) >= 4:
            left, top, right, bottom = shoe_bbox
            draw.rectangle([left, top, right, bottom], outline="red", width=BOUNDING_BOX_WIDTH)
            
            # Get shoe label
            brand = shoe.get("new_label") or shoe.get("label") or shoe.get("classification_label", f"Shoe {i+1}")
            confidence = shoe.get("classification_confidence", 0.0)
            draw.text((left, top - 25), f'{brand} ({confidence:.2f})', fill="red", font=font)
    
    # Cache the result if cache isn't too large
    if len(_processed_image_cache) < 20:
        _processed_image_cache[cache_key] = img_copy
    
    return img_copy


def pil_to_qpixmap(pil_image: Image.Image) -> QPixmap:
    """Convert PIL Image to QPixmap."""
    # Convert PIL image to bytes
    byte_array = io.BytesIO()
    pil_image.save(byte_array, format='PNG')
    byte_array.seek(0)
    
    # Load QPixmap from bytes
    pixmap = QPixmap()
    pixmap.loadFromData(byte_array.getvalue())
    return pixmap

def correct_exif(img: Image.Image) -> Image.Image:
    """Corrects the orientation of an image based on its EXIF data."""
    try:
        exif = img.getexif()
        if exif is not None:
            orientation = exif.get(274)  # 274 is the EXIF tag for orientation
            if orientation == 3:
                img = img.rotate(180, expand=True)
            elif orientation == 6:
                img = img.rotate(270, expand=True)
            elif orientation == 8:
                img = img.rotate(90, expand=True)
    except (AttributeError, KeyError, TypeError):
        # No EXIF data or orientation info
        pass
    return img
