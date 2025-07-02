"""
Image processing utilities.
"""
import io
from typing import List
from PIL import Image
from PyQt5.QtGui import QPixmap


def crop_image(img: Image.Image, box: List[int]) -> Image.Image:
    """Crop an image using the provided bounding box."""
    left, top, right, bottom = box
    return img.crop((left, top, right, bottom))


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
