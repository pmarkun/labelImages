"""
UI panels for the Runner Viewer application.
"""
from typing import List
from PyQt5.QtCore import Qt, pyqtSignal
from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QTreeWidget, 
    QComboBox, QCheckBox, QGroupBox, QLineEdit, QGridLayout,
    QScrollArea, QSizePolicy
)
from .widgets import ClickableLabel


class LeftPanel(QWidget):
    """Left panel containing navigation tree and filters."""
    
    # Signals
    filter_changed = pyqtSignal()
    item_selected = pyqtSignal(object, object)  # current, previous
    
    def __init__(self):
        super().__init__()
        self.setup_ui()
    
    def setup_ui(self) -> None:
        """Setup the left panel UI."""
        layout = QVBoxLayout(self)
        layout.setSpacing(10)
        layout.setContentsMargins(10, 10, 10, 10)
        
        # Header
        header = QLabel("📁 Navegação")
        header.setStyleSheet("font-size: 16px; font-weight: bold; color: #007acc; margin-bottom: 10px;")
        layout.addWidget(header)
        
        # Filter section
        filter_group = QGroupBox("Filtros")
        filter_layout = QVBoxLayout(filter_group)
        
        # Category filter
        filter_layout.addWidget(QLabel("Categoria:"))
        self.category_filter = QComboBox()
        self.category_filter.addItem("Todas as categorias")
        self.category_filter.activated.connect(lambda: self.filter_changed.emit())
        filter_layout.addWidget(self.category_filter)
        
        # Gender filter
        filter_layout.addWidget(QLabel("Gênero:"))
        self.gender_filter = QComboBox()
        self.gender_filter.addItem("Todos os gêneros")
        self.gender_filter.activated.connect(lambda: self.filter_changed.emit())
        filter_layout.addWidget(self.gender_filter)
        
        self.filter_unchecked_only = QCheckBox("Mostrar apenas dorsais sem imagens checadas")
        self.filter_unchecked_only.stateChanged.connect(lambda: self.filter_changed.emit())
        filter_layout.addWidget(self.filter_unchecked_only)
        
        layout.addWidget(filter_group)
        
        # Tree widget
        self.tree = QTreeWidget()
        self.tree.setHeaderLabels(["Categoria / Dorsal / Nome"])
        self.tree.currentItemChanged.connect(self._on_item_changed)
        layout.addWidget(self.tree)
    
    def _on_item_changed(self, current, previous):
        """Handle tree item selection change."""
        self.item_selected.emit(current, previous)


class CenterPanel(QWidget):
    """Center panel containing image displays."""
    
    def __init__(self):
        super().__init__()
        self.setup_ui()
    
    def setup_ui(self) -> None:
        """Setup the center panel UI."""
        layout = QVBoxLayout(self)
        layout.setSpacing(15)
        layout.setContentsMargins(10, 10, 10, 10)
        
        # Header
        header = QLabel("🖼️ Visualização de Imagens")
        header.setStyleSheet("font-size: 16px; font-weight: bold; color: #007acc; margin-bottom: 10px;")
        layout.addWidget(header)
        
        # Original image thumbnail
        thumb_group = QGroupBox("Imagem Original")
        thumb_layout = QVBoxLayout()
        self.thumb_label = QLabel()
        self.thumb_label.setAlignment(Qt.AlignCenter)
        self.thumb_label.setStyleSheet("border: 2px dashed #ddd; border-radius: 8px; padding: 20px; background-color: #f8f9fa;")
        self.thumb_label.setMinimumHeight(200)
        thumb_layout.addWidget(self.thumb_label)
        
        # Runner and shoes section
        runner_group = QGroupBox("Corredor e Tênis")
        runner_layout = QHBoxLayout(runner_group)
        
        # Runner image
        runner_container = QVBoxLayout()
        
        self.runner_label = QLabel()
        self.runner_label.setAlignment(Qt.AlignCenter)
        self.runner_label.setStyleSheet("border: 2px dashed #ddd; border-radius: 8px; padding: 10px; background-color: #f8f9fa;")
        self.runner_label.setMinimumHeight(300)
        runner_container.addWidget(self.runner_label)
        
        # Shoes section
        shoes_container = QVBoxLayout()
        
        shoes_scroll = QScrollArea()
        shoes_scroll.setWidgetResizable(True)
        shoes_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        shoes_scroll.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        
        self.shoe_container = QWidget()
        self.shoe_box = QVBoxLayout(self.shoe_container)
        self.shoe_box.setSpacing(5)
        self.shoe_box.setContentsMargins(5, 5, 5, 5)
        shoes_scroll.setWidget(self.shoe_container)
        shoes_scroll.setMaximumWidth(300)
        shoes_scroll.setMinimumHeight(400)
        shoes_container.addWidget(shoes_scroll)
        
        runner_layout.addLayout(thumb_layout, 1)
        runner_layout.addLayout(runner_container, 2)
        runner_layout.addLayout(shoes_container, 2)
        layout.addWidget(runner_group)


