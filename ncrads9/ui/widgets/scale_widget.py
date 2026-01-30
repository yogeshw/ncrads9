# This file is part of ncrads9.
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
ScaleWidget - Widget for scale parameter input.

Author: Yogesh Wadadekar
"""

from typing import Optional

from PyQt6.QtCore import pyqtSignal
from PyQt6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QComboBox,
    QDoubleSpinBox,
    QLabel,
    QGroupBox,
)


class ScaleWidget(QWidget):
    """A widget for configuring image scale parameters."""

    scaleChanged = pyqtSignal(str, float, float)

    # Available scaling algorithms
    SCALE_TYPES = [
        "linear",
        "log",
        "sqrt",
        "squared",
        "asinh",
        "sinh",
        "histequ",
        "power",
    ]

    def __init__(
        self,
        parent: Optional[QWidget] = None,
    ) -> None:
        """
        Initialize the ScaleWidget.

        Args:
            parent: Parent widget.
        """
        super().__init__(parent)

        self._scale_type: str = "linear"
        self._low: float = 0.0
        self._high: float = 100.0

        self._setup_ui()
        self._connect_signals()

    def _setup_ui(self) -> None:
        """Set up the widget UI."""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        group = QGroupBox("Scale Parameters")
        group_layout = QVBoxLayout(group)

        # Scale type selector
        type_layout = QHBoxLayout()
        type_layout.addWidget(QLabel("Type:"))
        self._type_combo = QComboBox()
        self._type_combo.addItems(self.SCALE_TYPES)
        type_layout.addWidget(self._type_combo)
        type_layout.addStretch()
        group_layout.addLayout(type_layout)

        # Low value
        low_layout = QHBoxLayout()
        low_layout.addWidget(QLabel("Low:"))
        self._low_spinbox = QDoubleSpinBox()
        self._low_spinbox.setRange(-1e10, 1e10)
        self._low_spinbox.setDecimals(6)
        self._low_spinbox.setValue(0.0)
        low_layout.addWidget(self._low_spinbox)
        group_layout.addLayout(low_layout)

        # High value
        high_layout = QHBoxLayout()
        high_layout.addWidget(QLabel("High:"))
        self._high_spinbox = QDoubleSpinBox()
        self._high_spinbox.setRange(-1e10, 1e10)
        self._high_spinbox.setDecimals(6)
        self._high_spinbox.setValue(100.0)
        high_layout.addWidget(self._high_spinbox)
        group_layout.addLayout(high_layout)

        layout.addWidget(group)

    def _connect_signals(self) -> None:
        """Connect internal signals."""
        self._type_combo.currentTextChanged.connect(self._on_scale_changed)
        self._low_spinbox.valueChanged.connect(self._on_scale_changed)
        self._high_spinbox.valueChanged.connect(self._on_scale_changed)

    def _on_scale_changed(self) -> None:
        """Handle scale parameter change."""
        self._scale_type = self._type_combo.currentText()
        self._low = self._low_spinbox.value()
        self._high = self._high_spinbox.value()
        self.scaleChanged.emit(self._scale_type, self._low, self._high)

    def scaleType(self) -> str:
        """Get the current scale type."""
        return self._scale_type

    def setScaleType(self, scale_type: str) -> None:
        """Set the scale type."""
        if scale_type in self.SCALE_TYPES:
            self._type_combo.setCurrentText(scale_type)

    def lowValue(self) -> float:
        """Get the low scale value."""
        return self._low

    def setLowValue(self, value: float) -> None:
        """Set the low scale value."""
        self._low_spinbox.setValue(value)

    def highValue(self) -> float:
        """Get the high scale value."""
        return self._high

    def setHighValue(self, value: float) -> None:
        """Set the high scale value."""
        self._high_spinbox.setValue(value)

    def setScale(self, scale_type: str, low: float, high: float) -> None:
        """Set all scale parameters at once."""
        self.setScaleType(scale_type)
        self.setLowValue(low)
        self.setHighValue(high)
