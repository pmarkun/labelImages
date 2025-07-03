"""
Export dialog for the Runner Viewer application.
"""
import os
from typing import List, Dict, Any, Optional
from PyQt5.QtCore import Qt, QThread, pyqtSignal
from PyQt5.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QGridLayout, QLabel, QPushButton,
    QCheckBox, QSlider, QGroupBox, QProgressBar, QTextEdit, QFileDialog,
    QMessageBox, QComboBox, QSpinBox
)
from PyQt5.QtGui import QFont


class ExportWorker(QThread):
    """Worker thread for export operations."""
    
    progress = pyqtSignal(int)  # Progress percentage
    message = pyqtSignal(str)   # Status message
    finished = pyqtSignal(int)  # Total exported count
    
    def __init__(self, data: List[Dict[str, Any]], base_path: str, output_path: str,
                 export_types: Dict[str, bool], only_checked: bool, confidence_values: Dict[str, float]):
        super().__init__()
        self.data = data
        self.base_path = base_path
        self.output_path = output_path
        self.export_types = export_types
        self.only_checked = only_checked
        self.confidence_values = confidence_values
        self.total_exported = 0
    
    def run(self):
        """Run the export process."""
        try:
            self.message.emit("Iniciando exportação...")
            
            # Filter data if only checked items should be exported
            data_to_process = []
            if self.only_checked:
                # In the new format, 'checked' is at participant level
                data_to_process = [item for item in self.data if item.get('checked', False)]
            else:
                data_to_process = self.data
            
            total_items = len(data_to_process)
            self.message.emit(f"Processando {total_items} participantes...")
            
            for i, item in enumerate(data_to_process):
                if self.export_types.get('shoes_classification', False):
                    self._export_shoes_classification(item, i)
                
                if self.export_types.get('shoes_yolo', False):
                    self._export_shoes_yolo(item, i)
                
                if self.export_types.get('chest_plate_yolo', False):
                    self._export_chest_plate_yolo(item, i)
                
                # Update progress
                progress = int((i + 1) * 100 / total_items)
                self.progress.emit(progress)
            
            self.message.emit(f"Exportação concluída! {self.total_exported} arquivos exportados.")
            self.finished.emit(self.total_exported)
            
        except Exception as e:
            self.message.emit(f"Erro durante exportação: {str(e)}")
            self.finished.emit(0)
    
    def _export_shoes_classification(self, item: Dict[str, Any], item_index: int):
        """Export shoes for classification (crop images by brand)."""
        try:
            from PIL import Image
            from utils.image_utils import crop_image
            
            # Get runners from the new format
            runners_found = item.get("runners_found", [])
            if not runners_found:
                return
            
            # Process each runner
            for runner_index, runner in enumerate(runners_found):
                img_filename = runner.get("image_path", "")
                if not img_filename:
                    continue
                
                img_path = os.path.join(self.base_path, img_filename)
                if not os.path.exists(img_path):
                    continue
                
                img = Image.open(img_path)
                shoes = runner.get("shoes", [])
                
                for shoe_index, shoe in enumerate(shoes):
                    # Check confidence threshold
                    confidence = shoe.get("confidence", 1.0)
                    if confidence < self.confidence_values.get('shoes', 0.5):
                        continue
                    
                    # Get brand with priority: classification_label > new_label > label
                    brand = (shoe.get("classification_label") or 
                            shoe.get("new_label") or 
                            shoe.get("label", ""))
                    if not brand:
                        continue
                    
                    shoe_bbox = shoe.get("bbox")
                    if not shoe_bbox or len(shoe_bbox) < 4:
                        continue
                    
                    # Crop and save
                    shoe_crop = crop_image(img, shoe_bbox)
                    brand_dir = os.path.join(self.output_path, "shoes_classification", brand)
                    os.makedirs(brand_dir, exist_ok=True)
                    
                    base_name = os.path.splitext(os.path.basename(img_filename))[0]
                    shoe_filename = f"crop_{base_name}_item{item_index}_runner{runner_index}_shoe_{shoe_index}.jpg"
                    output_file = os.path.join(brand_dir, shoe_filename)
                    
                    shoe_crop.save(output_file, "JPEG", quality=95)
                    self.total_exported += 1
                
        except Exception as e:
            self.message.emit(f"Erro exportando sapatos classificação: {str(e)}")
    
    def _export_shoes_yolo(self, item: Dict[str, Any], item_index: int):
        """Export shoes in YOLO format."""
        try:
            # Get runners from the new format
            runners_found = item.get("runners_found", [])
            if not runners_found:
                return
            
            # Process each runner
            for runner_index, runner in enumerate(runners_found):
                img_filename = runner.get("image_path", "")
                if not img_filename:
                    continue
                
                shoes = runner.get("shoes", [])
                valid_shoes = []
                
                for shoe in shoes:
                    confidence = shoe.get("confidence", 1.0)
                    if confidence >= self.confidence_values.get('shoes', 0.5):
                        valid_shoes.append(shoe)
                
                if not valid_shoes:
                    continue
                
                # Create YOLO format directories
                images_dir = os.path.join(self.output_path, "shoes_yolo", "images")
                labels_dir = os.path.join(self.output_path, "shoes_yolo", "labels")
                os.makedirs(images_dir, exist_ok=True)
                os.makedirs(labels_dir, exist_ok=True)
                
                # Copy image
                img_src = os.path.join(self.base_path, img_filename)
                if os.path.exists(img_src):
                    import shutil
                    base_name = os.path.splitext(os.path.basename(img_filename))[0]
                    # Include runner index to avoid filename conflicts
                    img_dst = os.path.join(images_dir, f"{base_name}_runner{runner_index}.jpg")
                    shutil.copy2(img_src, img_dst)
                    
                    # Create label file
                    label_file = os.path.join(labels_dir, f"{base_name}_runner{runner_index}.txt")
                    with open(label_file, 'w') as f:
                        for shoe in valid_shoes:
                            bbox = shoe.get("bbox")
                            if bbox and len(bbox) >= 4:
                                # Get image dimensions from runner or estimate
                                img_width = runner.get("image_width")
                                img_height = runner.get("image_height")
                                
                                # If dimensions not available, read from image
                                if not img_width or not img_height:
                                    from PIL import Image
                                    with Image.open(img_src) as img:
                                        img_width, img_height = img.size
                                
                                # Convert to YOLO format (normalized coordinates)
                                x, y, w, h = bbox
                                center_x = (x + w/2) / img_width
                                center_y = (y + h/2) / img_height
                                norm_w = w / img_width
                                norm_h = h / img_height
                                
                                # Class 0 for shoes
                                f.write(f"0 {center_x:.6f} {center_y:.6f} {norm_w:.6f} {norm_h:.6f}\n")
                    
                    self.total_exported += 1
                
        except Exception as e:
            self.message.emit(f"Erro exportando sapatos YOLO: {str(e)}")
    
    def _export_chest_plate_yolo(self, item: Dict[str, Any], item_index: int):
        """Export chest plates in YOLO format."""
        try:
            # Get runners from the new format
            runners_found = item.get("runners_found", [])
            if not runners_found:
                return
            
            # Process each runner
            for runner_index, runner in enumerate(runners_found):
                img_filename = runner.get("image_path", "")
                if not img_filename:
                    continue
                
                # Look for chest plate detection in this runner
                chest_plate = runner.get("chest_plate")
                if not chest_plate:
                    continue
                
                confidence = chest_plate.get("confidence", 1.0)
                if confidence < self.confidence_values.get('chest_plate', 0.5):
                    continue
                
                bbox = chest_plate.get("bbox")
                if not bbox or len(bbox) < 4:
                    continue
                
                # Create YOLO format directories
                images_dir = os.path.join(self.output_path, "chest_plate_yolo", "images")
                labels_dir = os.path.join(self.output_path, "chest_plate_yolo", "labels")
                os.makedirs(images_dir, exist_ok=True)
                os.makedirs(labels_dir, exist_ok=True)
                
                # Copy image
                img_src = os.path.join(self.base_path, img_filename)
                if os.path.exists(img_src):
                    import shutil
                    base_name = os.path.splitext(os.path.basename(img_filename))[0]
                    # Include runner index to avoid filename conflicts
                    img_dst = os.path.join(images_dir, f"{base_name}_runner{runner_index}.jpg")
                    shutil.copy2(img_src, img_dst)
                    
                    # Create label file
                    label_file = os.path.join(labels_dir, f"{base_name}_runner{runner_index}.txt")
                    with open(label_file, 'w') as f:
                        # Get image dimensions from runner or read from image
                        img_width = runner.get("image_width")
                        img_height = runner.get("image_height")
                        
                        # If dimensions not available, read from image
                        if not img_width or not img_height:
                            from PIL import Image
                            with Image.open(img_src) as img:
                                img_width, img_height = img.size
                        
                        # Convert to YOLO format
                        x, y, w, h = bbox
                        center_x = (x + w/2) / img_width
                        center_y = (y + h/2) / img_height
                        norm_w = w / img_width
                        norm_h = h / img_height
                        
                        # Class 0 for chest plate
                        f.write(f"0 {center_x:.6f} {center_y:.6f} {norm_w:.6f} {norm_h:.6f}\n")
                    
                    self.total_exported += 1
                
        except Exception as e:
            self.message.emit(f"Erro exportando placa de peito YOLO: {str(e)}")


