# NCRADS9 - NCRA DS9-like FITS Viewer
# Copyright (C) 2026 Yogesh Wadadekar
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <https://www.gnu.org/licenses/>.

"""
Export image dialog.

Author: Yogesh Wadadekar
"""

from typing import Optional
from PyQt6.QtWidgets import (
    QDialog,
    QVBoxLayout,
    QHBoxLayout,
    QPushButton,
    QLabel,
    QComboBox,
    QFileDialog,
    QWidget,
    QLineEdit,
    QFormLayout,
)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QPixmap


class ExportDialog(QDialog):
    """Dialog for exporting images."""

    def __init__(self, pixmap: QPixmap, parent: Optional[QWidget] = None) -> None:
        """
        Initialize the export dialog.

        Args:
            pixmap: The image pixmap to export.
            parent: Optional parent widget.
        """
        super().__init__(parent)
        self.pixmap = pixmap
        self.export_path = None
        
        self.setWindowTitle("Export Image")
        self.setMinimumSize(400, 200)
        
        self._setup_ui()

    def _setup_ui(self) -> None:
        """Set up the user interface."""
        layout = QVBoxLayout()
        
        # Title
        title = QLabel("Export Current View")
        title.setStyleSheet("font-weight: bold; font-size: 14px;")
        layout.addWidget(title)
        
        # Form layout
        form = QFormLayout()
        
        # Format selection
        self.format_combo = QComboBox()
        self.format_combo.addItems(["PNG", "JPEG", "TIFF", "BMP"])
        form.addRow("Format:", self.format_combo)
        
        # File path
        path_layout = QHBoxLayout()
        self.path_edit = QLineEdit()
        path_layout.addWidget(self.path_edit)
        
        browse_button = QPushButton("Browse...")
        browse_button.clicked.connect(self._browse_file)
        path_layout.addWidget(browse_button)
        
        form.addRow("Save to:", path_layout)
        
        layout.addLayout(form)
        layout.addStretch()
        
        # Buttons
        button_layout = QHBoxLayout()
        button_layout.addStretch()
        
        export_button = QPushButton("Export")
        export_button.clicked.connect(self._export)
        export_button.setDefault(True)
        button_layout.addWidget(export_button)
        
        cancel_button = QPushButton("Cancel")
        cancel_button.clicked.connect(self.reject)
        button_layout.addWidget(cancel_button)
        
        layout.addLayout(button_layout)
        self.setLayout(layout)

    def _browse_file(self) -> None:
        """Open file browser for save path."""
        format_ext = self.format_combo.currentText().lower()
        filters = {
            "png": "PNG Images (*.png)",
            "jpeg": "JPEG Images (*.jpg *.jpeg)",
            "tiff": "TIFF Images (*.tif *.tiff)",
            "bmp": "BMP Images (*.bmp)",
        }
        
        filepath, _ = QFileDialog.getSaveFileName(
            self,
            "Export Image",
            "",
            filters.get(format_ext, "All Files (*)"),
        )
        
        if filepath:
            self.path_edit.setText(filepath)

    def _export(self) -> None:
        """Export the image."""
        filepath = self.path_edit.text()
        if not filepath:
            return
        
        format_str = self.format_combo.currentText()
        
        # Save pixmap to file
        success = self.pixmap.save(filepath, format_str)
        
        if success:
            self.export_path = filepath
            self.accept()
        else:
            from PyQt6.QtWidgets import QMessageBox
            QMessageBox.warning(
                self,
                "Export Failed",
                f"Could not export image to {filepath}",
            )
