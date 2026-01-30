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
Smoothing parameters dialog.

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
    QLabel,
)


class SmoothDialog(QDialog):
    """Dialog for configuring image smoothing parameters."""

    smoothing_changed = pyqtSignal(dict)

    def __init__(self, parent: Optional[QDialog] = None) -> None:
        """Initialize the smooth dialog.

        Args:
            parent: Parent widget.
        """
        super().__init__(parent)
        self.setWindowTitle("Smoothing Parameters")
        self.setMinimumWidth(350)
        self._setup_ui()

    def _setup_ui(self) -> None:
        """Set up the dialog UI."""
        layout = QVBoxLayout(self)

        # Kernel settings
        kernel_group = QGroupBox("Kernel")
        kernel_layout = QFormLayout(kernel_group)

        self._kernel_combo = QComboBox()
        self._kernel_combo.addItems(["Gaussian", "Boxcar", "Tophat", "Median"])
        self._kernel_combo.currentTextChanged.connect(self._on_kernel_changed)
        kernel_layout.addRow("Type:", self._kernel_combo)

        self._sigma_spin = QDoubleSpinBox()
        self._sigma_spin.setRange(0.1, 100.0)
        self._sigma_spin.setValue(2.0)
        self._sigma_spin.setDecimals(2)
        self._sigma_spin.setSingleStep(0.5)
        kernel_layout.addRow("Sigma (pixels):", self._sigma_spin)

        self._kernel_size_spin = QDoubleSpinBox()
        self._kernel_size_spin.setRange(1, 101)
        self._kernel_size_spin.setValue(5)
        self._kernel_size_spin.setSingleStep(2)
        kernel_layout.addRow("Kernel size:", self._kernel_size_spin)

        layout.addWidget(kernel_group)

        # Elliptical kernel options
        self._ellipse_group = QGroupBox("Elliptical Kernel")
        ellipse_layout = QFormLayout(self._ellipse_group)

        self._elliptical_check = QCheckBox("Use elliptical kernel")
        ellipse_layout.addRow("", self._elliptical_check)

        self._ratio_spin = QDoubleSpinBox()
        self._ratio_spin.setRange(0.1, 10.0)
        self._ratio_spin.setValue(1.0)
        self._ratio_spin.setDecimals(2)
        ellipse_layout.addRow("Axis ratio:", self._ratio_spin)

        self._angle_spin = QDoubleSpinBox()
        self._angle_spin.setRange(0.0, 180.0)
        self._angle_spin.setValue(0.0)
        self._angle_spin.setDecimals(1)
        self._angle_spin.setSuffix(" deg")
        ellipse_layout.addRow("Position angle:", self._angle_spin)

        layout.addWidget(self._ellipse_group)

        # Options
        options_group = QGroupBox("Options")
        options_layout = QFormLayout(options_group)

        self._preserve_nan_check = QCheckBox("Preserve NaN values")
        self._preserve_nan_check.setChecked(True)
        options_layout.addRow("", self._preserve_nan_check)

        self._normalize_check = QCheckBox("Normalize kernel")
        self._normalize_check.setChecked(True)
        options_layout.addRow("", self._normalize_check)

        layout.addWidget(options_group)

        # Info label
        self._info_label = QLabel()
        self._update_info()
        layout.addWidget(self._info_label)

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

    def _on_kernel_changed(self, kernel_type: str) -> None:
        """Handle kernel type change.

        Args:
            kernel_type: Selected kernel type.
        """
        is_gaussian = kernel_type == "Gaussian"
        self._sigma_spin.setEnabled(is_gaussian)
        self._ellipse_group.setEnabled(is_gaussian)
        self._update_info()

    def _update_info(self) -> None:
        """Update the info label."""
        kernel = self._kernel_combo.currentText()
        if kernel == "Gaussian":
            self._info_label.setText("Gaussian smoothing with specified sigma.")
        elif kernel == "Boxcar":
            self._info_label.setText("Simple box average (mean filter).")
        elif kernel == "Tophat":
            self._info_label.setText("Circular tophat smoothing kernel.")
        elif kernel == "Median":
            self._info_label.setText("Median filter (good for noise reduction).")

    def _get_settings(self) -> dict:
        """Get current smoothing settings.

        Returns:
            Dictionary of smoothing settings.
        """
        return {
            "kernel_type": self._kernel_combo.currentText(),
            "sigma": self._sigma_spin.value(),
            "kernel_size": int(self._kernel_size_spin.value()),
            "elliptical": self._elliptical_check.isChecked(),
            "axis_ratio": self._ratio_spin.value(),
            "position_angle": self._angle_spin.value(),
            "preserve_nan": self._preserve_nan_check.isChecked(),
            "normalize": self._normalize_check.isChecked(),
        }

    def _apply(self) -> None:
        """Apply current settings."""
        self.smoothing_changed.emit(self._get_settings())

    def _ok(self) -> None:
        """Apply settings and close dialog."""
        self._apply()
        self.accept()
