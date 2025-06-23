import sys
import os
import shutil
import yaml
from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QLabel, QFileDialog, QAction,
    QDialog, QTextEdit, QVBoxLayout, QPushButton, QWidget,
    QInputDialog, QToolBar, QStatusBar, QHBoxLayout, QSizePolicy,
    QScrollArea, QFrame, QListWidget, QListWidgetItem, QSplitter
)
from PyQt5.QtGui import QPixmap, QIcon
from PyQt5.QtCore import Qt, QSize

DEFAULT_CONFIG = {
    'default_output_folder': os.getcwd(),
    'default_label': 'Olympikus',
    'labels': [
        {'key': 'q', 'label': 'Olympikus'},
        {'key': 'w', 'label': 'Nike'},
        {'key': 'e', 'label': 'Adidas'},
        {'key': 'r', 'label': 'Asics'},
        {'key': 't', 'label': 'Fila'},
        {'key': 'y', 'label': 'Hoka'},
        {'key': 'u', 'label': 'Mizuno'},
        {'key': 'i', 'label': 'New Balance'},
        {'key': 'o', 'label': 'On Running'},
        {'key': 'p', 'label': 'Under Armour'},
        {'key': 'z', 'label': 'Outros'},
    ]
}

class ConfigEditor(QDialog):
    def __init__(self, config_path, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Editar Configuração")
        self.config_path = config_path
        self.resize(500, 400)

        self.text_edit = QTextEdit(self)
        with open(self.config_path, 'r', encoding='utf-8') as f:
            self.text_edit.setText(f.read())

        save_btn = QPushButton("Salvar")
        save_btn.clicked.connect(self.save_config)
        cancel_btn = QPushButton("Cancelar")
        cancel_btn.clicked.connect(self.close)

        btn_layout = QHBoxLayout()
        btn_layout.addWidget(save_btn)
        btn_layout.addWidget(cancel_btn)

        layout = QVBoxLayout()
        layout.addWidget(self.text_edit)
        layout.addLayout(btn_layout)
        self.setLayout(layout)

    def save_config(self):
        try:
            data = yaml.safe_load(self.text_edit.toPlainText())
            with open(self.config_path, 'w', encoding='utf-8') as f:
                yaml.safe_dump(data, f, default_flow_style=False, allow_unicode=True)
            self.accept()
        except Exception:
            pass

class ImageMover(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Image Mover")
        self.resize(1400, 800)
        self.setFocusPolicy(Qt.StrongFocus)

        self.config_path = os.path.join(os.getcwd(), 'config.yaml')
        self.ensure_config()
        self.config = self.load_config()

        # Folder navigation list
        self.dir_list = QListWidget()
        self.dir_list.setFixedWidth(200)
        self.dir_list.itemClicked.connect(self.on_dir_selected)

        # Select initial folder
        start = QFileDialog.getExistingDirectory(self, "Selecione o diretório de imagens")
        if not start:
            sys.exit(0)
        self.load_dirs(start)

        # Undo stack
        self.undo_stack = []

        # Toolbar
        toolbar = QToolBar()
        toolbar.setIconSize(QSize(24, 24))
        self.addToolBar(toolbar)
        toolbar.addAction(QIcon.fromTheme('go-previous'), "Anterior", lambda: self.change_index(-1))
        toolbar.addAction(QIcon.fromTheme('go-next'), "Próxima", lambda: self.change_index(1))
        toolbar.addSeparator()
        toolbar.addAction(QIcon.fromTheme('edit-undo'), "Desfazer (Ctrl+Z)", self.undo_move)
        toolbar.addSeparator()
        toolbar.addAction(QIcon.fromTheme('settings'), "Config", self.open_config_menu)

        self.status = QStatusBar()
        self.setStatusBar(self.status)

        # Image and labels panel
        img_frame = QFrame()
        img_layout = QVBoxLayout(img_frame)
        self.image_label = QLabel()
        self.image_label.setAlignment(Qt.AlignCenter)
        self.image_label.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        img_layout.addWidget(self.image_label)
        self.file_label = QLabel(alignment=Qt.AlignCenter)
        img_layout.addWidget(self.file_label)
        self.move_msg = QLabel(alignment=Qt.AlignCenter)
        img_layout.addWidget(self.move_msg)

        side = QFrame()
        side.setFrameShape(QFrame.StyledPanel)
        side_layout = QVBoxLayout(side)
        side_layout.addWidget(QLabel("Labels:", alignment=Qt.AlignCenter))
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        self.labels_widget = QWidget()
        self.labels_layout = QVBoxLayout(self.labels_widget)
        scroll.setWidget(self.labels_widget)
        side_layout.addWidget(scroll)

        # Splitter for dir list and main panel
        splitter = QSplitter(Qt.Horizontal)
        splitter.addWidget(self.dir_list)
        main_widget = QWidget()
        main_layout = QHBoxLayout(main_widget)
        main_layout.addWidget(img_frame, 3)
        main_layout.addWidget(side, 1)
        splitter.addWidget(main_widget)
        self.setCentralWidget(splitter)

        # Load images in current folder
        self.images = []
        self.index = 0
        self.on_dir_selected(self.dir_list.item(0))

    def load_dirs(self, root):
        self.current_dir = root
        self.dir_list.clear()
        for d in sorted(os.listdir(root)):
            full = os.path.join(root, d)
            if os.path.isdir(full):
                count = len([f for f in os.listdir(full) if f.lower().endswith((".png",".jpg",".jpeg",".bmp",".gif"))])
                if count > 0:
                    
                    item = QListWidgetItem(f"{d} ({count})", self.dir_list)
                    item.setData(Qt.UserRole, full)

    def on_dir_selected(self, item):
        self.img_dir = os.path.join(self.current_dir, item.data(Qt.UserRole))
        self.images = sorted([f for f in os.listdir(self.img_dir)
                              if f.lower().endswith((".png",".jpg",".jpeg",".bmp",".gif"))])
        self.index = 0
        self.update_labels()
        self.update_image()

    def ensure_config(self):
        if not os.path.exists(self.config_path):
            with open(self.config_path, 'w', encoding='utf-8') as f:
                yaml.safe_dump(DEFAULT_CONFIG, f, default_flow_style=False, allow_unicode=True)

    def load_config(self):
        with open(self.config_path, 'r', encoding='utf-8') as f:
            return yaml.safe_load(f)

    def save_config(self):
        with open(self.config_path, 'w', encoding='utf-8') as f:
            yaml.safe_dump(self.config, f, default_flow_style=False, allow_unicode=True)

    def open_config_menu(self):
        menu = self.menuBar().addMenu("Config")
        menu.clear()
        menu.addAction("Editar Configuração", self.open_config_editor)
        menu.addAction("Selecionar Pasta de Saída", self.select_output_folder)
        menu.addAction("Selecionar Label Padrão", self.select_default_label)
        menu.exec_(self.mapToGlobal(self.cursor().pos()))

    def open_config_editor(self):
        dlg = ConfigEditor(self.config_path, self)
        if dlg.exec_() == QDialog.Accepted:
            self.config = self.load_config()
            self.update_labels()

    def select_output_folder(self):
        folder = QFileDialog.getExistingDirectory(self, "Selecione a Pasta de Saída")
        if folder:
            self.config['default_output_folder'] = folder
            self.save_config()

    def select_default_label(self):
        labels = [item['label'] for item in self.config.get('labels', [])]
        lbl, ok = QInputDialog.getItem(self, "Label Padrão", "Escolha:", labels, editable=False)
        if ok:
            self.config['default_label'] = lbl
            self.save_config()

    def change_index(self, delta):
        if not self.images:
            return
        self.index = max(0, min(self.index + delta, len(self.images)-1))
        self.update_image()

    def update_image(self):
        if not self.images:
            self.image_label.setText("Nenhuma imagem.")
            return
        path = os.path.join(self.img_dir, self.images[self.index])
        pix = QPixmap(path).scaled(
            self.image_label.size(), Qt.KeepAspectRatio, Qt.SmoothTransformation
        )
        self.image_label.setPixmap(pix)
        self.file_label.setText(f"{self.index+1}/{len(self.images)}: {self.images[self.index]}")
        self.move_msg.clear()

    def update_labels(self):
        while self.labels_layout.count():
            item = self.labels_layout.takeAt(0)
            widget = item.widget()
            if widget:
                widget.deleteLater()
        output = self.config.get('default_output_folder', '')
        for item in self.config.get('labels', []):
            count = len(os.listdir(os.path.join(output, item['label']))) if os.path.exists(os.path.join(output, item['label'])) else 0
            btn = QPushButton(f"{item['label']} ({count}) => {item['key']}")
            btn.clicked.connect(lambda _, lbl=item['label']: self.move_current(lbl))
            self.labels_layout.addWidget(btn)
        default = self.config.get('default_label')
        btn = QPushButton(f"Padrão: {default} [Espaço]")
        btn.clicked.connect(lambda _, lbl=default: self.move_current(lbl))
        self.labels_layout.addWidget(btn)
        self.labels_layout.addStretch()

    def move_current(self, label):
        if not self.images:
            return
        name = self.images[self.index]
        src = os.path.join(self.img_dir, name)
        dst_folder = os.path.join(self.config['default_output_folder'], label)
        os.makedirs(dst_folder, exist_ok=True)
        dst = os.path.join(dst_folder, name)
        shutil.move(src, dst)
        self.undo_stack.append((name, label, self.index))
        self.move_msg.setText(f"Movido para: {label}")
        self.images.pop(self.index)
        if self.index >= len(self.images):
            self.index = max(0, len(self.images)-1)
        self.update_image()
        self.update_labels()

    def undo_move(self):
        if not self.undo_stack:
            self.status.showMessage("Nada a desfazer", 2000)
            return
        name, label, idx = self.undo_stack.pop()
        dst_folder = os.path.join(self.config['default_output_folder'], label)
        dst = os.path.join(dst_folder, name)
        src = os.path.join(self.img_dir, name)
        if os.path.exists(dst):
            shutil.move(dst, src)
            self.images.insert(idx, name)
            self.index = idx
            self.update_image()
            self.update_labels()
            self.move_msg.setText(f"Desfeito: {name}")
        else:
            self.status.showMessage("Arquivo não encontrado para desfazer", 2000)

    def keyPressEvent(self, event):
        if event.key() == Qt.Key_Z and event.modifiers() & Qt.ControlModifier:
            self.undo_move()
            return
        if not self.images:
            return
        txt = event.text()
        if event.key() == Qt.Key_Right:
            self.change_index(1)
        elif event.key() == Qt.Key_Left:
            self.change_index(-1)
        else:
            labels = {item['key']: item['label'] for item in self.config.get('labels', [])}
            if event.key() == Qt.Key_Space:
                self.move_current(self.config.get('default_label'))
            elif txt in labels:
                self.move_current(labels[txt])

if __name__ == '__main__':
    app = QApplication(sys.argv)
    mover = ImageMover()
    mover.show()
    sys.exit(app.exec_())
