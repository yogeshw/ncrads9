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
Save/export dialog for FITS and image files.

Author: Yogesh Wadadekar
"""

from pathlib import Path
from typing import Optional

from PyQt6.QtCore import pyqtSignal
from PyQt6.QtWidgets import (
    QDialog,
    QVBoxLayout,
    QHBoxLayout,
    QFileDialog,
    QLabel,
    QPushButton,
    QComboBox,
    QGroupBox,
    QFormLayout,
    QLineEdit,
    QCheckBox,
    QSpinBox,
)


class SaveDialog(QDialog):
    """Dialog for saving and exporting files."""

    file_saved = pyqtSignal(str, str)  # path, format

    def __init__(self, parent: Optional[QDialog] = None) -> None:
        """Initialize the save dialog.

        Args:
            parent: Parent widget.
        """
        super().__init__(parent)
        self.setWindowTitle("Save/Export")
        self.setMinimumWidth(500)
        self._setup_ui()

    def _setup_ui(self) -> None:
        """Set up the dialog UI."""
        layout = QVBoxLayout(self)

        # File path section
        path_group = QGroupBox("Output File")
        path_layout = QHBoxLayout(path_group)

        self._path_edit = QLineEdit()
        self._path_edit.setPlaceholderText("Select output file...")
        path_layout.addWidget(self._path_edit)

        browse_btn = QPushButton("Browse...")
        browse_btn.clicked.connect(self._browse_save_location)
        path_layout.addWidget(browse_btn)

        layout.addWidget(path_group)

        # Format options
        format_group = QGroupBox("Format Options")
        format_layout = QFormLayout(format_group)

        self._format_combo = QComboBox()
        self._format_combo.addItems(["FITS", "PNG", "JPEG", "TIFF", "PDF"])
        self._format_combo.currentTextChanged.connect(self._on_format_changed)
        format_layout.addRow("Format:", self._format_combo)

        self._quality_spin = QSpinBox()
        self._quality_spin.setRange(1, 100)
        self._quality_spin.setValue(95)
        format_layout.addRow("Quality:", self._quality_spin)

        self._compress_check = QCheckBox("Compress output")
        format_layout.addRow("", self._compress_check)

        layout.addWidget(format_group)

        # FITS-specific options
        self._fits_group = QGroupBox("FITS Options")
        fits_layout = QFormLayout(self._fits_group)

        self._preserve_wcs_check = QCheckBox("Preserve WCS")
        self._preserve_wcs_check.setChecked(True)
        fits_layout.addRow("", self._preserve_wcs_check)

        self._preserve_header_check = QCheckBox("Preserve header")
        self._preserve_header_check.setChecked(True)
        fits_layout.addRow("", self._preserve_header_check)

        layout.addWidget(self._fits_group)

        # Button row
        button_layout = QHBoxLayout()
        button_layout.addStretch()

        save_btn = QPushButton("Save")
        save_btn.clicked.connect(self._save)
        button_layout.addWidget(save_btn)

        cancel_btn = QPushButton("Cancel")
        cancel_btn.clicked.connect(self.reject)
        button_layout.addWidget(cancel_btn)

        layout.addLayout(button_layout)

    def _browse_save_location(self) -> None:
        """Open save file dialog."""
        format_text = self._format_combo.currentText()
        extensions = {
            "FITS": "FITS Files (*.fits *.fit)",
            "PNG": "PNG Files (*.png)",
            "JPEG": "JPEG Files (*.jpg *.jpeg)",
            "TIFF": "TIFF Files (*.tiff *.tif)",
            "PDF": "PDF Files (*.pdf)",
        }
        file_path, _ = QFileDialog.getSaveFileName(
            self,
            "Save File",
            "",
            extensions.get(format_text, "All Files (*)"),
        )
        if file_path:
            self._path_edit.setText(file_path)

    def _on_format_changed(self, format_text: str) -> None:
        """Handle format selection change.

        Args:
            format_text: Selected format.
        """
        is_fits = format_text == "FITS"
        self._fits_group.setVisible(is_fits)
        self._quality_spin.setEnabled(format_text in ("JPEG", "PNG"))

    def _save(self) -> None:
        """Save the file."""
        path = self._path_edit.text()
        if path:
            self.file_saved.emit(path, self._format_combo.currentText())
            self.accept()

    def get_save_path(self) -> str:
        """Get the save path.

        Returns:
            Save file path.
        """
        return self._path_edit.text()

    def get_format(self) -> str:
        """Get the selected format.

        Returns:
            Selected format string.
        """
        return self._format_combo.currentText()
