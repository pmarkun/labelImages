"""
Hybrid image display - displays images from the enrich_run_data.py format.

Expected data format:
- Data items are participants with runners_found array
- Structure: {bib_number, name, position, time, gender, category, run_name, run_category, runners_found: [{image_path, shoes, person_bbox, bib, ...}]}
"""
import os
from typing import List, Dict, Any, Optional
from PIL import Image
from PyQt5.QtCore import Qt, QTimer
from PyQt5.QtWidgets import QLabel, QVBoxLayout, QWidget, QMessageBox, QSizePolicy
from .widgets import ClickableLabel
from utils.image_utils import crop_image, pil_to_qpixmap, draw_bounding_boxes
from utils.lazy_image_loader import get_lazy_cache

class ImageDisplayManager:
    """Best of both worlds - fast performance with proper zoom."""
    
    def __init__(self, thumb_label: QLabel, runner_label: QLabel, 
                 shoe_container: QWidget, shoe_layout: QVBoxLayout):
        self.thumb_label = thumb_label
        self.runner_label = runner_label
        self.shoe_container = shoe_container
        self.shoe_layout = shoe_layout
        self.shoe_click_callback = None
        
        # Smart caching system
        self._zoom_cache = {}  # Caches zoomed components
        self._size_dependent_cache = {}  # Invalidated on resize
        
        # Lazy cache
        self._lazy_cache = get_lazy_cache()
        
        # Current state
        self._current_img_path = None
        self._current_data_item = None
        self._last_container_sizes = None
        
        # Performance tracking
        self._cache_hits = 0
        self._cache_misses = 0
    
    def clear_cache(self):
        """Clear all caches."""
        self._zoom_cache.clear()
        self._size_dependent_cache.clear()
        self._cache_hits = 0
        self._cache_misses = 0
    
    def set_shoe_click_callback(self, callback) -> None:
        """Set the callback for shoe clicks."""
        self.shoe_click_callback = callback
    
    def display_image(self, data_item: Dict[str, Any], base_path: str) -> None:
        """Display image from enrich_run_data.py format."""
        if not data_item:
            return
        
        # Get the first runner from runners_found
        runners_found = data_item.get("runners_found", [])
        if not runners_found:
            self._display_no_runners_message()
            return
        
        runner_data = runners_found[0]  # Display first runner
        
        # Get image path 
        img_filename = runner_data.get("image_path", "")
        
        # Check if we have a valid filename
        if not img_filename:
            self._display_no_image_message()
            return
            
        img_path = os.path.join(base_path, img_filename)
        
        # Store current request
        self._current_img_path = img_path
        self._current_data_item = runner_data
        self._original_data_item = data_item  # Store original for checked status
        
        # Check if container sizes changed (invalidate size-dependent cache)
        current_sizes = self._get_current_sizes()
        if current_sizes != self._last_container_sizes:
            self._size_dependent_cache.clear()
            self._last_container_sizes = current_sizes
        
        # Check for cached components
        cache_key = self._get_smart_cache_key(img_path, runner_data, current_sizes)
        if cache_key in self._zoom_cache:
            self._cache_hits += 1
            self._apply_cached_components(cache_key, data_item.get('checked', False))
            return
        
        # Show loading state
        self._show_loading_state(data_item.get('checked', False))
        
        # Get image with lazy loading
        img = self._lazy_cache.get_image(
            img_path,
            callback=self._on_image_ready,
            priority=0
        )
        
        if img is not None:
            # Image available immediately
            self._cache_misses += 1
            self._process_and_display_with_zoom(img, runner_data, img_path, current_sizes)
    
    def _get_current_sizes(self) -> Dict[str, int]:
        """Get current container sizes."""
        return {
            'thumb_width': 150,  # Fixed for consistency
            'runner_width': max(self.runner_label.width(), 400),
            'runner_height': max(self.runner_label.height(), 600),
            'shoe_container_height': max(self.shoe_container.height(), 400),
            'shoe_container_width': 270
        }
    
    def _get_smart_cache_key(self, img_path: str, runner_data: Dict[str, Any], sizes: Dict[str, int]) -> str:
        """Generate intelligent cache key."""
        # Only include size-affecting elements in cache key
        relevant_data = {
            'path': img_path,
            'bib': runner_data.get('bib', {}),
            'shoes': runner_data.get('shoes', []),
            'bbox': runner_data.get('person_bbox'),
            'sizes': sizes
        }
        return str(hash(str(relevant_data)))
    
    def _show_loading_state(self, is_checked: bool):
        """Show loading with proper styling."""
        style = self._get_style(is_checked)
        self.thumb_label.setStyleSheet(style)
        self.runner_label.setStyleSheet("background-color: #f8f8f8;")
        self._clear_shoes_efficiently()
    
    def _get_style(self, is_checked: bool) -> str:
        """Get style for checked/unchecked state."""
        if is_checked:
            return "border: 4px solid #28a745; border-radius: 8px; padding: 16px; background-color: #d4edda;"
        else:
            return "border: 2px dashed #ddd; border-radius: 8px; padding: 20px; background-color: #f8f9fa;"
    
    def _clear_shoes_efficiently(self):
        """Efficiently clear shoes by hiding instead of deleting."""
        for i in range(self.shoe_layout.count()):
            item = self.shoe_layout.itemAt(i)
            if item and item.widget():
                widget = item.widget()
                if widget:
                    widget.hide()
    
    def _on_image_ready(self, img_path: str, img: Optional[Image.Image]):
        """Callback when image is loaded."""
        if (img is None or img_path != self._current_img_path or 
            self._current_data_item is None):
            return
        
        current_sizes = self._get_current_sizes()
        self._process_and_display_with_zoom(img, self._current_data_item, img_path, current_sizes)
    
    def _process_and_display_with_zoom(self, img: Image.Image, runner_data: Dict[str, Any], 
                                     img_path: str, sizes: Dict[str, int]):
        """Process image with proper zoom calculations."""
        try:
            cache_key = self._get_smart_cache_key(img_path, runner_data, sizes)
            
            # Create components with proper zoom
            components = self._create_components_with_optimal_zoom(img, runner_data, sizes)
            
            # Cache the results (limit cache size for memory management)
            if len(self._zoom_cache) < 25:
                self._zoom_cache[cache_key] = components
            elif len(self._zoom_cache) >= 50:
                # Clear oldest entries when cache gets too large
                keys_to_remove = list(self._zoom_cache.keys())[:10]
                for key in keys_to_remove:
                    del self._zoom_cache[key]
                self._zoom_cache[cache_key] = components
            
            # Apply to UI - get checked status from original data_item if available
            is_checked = getattr(self, '_original_data_item', {}).get('checked', False)
            self._apply_components(components, is_checked)
            
        except Exception as e:
            print(f"Error processing {img_path}: {e}")
            self._show_error_state()
    
    def _create_components_with_optimal_zoom(self, img: Image.Image, runner_data: Dict[str, Any], 
                                           sizes: Dict[str, int]) -> Dict[str, Any]:
        """Create components with optimal zoom - balance of quality and performance."""
        
        # Use cached bounding box drawing
        img_with_boxes = draw_bounding_boxes(img, runner_data)
        
        # Thumbnail - high quality but fixed size
        thumb_target_width = sizes['thumb_width']
        thumb_height = int(thumb_target_width * img.height / img.width)
        thumb_img = img_with_boxes.resize((thumb_target_width, thumb_height), Image.Resampling.LANCZOS)
        thumb_pixmap = pil_to_qpixmap(thumb_img)
        
        # Runner - smart zoom with quality
        runner_pixmap = self._create_runner_with_smart_zoom(img_with_boxes, runner_data, sizes)
        
        # Shoes - optimal zoom for container
        shoes_data = self._create_shoes_with_optimal_zoom(img, runner_data, sizes)
        
        return {
            'thumb_pixmap': thumb_pixmap,
            'runner_pixmap': runner_pixmap,
            'shoes_data': shoes_data
        }
    
    def _create_runner_with_smart_zoom(self, img_with_boxes: Image.Image, 
                                     runner_data: Dict[str, Any], sizes: Dict[str, int]):
        """Create runner with smart zoom calculation."""
        bbox = runner_data.get("person_bbox", [0, 0, img_with_boxes.width, img_with_boxes.height])
        runner_crop = crop_image(img_with_boxes, bbox)
        
        target_width = sizes['runner_width']
        target_height = sizes['runner_height']
        
        # Advanced zoom calculation
        if runner_crop.width > 0 and runner_crop.height > 0:
            # Calculate scale to fill available space efficiently
            scale_x = (target_width * 0.9) / runner_crop.width
            scale_y = (target_height * 0.9) / runner_crop.height
            
            # Use the smaller scale to ensure it fits, but allow reasonable zoom
            scale = min(scale_x, scale_y)
            
            # Apply zoom limits
            scale = min(scale, 3.5)  # Max 3.5x zoom
            scale = max(scale, 0.3)  # Min 0.3x to keep readable
            
            # Calculate final dimensions
            final_width = max(int(runner_crop.width * scale), 100)
            final_height = max(int(runner_crop.height * scale), 100)
            
            # Use high quality resize
            runner_img = runner_crop.resize((final_width, final_height), Image.Resampling.LANCZOS)
            
        else:
            runner_img = runner_crop
        
        return pil_to_qpixmap(runner_img)
    
    def _create_shoes_with_optimal_zoom(self, img: Image.Image, runner_data: Dict[str, Any], 
                                      sizes: Dict[str, int]) -> List[Dict[str, Any]]:
        """Create shoes with optimal zoom for container."""
        shoes_data = []
        shoes = runner_data.get("shoes", [])
        
        if not shoes:
            return shoes_data
        
        # Calculate space per shoe
        container_height = sizes['shoe_container_height']
        container_width = sizes['shoe_container_width']
        num_shoes = len(shoes)
        
        # Reserve space for labels and margins
        label_height = 20
        margin_per_shoe = 15
        total_reserved = num_shoes * (label_height + margin_per_shoe) + 40
        
        available_height_per_shoe = max((container_height - total_reserved) / num_shoes, 80)
        available_width = container_width - 25
        
        for shoe_index, shoe in enumerate(shoes):
            shoe_bbox = shoe.get("bbox")
            if shoe_bbox and len(shoe_bbox) >= 4:
                try:
                    shoe_crop = crop_image(img, shoe_bbox)
                    
                    if shoe_crop.width > 0 and shoe_crop.height > 0:
                        # Smart shoe scaling
                        height_scale = available_height_per_shoe / shoe_crop.height
                        width_scale = available_width / shoe_crop.width
                        
                        # Choose scale that fits well
                        shoe_scale = min(height_scale, width_scale)
                        
                        # Apply reasonable limits for shoes
                        shoe_scale = min(shoe_scale, 5.0)  # Max 5x for small shoes
                        shoe_scale = max(shoe_scale, 0.4)  # Min scale
                        
                        new_width = max(int(shoe_crop.width * shoe_scale), 80)
                        new_height = max(int(shoe_crop.height * shoe_scale), 60)
                        
                        # High quality resize for shoes
                        shoe_img = shoe_crop.resize((new_width, new_height), Image.Resampling.LANCZOS)
                        shoe_pixmap = pil_to_qpixmap(shoe_img)
                        
                        # Get brand with priority: classification_label > new_label > label
                        brand = (shoe.get("classification_label") or 
                                shoe.get("new_label") or 
                                shoe.get("label", ""))
                        
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
        components = self._zoom_cache[cache_key]
        self._apply_components(components, is_checked)
    
    def _apply_components(self, components: Dict[str, Any], is_checked: bool):
        """Apply components to UI."""
        # Thumbnail
        self.thumb_label.setPixmap(components['thumb_pixmap'])
        self.thumb_label.setStyleSheet(self._get_style(is_checked))
        
        # Runner
        self.runner_label.setPixmap(components['runner_pixmap'])
        self.runner_label.setStyleSheet("")
        
        # Shoes
        self._display_shoes_with_reuse(components['shoes_data'])
    
    def _display_shoes_with_reuse(self, shoes_data: List[Dict[str, Any]]):
        """Display shoes with widget reuse for efficiency."""
        # Get existing widgets
        existing_widgets = []
        for i in range(self.shoe_layout.count()):
            item = self.shoe_layout.itemAt(i)
            if item and item.widget():
                existing_widgets.append(item.widget())
        
        # Reuse or create widgets
        for i, shoe_data in enumerate(shoes_data):
            if i < len(existing_widgets):
                # Reuse existing widget
                self._update_shoe_widget(existing_widgets[i], shoe_data)
                existing_widgets[i].show()
            else:
                # Create new widget
                self._create_new_shoe_widget(shoe_data)
        
        # Hide unused widgets
        for i in range(len(shoes_data), len(existing_widgets)):
            existing_widgets[i].hide()
    
    def _update_shoe_widget(self, widget: QWidget, shoe_data: Dict[str, Any]):
        """Update existing shoe widget with new data."""
        layout = widget.layout()
        if layout and layout.count() > 0:
            # Update brand label
            if layout.count() > 0:
                brand_item = layout.itemAt(0)
                if brand_item:
                    brand_widget = brand_item.widget()
                    if isinstance(brand_widget, QLabel) and shoe_data['brand']:
                        brand_widget.setText(shoe_data['brand'])
            
            # Update shoe image
            if layout.count() > 1:
                shoe_item = layout.itemAt(1)
                if shoe_item:
                    shoe_label = shoe_item.widget()
                    if shoe_label and hasattr(shoe_label, 'setPixmap'):
                        shoe_label.setPixmap(shoe_data['pixmap'])
                        shoe_label.shoe_index = shoe_data['index']
    
    def _create_new_shoe_widget(self, shoe_data: Dict[str, Any]):
        """Create new shoe widget."""
        shoe_widget = QWidget()
        shoe_layout = QVBoxLayout(shoe_widget)
        shoe_layout.setContentsMargins(3, 3, 3, 3)
        shoe_layout.setSpacing(3)
        
        # Brand label
        if shoe_data['brand']:
            brand_lbl = QLabel(shoe_data['brand'])
            brand_lbl.setStyleSheet("font-size: 11px; color: #666; font-weight: bold;")
            brand_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
            shoe_layout.addWidget(brand_lbl)
        
        # Shoe image
        lbl = ClickableLabel(shoe_index=shoe_data['index'], callback=self.shoe_click_callback)
        lbl.setPixmap(shoe_data['pixmap'])
        lbl.setStyleSheet("border: 1px solid #ddd; border-radius: 4px; padding: 2px; cursor: pointer;")
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
    
    def _display_no_image_message(self):
        """Display message when no image is available."""
        self.thumb_label.setText("Sem\nImagem")
        self.thumb_label.setStyleSheet("border: 2px solid #ccc; background-color: #f5f5f5; color: #666;")
        self.runner_label.setText("Nenhuma imagem encontrada")
        self.runner_label.setStyleSheet("border: 2px solid #ccc; background-color: #f5f5f5; color: #666;")
        
        # Clear shoes container
        self._clear_shoes_efficiently()
    
    def _display_no_runners_message(self):
        """Display message when no runners are found."""
        self.thumb_label.setText("Sem\nCorredores")
        self.thumb_label.setStyleSheet("border: 2px solid #ccc; background-color: #f5f5f5; color: #666;")
        self.runner_label.setText("Nenhum corredor encontrado para este participante")
        self.runner_label.setStyleSheet("border: 2px solid #ccc; background-color: #f5f5f5; color: #666;")
        
        # Clear shoes container
        self._clear_shoes_efficiently()
    
    def preload_images(self, data_items: List[Dict[str, Any]], base_path: str):
        """Preload images for faster navigation."""
        paths = []
        for item in data_items[:8]:  # Preload 8 images
            # Get image paths from runners_found
            runners_found = item.get("runners_found", [])
            for runner in runners_found[:2]:  # Max 2 runners per participant
                img_filename = runner.get("image_path", "")
                if img_filename:
                    paths.append(os.path.join(base_path, img_filename))
        
        if paths:
            self._lazy_cache.preload(paths, priority=5)
    
    def get_cache_stats(self) -> Dict[str, Any]:
        """Get cache performance statistics."""
        total_requests = self._cache_hits + self._cache_misses
        hit_rate = (self._cache_hits / total_requests * 100) if total_requests > 0 else 0
        
        return {
            'cache_hits': self._cache_hits,
            'cache_misses': self._cache_misses,
            'hit_rate_percent': hit_rate,
            'cached_items': len(self._zoom_cache)
        }


