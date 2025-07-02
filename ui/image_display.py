"""
Image display and management for the Runner Viewer application.
"""
import os
from typing import List, Dict, Any, Optional
from PIL import Image
from PyQt5.QtCore import Qt, QTimer
from PyQt5.QtWidgets import QLabel, QVBoxLayout, QWidget, QMessageBox, QSizePolicy
from .widgets import ClickableLabel
from utils.image_utils import crop_image, pil_to_qpixmap, draw_bounding_boxes, load_image_cached
from utils.lazy_image_loader import get_lazy_cache


class ImageDisplayManager:
    """Manages image display in the center panel with lazy loading."""
    
    def __init__(self, thumb_label: QLabel, runner_label: QLabel, 
                 shoe_container: QWidget, shoe_layout: QVBoxLayout):
        self.thumb_label = thumb_label
        self.runner_label = runner_label
        self.shoe_container = shoe_container
        self.shoe_layout = shoe_layout
        self.shoe_click_callback = None
        
        # Cache for processed components (lighter than full images)
        self._pixmap_cache = {}  # Stores final QPixmaps
        self._pending_displays = {}  # Track pending lazy loads
        
        # Get lazy cache instance
        self._lazy_cache = get_lazy_cache()
        
        # Current display state
        self._current_data_item = None
        self._current_base_path = None
        
        # Timer for batch updates
        self._update_timer = QTimer()
        self._update_timer.setSingleShot(True)
        self._update_timer.timeout.connect(self._process_pending_updates)
        self._update_timer.setInterval(50)  # 50ms delay
    
    def clear_cache(self):
        """Clear all display caches."""
        self._pixmap_cache.clear()
        self._pending_displays.clear()
    
    def set_shoe_click_callback(self, callback) -> None:
        """Set the callback for shoe clicks."""
        self.shoe_click_callback = callback
    
    def display_image(self, data_item: Dict[str, Any], base_path: str) -> None:
        """Display an image with lazy loading."""
        if not data_item:
            return
        
        # Store current display request
        self._current_data_item = data_item
        self._current_base_path = base_path
        
        # Get image path
        img_filename = data_item.get("filename") or data_item.get("image_path", "")
        img_path = os.path.join(base_path, img_filename)
        
        # Show loading placeholder immediately
        self._show_loading_placeholder(data_item.get('checked', False))
        
        # Try to get image from lazy cache
        img = self._lazy_cache.get_image(
            img_path, 
            callback=self._on_image_loaded,
            priority=0  # High priority for current image
        )
        
        if img is not None:
            # Image already cached, display immediately
            self._display_image_components(img, data_item, img_path)
    
    def _show_loading_placeholder(self, is_checked: bool):
        """Show loading placeholder while image loads."""
        # Apply style based on checked status
        if is_checked:
            style = "border: 4px solid #28a745; border-radius: 8px; padding: 16px; background-color: #d4edda;"
        else:
            style = "border: 2px dashed #ddd; border-radius: 8px; padding: 20px; background-color: #f8f9fa;"
        
        self.thumb_label.setStyleSheet(style)
        self.thumb_label.setText("Carregando...")
        self.thumb_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        
        self.runner_label.setText("Carregando...")
        self.runner_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        
        # Clear shoes
        self._clear_shoes()
    
    def _on_image_loaded(self, img_path: str, img: Optional[Image.Image]):
        """Callback when image is loaded by lazy cache."""
        if img is None:
            self._show_error_placeholder()
            return
        
        # Check if this is still the current image request
        if (self._current_data_item and self._current_base_path):
            current_img_filename = self._current_data_item.get("filename") or self._current_data_item.get("image_path", "")
            current_img_path = os.path.join(self._current_base_path, current_img_filename)
            
            if img_path == current_img_path:
                self._display_image_components(img, self._current_data_item, img_path)
    
    def _show_error_placeholder(self):
        """Show error placeholder when image fails to load."""
        self.thumb_label.setText("Erro ao carregar")
        self.thumb_label.setStyleSheet("border: 2px solid red; border-radius: 8px; padding: 20px; background-color: #ffe6e6;")
        self.runner_label.setText("Erro ao carregar")
    
    def _display_image_components(self, img: Image.Image, data_item: Dict[str, Any], img_path: str):
        """Display all image components."""
        # Check if already processed and cached
        cache_key = f"{img_path}_{hash(str(data_item))}"
        
        if cache_key in self._pixmap_cache:
            cached_data = self._pixmap_cache[cache_key]
            self._apply_cached_display(cached_data, data_item.get('checked', False))
            return
        
        # Process in background to avoid blocking UI
        self._update_timer.start()  # Batch updates
        
        try:
            # Generate all components
            is_checked = data_item.get('checked', False)
            
            # Thumbnail
            thumb_pixmap = self._create_thumbnail(img, data_item)
            
            # Runner
            runner_pixmap = self._create_runner_crop(img, data_item)
            
            # Shoes
            shoe_widgets = self._create_shoe_widgets(img, data_item)
            
            # Cache the results
            cached_data = {
                'thumb_pixmap': thumb_pixmap,
                'runner_pixmap': runner_pixmap,
                'shoe_widgets': shoe_widgets
            }
            
            if len(self._pixmap_cache) < 50:  # Limit cache size
                self._pixmap_cache[cache_key] = cached_data
            
            # Apply to UI
            self._apply_cached_display(cached_data, is_checked)
            
        except Exception as e:
            print(f"Error processing image: {e}")
            self._show_error_placeholder()
    
    def _process_pending_updates(self):
        """Process any pending UI updates."""
        # This method can be used for batching updates if needed
        pass
    
    def _display_thumbnail(self, img: Image.Image, is_checked: bool, data_item: Dict[str, Any], img_path: Optional[str] = None) -> None:
        """Display the thumbnail image with bounding boxes."""
        # Create cache key
        cache_key = f"thumb_{img_path}_{is_checked}_{hash(str(data_item.get('bib', {})))}"
        
        if cache_key in self._thumbnail_cache:
            thumb_pixmap = self._thumbnail_cache[cache_key]
        else:
            # Draw bounding boxes on the image
            img_with_boxes = draw_bounding_boxes(img, data_item)
            
            # Resize for thumbnail
            thumb_img = img_with_boxes.resize((150, int(150 * img_with_boxes.height / img_with_boxes.width)), Image.Resampling.LANCZOS)
            thumb_pixmap = pil_to_qpixmap(thumb_img)
            
            # Cache if not too large
            if len(self._thumbnail_cache) < 10:
                self._thumbnail_cache[cache_key] = thumb_pixmap
        
        # Apply style based on checked status
        if is_checked:
            self.thumb_label.setStyleSheet(
                "border: 4px solid #28a745; border-radius: 8px; padding: 16px; background-color: #d4edda;"
            )
        else:
            self.thumb_label.setStyleSheet(
                "border: 2px dashed #ddd; border-radius: 8px; padding: 20px; background-color: #f8f9fa;"
            )
        
        self.thumb_label.setPixmap(thumb_pixmap)
    
    def _display_runner(self, img: Image.Image, data_item: Dict[str, Any], img_path: Optional[str] = None) -> None:
        """Display the runner crop with bounding boxes."""
        # Create cache key
        bbox = data_item.get("bbox") or data_item.get("person_bbox", [0, 0, img.width, img.height])
        cache_key = f"runner_{img_path}_{hash(str(bbox))}_{self.runner_label.width()}_{self.runner_label.height()}"
        
        if cache_key in self._runner_cache:
            runner_pixmap = self._runner_cache[cache_key]
        else:
            # Draw bounding boxes on the full image first
            img_with_boxes = draw_bounding_boxes(img, data_item)
            
            # Then crop the runner area
            runner = crop_image(img_with_boxes, bbox)
            
            # Calculate proportional resize
            target_width, target_height = self.runner_label.width(), self.runner_label.height()
            if target_width > 0 and target_height > 0:
                width_ratio = target_width / runner.width * 0.95
                height_ratio = target_height / runner.height * 0.95
                scale_ratio = min(width_ratio, height_ratio)
                
                runner_img = runner.resize((int(runner.width * scale_ratio), int(runner.height * scale_ratio)), Image.Resampling.LANCZOS)
                runner_pixmap = pil_to_qpixmap(runner_img)
                
                # Cache if not too large
                if len(self._runner_cache) < 10:
                    self._runner_cache[cache_key] = runner_pixmap
            else:
                runner_pixmap = pil_to_qpixmap(runner)
        
        self.runner_label.setPixmap(runner_pixmap)
    
    def _display_shoes(self, img: Image.Image, data_item: Dict[str, Any], img_path: Optional[str] = None) -> None:
        """Display all shoes from the image."""
        # Clear existing shoes
        for i in reversed(range(self.shoe_layout.count())):
            layout_item = self.shoe_layout.itemAt(i)
            if layout_item:
                w = layout_item.widget()
                if w:
                    w.deleteLater()
        
        shoes = data_item.get("shoes", [])
        num_shoes = len(shoes)
        
        if num_shoes == 0:
            return
        
        # Calculate container dimensions
        container_height = self.shoe_container.height()
        container_width = 270
        
        self.shoe_container.setMinimumHeight(container_height)
        self.shoe_container.setMaximumHeight(container_height)
        
        # Calculate available space per shoe
        label_height = 20
        widget_margins = 10
        layout_spacing = self.shoe_layout.spacing() * max(0, num_shoes - 1)
        total_reserved_height = num_shoes * (label_height + widget_margins) + layout_spacing + 30
        
        available_height_per_shoe = max((container_height - total_reserved_height) / num_shoes, 40)
        available_width = container_width - 20
        
        # Display each shoe
        for shoe_index, shoe in enumerate(shoes):
            shoe_bbox = shoe.get("bbox")
            if shoe_bbox and len(shoe_bbox) >= 4:
                try:
                    # Create cache key for this shoe
                    shoe_cache_key = f"shoe_{img_path}_{shoe_index}_{hash(str(shoe_bbox))}_{available_height_per_shoe}_{available_width}"
                    
                    if shoe_cache_key in self._shoe_cache:
                        shoe_pixmap = self._shoe_cache[shoe_cache_key]
                    else:
                        crop = crop_image(img, shoe_bbox)
                        
                        # Calculate scaling
                        height_ratio = available_height_per_shoe / crop.height if crop.height > 0 else 1
                        width_ratio = available_width / crop.width if crop.width > 0 else 1
                        shoe_ratio = min(height_ratio, width_ratio, 2.0)
                        shoe_ratio = max(shoe_ratio, 0.2)
                        shoe_ratio = min(shoe_ratio, 3.0)
                        
                        new_width = max(int(crop.width * shoe_ratio), 60)
                        new_height = max(int(crop.height * shoe_ratio), 40)
                        
                        shoe_img = crop.resize((new_width, new_height), Image.Resampling.LANCZOS)
                        shoe_pixmap = pil_to_qpixmap(shoe_img)
                        
                        # Cache if not too large
                        if len(self._shoe_cache) < 20:
                            self._shoe_cache[shoe_cache_key] = shoe_pixmap
                    
                    # Create shoe widget container
                    shoe_widget = QWidget()
                    shoe_layout = QVBoxLayout(shoe_widget)
                    shoe_layout.setContentsMargins(5, 5, 5, 5)
                    
                    # Add brand label
                    brand = shoe.get("new_label") or shoe.get("label") or shoe.get("classification_label", "")
                    if brand:
                        brand_lbl = QLabel(brand)
                        brand_lbl.setStyleSheet("font-size: 11px; color: #666; font-weight: bold;")
                        brand_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
                        shoe_layout.addWidget(brand_lbl)
                    
                    # Create clickable shoe label
                    lbl = ClickableLabel(shoe_index=shoe_index, callback=self.shoe_click_callback)
                    lbl.setPixmap(shoe_pixmap)
                    lbl.setStyleSheet("border: 1px solid #ddd; border-radius: 4px; padding: 2px; cursor: pointer;")
                    lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
                    
                    shoe_layout.addWidget(lbl)
                    shoe_layout.addStretch()
                    
                    shoe_widget.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Expanding)
                    self.shoe_layout.addWidget(shoe_widget)
                    
                except Exception as e:
                    print(f"Error processing shoe image: {e}")