class ExportDialog(QDialog):
    """Dialog for configuring and running exports."""
    
    def __init__(self, data: List[Dict[str, Any]], base_path: str, parent=None):
        super().__init__(parent)
        self.data = data
        self.base_path = base_path
        self.worker = None
        
        self.setWindowTitle("Exportar Dados")
        self.setModal(True)
        self.resize(500, 600)
        
        self._setup_ui()
        self._connect_signals()
    
    def _setup_ui(self):
        """Setup the user interface."""
        layout = QVBoxLayout(self)
        
        # Export types group
        export_group = QGroupBox("Tipos de Exportação")
        export_layout = QVBoxLayout(export_group)
        
        self.shoes_classification_cb = QCheckBox("Sapatos (Classificação)")
        self.shoes_classification_cb.setToolTip("Exporta crops dos sapatos organizados por marca")
        self.shoes_yolo_cb = QCheckBox("Sapatos (YOLO)")
        self.shoes_yolo_cb.setToolTip("Exporta dataset YOLO para detecção de sapatos")
        self.chest_plate_yolo_cb = QCheckBox("Placa de Peito (YOLO)")
        self.chest_plate_yolo_cb.setToolTip("Exporta dataset YOLO para detecção de placas de peito")
        
        export_layout.addWidget(self.shoes_classification_cb)
        export_layout.addWidget(self.shoes_yolo_cb)
        export_layout.addWidget(self.chest_plate_yolo_cb)
        
        layout.addWidget(export_group)
        
        # Filter group
        filter_group = QGroupBox("Filtros")
        filter_layout = QVBoxLayout(filter_group)
        
        self.only_checked_cb = QCheckBox("Exportar apenas imagens checadas")
        self.only_checked_cb.setToolTip("Se marcado, exporta apenas imagens marcadas como checadas")
        filter_layout.addWidget(self.only_checked_cb)
        
        layout.addWidget(filter_group)
        
        # Confidence thresholds group
        confidence_group = QGroupBox("Limites de Confiança")
        confidence_layout = QGridLayout(confidence_group)
        
        # Shoes confidence
        confidence_layout.addWidget(QLabel("Sapatos:"), 0, 0)
        self.shoes_confidence_slider = QSlider(Qt.Orientation.Horizontal)
        self.shoes_confidence_slider.setRange(0, 100)
        self.shoes_confidence_slider.setValue(50)
        self.shoes_confidence_label = QLabel("0.50")
        confidence_layout.addWidget(self.shoes_confidence_slider, 0, 1)
        confidence_layout.addWidget(self.shoes_confidence_label, 0, 2)
        
        # Chest plate confidence
        confidence_layout.addWidget(QLabel("Placa de Peito:"), 1, 0)
        self.chest_confidence_slider = QSlider(Qt.Orientation.Horizontal)
        self.chest_confidence_slider.setRange(0, 100)
        self.chest_confidence_slider.setValue(50)
        self.chest_confidence_label = QLabel("0.50")
        confidence_layout.addWidget(self.chest_confidence_slider, 1, 1)
        confidence_layout.addWidget(self.chest_confidence_label, 1, 2)
        
        layout.addWidget(confidence_group)
        
        # Output directory
        output_group = QGroupBox("Diretório de Saída")
        output_layout = QHBoxLayout(output_group)
        
        self.output_path_label = QLabel("Selecione um diretório...")
        self.output_path_button = QPushButton("Escolher...")
        
        output_layout.addWidget(self.output_path_label)
        output_layout.addWidget(self.output_path_button)
        
        layout.addWidget(output_group)
        
        # Progress area
        progress_group = QGroupBox("Progresso")
        progress_layout = QVBoxLayout(progress_group)
        
        self.progress_bar = QProgressBar()
        self.progress_bar.setVisible(False)
        
        self.status_text = QTextEdit()
        self.status_text.setMaximumHeight(100)
        self.status_text.setReadOnly(True)
        
        progress_layout.addWidget(self.progress_bar)
        progress_layout.addWidget(self.status_text)
        
        layout.addWidget(progress_group)
        
        # Buttons
        button_layout = QHBoxLayout()
        
        self.export_button = QPushButton("Exportar")
        self.export_button.setEnabled(False)
        self.cancel_button = QPushButton("Cancelar")
        
        button_layout.addStretch()
        button_layout.addWidget(self.export_button)
        button_layout.addWidget(self.cancel_button)
        
        layout.addLayout(button_layout)
    
    def _connect_signals(self):
        """Connect UI signals."""
        self.output_path_button.clicked.connect(self._select_output_path)
        self.export_button.clicked.connect(self._start_export)
        self.cancel_button.clicked.connect(self.reject)
        
        # Update confidence labels
        self.shoes_confidence_slider.valueChanged.connect(
            lambda v: self.shoes_confidence_label.setText(f"{v/100:.2f}")
        )
        self.chest_confidence_slider.valueChanged.connect(
            lambda v: self.chest_confidence_label.setText(f"{v/100:.2f}")
        )
        
        # Enable export button when output path is selected or export types change
        self.output_path_button.clicked.connect(self._check_export_ready)
        self.shoes_classification_cb.stateChanged.connect(self._check_export_ready)
        self.shoes_yolo_cb.stateChanged.connect(self._check_export_ready)
        self.chest_plate_yolo_cb.stateChanged.connect(self._check_export_ready)
    
    def _select_output_path(self):
        """Select output directory."""
        directory = QFileDialog.getExistingDirectory(
            self,
            "Selecionar Diretório de Saída",
            os.path.expanduser("~")
        )
        
        if directory:
            self.output_path_label.setText(directory)
            self._check_export_ready()
    
    def _check_export_ready(self):
        """Check if export can be started."""
        has_output_path = self.output_path_label.text() != "Selecione um diretório..."
        has_export_type = (self.shoes_classification_cb.isChecked() or 
                          self.shoes_yolo_cb.isChecked() or 
                          self.chest_plate_yolo_cb.isChecked())
        
        self.export_button.setEnabled(has_output_path and has_export_type)
        
        # Update UI feedback
        if not has_output_path:
            self.export_button.setToolTip("Selecione um diretório de saída primeiro")
        elif not has_export_type:
            self.export_button.setToolTip("Selecione pelo menos um tipo de exportação")
        else:
            self.export_button.setToolTip("Iniciar exportação")
    
    def _start_export(self):
        """Start the export process."""
        output_path = self.output_path_label.text()
        if output_path == "Selecione um diretório...":
            QMessageBox.warning(self, "Aviso", "Selecione um diretório de saída.")
            return
        
        export_types = {
            'shoes_classification': self.shoes_classification_cb.isChecked(),
            'shoes_yolo': self.shoes_yolo_cb.isChecked(),
            'chest_plate_yolo': self.chest_plate_yolo_cb.isChecked()
        }
        
        if not any(export_types.values()):
            QMessageBox.warning(self, "Aviso", "Selecione pelo menos um tipo de exportação.")
            return
        
        confidence_values = {
            'shoes': self.shoes_confidence_slider.value() / 100.0,
            'chest_plate': self.chest_confidence_slider.value() / 100.0
        }
        
        only_checked = self.only_checked_cb.isChecked()
        
        # Disable UI during export
        self.export_button.setEnabled(False)
        self.progress_bar.setVisible(True)
        self.progress_bar.setValue(0)
        
        # Start worker thread
        self.worker = ExportWorker(
            self.data, self.base_path, output_path,
            export_types, only_checked, confidence_values
        )
        
        self.worker.progress.connect(self.progress_bar.setValue)
        self.worker.message.connect(self._add_status_message)
        self.worker.finished.connect(self._export_finished)
        
        self.worker.start()
    
    def _add_status_message(self, message: str):
        """Add message to status text."""
        self.status_text.append(message)
    
    def _export_finished(self, total_exported: int):
        """Handle export completion."""
        self.progress_bar.setVisible(False)
        self.export_button.setEnabled(True)
        
        if total_exported > 0:
            QMessageBox.information(
                self, 
                "Exportação Concluída", 
                f"Exportação concluída com sucesso!\n{total_exported} arquivos exportados."
            )
        else:
            QMessageBox.warning(
                self, 
                "Exportação", 
                "Nenhum arquivo foi exportado. Verifique os filtros e configurações."
            )
