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
Contour settings dialog.

Author: Yogesh Wadadekar
"""

from typing import Optional, List

from PyQt6.QtCore import pyqtSignal
from PyQt6.QtWidgets import (
    QDialog,
    QVBoxLayout,
    QHBoxLayout,
    QPushButton,
    QGroupBox,
    QFormLayout,
    QLineEdit,
    QComboBox,
    QSpinBox,
    QDoubleSpinBox,
    QCheckBox,
    QColorDialog,
)
from PyQt6.QtGui import QColor


class ContourDialog(QDialog):
    """Dialog for configuring contour overlay settings."""

    contours_changed = pyqtSignal(dict)

    def __init__(self, parent: Optional[QDialog] = None) -> None:
        """Initialize the contour dialog.

        Args:
            parent: Parent widget.
        """
        super().__init__(parent)
        self.setWindowTitle("Contour Settings")
        self.setMinimumWidth(400)
        self._contour_color = QColor(0, 255, 0)  # Default green
        self._setup_ui()

    def _setup_ui(self) -> None:
        """Set up the dialog UI."""
        layout = QVBoxLayout(self)

        # Level settings
        level_group = QGroupBox("Contour Levels")
        level_layout = QFormLayout(level_group)

        self._method_combo = QComboBox()
        self._method_combo.addItems(["Linear", "Logarithmic", "Square Root", "Custom"])
        self._method_combo.currentTextChanged.connect(self._on_method_changed)
        level_layout.addRow("Method:", self._method_combo)

        self._num_levels_spin = QSpinBox()
        self._num_levels_spin.setRange(1, 50)
        self._num_levels_spin.setValue(10)
        level_layout.addRow("Number of levels:", self._num_levels_spin)

        self._min_level_spin = QDoubleSpinBox()
        self._min_level_spin.setDecimals(6)
        self._min_level_spin.setRange(-1e10, 1e10)
        level_layout.addRow("Minimum level:", self._min_level_spin)

        self._max_level_spin = QDoubleSpinBox()
        self._max_level_spin.setDecimals(6)
        self._max_level_spin.setRange(-1e10, 1e10)
        level_layout.addRow("Maximum level:", self._max_level_spin)

        self._custom_levels_edit = QLineEdit()
        self._custom_levels_edit.setPlaceholderText("e.g., 0.1, 0.5, 1.0, 2.0")
        self._custom_levels_edit.setEnabled(False)
        level_layout.addRow("Custom levels:", self._custom_levels_edit)

        layout.addWidget(level_group)

        # Appearance settings
        appearance_group = QGroupBox("Appearance")
        appearance_layout = QFormLayout(appearance_group)

        color_layout = QHBoxLayout()
        self._color_btn = QPushButton()
        self._color_btn.setFixedSize(60, 25)
        self._update_color_button()
        self._color_btn.clicked.connect(self._choose_color)
        color_layout.addWidget(self._color_btn)
        color_layout.addStretch()
        appearance_layout.addRow("Color:", color_layout)

        self._line_width_spin = QDoubleSpinBox()
        self._line_width_spin.setRange(0.1, 10.0)
        self._line_width_spin.setValue(1.0)
        self._line_width_spin.setSingleStep(0.5)
        appearance_layout.addRow("Line width:", self._line_width_spin)

        self._line_style_combo = QComboBox()
        self._line_style_combo.addItems(["Solid", "Dashed", "Dotted", "Dash-Dot"])
        appearance_layout.addRow("Line style:", self._line_style_combo)

        self._smooth_check = QCheckBox("Smooth contours")
        appearance_layout.addRow("", self._smooth_check)

        self._labels_check = QCheckBox("Show labels")
        appearance_layout.addRow("", self._labels_check)

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

    def _on_method_changed(self, method: str) -> None:
        """Handle method selection change.

        Args:
            method: Selected method.
        """
        is_custom = method == "Custom"
        self._custom_levels_edit.setEnabled(is_custom)
        self._num_levels_spin.setEnabled(not is_custom)

    def _choose_color(self) -> None:
        """Open color picker dialog."""
        color = QColorDialog.getColor(self._contour_color, self, "Choose Contour Color")
        if color.isValid():
            self._contour_color = color
            self._update_color_button()

    def _update_color_button(self) -> None:
        """Update the color button appearance."""
        self._color_btn.setStyleSheet(
            f"background-color: {self._contour_color.name()}; border: 1px solid black;"
        )

    def _get_settings(self) -> dict:
        """Get current contour settings.

        Returns:
            Dictionary of contour settings.
        """
        return {
            "method": self._method_combo.currentText(),
            "num_levels": self._num_levels_spin.value(),
            "min_level": self._min_level_spin.value(),
            "max_level": self._max_level_spin.value(),
            "custom_levels": self._parse_custom_levels(),
            "color": self._contour_color.name(),
            "line_width": self._line_width_spin.value(),
            "line_style": self._line_style_combo.currentText(),
            "smooth": self._smooth_check.isChecked(),
            "show_labels": self._labels_check.isChecked(),
        }

    def _parse_custom_levels(self) -> List[float]:
        """Parse custom levels from text input.

        Returns:
            List of custom level values.
        """
        text = self._custom_levels_edit.text()
        if not text:
            return []
        try:
            return [float(x.strip()) for x in text.split(",")]
        except ValueError:
            return []

    def _apply(self) -> None:
        """Apply current settings."""
        self.contours_changed.emit(self._get_settings())

    def _ok(self) -> None:
        """Apply settings and close dialog."""
        self._apply()
        self.accept()
