"""
Image processing utilities.
"""
import io
from typing import List, Dict, Any, Tuple
from PIL import Image, ImageDraw, ImageFont
from PyQt5.QtGui import QPixmap


def crop_image(img: Image.Image, box: List[int]) -> Image.Image:
    """Crop an image using the provided bounding box."""
    left, top, right, bottom = box
    return img.crop((left, top, right, bottom))


def draw_bounding_boxes(img: Image.Image, data_item: Dict[str, Any]) -> Image.Image:
    """Draw bounding boxes on the image for person, bib, and shoes."""
    # Create a copy of the image to draw on
    img_copy = img.copy()
    draw = ImageDraw.Draw(img_copy)
    
    # Try to load a font, fall back to default if not available
    try:
        font = ImageFont.truetype("arial.ttf", 20)
    except:
        try:
            font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 20)
        except:
            font = ImageFont.load_default()
    
    # Draw person bounding box (green)
    person_bbox = data_item.get("bbox") or data_item.get("person_bbox")
    if person_bbox and len(person_bbox) >= 4:
        left, top, right, bottom = person_bbox
        draw.rectangle([left, top, right, bottom], outline="green", width=3)
        draw.text((left, top - 25), "Person", fill="green", font=font)
    
    # Draw bib bounding box (blue)
    bib_data = data_item.get("bib", {})
    if isinstance(bib_data, dict) and "bbox" in bib_data:
        bib_bbox = bib_data["bbox"]
        if len(bib_bbox) >= 4:
            left, top, right, bottom = bib_bbox
            draw.rectangle([left, top, right, bottom], outline="blue", width=3)
            draw.text((left, top - 25), "Bib", fill="blue", font=font)
    
    # Draw shoe bounding boxes (red)
    shoes = data_item.get("shoes", [])
    for i, shoe in enumerate(shoes):
        shoe_bbox = shoe.get("bbox")
        if shoe_bbox and len(shoe_bbox) >= 4:
            left, top, right, bottom = shoe_bbox
            draw.rectangle([left, top, right, bottom], outline="red", width=3)
            
            # Get shoe label
            brand = shoe.get("new_label") or shoe.get("label") or shoe.get("classification_label", f"Shoe {i+1}")
            draw.text((left, top - 25), brand, fill="red", font=font)
    
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
