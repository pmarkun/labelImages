"""
Image display and management for the Runner Viewer application.
"""
import os
from typing import List, Dict, Any
from PIL import Image
from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import QLabel, QVBoxLayout, QWidget, QMessageBox, QSizePolicy
from .widgets import ClickableLabel
from utils.image_utils import crop_image, pil_to_qpixmap, draw_bounding_boxes


class ImageDisplayManager:
    """Manages image display in the center panel."""
    
    def __init__(self, thumb_label: QLabel, runner_label: QLabel, 
                 shoe_container: QWidget, shoe_layout: QVBoxLayout):
        self.thumb_label = thumb_label
        self.runner_label = runner_label
        self.shoe_container = shoe_container
        self.shoe_layout = shoe_layout
        self.shoe_click_callback = None
    
    def set_shoe_click_callback(self, callback) -> None:
        """Set the callback for shoe clicks."""
        self.shoe_click_callback = callback
    
    def display_image(self, data_item: Dict[str, Any], base_path: str) -> None:
        """Display an image with all its components."""
        if not data_item:
            return
        
        # Check if image is checked
        is_checked = data_item.get('checked', False)
        
        # Get image path
        img_filename = data_item.get("filename") or data_item.get("image_path", "")
        img_path = os.path.join(base_path, img_filename)
        
        try:
            img = Image.open(img_path)
        except Exception:
            print("Imagem não encontrada")
            return
        
        # Display thumbnail
        self._display_thumbnail(img, is_checked, data_item)
        
        # Display runner crop
        self._display_runner(img, data_item)
        
        # Display shoes
        self._display_shoes(img, data_item)
    
    def _display_thumbnail(self, img: Image.Image, is_checked: bool, data_item: Dict[str, Any]) -> None:
        """Display the thumbnail image with bounding boxes."""
        # Draw bounding boxes on the image
        img_with_boxes = draw_bounding_boxes(img, data_item)
        
        # Resize for thumbnail
        thumb_img = img_with_boxes.resize((150, int(150 * img_with_boxes.height / img_with_boxes.width)))
        thumb_pixmap = pil_to_qpixmap(thumb_img)
        
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
    
    def _display_runner(self, img: Image.Image, data_item: Dict[str, Any]) -> None:
        """Display the runner crop with bounding boxes."""
        # Draw bounding boxes on the full image first
        img_with_boxes = draw_bounding_boxes(img, data_item)
        
        # Then crop the runner area
        bbox = data_item.get("bbox") or data_item.get("person_bbox", [0, 0, img.width, img.height])
        runner = crop_image(img_with_boxes, bbox)
        
        # Calculate proportional resize
        target_width, target_height = self.runner_label.width(), self.runner_label.height()
        width_ratio = target_width / runner.width * 0.95
        height_ratio = target_height / runner.height * 0.95
        scale_ratio = min(width_ratio, height_ratio)
        
        runner_img = runner.resize((int(runner.width * scale_ratio), int(runner.height * scale_ratio)))
        runner_pixmap = pil_to_qpixmap(runner_img)
        self.runner_label.setPixmap(runner_pixmap)
    
    def _display_shoes(self, img: Image.Image, data_item: Dict[str, Any]) -> None:
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
                    crop = crop_image(img, shoe_bbox)
                    
                    # Calculate scaling
                    height_ratio = available_height_per_shoe / crop.height if crop.height > 0 else 1
                    width_ratio = available_width / crop.width if crop.width > 0 else 1
                    shoe_ratio = min(height_ratio, width_ratio, 2.0)
                    shoe_ratio = max(shoe_ratio, 0.2)
                    shoe_ratio = min(shoe_ratio, 3.0)
                    
                    new_width = max(int(crop.width * shoe_ratio), 60)
                    new_height = max(int(crop.height * shoe_ratio), 40)
                    
                    shoe_img = crop.resize((new_width, new_height))
                    shoe_pixmap = pil_to_qpixmap(shoe_img)
                    
                    # Create shoe widget container
                    shoe_widget = QWidget()
                    shoe_layout = QVBoxLayout(shoe_widget)
                    shoe_layout.setContentsMargins(5, 5, 5, 5)
                    
                    # Add brand label
                    brand = shoe.get("new_label") or shoe.get("label") or shoe.get("classification_label", "")
                    if brand:
                        brand_lbl = QLabel(brand)
                        brand_lbl.setStyleSheet("font-size: 11px; color: #666; font-weight: bold;")
                        brand_lbl.setAlignment(Qt.AlignCenter)
                        shoe_layout.addWidget(brand_lbl)
                    
                    # Create clickable shoe label
                    lbl = ClickableLabel(shoe_index=shoe_index, callback=self.shoe_click_callback)
                    lbl.setPixmap(shoe_pixmap)
                    lbl.setStyleSheet("border: 1px solid #ddd; border-radius: 4px; padding: 2px; cursor: pointer;")
                    lbl.setAlignment(Qt.AlignCenter)
                    
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
