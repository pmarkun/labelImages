"""
Main window UI components for the Runner Viewer application.
"""
import os
from typing import List, Optional, Callable
from PyQt5.QtCore import Qt, QEvent, pyqtSignal
from PyQt5.QtGui import QPixmap, QKeyEvent, QCursor
from PyQt5.QtWidgets import (
    QMainWindow, QApplication, QWidget, QVBoxLayout, QHBoxLayout,
    QSplitter, QLabel, QTreeWidget, QTreeWidgetItem, QComboBox,
    QCheckBox, QGroupBox, QLineEdit, QGridLayout, QScrollArea,
    QPushButton, QAction, QFileDialog, QMessageBox
)
from .widgets import ClickableLabel
from .panels import LeftPanel, CenterPanel, RightPanel


class RunnerViewerMainWindow(QMainWindow):
    """Main window for the Runner Viewer application."""
    
    # Signals for communication with the main application
    json_load_requested = pyqtSignal(str)  # file_path
    json_save_requested = pyqtSignal()
    json_save_as_requested = pyqtSignal()
    base_path_change_requested = pyqtSignal()
    configuration_requested = pyqtSignal()
    export_requested = pyqtSignal()
    
    def __init__(self):
        super().__init__()
        self.setWindowTitle("🏃 Runner Data Viewer")
        self.setMinimumSize(800, 600)
        self.setup_styling()
        self.setup_ui()
        self.setup_menu()
    
    def setup_styling(self) -> None:
        """Apply modern styling to the application."""
        self.setStyleSheet("""
            QMainWindow {
                background-color: #f8f9fa;
                color: #333;
            }
            QTreeWidget {
                background-color: white;
                border: 1px solid #ddd;
                border-radius: 8px;
                padding: 5px;
                font-size: 13px;
            }
            QTreeWidget::item {
                padding: 4px;
                border-bottom: 1px solid #f0f0f0;
            }
            QTreeWidget::item:selected {
                background-color: #007acc;
                color: white;
            }
            QLabel {
                color: #333;
                font-size: 13px;
            }
            QGroupBox {
                font-weight: bold;
                border: 2px solid #ddd;
                border-radius: 8px;
                margin: 10px 0px;
                padding-top: 10px;
                background-color: white;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 5px 0 5px;
                color: #007acc;
                font-size: 14px;
            }
            QLineEdit, QComboBox {
                border: 2px solid #ddd;
                border-radius: 6px;
                padding: 8px;
                font-size: 13px;
                background-color: white;
            }
            QLineEdit:focus, QComboBox:focus {
                border-color: #007acc;
            }
            QCheckBox {
                spacing: 8px;
                font-size: 12px;
                padding: 4px;
            }
            QCheckBox::indicator {
                width: 18px;
                height: 18px;
            }
            QCheckBox::indicator:unchecked {
                border: 2px solid #ddd;
                border-radius: 3px;
                background-color: white;
            }
            QCheckBox::indicator:checked {
                border: 2px solid #007acc;
                border-radius: 3px;
                background-color: #007acc;
            }
            QPushButton {
                background-color: #007acc;
                color: white;
                border: none;
                border-radius: 6px;
                padding: 10px 20px;
                font-size: 13px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #005fa3;
            }
            QPushButton:pressed {
                background-color: #004578;
            }
            QSplitter::handle {
                background-color: #ddd;
                width: 3px;
            }
            QScrollArea {
                border: 1px solid #ddd;
                border-radius: 8px;
                background-color: white;
            }
        """)
    
    def setup_menu(self) -> None:
        """Setup the application menu."""
        # File menu
        open_json = QAction("📂 Abrir JSON", self)
        open_json.triggered.connect(self._on_open_json)
        open_json.setShortcut("Ctrl+O")
        
        save_json = QAction("💾 Salvar", self)
        save_json.triggered.connect(lambda: self.json_save_requested.emit())
        save_json.setShortcut("Ctrl+S")
        
        save_as_json = QAction("💾 Salvar Como...", self)
        save_as_json.triggered.connect(lambda: self.json_save_as_requested.emit())
        save_as_json.setShortcut("Ctrl+Shift+S")
        
        set_base = QAction("📁 Definir Base Path", self)
        set_base.triggered.connect(lambda: self.base_path_change_requested.emit())
        
        file_menu = self.menuBar().addMenu("Arquivo")
        if file_menu:
            file_menu.addAction(open_json)
            file_menu.addSeparator()
            file_menu.addAction(save_json)
            file_menu.addAction(save_as_json)
            file_menu.addSeparator()
            file_menu.addAction(set_base)
        
        # Tools menu
        config_action = QAction("⚙️ Configurações", self)
        config_action.triggered.connect(lambda: self.configuration_requested.emit())
        config_action.setShortcut("Ctrl+,")
        
        export_action = QAction("📤 Exportar Dados", self)
        export_action.triggered.connect(lambda: self.export_requested.emit())
        export_action.setShortcut("Ctrl+E")
        
        tools_menu = self.menuBar().addMenu("Ferramentas")
        if tools_menu:
            tools_menu.addAction(config_action)
            tools_menu.addSeparator()
            tools_menu.addAction(export_action)
    
    def setup_ui(self) -> None:
        """Setup the main user interface."""
        # Create main splitter
        main_splitter = QSplitter(Qt.Horizontal)
        
        # Create panels
        self.left_panel = LeftPanel()
        self.center_panel = CenterPanel()
        self.right_panel = RightPanel()
        
        # Add panels to splitter
        main_splitter.addWidget(self.left_panel)
        main_splitter.addWidget(self.center_panel)
        main_splitter.addWidget(self.right_panel)
        
        # Set splitter proportions
        main_splitter.setStretchFactor(0, 1)  # Left panel
        main_splitter.setStretchFactor(1, 3)  # Center panel (larger)
        main_splitter.setStretchFactor(2, 3)  # Right panel
        self.setCentralWidget(main_splitter)
    
    def _on_open_json(self) -> None:
        """Handle open JSON file action."""
        path, _ = QFileDialog.getOpenFileName(self, "JSON", filter="JSON Files (*.json)")
        if path:
            self.json_load_requested.emit(path)
    
    def update_window_title(self, json_path: str = "", has_unsaved_changes: bool = False) -> None:
        """Update the window title with file info and unsaved changes indicator."""
        title = "🏃 Runner Data Viewer"
        if json_path:
            filename = os.path.basename(json_path)
            title += f" - {filename}"
        if has_unsaved_changes:
            title += " *"
        self.setWindowTitle(title)
    
    def show_unsaved_changes_dialog(self) -> str:
        """Show dialog for unsaved changes and return user choice."""
        reply = QMessageBox.question(
            self, 
            "Mudanças não salvas", 
            "Você tem mudanças não salvas. Deseja salvar antes de sair?",
            QMessageBox.Save | QMessageBox.Discard | QMessageBox.Cancel
        )
        
        if reply == QMessageBox.Save:
            return "save"
        elif reply == QMessageBox.Discard:
            return "discard"
        else:
            return "cancel"
    
    def update_status_bar(self, checked: int, total: int, percentage: float) -> None:
        """Update the status bar with progress information."""
        status_text = f"✓ Checadas: {checked} | Total: {total} | Progresso: {percentage:.1f}%"
        self.statusBar().showMessage(status_text)
    
    def show_protected_image_message(self) -> None:
        """Show message that image is protected (checked)."""
        QMessageBox.information(
            self, 
            "Imagem Checada", 
            "Esta imagem está checada e não pode ser editada. Pressione 'C' para deschequear primeiro."
        )
    
    def get_tree_widget(self) -> QTreeWidget:
        """Get the tree widget for external manipulation."""
        return self.left_panel.tree
    
    def get_category_filter(self) -> QComboBox:
        """Get the category filter combo box."""
        return self.left_panel.category_filter
    
    def get_filter_unchecked_only(self) -> QCheckBox:
        """Get the unchecked filter checkbox."""
        return self.left_panel.filter_unchecked_only
    
    def get_gender_filter(self) -> QComboBox:
        """Get the gender filter combo box."""
        return self.left_panel.gender_filter
    
    def get_bib_number_field(self) -> QLineEdit:
        """Get the bib number input field."""
        return self.right_panel.bib_number
    
    def get_bib_category_field(self) -> QComboBox:
        """Get the bib category combo box."""
        return self.right_panel.bib_category
    
    def get_brand_checks(self) -> List[QCheckBox]:
        """Get the list of brand checkboxes."""
        return self.right_panel.brand_checks
    
    def get_shoe_container(self) -> QWidget:
        """Get the shoe container widget."""
        return self.center_panel.shoe_container
    
    def get_shoe_layout(self) -> QVBoxLayout:
        """Get the shoe layout."""
        return self.center_panel.shoe_box
    
    def get_thumb_label(self) -> QLabel:
        """Get the thumbnail label."""
        return self.center_panel.thumb_label
    
    def get_runner_label(self) -> QLabel:
        """Get the runner image label."""
        return self.center_panel.runner_label