class ExportManager:
    """Manages exporting shoe crops to training folders."""
    
    def __init__(self, data: List[Dict[str, Any]], base_path: str, output_folder: str = "train"):
        self.data = data
        self.base_path = base_path
        self.output_folder = output_folder
    
    def export_shoes_for_bib(self, bib_number: str) -> int:
        """Export all shoes for participants with the same bib number."""
        if not bib_number:
            print("No bib number provided")
            return 0
        
        exported_count = 0
        
        for idx, item in enumerate(self.data):
            # Check bib_number at participant level
            item_bib_number = item.get("bib_number", "")
            if item_bib_number != bib_number:
                continue
            
            # Process all runners for this participant
            runners = item.get("runners_found", [])
            for runner_idx, runner in enumerate(runners):
                exported_count += self._export_runner_shoes(
                    runner, idx, runner_idx, item_bib_number
                )
        
        print(f"Exported {exported_count} shoe crops for bib number {bib_number}")
        return exported_count
    
    def _export_runner_shoes(self, runner_data: Dict[str, Any], item_idx: int, 
                           runner_idx: int, bib_number: str) -> int:
        """Export shoes from a single runner."""
        exported_count = 0
        
        # Get the original image path
        img_filename = runner_data.get("image_path", "")
        if not img_filename:
            print(f"No image filename found for item {item_idx}, runner {runner_idx}")
            return 0
        
        img_path = os.path.join(self.base_path, img_filename)
        if not os.path.exists(img_path):
            print(f"Original image not found: {img_path}")
            return 0
        
        try:
            img = Image.open(img_path)
        except Exception as e:
            print(f"Error opening image {img_path}: {e}")
            return 0
        
        # Process each shoe in this runner
        shoes = runner_data.get("shoes", [])
        for i, shoe in enumerate(shoes):
            try:
                # Get the brand/label for this shoe
                brand = (shoe.get("classification_label") or 
                        shoe.get("new_label") or 
                        shoe.get("label", ""))
                if not brand:
                    print(f"No brand found for shoe {i} in item {item_idx}, runner {runner_idx}")
                    continue
                
                # Get the bounding box
                shoe_bbox = shoe.get("bbox")
                if not shoe_bbox or len(shoe_bbox) < 4:
                    print(f"No valid bbox found for shoe {i} in item {item_idx}, runner {runner_idx}")
                    continue
                
                # Crop the shoe
                shoe_crop = crop_image(img, shoe_bbox)
                
                # Create output directory
                brand_dir = os.path.join(self.output_folder, brand)
                os.makedirs(brand_dir, exist_ok=True)
                
                # Generate output filename
                base_name = os.path.splitext(os.path.basename(img_filename))[0]
                shoe_filename = f"crop_{base_name}_item{item_idx}_runner{runner_idx}_shoe_{i}.jpg"
                output_path = os.path.join(brand_dir, shoe_filename)
                
                # Save the cropped shoe
                shoe_crop.save(output_path, "JPEG", quality=95)
                print(f"Exported shoe crop: {output_path}")
                exported_count += 1
                
            except Exception as e:
                print(f"Error exporting shoe {i} from item {item_idx}, runner {runner_idx}: {e}")
        
        return exported_count
    
    def on_shoe_click(self, event, shoe_index: int, current_item: Dict[str, Any], 
                      current_index: int, save_state_callback, mark_unsaved_callback, 
                      refresh_display_callback) -> None:
        """Handle clicking on a shoe image to remove it."""
        if not current_item:
            return
        
        # Get the first runner from runners_found
        runners_found = current_item.get("runners_found", [])
        if not runners_found:
            return
        
        runner_data = runners_found[0]
        shoes = runner_data.get("shoes", [])
        if shoe_index >= len(shoes):
            return
        
        shoe = shoes[shoe_index]
        brand = (shoe.get("classification_label") or 
                shoe.get("new_label") or 
                shoe.get("label", "Unknown"))
        
        # Show confirmation dialog
        reply = QMessageBox.question(
            None,
            'Remove Shoe',
            f'Are you sure you want to remove this {brand} shoe from the image?',
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No
        )
        
        if reply == QMessageBox.Yes:
            # Save state for undo
            save_state_callback()
            
            # Remove the shoe from the data
            shoes.pop(shoe_index)
            runner_data["shoes"] = shoes
            
            # Mark as having unsaved changes
            mark_unsaved_callback()
            
            # Refresh the display
            refresh_display_callback()
