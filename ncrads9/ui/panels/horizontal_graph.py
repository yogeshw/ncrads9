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
Horizontal graph panel showing pixel values along a horizontal line.

Author: Yogesh Wadadekar
"""

from typing import Optional

import numpy as np
from numpy.typing import NDArray
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QPainter, QPen, QColor, QPainterPath
from PyQt6.QtWidgets import (
    QDockWidget,
    QWidget,
    QVBoxLayout,
    QLabel,
)


class HorizontalGraphWidget(QWidget):
    """Widget for displaying horizontal pixel profile graph."""

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        """Initialize the graph widget."""
        super().__init__(parent)
        self._data: Optional[NDArray[np.float64]] = None
        self._cursor_x: Optional[int] = None
        self.setMinimumSize(200, 100)

    def set_data(self, data: NDArray[np.float64], cursor_x: int) -> None:
        """
        Set the data to display.

        Args:
            data: 1D array of pixel values.
            cursor_x: Current cursor X position.
        """
        self._data = data
        self._cursor_x = cursor_x
        self.update()

    def paintEvent(self, event: Optional[object]) -> None:
        """Paint the graph."""
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        # Background
        painter.fillRect(self.rect(), QColor(30, 30, 30))

        if self._data is None or len(self._data) == 0:
            painter.end()
            return

        width = self.width()
        height = self.height()
        margin = 10

        # Calculate scaling
        data_min = np.nanmin(self._data)
        data_max = np.nanmax(self._data)
        data_range = data_max - data_min if data_max > data_min else 1.0

        x_scale = (width - 2 * margin) / len(self._data)
        y_scale = (height - 2 * margin) / data_range

        # Draw axes
        painter.setPen(QPen(QColor(100, 100, 100), 1))
        painter.drawLine(margin, height - margin, width - margin, height - margin)
        painter.drawLine(margin, margin, margin, height - margin)

        # Draw data line
        painter.setPen(QPen(QColor(0, 200, 255), 2))
        path = QPainterPath()

        for i, value in enumerate(self._data):
            if np.isnan(value):
                continue
            x = margin + i * x_scale
            y = height - margin - (value - data_min) * y_scale

            if i == 0 or np.isnan(self._data[i - 1]):
                path.moveTo(x, y)
            else:
                path.lineTo(x, y)

        painter.drawPath(path)

        # Draw cursor position line
        if self._cursor_x is not None and 0 <= self._cursor_x < len(self._data):
            painter.setPen(QPen(QColor(255, 100, 100), 1, Qt.PenStyle.DashLine))
            x = margin + self._cursor_x * x_scale
            painter.drawLine(int(x), margin, int(x), height - margin)

        painter.end()


class HorizontalGraph(QDockWidget):
    """Dockable panel showing pixel values along horizontal line."""

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        """
        Initialize the horizontal graph panel.

        Args:
            parent: Parent widget.
        """
        super().__init__("Horizontal Profile", parent)
        self.setObjectName("HorizontalGraph")

        self._current_image: Optional[NDArray[np.float64]] = None
        self._current_y: int = 0

        self._setup_ui()

    def _setup_ui(self) -> None:
        """Set up the user interface."""
        container = QWidget()
        layout = QVBoxLayout(container)

        # Info label
        self._info_label = QLabel("Y: ---")
        layout.addWidget(self._info_label)

        # Graph widget
        self._graph_widget = HorizontalGraphWidget()
        layout.addWidget(self._graph_widget)

        self.setWidget(container)

    def set_image(self, image: NDArray[np.float64]) -> None:
        """
        Set the image data.

        Args:
            image: 2D numpy array of image data.
        """
        self._current_image = image

    def update_cursor_position(self, x: float, y: float) -> None:
        """
        Update the graph for current cursor position.

        Args:
            x: X coordinate in image pixels.
            y: Y coordinate in image pixels.
        """
        if self._current_image is None:
            return

        iy = int(y)
        ix = int(x)
        h, w = self._current_image.shape[:2]

        if 0 <= iy < h:
            self._current_y = iy
            row_data = self._current_image[iy, :]
            self._graph_widget.set_data(row_data, ix)
            self._info_label.setText(f"Y: {iy}")
        else:
            self._info_label.setText("Y: ---")
