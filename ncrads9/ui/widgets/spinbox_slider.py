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
SpinboxSlider Widget - Combined spinbox and slider control.

Author: Yogesh Wadadekar
"""

from typing import Optional

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import (
    QWidget,
    QHBoxLayout,
    QSlider,
    QDoubleSpinBox,
    QLabel,
)


class SpinboxSlider(QWidget):
    """A combined spinbox and slider widget for numeric input."""

    valueChanged = pyqtSignal(float)

    def __init__(
        self,
        label: str = "",
        minimum: float = 0.0,
        maximum: float = 100.0,
        value: float = 0.0,
        decimals: int = 2,
        parent: Optional[QWidget] = None,
    ) -> None:
        """
        Initialize the SpinboxSlider widget.

        Args:
            label: Optional label text.
            minimum: Minimum value.
            maximum: Maximum value.
            value: Initial value.
            decimals: Number of decimal places.
            parent: Parent widget.
        """
        super().__init__(parent)

        self._minimum = minimum
        self._maximum = maximum
        self._decimals = decimals
        self._updating = False

        self._setup_ui(label, minimum, maximum, value, decimals)
        self._connect_signals()

    def _setup_ui(
        self,
        label: str,
        minimum: float,
        maximum: float,
        value: float,
        decimals: int,
    ) -> None:
        """Set up the widget UI."""
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        if label:
            self._label = QLabel(label)
            layout.addWidget(self._label)

        self._slider = QSlider(Qt.Orientation.Horizontal)
        self._slider.setRange(0, 1000)
        layout.addWidget(self._slider)

        self._spinbox = QDoubleSpinBox()
        self._spinbox.setRange(minimum, maximum)
        self._spinbox.setDecimals(decimals)
        self._spinbox.setValue(value)
        layout.addWidget(self._spinbox)

        self._update_slider_from_spinbox()

    def _connect_signals(self) -> None:
        """Connect internal signals."""
        self._slider.valueChanged.connect(self._on_slider_changed)
        self._spinbox.valueChanged.connect(self._on_spinbox_changed)

    def _on_slider_changed(self, value: int) -> None:
        """Handle slider value change."""
        if self._updating:
            return
        self._updating = True
        ratio = value / 1000.0
        new_value = self._minimum + ratio * (self._maximum - self._minimum)
        self._spinbox.setValue(new_value)
        self.valueChanged.emit(new_value)
        self._updating = False

    def _on_spinbox_changed(self, value: float) -> None:
        """Handle spinbox value change."""
        if self._updating:
            return
        self._updating = True
        self._update_slider_from_spinbox()
        self.valueChanged.emit(value)
        self._updating = False

    def _update_slider_from_spinbox(self) -> None:
        """Update slider position from spinbox value."""
        value = self._spinbox.value()
        if self._maximum != self._minimum:
            ratio = (value - self._minimum) / (self._maximum - self._minimum)
            self._slider.setValue(int(ratio * 1000))

    def value(self) -> float:
        """Get the current value."""
        return self._spinbox.value()

    def setValue(self, value: float) -> None:
        """Set the current value."""
        self._spinbox.setValue(value)

    def setRange(self, minimum: float, maximum: float) -> None:
        """Set the value range."""
        self._minimum = minimum
        self._maximum = maximum
        self._spinbox.setRange(minimum, maximum)
        self._update_slider_from_spinbox()