class RightPanel(QWidget):
    """Right panel containing details and controls."""
    
    # Signals
    bib_number_entered = pyqtSignal()
    category_selected = pyqtSignal(int)
    brand_changed = pyqtSignal()
    
    def __init__(self):
        super().__init__()
        self.brand_checks: List[QCheckBox] = []
        self.setup_ui()
    
    def setup_ui(self) -> None:
        """Setup the right panel UI."""
        layout = QVBoxLayout(self)
        layout.setSpacing(15)
        layout.setContentsMargins(10, 10, 10, 10)
        
        # Header
        header = QLabel("⚙️ Detalhes e Edição")
        header.setStyleSheet("font-size: 16px; font-weight: bold; color: #007acc; margin-bottom: 10px;")
        layout.addWidget(header)
        
        # Bib information group
        bib_group = QGroupBox("Informações do Dorsal")
        bib_layout = QVBoxLayout(bib_group)
        
        # Bib number
        bib_layout.addWidget(QLabel("Número do Dorsal:"))
        self.bib_number = QLineEdit()
        self.bib_number.setPlaceholderText("Digite o número...")
        self.bib_number.returnPressed.connect(lambda: self.bib_number_entered.emit())
        bib_layout.addWidget(self.bib_number)
        
        # Bib category
        bib_layout.addWidget(QLabel("Categoria:"))
        self.bib_category = QComboBox()
        self.bib_category.activated.connect(self.category_selected.emit)
        bib_layout.addWidget(self.bib_category)
        
        layout.addWidget(bib_group)
        
        # Brand selection group
        brand_group = QGroupBox("Marcas dos Tênis")
        brand_layout = QVBoxLayout(brand_group)
        
        # Create scrollable area for brands
        brand_scroll = QScrollArea()
        brand_scroll.setWidgetResizable(True)
        brand_scroll.setMinimumHeight(350)
        brand_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        
        self.brand_panel = QWidget()
        self.brand_layout = QGridLayout(self.brand_panel)
        self.brand_layout.setSpacing(5)
        
        brand_scroll.setWidget(self.brand_panel)
        brand_layout.addWidget(brand_scroll)
        layout.addWidget(brand_group)
        
        # Add stretch to push everything to top
        layout.addStretch()
    
    def setup_brand_checkboxes(self, brands: List[str]) -> None:
        """Setup brand checkboxes based on available brands."""
        # Clear existing checkboxes
        for chk in self.brand_checks:
            chk.deleteLater()
        self.brand_checks = []
        
        # Create new checkboxes in two columns
        for i, brand in enumerate(brands):
            cb = QCheckBox(brand)
            cb.stateChanged.connect(lambda: self.brand_changed.emit())
            row = i // 2
            col = i % 2
            self.brand_layout.addWidget(cb, row, col)
            self.brand_checks.append(cb)
    
    def setup_shortcuts_info(self, config_labels: List[dict]) -> None:
        """Setup keyboard shortcuts information display."""
        # Remove existing shortcuts group if it exists
        layout = self.layout()
        for i in range(layout.count()):
            item = layout.itemAt(i)
            if item and item.widget():
                widget = item.widget()
                if isinstance(widget, QGroupBox) and widget.title() == "Atalhos de Teclado":
                    widget.deleteLater()
                    break
        
        # Create new shortcuts group
        shortcuts_group = QGroupBox("Atalhos de Teclado")
        shortcuts_layout = QVBoxLayout(shortcuts_group)
        
        # Dynamic shortcuts text based on config
        brand_shortcuts = ""
        if config_labels:
            brand_shortcuts = "<b>Marcas:</b><br>"
            for label_config in config_labels:
                if isinstance(label_config, dict):
                    key = label_config.get("key", "").upper()
                    label = label_config.get("label", "")
                    if key and label:
                        brand_shortcuts += f"<b>{key}</b> : {label}<br>"
            brand_shortcuts += "<br>"
        
        shortcuts_text = QLabel(f"""
        <b>Navegação:</b><br>
        ← → ↑ ↓ : Navegar<br>
        Enter : Salvar mudanças<br><br>
        
        <b>Edição:</b><br>
        <b>Del</b> : Remover imagem<br>
        <b>K</b> : Propagar dados e exportar crops de TODAS as imagens do mesmo dorsal<br>
        <b>C</b> : Marcar/desmarcar como checada<br>
        <b>Ctrl+Z</b> : Desfazer última alteração<br><br>
        
        {brand_shortcuts}
        <small>💡 Imagens checadas ficam protegidas contra edição</small>
        """)
        shortcuts_text.setStyleSheet("font-size: 11px; color: #666; padding: 5px;")
        shortcuts_text.setWordWrap(True)
        shortcuts_layout.addWidget(shortcuts_text)
        
        # Add to layout
        layout.addWidget(shortcuts_group)
