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
WCS grid configuration dialog.

Author: Yogesh Wadadekar
"""

from typing import Optional

from PyQt6.QtCore import pyqtSignal
from PyQt6.QtWidgets import (
    QDialog,
    QVBoxLayout,
    QHBoxLayout,
    QPushButton,
    QGroupBox,
    QFormLayout,
    QComboBox,
    QDoubleSpinBox,
    QCheckBox,
    QColorDialog,
    QSpinBox,
)
from PyQt6.QtGui import QColor


class GridDialog(QDialog):
    """Dialog for configuring WCS grid overlay settings."""

    grid_changed = pyqtSignal(dict)

    def __init__(self, parent: Optional[QDialog] = None) -> None:
        """Initialize the grid dialog.

        Args:
            parent: Parent widget.
        """
        super().__init__(parent)
        self.setWindowTitle("WCS Grid Settings")
        self.setMinimumWidth(400)
        self._grid_color = QColor(128, 128, 128)  # Default gray
        self._label_color = QColor(255, 255, 255)  # Default white
        self._setup_ui()

    def _setup_ui(self) -> None:
        """Set up the dialog UI."""
        layout = QVBoxLayout(self)

        # Grid type settings
        type_group = QGroupBox("Grid Type")
        type_layout = QFormLayout(type_group)

        self._coord_combo = QComboBox()
        self._coord_combo.addItems(["WCS", "Pixel", "Physical"])
        type_layout.addRow("Coordinate system:", self._coord_combo)

        self._format_combo = QComboBox()
        self._format_combo.addItems(["Sexagesimal", "Degrees", "Arcmin", "Arcsec"])
        type_layout.addRow("Label format:", self._format_combo)

        layout.addWidget(type_group)

        # Grid spacing
        spacing_group = QGroupBox("Spacing")
        spacing_layout = QFormLayout(spacing_group)

        self._auto_spacing_check = QCheckBox("Automatic spacing")
        self._auto_spacing_check.setChecked(True)
        self._auto_spacing_check.stateChanged.connect(self._on_auto_spacing_changed)
        spacing_layout.addRow("", self._auto_spacing_check)

        self._ra_spacing_spin = QDoubleSpinBox()
        self._ra_spacing_spin.setRange(0.001, 360.0)
        self._ra_spacing_spin.setValue(1.0)
        self._ra_spacing_spin.setDecimals(4)
        self._ra_spacing_spin.setSuffix(" deg")
        self._ra_spacing_spin.setEnabled(False)
        spacing_layout.addRow("RA spacing:", self._ra_spacing_spin)

        self._dec_spacing_spin = QDoubleSpinBox()
        self._dec_spacing_spin.setRange(0.001, 180.0)
        self._dec_spacing_spin.setValue(1.0)
        self._dec_spacing_spin.setDecimals(4)
        self._dec_spacing_spin.setSuffix(" deg")
        self._dec_spacing_spin.setEnabled(False)
        spacing_layout.addRow("Dec spacing:", self._dec_spacing_spin)

        layout.addWidget(spacing_group)

        # Appearance
        appearance_group = QGroupBox("Appearance")
        appearance_layout = QFormLayout(appearance_group)

        grid_color_layout = QHBoxLayout()
        self._grid_color_btn = QPushButton()
        self._grid_color_btn.setFixedSize(60, 25)
        self._update_grid_color_button()
        self._grid_color_btn.clicked.connect(self._choose_grid_color)
        grid_color_layout.addWidget(self._grid_color_btn)
        grid_color_layout.addStretch()
        appearance_layout.addRow("Grid color:", grid_color_layout)

        label_color_layout = QHBoxLayout()
        self._label_color_btn = QPushButton()
        self._label_color_btn.setFixedSize(60, 25)
        self._update_label_color_button()
        self._label_color_btn.clicked.connect(self._choose_label_color)
        label_color_layout.addWidget(self._label_color_btn)
        label_color_layout.addStretch()
        appearance_layout.addRow("Label color:", label_color_layout)

        self._line_width_spin = QDoubleSpinBox()
        self._line_width_spin.setRange(0.1, 5.0)
        self._line_width_spin.setValue(1.0)
        self._line_width_spin.setSingleStep(0.5)
        appearance_layout.addRow("Line width:", self._line_width_spin)

        self._font_size_spin = QSpinBox()
        self._font_size_spin.setRange(6, 24)
        self._font_size_spin.setValue(10)
        appearance_layout.addRow("Font size:", self._font_size_spin)

        self._show_labels_check = QCheckBox("Show labels")
        self._show_labels_check.setChecked(True)
        appearance_layout.addRow("", self._show_labels_check)

        layout.addWidget(appearance_group)

        # Button row
        button_layout = QHBoxLayout()
        button_layout.addStretch()

        apply_btn = QPushButton("Apply")
        apply_btn.clicked.connect(self._apply)
        button_layout.addWidget(apply_btn)

        ok_btn = QPushButton("OK")
        ok_btn.clicked.connect(self._ok)
        button_layout.addWidget(ok_btn)

        cancel_btn = QPushButton("Cancel")
        cancel_btn.clicked.connect(self.reject)
        button_layout.addWidget(cancel_btn)

        layout.addLayout(button_layout)

    def _on_auto_spacing_changed(self, state: int) -> None:
        """Handle auto spacing checkbox change.

        Args:
            state: Checkbox state.
        """
        manual = state == 0
        self._ra_spacing_spin.setEnabled(manual)
        self._dec_spacing_spin.setEnabled(manual)

    def _choose_grid_color(self) -> None:
        """Open color picker for grid color."""
        color = QColorDialog.getColor(self._grid_color, self, "Choose Grid Color")
        if color.isValid():
            self._grid_color = color
            self._update_grid_color_button()

    def _choose_label_color(self) -> None:
        """Open color picker for label color."""
        color = QColorDialog.getColor(self._label_color, self, "Choose Label Color")
        if color.isValid():
            self._label_color = color
            self._update_label_color_button()

    def _update_grid_color_button(self) -> None:
        """Update the grid color button appearance."""
        self._grid_color_btn.setStyleSheet(
            f"background-color: {self._grid_color.name()}; border: 1px solid black;"
        )

    def _update_label_color_button(self) -> None:
        """Update the label color button appearance."""
        self._label_color_btn.setStyleSheet(
            f"background-color: {self._label_color.name()}; border: 1px solid black;"
        )

    def _get_settings(self) -> dict:
        """Get current grid settings.

        Returns:
            Dictionary of grid settings.
        """
        return {
            "coord_system": self._coord_combo.currentText(),
            "label_format": self._format_combo.currentText(),
            "auto_spacing": self._auto_spacing_check.isChecked(),
            "ra_spacing": self._ra_spacing_spin.value(),
            "dec_spacing": self._dec_spacing_spin.value(),
            "grid_color": self._grid_color.name(),
            "label_color": self._label_color.name(),
            "line_width": self._line_width_spin.value(),
            "font_size": self._font_size_spin.value(),
            "show_labels": self._show_labels_check.isChecked(),
        }

    def _apply(self) -> None:
        """Apply current settings."""
        self.grid_changed.emit(self._get_settings())

    def _ok(self) -> None:
        """Apply settings and close dialog."""
        self._apply()
        self.accept()
