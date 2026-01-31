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

from typing import Optional, List, Dict, Any

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
    QFileDialog,
)
from PyQt6.QtGui import QColor


class ContourDialog(QDialog):
    """Dialog for configuring contour overlay settings."""

    contours_changed = pyqtSignal(dict)
    contours_export_requested = pyqtSignal(dict)

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

        self._sigma_check = QCheckBox("Use sigma levels")
        self._sigma_check.toggled.connect(self._on_sigma_changed)
        level_layout.addRow("", self._sigma_check)

        self._sigma_levels_edit = QLineEdit()
        self._sigma_levels_edit.setPlaceholderText("e.g., 3, 5, 10, 20")
        self._sigma_levels_edit.setEnabled(False)
        level_layout.addRow("Sigma levels:", self._sigma_levels_edit)

        self._sigma_base_combo = QComboBox()
        self._sigma_base_combo.addItems(["Median", "Mean"])
        self._sigma_base_combo.setEnabled(False)
        level_layout.addRow("Sigma base:", self._sigma_base_combo)

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
        self._smooth_check.toggled.connect(lambda checked: self._smooth_sigma_spin.setEnabled(checked))
        appearance_layout.addRow("", self._smooth_check)

        self._smooth_sigma_spin = QDoubleSpinBox()
        self._smooth_sigma_spin.setRange(0.1, 10.0)
        self._smooth_sigma_spin.setSingleStep(0.1)
        self._smooth_sigma_spin.setValue(1.0)
        self._smooth_sigma_spin.setEnabled(False)
        appearance_layout.addRow("Smooth sigma:", self._smooth_sigma_spin)

        self._labels_check = QCheckBox("Show labels")
        appearance_layout.addRow("", self._labels_check)

        layout.addWidget(appearance_group)

        # Button row
        button_layout = QHBoxLayout()
        button_layout.addStretch()

        export_btn = QPushButton("Export...")
        export_btn.clicked.connect(self._export)
        button_layout.addWidget(export_btn)

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

    def _on_sigma_changed(self, checked: bool) -> None:
        self._sigma_levels_edit.setEnabled(checked)
        self._sigma_base_combo.setEnabled(checked)

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
            "use_sigma": self._sigma_check.isChecked(),
            "sigma_levels": self._parse_sigma_levels(),
            "sigma_base": self._sigma_base_combo.currentText(),
            "color": self._contour_color.name(),
            "line_width": self._line_width_spin.value(),
            "line_style": self._line_style_combo.currentText(),
            "smooth": self._smooth_check.isChecked(),
            "smooth_sigma": self._smooth_sigma_spin.value(),
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

    def _parse_sigma_levels(self) -> List[float]:
        text = self._sigma_levels_edit.text()
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

    def _export(self) -> None:
        """Request contour export."""
        self.contours_export_requested.emit(self._get_settings())

    def load_settings(self, settings: Dict[str, Any]) -> None:
        """Load settings into the dialog."""
        if "method" in settings:
            self._method_combo.setCurrentText(settings["method"])
        if "num_levels" in settings:
            self._num_levels_spin.setValue(settings["num_levels"])
        if "min_level" in settings:
            self._min_level_spin.setValue(settings["min_level"])
        if "max_level" in settings:
            self._max_level_spin.setValue(settings["max_level"])
        if "custom_levels" in settings:
            self._custom_levels_edit.setText(", ".join(str(x) for x in settings["custom_levels"]))
        if "use_sigma" in settings:
            self._sigma_check.setChecked(settings["use_sigma"])
            self._on_sigma_changed(settings["use_sigma"])
        if "sigma_levels" in settings:
            self._sigma_levels_edit.setText(", ".join(str(x) for x in settings["sigma_levels"]))
        if "sigma_base" in settings:
            self._sigma_base_combo.setCurrentText(settings["sigma_base"])
        if "color" in settings:
            self._contour_color = QColor(settings["color"])
            self._update_color_button()
        if "line_width" in settings:
            self._line_width_spin.setValue(settings["line_width"])
        if "line_style" in settings:
            self._line_style_combo.setCurrentText(settings["line_style"])
        if "smooth" in settings:
            self._smooth_check.setChecked(settings["smooth"])
        if "smooth_sigma" in settings:
            self._smooth_sigma_spin.setValue(settings["smooth_sigma"])
        if "show_labels" in settings:
            self._labels_check.setChecked(settings["show_labels"])