class ExportManager:
    """Manages exporting shoe crops to training folders."""
    
    def __init__(self, data: List[Dict[str, Any]], base_path: str, output_folder: str = "train"):
        self.data = data
        self.base_path = base_path
        self.output_folder = output_folder
    
    def export_shoes_for_bib(self, bib_number: str) -> int:
        """Export all shoes for images with the same bib number."""
        if not bib_number:
            print("No bib number provided")
            return 0
        
        exported_count = 0
        
        for idx, item in enumerate(self.data):
            # Get bib number from this item
            item_bib_number = ""
            item_run_data = item.get("run_data", {})
            if isinstance(item_run_data, dict):
                item_bib_number = str(item_run_data.get("bib_number", ""))
            
            # Skip if not the same bib number
            if item_bib_number != bib_number:
                continue
            
            # Get the original image path
            img_filename = item.get("filename") or item.get("image_path", "")
            if not img_filename:
                print(f"No image filename found for item {idx}")
                continue
            
            img_path = os.path.join(self.base_path, img_filename)
            if not os.path.exists(img_path):
                print(f"Original image not found: {img_path}")
                continue
            
            try:
                img = Image.open(img_path)
            except Exception as e:
                print(f"Error opening image {img_path}: {e}")
                continue
            
            # Process each shoe in this image
            shoes = item.get("shoes", [])
            for i, shoe in enumerate(shoes):
                try:
                    # Get the brand/label for this shoe
                    brand = shoe.get("new_label") or shoe.get("label") or shoe.get("classification_label", "")
                    if not brand:
                        print(f"No brand found for shoe {i} in image {idx}")
                        continue
                    
                    # Get the bounding box
                    shoe_bbox = shoe.get("bbox")
                    if not shoe_bbox or len(shoe_bbox) < 4:
                        print(f"No valid bbox found for shoe {i} in image {idx}")
                        continue
                    
                    # Crop the shoe
                    shoe_crop = crop_image(img, shoe_bbox)
                    
                    # Create output directory
                    brand_dir = os.path.join(self.output_folder, brand)
                    os.makedirs(brand_dir, exist_ok=True)
                    
                    # Generate output filename
                    base_name = os.path.splitext(os.path.basename(img_filename))[0]
                    shoe_filename = f"crop_{base_name}_img{idx}_shoe_{i}.jpg"
                    output_path = os.path.join(brand_dir, shoe_filename)
                    
                    # Save the cropped shoe
                    shoe_crop.save(output_path, "JPEG", quality=95)
                    print(f"Exported shoe crop: {output_path}")
                    exported_count += 1
                    
                except Exception as e:
                    print(f"Error exporting shoe {i} from image {idx}: {e}")
        
        print(f"Exported {exported_count} shoe crops for bib number {bib_number}")
        return exported_count
    
    def on_shoe_click(self, event, shoe_index: int, current_item: Dict[str, Any], 
                      current_index: int, save_state_callback, mark_unsaved_callback, 
                      refresh_display_callback) -> None:
        """Handle clicking on a shoe image to remove it."""
        if not current_item:
            return
        
        shoes = current_item.get("shoes", [])
        if shoe_index >= len(shoes):
            return
        
        shoe = shoes[shoe_index]
        brand = shoe.get("new_label") or shoe.get("label") or shoe.get("classification_label", "Unknown")
        
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
            current_item["shoes"] = shoes
            
            # Mark as having unsaved changes
            mark_unsaved_callback()
            
            # Refresh the display
            refresh_display_callback()
