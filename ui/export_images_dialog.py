"""Dialog for exporting images in batch from the Runner Viewer application."""

import os
import random
from typing import List, Dict, Any, Optional

from PIL import Image
from PyQt5.QtCore import Qt, QThread, pyqtSignal
from PyQt5.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QGridLayout, QLabel, QPushButton,
    QCheckBox, QSlider, QGroupBox, QProgressBar, QTextEdit, QFileDialog,
    QMessageBox, QComboBox, QSpinBox, QRadioButton
)

from utils.image_utils import load_image_cached, crop_image


class ExportImagesWorker(QThread):
    """Worker thread for exporting images."""

    progress = pyqtSignal(int)
    message = pyqtSignal(str)
    finished = pyqtSignal(int)

    def __init__(
        self,
        data: List[Dict[str, Any]],
        base_path: str,
        output_path: str,
        num_images: int,
        randomize: bool,
        category: Optional[str],
        gender: Optional[str],
        bib_filter: str,
        min_conf: float,
        max_conf: float,
        export_types: Dict[str, bool]
    ):
        super().__init__()
        self.data = data
        self.base_path = base_path
        self.output_path = output_path
        self.num_images = num_images
        self.randomize = randomize
        self.category = category
        self.gender = gender
        self.bib_filter = bib_filter
        self.min_conf = min_conf
        self.max_conf = max_conf
        self.export_types = export_types
        self.total_exported = 0

    def run(self):
        try:
            self.message.emit("Iniciando exportação de imagens...")

            # Apply filters
            filtered = []
            for item in self.data:
                if self.category and item.get("run_category") != self.category:
                    continue
                if self.gender and item.get("gender") != self.gender:
                    continue

                has_bib = False
                for runner in item.get("runners_found", []):
                    chest = runner.get("chest_plate")
                    if chest and chest.get("bbox"):
                        has_bib = True
                        break
                if self.bib_filter == "Com bib" and not has_bib:
                    continue
                if self.bib_filter == "Sem bib" and has_bib:
                    continue

                filtered.append(item)

            total_available = len(filtered)
            count = self.num_images if self.num_images > 0 else total_available
            count = min(count, total_available)

            if self.randomize:
                selected = random.sample(filtered, count)
            else:
                selected = filtered[:count]
            total_sel = len(selected)
            self.message.emit(f"Exportando {total_sel} participantes selecionados...")

            for idx, item in enumerate(selected):
                for runner_index, runner in enumerate(item.get("runners_found", [])):
                    img_file = runner.get("image_path", "")
                    if not img_file:
                        continue
                    img_src = os.path.join(self.base_path, img_file)
                    if not os.path.exists(img_src):
                        continue

                    # Full image
                    if self.export_types.get("full", False):
                        dest = os.path.join(self.output_path, "full_images")
                        os.makedirs(dest, exist_ok=True)
                        from shutil import copy2

                        dst_file = os.path.join(
                            dest,
                            f"full_{idx}_runner{runner_index}_{os.path.basename(img_file)}"
                        )
                        copy2(img_src, dst_file)
                        self.total_exported += 1

                    # Person crop
                    if self.export_types.get("person", False):
                        bbox = runner.get("bbox")
                        if bbox and len(bbox) >= 4:
                            img = load_image_cached(img_src)
                            crop = crop_image(img, bbox)
                            dest = os.path.join(self.output_path, "person_crops")
                            os.makedirs(dest, exist_ok=True)
                            dst_file = os.path.join(
                                dest,
                                f"person_{idx}_runner{runner_index}_" +
                                os.path.splitext(os.path.basename(img_file))[0] +
                                ".jpg"
                            )
                            crop.save(dst_file, "JPEG", quality=95)
                            self.total_exported += 1

                    # Bib crop
                    if self.export_types.get("bibs", False):
                        chest = runner.get("chest_plate")
                        if chest:
                            bbox = chest.get("bbox")
                            if bbox and len(bbox) >= 4:
                                img = load_image_cached(img_src)
                                crop = crop_image(img, bbox)
                                dest = os.path.join(self.output_path, "bib_crops")
                                os.makedirs(dest, exist_ok=True)
                                dst_file = os.path.join(
                                    dest,
                                    f"bib_{idx}_runner{runner_index}_" +
                                    os.path.splitext(os.path.basename(img_file))[0] +
                                    ".jpg"
                                )
                                crop.save(dst_file, "JPEG", quality=95)
                                self.total_exported += 1

                    # Shoes crop
                    if self.export_types.get("shoes", False):
                        for shoe_index, shoe in enumerate(runner.get("shoes", [])):
                            conf = shoe.get("confidence", 0.0)
                            if conf < self.min_conf or conf > self.max_conf:
                                continue
                            bbox = shoe.get("bbox")
                            if bbox and len(bbox) >= 4:
                                img = load_image_cached(img_src)
                                crop = crop_image(img, bbox)
                                dest = os.path.join(self.output_path, "shoe_crops")
                                os.makedirs(dest, exist_ok=True)
                                dst_file = os.path.join(
                                    dest,
                                    f"shoe_{idx}_runner{runner_index}_{shoe_index}_" +
                                    os.path.splitext(os.path.basename(img_file))[0] +
                                    ".jpg"
                                )
                                crop.save(dst_file, "JPEG", quality=95)
                                self.total_exported += 1

                progress = int((idx + 1) * 100 / total_sel) if total_sel > 0 else 100
                self.progress.emit(progress)

            self.message.emit(
                f"Exportação concluída! {self.total_exported} arquivos exportados."
            )
            self.finished.emit(self.total_exported)
        except Exception as e:
            self.message.emit(f"Erro durante exportação de imagens: {e}")
            self.finished.emit(self.total_exported)


