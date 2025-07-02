"""
Custom widgets for the Runner Viewer application.
"""
from PyQt5.QtWidgets import QLabel
from PyQt5.QtCore import pyqtSignal, Qt, QEvent
from PyQt5.QtGui import QMouseEvent, QCursor
from typing import Callable, Any


class ClickableLabel(QLabel):
    """A QLabel that can be clicked and emits signals."""
    
    clicked = pyqtSignal()
    
    def __init__(self, shoe_index: int = 0, callback=None, parent=None):
        super().__init__(parent)
        self.shoe_index = shoe_index
        self.callback = callback
        self.setCursor(QCursor(Qt.PointingHandCursor))
    
    def mousePressEvent(self, ev: QMouseEvent) -> None:
        """Handle mouse press events."""
        if ev.button() == Qt.LeftButton:
            self.clicked.emit()
            if self.callback:
                self.callback(ev, self.shoe_index)
        super().mousePressEvent(ev)
