"""
Fast image display manager with lazy loading and aggressive caching.
"""
import os
from typing import List, Dict, Any, Optional
from PIL import Image
from PyQt5.QtCore import Qt, QTimer
from PyQt5.QtWidgets import QLabel, QVBoxLayout, QWidget, QMessageBox, QSizePolicy
from .widgets import ClickableLabel
from utils.image_utils import crop_image, pil_to_qpixmap, draw_bounding_boxes
from utils.lazy_image_loader import get_lazy_cache


class FastImageDisplayManager:
    """Ultra-fast image display manager with lazy loading."""
    
    def __init__(self, thumb_label: QLabel, runner_label: QLabel, 
                 shoe_container: QWidget, shoe_layout: QVBoxLayout):
        self.thumb_label = thumb_label
        self.runner_label = runner_label
        self.shoe_container = shoe_container
        self.shoe_layout = shoe_layout
        self.shoe_click_callback = None
        
        # Lightweight caches for processed components
        self._component_cache = {}  # Full display cache
        self._pending_loads = set()
        
        # Lazy cache
        self._lazy_cache = get_lazy_cache()
        
        # Current state
        self._current_img_path = None
        self._current_data_item = None
    
    def clear_cache(self):
        """Clear all caches."""
        self._component_cache.clear()
        self._pending_loads.clear()
    
    def set_shoe_click_callback(self, callback) -> None:
        """Set the callback for shoe clicks."""
        self.shoe_click_callback = callback
    
    def display_image(self, data_item: Dict[str, Any], base_path: str) -> None:
        """Display image with ultra-fast lazy loading."""
        if not data_item:
            return
        
        # Get image path
        img_filename = data_item.get("filename") or data_item.get("image_path", "")
        img_path = os.path.join(base_path, img_filename)
        
        # Store current request
        self._current_img_path = img_path
        self._current_data_item = data_item
        
        # Check if we have cached components
        cache_key = self._get_cache_key(img_path, data_item)
        if cache_key in self._component_cache:
            self._apply_cached_components(cache_key, data_item.get('checked', False))
            return
        
        # Show minimal loading state
        self._show_loading_state(data_item.get('checked', False))
        
        # Try to get image
        img = self._lazy_cache.get_image(
            img_path,
            callback=self._on_image_ready,
            priority=0
        )
        
        if img is not None:
            # Image available immediately
            self._process_and_display(img, data_item, img_path)
    
    def _get_cache_key(self, img_path: str, data_item: Dict[str, Any]) -> str:
        """Generate cache key for components."""
        # Use hash of relevant data for cache key
        data_hash = hash(str({
            'bib': data_item.get('bib', {}),
            'shoes': data_item.get('shoes', []),
            'bbox': data_item.get('bbox')
        }))
        return f"{img_path}_{data_hash}"
    
    def _show_loading_state(self, is_checked: bool):
        """Show minimal loading state."""
        style = self._get_style(is_checked)
        
        # Just update styles, no text to avoid flicker
        self.thumb_label.setStyleSheet(style)
        self.runner_label.setStyleSheet("background-color: #f0f0f0;")
        
        # Clear shoes quickly
        self._clear_shoes_fast()
    
    def _get_style(self, is_checked: bool) -> str:
        """Get style for checked/unchecked state."""
        if is_checked:
            return "border: 4px solid #28a745; border-radius: 8px; padding: 16px; background-color: #d4edda;"
        else:
            return "border: 2px dashed #ddd; border-radius: 8px; padding: 20px; background-color: #f8f9fa;"
    
    def _clear_shoes_fast(self):
        """Fast shoe clearing without delete."""
        # Hide widgets instead of deleting for speed
        for i in range(self.shoe_layout.count()):
            item = self.shoe_layout.itemAt(i)
            if item and item.widget():
                widget = item.widget()
                if widget:
                    widget.hide()
    
    def _on_image_ready(self, img_path: str, img: Optional[Image.Image]):
        """Callback when image is loaded."""
        if img is None or img_path != self._current_img_path or self._current_data_item is None:
            return
        
        self._process_and_display(img, self._current_data_item, img_path)
    
    def _process_and_display(self, img: Image.Image, data_item: Dict[str, Any], img_path: str):
        """Process and display image components."""
        try:
            cache_key = self._get_cache_key(img_path, data_item)
            
            # Create all components quickly
            components = self._create_components_fast(img, data_item)
            
            # Cache components
            if len(self._component_cache) < 30:  # Keep cache small for speed
                self._component_cache[cache_key] = components
            
            # Apply to UI
            self._apply_components(components, data_item.get('checked', False))
            
        except Exception as e:
            print(f"Error processing {img_path}: {e}")
            self._show_error_state()
    
    def _create_components_fast(self, img: Image.Image, data_item: Dict[str, Any]) -> Dict[str, Any]:
        """Create all components with minimal processing."""
        # Use minimal image processing for speed
        img_with_boxes = draw_bounding_boxes(img, data_item)
        
        # Thumbnail - small and fast
        thumb_size = (120, int(120 * img.height / img.width))
        thumb_img = img_with_boxes.resize(thumb_size, Image.Resampling.NEAREST)  # Fastest resize
        thumb_pixmap = pil_to_qpixmap(thumb_img)
        
        # Runner - medium size
        bbox = data_item.get("bbox") or data_item.get("person_bbox", [0, 0, img.width, img.height])
        runner_crop = crop_image(img_with_boxes, bbox)
        
        # Fast resize calculation
        target_size = min(300, max(runner_crop.width, runner_crop.height))
        if runner_crop.width > runner_crop.height:
            runner_size = (target_size, int(target_size * runner_crop.height / runner_crop.width))
        else:
            runner_size = (int(target_size * runner_crop.width / runner_crop.height), target_size)
        
        runner_img = runner_crop.resize(runner_size, Image.Resampling.NEAREST)
        runner_pixmap = pil_to_qpixmap(runner_img)
        
        # Shoes - create minimal info for fast rendering
        shoes_data = []
        for shoe_index, shoe in enumerate(data_item.get("shoes", [])):
            shoe_bbox = shoe.get("bbox")
            if shoe_bbox and len(shoe_bbox) >= 4:
                # Create small shoe crop
                shoe_crop = crop_image(img, shoe_bbox)
                shoe_size = (80, int(80 * shoe_crop.height / shoe_crop.width)) if shoe_crop.width > 0 else (80, 80)
                shoe_img = shoe_crop.resize(shoe_size, Image.Resampling.NEAREST)
                shoe_pixmap = pil_to_qpixmap(shoe_img)
                
                brand = shoe.get("new_label") or shoe.get("label") or shoe.get("classification_label", "")
                
                shoes_data.append({
                    'pixmap': shoe_pixmap,
                    'brand': brand,
                    'index': shoe_index
                })
        
        return {
            'thumb_pixmap': thumb_pixmap,
            'runner_pixmap': runner_pixmap,
            'shoes_data': shoes_data
        }
    
    def _apply_cached_components(self, cache_key: str, is_checked: bool):
        """Apply cached components to UI."""
        components = self._component_cache[cache_key]
        self._apply_components(components, is_checked)
    
    def _apply_components(self, components: Dict[str, Any], is_checked: bool):
        """Apply components to UI quickly."""
        # Thumbnail
        self.thumb_label.setPixmap(components['thumb_pixmap'])
        self.thumb_label.setStyleSheet(self._get_style(is_checked))
        
        # Runner
        self.runner_label.setPixmap(components['runner_pixmap'])
        self.runner_label.setStyleSheet("")
        
        # Shoes - reuse widgets when possible
        self._display_shoes_fast(components['shoes_data'])
    
    def _display_shoes_fast(self, shoes_data: List[Dict[str, Any]]):
        """Display shoes with widget reuse for speed."""
        # Show/hide existing widgets as needed
        existing_widgets = []
        for i in range(self.shoe_layout.count()):
            item = self.shoe_layout.itemAt(i)
            if item and item.widget():
                existing_widgets.append(item.widget())
        
        # Use existing widgets where possible
        for i, shoe_data in enumerate(shoes_data):
            if i < len(existing_widgets):
                # Reuse existing widget
                widget = existing_widgets[i]
                widget.show()
                
                # Update content
                layout = widget.layout()
                if layout and layout.count() > 0:
                    # Update brand label if exists
                    if layout.count() > 0:
                        brand_widget = layout.itemAt(0).widget()
                        if isinstance(brand_widget, QLabel):
                            brand_widget.setText(shoe_data['brand'])
                    
                    # Update shoe image
                    if layout.count() > 1:
                        shoe_widget = layout.itemAt(1).widget()
                        if hasattr(shoe_widget, 'setPixmap'):
                            shoe_widget.setPixmap(shoe_data['pixmap'])
                            shoe_widget.shoe_index = shoe_data['index']
            else:
                # Create new widget
                self._create_new_shoe_widget(shoe_data)
        
        # Hide unused widgets
        for i in range(len(shoes_data), len(existing_widgets)):
            existing_widgets[i].hide()
    
    def _create_new_shoe_widget(self, shoe_data: Dict[str, Any]):
        """Create new shoe widget."""
        shoe_widget = QWidget()
        shoe_layout = QVBoxLayout(shoe_widget)
        shoe_layout.setContentsMargins(2, 2, 2, 2)
        shoe_layout.setSpacing(2)
        
        # Brand label
        if shoe_data['brand']:
            brand_lbl = QLabel(shoe_data['brand'])
            brand_lbl.setStyleSheet("font-size: 10px; color: #666; font-weight: bold;")
            brand_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
            shoe_layout.addWidget(brand_lbl)
        
        # Shoe image
        lbl = ClickableLabel(shoe_index=shoe_data['index'], callback=self.shoe_click_callback)
        lbl.setPixmap(shoe_data['pixmap'])
        lbl.setStyleSheet("border: 1px solid #ddd; border-radius: 2px; padding: 1px;")
        lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        
        shoe_layout.addWidget(lbl)
        shoe_layout.addStretch()
        
        shoe_widget.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Expanding)
        self.shoe_layout.addWidget(shoe_widget)
    
    def _show_error_state(self):
        """Show error state."""
        self.thumb_label.setText("Erro")
        self.thumb_label.setStyleSheet("border: 2px solid red; background-color: #ffe6e6;")
        self.runner_label.setText("Erro")
    
    def preload_images(self, data_items: List[Dict[str, Any]], base_path: str):
        """Preload images for faster navigation."""
        paths = []
        for item in data_items[:10]:  # Preload next 10 images
            img_filename = item.get("filename") or item.get("image_path", "")
            if img_filename:
                paths.append(os.path.join(base_path, img_filename))
        
        if paths:
            self._lazy_cache.preload(paths, priority=5)


# Keep old class for compatibility
ImageDisplayManager = FastImageDisplayManager
