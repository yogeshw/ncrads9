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
Scale parameters dialog.

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
    QSlider,
)
from PyQt6.QtCore import Qt


class ScaleDialog(QDialog):
    """Dialog for configuring image scaling parameters."""

    scale_changed = pyqtSignal(dict)

    def __init__(self, parent: Optional[QDialog] = None) -> None:
        """Initialize the scale dialog.

        Args:
            parent: Parent widget.
        """
        super().__init__(parent)
        self.setWindowTitle("Scale Parameters")
        self.setMinimumWidth(400)
        self._setup_ui()

    def _setup_ui(self) -> None:
        """Set up the dialog UI."""
        layout = QVBoxLayout(self)

        # Scale function
        scale_group = QGroupBox("Scale Function")
        scale_layout = QFormLayout(scale_group)

        self._scale_combo = QComboBox()
        self._scale_combo.addItems([
            "Linear",
            "Log",
            "Power",
            "Sqrt",
            "Squared",
            "Asinh",
            "Sinh",
            "Histogram Equalization",
        ])
        self._scale_combo.currentTextChanged.connect(self._on_scale_changed)
        scale_layout.addRow("Function:", self._scale_combo)

        self._exponent_spin = QDoubleSpinBox()
        self._exponent_spin.setRange(0.01, 10.0)
        self._exponent_spin.setValue(2.0)
        self._exponent_spin.setDecimals(2)
        self._exponent_spin.setEnabled(False)
        scale_layout.addRow("Exponent:", self._exponent_spin)

        self._asinh_a_spin = QDoubleSpinBox()
        self._asinh_a_spin.setRange(0.001, 1.0)
        self._asinh_a_spin.setValue(0.1)
        self._asinh_a_spin.setDecimals(4)
        self._asinh_a_spin.setEnabled(False)
        scale_layout.addRow("Asinh 'a' parameter:", self._asinh_a_spin)

        layout.addWidget(scale_group)

        # Limits
        limits_group = QGroupBox("Scale Limits")
        limits_layout = QFormLayout(limits_group)

        self._auto_limits_check = QCheckBox("Auto-calculate limits")
        self._auto_limits_check.setChecked(True)
        self._auto_limits_check.stateChanged.connect(self._on_auto_limits_changed)
        limits_layout.addRow("", self._auto_limits_check)

        self._min_spin = QDoubleSpinBox()
        self._min_spin.setRange(-1e20, 1e20)
        self._min_spin.setDecimals(6)
        self._min_spin.setEnabled(False)
        limits_layout.addRow("Minimum:", self._min_spin)

        self._max_spin = QDoubleSpinBox()
        self._max_spin.setRange(-1e20, 1e20)
        self._max_spin.setDecimals(6)
        self._max_spin.setEnabled(False)
        limits_layout.addRow("Maximum:", self._max_spin)

        layout.addWidget(limits_group)

        # Auto-scale options
        auto_group = QGroupBox("Auto-Scale Options")
        auto_layout = QFormLayout(auto_group)

        self._clip_combo = QComboBox()
        self._clip_combo.addItems([
            "MinMax",
            "ZScale",
            "Percentile",
            "Sigma Clip",
        ])
        self._clip_combo.currentTextChanged.connect(self._on_clip_changed)
        auto_layout.addRow("Algorithm:", self._clip_combo)

        self._percentile_low_spin = QDoubleSpinBox()
        self._percentile_low_spin.setRange(0.0, 50.0)
        self._percentile_low_spin.setValue(0.25)
        self._percentile_low_spin.setDecimals(2)
        self._percentile_low_spin.setSuffix(" %")
        auto_layout.addRow("Low percentile:", self._percentile_low_spin)

        self._percentile_high_spin = QDoubleSpinBox()
        self._percentile_high_spin.setRange(50.0, 100.0)
        self._percentile_high_spin.setValue(99.75)
        self._percentile_high_spin.setDecimals(2)
        self._percentile_high_spin.setSuffix(" %")
        auto_layout.addRow("High percentile:", self._percentile_high_spin)

        self._sigma_spin = QDoubleSpinBox()
        self._sigma_spin.setRange(0.5, 10.0)
        self._sigma_spin.setValue(3.0)
        self._sigma_spin.setDecimals(1)
        auto_layout.addRow("Sigma:", self._sigma_spin)

        layout.addWidget(auto_group)

        # Contrast/Bias sliders
        adjust_group = QGroupBox("Contrast/Bias")
        adjust_layout = QFormLayout(adjust_group)

        self._contrast_slider = QSlider(Qt.Orientation.Horizontal)
        self._contrast_slider.setRange(0, 100)
        self._contrast_slider.setValue(50)
        adjust_layout.addRow("Contrast:", self._contrast_slider)

        self._bias_slider = QSlider(Qt.Orientation.Horizontal)
        self._bias_slider.setRange(0, 100)
        self._bias_slider.setValue(50)
        adjust_layout.addRow("Bias:", self._bias_slider)

        reset_btn = QPushButton("Reset")
        reset_btn.clicked.connect(self._reset_sliders)
        adjust_layout.addRow("", reset_btn)

        layout.addWidget(adjust_group)

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

    def _on_scale_changed(self, scale: str) -> None:
        """Handle scale function change.

        Args:
            scale: Selected scale function.
        """
        self._exponent_spin.setEnabled(scale == "Power")
        self._asinh_a_spin.setEnabled(scale in ("Asinh", "Sinh"))

    def _on_auto_limits_changed(self, state: int) -> None:
        """Handle auto limits checkbox change.

        Args:
            state: Checkbox state.
        """
        manual = state == 0
        self._min_spin.setEnabled(manual)
        self._max_spin.setEnabled(manual)

    def _on_clip_changed(self, clip: str) -> None:
        """Handle clip algorithm change.

        Args:
            clip: Selected clip algorithm.
        """
        is_percentile = clip == "Percentile"
        is_sigma = clip == "Sigma Clip"
        self._percentile_low_spin.setEnabled(is_percentile)
        self._percentile_high_spin.setEnabled(is_percentile)
        self._sigma_spin.setEnabled(is_sigma)

    def _reset_sliders(self) -> None:
        """Reset contrast and bias sliders to default."""
        self._contrast_slider.setValue(50)
        self._bias_slider.setValue(50)

    def _get_settings(self) -> dict:
        """Get current scale settings.

        Returns:
            Dictionary of scale settings.
        """
        return {
            "scale_function": self._scale_combo.currentText(),
            "exponent": self._exponent_spin.value(),
            "asinh_a": self._asinh_a_spin.value(),
            "auto_limits": self._auto_limits_check.isChecked(),
            "min_value": self._min_spin.value(),
            "max_value": self._max_spin.value(),
            "clip_algorithm": self._clip_combo.currentText(),
            "percentile_low": self._percentile_low_spin.value(),
            "percentile_high": self._percentile_high_spin.value(),
            "sigma": self._sigma_spin.value(),
            "contrast": self._contrast_slider.value() / 50.0,
            "bias": self._bias_slider.value() / 50.0,
        }

    def _apply(self) -> None:
        """Apply current settings."""
        self.scale_changed.emit(self._get_settings())

    def _ok(self) -> None:
        """Apply settings and close dialog."""
        self._apply()
        self.accept()