class ExportImagesDialog(QDialog):
    """Dialog for configuring and exporting images."""

    def __init__(
        self,
        data: List[Dict[str, Any]],
        base_path: str,
        parent=None
    ):
        super().__init__(parent)
        self.data = data
        self.base_path = base_path
        self.worker: Optional[ExportImagesWorker] = None

        self.setWindowTitle("Exportar Imagens")
        self.setModal(True)
        self.resize(500, 700)

        self._setup_ui()
        self._connect_signals()

    def _setup_ui(self):
        layout = QVBoxLayout(self)

        # Quantity
        qty_group = QGroupBox("Quantidade de Imagens")
        qty_layout = QHBoxLayout(qty_group)
        total = len(self.data)
        qty_layout.addWidget(QLabel("Quantidade:"))
        self.qty_spin = QSpinBox()
        self.qty_spin.setRange(0, total)
        self.qty_spin.setValue(total)
        qty_layout.addWidget(self.qty_spin)
        qty_layout.addWidget(QLabel(f"/ {total}"))
        layout.addWidget(qty_group)

        # Selection mode
        mode_group = QGroupBox("Modo de Seleção")
        mode_layout = QHBoxLayout(mode_group)
        self.seq_rb = QRadioButton("Sequencial")
        self.rand_rb = QRadioButton("Aleatório")
        self.seq_rb.setChecked(True)
        mode_layout.addWidget(self.seq_rb)
        mode_layout.addWidget(self.rand_rb)
        layout.addWidget(mode_group)

        # Filters
        filt_group = QGroupBox("Filtros")
        filt_layout = QGridLayout(filt_group)
        filt_layout.addWidget(QLabel("Categoria:"), 0, 0)
        self.category_cb = QComboBox()
        self.category_cb.addItem("Todas as categorias")
        cats = sorted({p.get("run_category") for p in self.data if p.get("run_category")})
        for c in cats:
            self.category_cb.addItem(c)
        filt_layout.addWidget(self.category_cb, 0, 1)

        filt_layout.addWidget(QLabel("Gênero:"), 1, 0)
        self.gender_cb = QComboBox()
        self.gender_cb.addItem("Todos os gêneros")
        gens = sorted({p.get("gender") for p in self.data if p.get("gender")})
        for g in gens:
            self.gender_cb.addItem(g)
        filt_layout.addWidget(self.gender_cb, 1, 1)

        filt_layout.addWidget(QLabel("Bib detectado:"), 2, 0)
        self.bib_cb = QComboBox()
        self.bib_cb.addItems(["Todos", "Com bib", "Sem bib"])
        filt_layout.addWidget(self.bib_cb, 2, 1)
        layout.addWidget(filt_group)

        # Confidence thresholds
        conf_group = QGroupBox("Limites de Confiança para Tênis")
        conf_layout = QGridLayout(conf_group)
        conf_layout.addWidget(QLabel("Mínimo:"), 0, 0)
        self.min_slider = QSlider(Qt.Horizontal)
        self.min_slider.setRange(0, 100)
        self.min_slider.setValue(0)
        self.min_label = QLabel("0.00")
        conf_layout.addWidget(self.min_slider, 0, 1)
        conf_layout.addWidget(self.min_label, 0, 2)

        conf_layout.addWidget(QLabel("Máximo:"), 1, 0)
        self.max_slider = QSlider(Qt.Horizontal)
        self.max_slider.setRange(0, 100)
        self.max_slider.setValue(100)
        self.max_label = QLabel("1.00")
        conf_layout.addWidget(self.max_slider, 1, 1)
        conf_layout.addWidget(self.max_label, 1, 2)
        layout.addWidget(conf_group)

        # Export types
        type_group = QGroupBox("Tipos de Exportação")
        type_layout = QVBoxLayout(type_group)
        self.shoes_cb = QCheckBox("Tênis (crops)")
        self.bibs_cb = QCheckBox("Dorsais (crops)")
        self.person_cb = QCheckBox("Pessoa (crops)")
        self.full_cb = QCheckBox("Imagem Completa")
        for cb in [self.shoes_cb, self.bibs_cb, self.person_cb, self.full_cb]:
            type_layout.addWidget(cb)
        layout.addWidget(type_group)

        # Output directory
        out_group = QGroupBox("Diretório de Saída")
        out_layout = QHBoxLayout(out_group)
        self.output_path_label = QLabel("Selecione um diretório...")
        self.output_path_btn = QPushButton("Escolher...")
        out_layout.addWidget(self.output_path_label)
        out_layout.addWidget(self.output_path_btn)
        layout.addWidget(out_group)

        # Progress
        prog_group = QGroupBox("Progresso")
        prog_layout = QVBoxLayout(prog_group)
        self.progress_bar = QProgressBar()
        self.progress_bar.setVisible(False)
        self.status_text = QTextEdit()
        self.status_text.setReadOnly(True)
        self.status_text.setMaximumHeight(100)
        prog_layout.addWidget(self.progress_bar)
        prog_layout.addWidget(self.status_text)
        layout.addWidget(prog_group)

        # Buttons
        btn_layout = QHBoxLayout()
        self.export_btn = QPushButton("Exportar")
        self.export_btn.setEnabled(False)
        self.cancel_btn = QPushButton("Cancelar")
        btn_layout.addStretch()
        btn_layout.addWidget(self.export_btn)
        btn_layout.addWidget(self.cancel_btn)
        layout.addLayout(btn_layout)

    def _connect_signals(self):
        self.output_path_btn.clicked.connect(self._select_output_path)
        widgets = [
            self.qty_spin, self.seq_rb, self.rand_rb, self.category_cb,
            self.gender_cb, self.bib_cb, self.min_slider, self.max_slider,
            self.shoes_cb, self.bibs_cb, self.person_cb, self.full_cb
        ]
        for w in widgets:
            if hasattr(w, 'stateChanged'):
                w.stateChanged.connect(self._check_export_ready)
            elif hasattr(w, 'valueChanged'):
                w.valueChanged.connect(self._check_export_ready)
            elif hasattr(w, 'currentIndexChanged'):
                w.currentIndexChanged.connect(self._check_export_ready)
        self.output_path_btn.clicked.connect(self._check_export_ready)

        self.min_slider.valueChanged.connect(
            lambda v: self.min_label.setText(f"{v/100:.2f}"))
        self.max_slider.valueChanged.connect(
            lambda v: self.max_label.setText(f"{v/100:.2f}"))
        self.min_slider.valueChanged.connect(self._sync_sliders)
        self.max_slider.valueChanged.connect(self._sync_sliders)

        self.export_btn.clicked.connect(self._start_export)
        self.cancel_btn.clicked.connect(self.reject)

    def _sync_sliders(self, v):
        if self.min_slider.value() > self.max_slider.value():
            self.max_slider.setValue(self.min_slider.value())
        if self.max_slider.value() < self.min_slider.value():
            self.min_slider.setValue(self.max_slider.value())

    def _check_export_ready(self):
        has_path = self.output_path_label.text() != "Selecione um diretório..."
        has_type = any([
            self.shoes_cb.isChecked(), self.bibs_cb.isChecked(),
            self.person_cb.isChecked(), self.full_cb.isChecked()
        ])
        self.export_btn.setEnabled(has_path and has_type)
        if not has_path:
            self.export_btn.setToolTip("Selecione um diretório de saída primeiro")
        elif not has_type:
            self.export_btn.setToolTip("Selecione pelo menos um tipo de exportação")
        else:
            self.export_btn.setToolTip("Iniciar exportação de imagens")

    def _select_output_path(self):
        directory = QFileDialog.getExistingDirectory(
            self, "Selecionar Diretório de Saída", os.path.expanduser("~")
        )
        if directory:
            self.output_path_label.setText(directory)

    def _start_export(self):
        out = self.output_path_label.text()
        if out == "Selecione um diretório...":
            QMessageBox.warning(self, "Aviso", "Selecione um diretório de saída.")
            return
        num = self.qty_spin.value()
        rand = self.rand_rb.isChecked()
        cat = self.category_cb.currentText()
        cat = None if cat.startswith("Todas") else cat
        gen = self.gender_cb.currentText()
        gen = None if gen.startswith("Todos") else gen
        bibf = self.bib_cb.currentText()
        minc = self.min_slider.value() / 100.0
        maxc = self.max_slider.value() / 100.0
        types = {
            "shoes": self.shoes_cb.isChecked(),
            "bibs": self.bibs_cb.isChecked(),
            "person": self.person_cb.isChecked(),
            "full": self.full_cb.isChecked()
        }
        if not any(types.values()):
            QMessageBox.warning(self, "Aviso", "Selecione pelo menos um tipo de exportação.")
            return

        self.export_btn.setEnabled(False)
        self.progress_bar.setVisible(True)
        self.progress_bar.setValue(0)

        self.worker = ExportImagesWorker(
            self.data,
            self.base_path,
            out,
            num,
            rand,
            cat,
            gen,
            bibf,
            minc,
            maxc,
            types
        )
        self.worker.progress.connect(self.progress_bar.setValue)
        self.worker.message.connect(self._add_status_message)
        self.worker.finished.connect(self._export_finished)
        self.worker.start()

    def _add_status_message(self, msg: str):
        self.status_text.append(msg)

    def _export_finished(self, total: int):
        self.progress_bar.setVisible(False)
        self.export_btn.setEnabled(True)
        if total > 0:
            QMessageBox.information(
                self,
                "Exportação Concluída",
                f"Exportação concluída!\n{total} arquivos exportados."
            )
        else:
            QMessageBox.warning(
                self,
                "Exportação",
                "Nenhum arquivo foi exportado. Verifique os filtros e configurações."
            )
