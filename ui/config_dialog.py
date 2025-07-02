"""
Configuration dialog for Runner Viewer application settings.
"""
from typing import Dict, Any
from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QDoubleSpinBox,
    QPushButton, QFormLayout, QGroupBox, QMessageBox
)


class ConfigurationDialog(QDialog):
    """Dialog for configuring application settings."""
    
    def __init__(self, current_config: Dict[str, Any], parent=None):
        super().__init__(parent)
        self.current_config = current_config
        self.new_config = current_config.copy()
        self.setup_ui()
        self.load_current_values()
    
    def setup_ui(self) -> None:
        """Setup the dialog UI."""
        self.setWindowTitle("⚙️ Configurações")
        self.setModal(True)
        self.setFixedSize(400, 250)
        
        layout = QVBoxLayout()
        
        # Create confidence thresholds group
        confidence_group = QGroupBox("Thresholds de Confiança")
        confidence_layout = QFormLayout()
        
        # Chest plate confidence threshold
        self.chest_plate_spin = QDoubleSpinBox()
        self.chest_plate_spin.setRange(0.0, 1.0)
        self.chest_plate_spin.setSingleStep(0.05)
        self.chest_plate_spin.setDecimals(2)
        self.chest_plate_spin.setSuffix(" (0-1)")
        confidence_layout.addRow("Confiança da Placa de Peito:", self.chest_plate_spin)
        
        # Shoes confidence threshold
        self.shoes_spin = QDoubleSpinBox()
        self.shoes_spin.setRange(0.0, 1.0)
        self.shoes_spin.setSingleStep(0.05)
        self.shoes_spin.setDecimals(2)
        self.shoes_spin.setSuffix(" (0-1)")
        confidence_layout.addRow("Confiança dos Tênis:", self.shoes_spin)
        
        confidence_group.setLayout(confidence_layout)
        layout.addWidget(confidence_group)
        
        # Add description
        description = QLabel(
            "<b>Thresholds de Confiança:</b><br><br>"
            "<b>• Confiança da Placa de Peito:</b> Define o nível mínimo de confiança "
            "para aceitar detecções de dorsais/placas de peito.<br><br>"
            "<b>• Confiança dos Tênis:</b> Define o nível mínimo de confiança para "
            "aceitar tanto a <i>detecção</i> quanto a <i>classificação da marca</i> dos tênis. "
            "Ambos os valores devem estar acima do threshold.<br><br>"
            "<small>⚠️ Valores mais altos = mais rigoroso (menos detecções, maior precisão)<br>"
            "Valores mais baixos = menos rigoroso (mais detecções, menor precisão)</small>"
        )
        description.setWordWrap(True)
        description.setStyleSheet("color: #444; font-size: 11px; margin: 10px 5px; padding: 8px; "
                                "background-color: #f0f8ff; border: 1px solid #cce7ff; border-radius: 4px;")
        layout.addWidget(description)
        
        # Buttons
        button_layout = QHBoxLayout()
        
        self.reset_button = QPushButton("🔄 Resetar")
        self.reset_button.clicked.connect(self.reset_to_defaults)
        
        self.cancel_button = QPushButton("❌ Cancelar")
        self.cancel_button.clicked.connect(self.reject)
        
        self.save_button = QPushButton("💾 Salvar")
        self.save_button.clicked.connect(self.save_settings)
        self.save_button.setDefault(True)
        
        button_layout.addWidget(self.reset_button)
        button_layout.addStretch()
        button_layout.addWidget(self.cancel_button)
        button_layout.addWidget(self.save_button)
        
        layout.addLayout(button_layout)
        self.setLayout(layout)
        
        # Apply styling
        self.setStyleSheet("""
            QDialog {
                background-color: #f8f9fa;
            }
            QGroupBox {
                font-weight: bold;
                border: 2px solid #ddd;
                border-radius: 8px;
                margin: 10px 0;
                padding-top: 10px;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 5px 0 5px;
            }
            QDoubleSpinBox {
                padding: 5px;
                border: 1px solid #ddd;
                border-radius: 4px;
                min-width: 100px;
            }
            QPushButton {
                padding: 8px 16px;
                border: none;
                border-radius: 6px;
                font-weight: bold;
                min-width: 80px;
            }
            QPushButton:hover {
                background-color: #e9ecef;
            }
            QPushButton:default {
                background-color: #007bff;
                color: white;
            }
            QPushButton:default:hover {
                background-color: #0056b3;
            }
        """)
    
    def load_current_values(self) -> None:
        """Load current configuration values into the UI."""
        self.chest_plate_spin.setValue(
            self.current_config.get('chest_plate_confidence_threshold', 0.5)
        )
        self.shoes_spin.setValue(
            self.current_config.get('shoes_confidence_threshold', 0.5)
        )
    
    def reset_to_defaults(self) -> None:
        """Reset all values to their defaults."""
        reply = QMessageBox.question(
            self,
            "Resetar Configurações",
            "Tem certeza que deseja resetar todas as configurações para os valores padrão?",
            QMessageBox.Yes | QMessageBox.No
        )
        
        if reply == QMessageBox.Yes:
            self.chest_plate_spin.setValue(0.5)
            self.shoes_spin.setValue(0.5)
    
    def save_settings(self) -> None:
        """Save the current settings and close the dialog."""
        # Update the new config with current values
        self.new_config['chest_plate_confidence_threshold'] = self.chest_plate_spin.value()
        self.new_config['shoes_confidence_threshold'] = self.shoes_spin.value()
        
        # Show confirmation message
        QMessageBox.information(
            self,
            "Configurações Salvas",
            "As configurações foram salvas com sucesso!"
        )
        
        self.accept()
    
    def get_updated_config(self) -> Dict[str, Any]:
        """Get the updated configuration."""
        return self.new_config
