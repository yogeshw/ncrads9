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
ColorPicker Widget - Color selection widget.

Author: Yogesh Wadadekar
"""

from typing import Optional

from PyQt6.QtCore import pyqtSignal
from PyQt6.QtGui import QColor
from PyQt6.QtWidgets import (
    QWidget,
    QHBoxLayout,
    QPushButton,
    QLabel,
    QColorDialog,
)


class ColorPicker(QWidget):
    """A color picker widget with preview button."""

    colorChanged = pyqtSignal(QColor)

    def __init__(
        self,
        label: str = "",
        color: Optional[QColor] = None,
        parent: Optional[QWidget] = None,
    ) -> None:
        """
        Initialize the ColorPicker widget.

        Args:
            label: Optional label text.
            color: Initial color.
            parent: Parent widget.
        """
        super().__init__(parent)

        self._color = color if color is not None else QColor(255, 255, 255)
        self._setup_ui(label)
        self._connect_signals()

    def _setup_ui(self, label: str) -> None:
        """Set up the widget UI."""
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        if label:
            self._label = QLabel(label)
            layout.addWidget(self._label)

        self._color_button = QPushButton()
        self._color_button.setFixedSize(40, 25)
        self._update_button_color()
        layout.addWidget(self._color_button)

        self._hex_label = QLabel(self._color.name())
        layout.addWidget(self._hex_label)

        layout.addStretch()

    def _connect_signals(self) -> None:
        """Connect internal signals."""
        self._color_button.clicked.connect(self._on_button_clicked)

    def _on_button_clicked(self) -> None:
        """Handle color button click."""
        color = QColorDialog.getColor(
            self._color, self, "Select Color"
        )
        if color.isValid():
            self.setColor(color)

    def _update_button_color(self) -> None:
        """Update the button background color."""
        self._color_button.setStyleSheet(
            f"background-color: {self._color.name()}; border: 1px solid gray;"
        )

    def color(self) -> QColor:
        """Get the current color."""
        return self._color

    def setColor(self, color: QColor) -> None:
        """Set the current color."""
        if color != self._color:
            self._color = color
            self._update_button_color()
            self._hex_label.setText(color.name())
            self.colorChanged.emit(color)

    def hexColor(self) -> str:
        """Get the color as a hex string."""
        return self._color.name()

    def setHexColor(self, hex_color: str) -> None:
        """Set the color from a hex string."""
        color = QColor(hex_color)
        if color.isValid():
            self.setColor(color)
