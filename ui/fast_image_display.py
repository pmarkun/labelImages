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
        """Generate cache key for components including size information."""
        # Include container sizes in cache key for proper zoom caching
        container_height = self.shoe_container.height() if self.shoe_container.height() > 0 else 400
        runner_width = self.runner_label.width() if self.runner_label.width() > 0 else 400
        runner_height = self.runner_label.height() if self.runner_label.height() > 0 else 600
        
        # Use hash of relevant data for cache key
        data_hash = hash(str({
            'bib': data_item.get('bib', {}),
            'shoes': data_item.get('shoes', []),
            'bbox': data_item.get('bbox'),
            'container_height': container_height,
            'runner_width': runner_width,
            'runner_height': runner_height
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
        """Create all components with optimal processing and proper zoom."""
        # Use cached image processing for bounding boxes
        img_with_boxes = draw_bounding_boxes(img, data_item)
        
        # Thumbnail - small but with good quality
        thumb_target_width = 150
        thumb_height = int(thumb_target_width * img.height / img.width)
        thumb_img = img_with_boxes.resize((thumb_target_width, thumb_height), Image.Resampling.LANCZOS)
        thumb_pixmap = pil_to_qpixmap(thumb_img)
        
        # Runner - with proper zoom calculation
        bbox = data_item.get("bbox") or data_item.get("person_bbox", [0, 0, img.width, img.height])
        runner_crop = crop_image(img_with_boxes, bbox)
        
        # Smart zoom calculation for runner - maintain aspect ratio and fill available space
        target_width = self.runner_label.width() if self.runner_label.width() > 0 else 400
        target_height = self.runner_label.height() if self.runner_label.height() > 0 else 600
        
        # Calculate scale to fit in available space with padding
        scale_x = (target_width * 0.95) / runner_crop.width if runner_crop.width > 0 else 1
        scale_y = (target_height * 0.95) / runner_crop.height if runner_crop.height > 0 else 1
        scale = min(scale_x, scale_y, 3.0)  # Max 3x zoom
        scale = max(scale, 0.1)  # Min scale to avoid tiny images
        
        runner_width = max(int(runner_crop.width * scale), 50)
        runner_height = max(int(runner_crop.height * scale), 50)
        
        runner_img = runner_crop.resize((runner_width, runner_height), Image.Resampling.LANCZOS)
        runner_pixmap = pil_to_qpixmap(runner_img)
        
        # Shoes - with intelligent sizing based on container
        shoes_data = self._create_shoes_with_smart_zoom(img, data_item)
        
        return {
            'thumb_pixmap': thumb_pixmap,
            'runner_pixmap': runner_pixmap,
            'shoes_data': shoes_data
        }
    
    def _create_shoes_with_smart_zoom(self, img: Image.Image, data_item: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Create shoe widgets with intelligent zoom based on container size."""
        shoes_data = []
        shoes = data_item.get("shoes", [])
        
        if not shoes:
            return shoes_data
        
        # Calculate available space per shoe
        container_height = self.shoe_container.height() if self.shoe_container.height() > 0 else 400
        container_width = 270
        
        num_shoes = len(shoes)
        label_height = 20
        widget_margins = 10
        layout_spacing = 5 * max(0, num_shoes - 1)
        total_reserved_height = num_shoes * (label_height + widget_margins) + layout_spacing + 30
        
        available_height_per_shoe = max((container_height - total_reserved_height) / num_shoes, 60)
        available_width = container_width - 20
        
        for shoe_index, shoe in enumerate(shoes):
            shoe_bbox = shoe.get("bbox")
            if shoe_bbox and len(shoe_bbox) >= 4:
                try:
                    # Create shoe crop
                    shoe_crop = crop_image(img, shoe_bbox)
                    
                    # Smart scaling for shoes
                    if shoe_crop.width > 0 and shoe_crop.height > 0:
                        # Calculate scaling to fit available space
                        height_ratio = available_height_per_shoe / shoe_crop.height
                        width_ratio = available_width / shoe_crop.width
                        shoe_scale = min(height_ratio, width_ratio, 4.0)  # Max 4x zoom for shoes
                        shoe_scale = max(shoe_scale, 0.2)  # Min scale
                        
                        new_width = max(int(shoe_crop.width * shoe_scale), 60)
                        new_height = max(int(shoe_crop.height * shoe_scale), 40)
                        
                        # Use high quality resize for shoes since they're small
                        shoe_img = shoe_crop.resize((new_width, new_height), Image.Resampling.LANCZOS)
                        shoe_pixmap = pil_to_qpixmap(shoe_img)
                        
                        brand = shoe.get("new_label") or shoe.get("label") or shoe.get("classification_label", "")
                        
                        shoes_data.append({
                            'pixmap': shoe_pixmap,
                            'brand': brand,
                            'index': shoe_index
                        })
                        
                except Exception as e:
                    print(f"Error processing shoe {shoe_index}: {e}")
        
        return shoes_data
    
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
    
    def invalidate_cache_on_resize(self):
        """Invalidate cache when container sizes change."""
        # Call this when the window is resized to recalculate zoom levels
        self._component_cache.clear()
    
    def get_zoom_info(self, data_item: Dict[str, Any]) -> Dict[str, Any]:
        """Get zoom information for debugging."""
        if not data_item:
            return {}
        
        bbox = data_item.get("bbox") or data_item.get("person_bbox", [0, 0, 100, 100])
        crop_width = bbox[2] - bbox[0] if len(bbox) >= 4 else 100
        crop_height = bbox[3] - bbox[1] if len(bbox) >= 4 else 100
        
        target_width = self.runner_label.width() if self.runner_label.width() > 0 else 400
        target_height = self.runner_label.height() if self.runner_label.height() > 0 else 600
        
        scale_x = (target_width * 0.95) / crop_width if crop_width > 0 else 1
        scale_y = (target_height * 0.95) / crop_height if crop_height > 0 else 1
        scale = min(scale_x, scale_y, 3.0)
        scale = max(scale, 0.1)
        
        return {
            'crop_size': (crop_width, crop_height),
            'target_size': (target_width, target_height),
            'scale_factor': scale,
            'final_size': (int(crop_width * scale), int(crop_height * scale))
        }
        

# Keep old class for compatibility
ImageDisplayManager = FastImageDisplayManager
