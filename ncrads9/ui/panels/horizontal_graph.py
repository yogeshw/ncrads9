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


import numpy as np
from numpy.typing import NDArray
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QColor, QPainter, QPainterPath, QPen
from PyQt6.QtWidgets import (
    QLabel,
    QVBoxLayout,
    QWidget,
)

from ...analysis.cut_graph import GraphSettings, cut, scaled

#: How many grid cells across and down, when DS9's grid is on.
GRID_DIVISIONS = 4


class HorizontalGraphWidget(QWidget):
    """Widget for displaying horizontal pixel profile graph."""

    def __init__(self, parent: QWidget | None = None) -> None:
        """Initialize the graph widget."""
        super().__init__(parent)
        self._data: NDArray[np.float64] | None = None
        self._cursor_x: int | None = None
        #: The grid and log settings, shared with the panel that owns this.
        self.settings = GraphSettings()
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

    def _draw_grid(self, painter: QPainter, margin: int, width: int, height: int) -> None:
        """Draw DS9's grid: four lines each way behind the curve."""
        painter.setPen(QPen(QColor(70, 70, 70), 1, Qt.PenStyle.DotLine))
        for step in range(1, GRID_DIVISIONS):
            fraction = step / GRID_DIVISIONS
            y = int(height - margin - fraction * (height - 2 * margin))
            painter.drawLine(margin, y, width - margin, y)
            x = int(margin + fraction * (width - 2 * margin))
            painter.drawLine(x, margin, x, height - margin)

    def paintEvent(self, event: object | None) -> None:
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

        # 0..1 against the cut's own range, on a log axis when asked
        # for; a value the axis cannot show comes back NaN and is drawn
        # as a gap rather than as zero.
        fractions = scaled(self._data, self.settings.log)
        x_scale = (width - 2 * margin) / len(self._data)
        plot_height = height - 2 * margin

        if self.settings.grid:
            self._draw_grid(painter, margin, width, height)

        # Draw axes
        painter.setPen(QPen(QColor(100, 100, 100), 1))
        painter.drawLine(margin, height - margin, width - margin, height - margin)
        painter.drawLine(margin, margin, margin, height - margin)

        # Draw data line
        painter.setPen(QPen(QColor(0, 200, 255), 2))
        path = QPainterPath()

        started = False
        for i, fraction in enumerate(fractions):
            if np.isnan(fraction):
                started = False
                continue
            x = margin + i * x_scale
            y = height - margin - fraction * plot_height
            if not started:
                path.moveTo(x, y)
                started = True
            else:
                path.lineTo(x, y)

        painter.drawPath(path)

        # Draw cursor position line
        if self._cursor_x is not None and 0 <= self._cursor_x < len(self._data):
            painter.setPen(QPen(QColor(255, 100, 100), 1, Qt.PenStyle.DashLine))
            x = margin + self._cursor_x * x_scale
            painter.drawLine(int(x), margin, int(x), height - margin)

        painter.end()


class HorizontalGraph(QWidget):
    """Panel showing pixel values along horizontal line."""

    def __init__(self, parent: QWidget | None = None) -> None:
        """
        Initialize the horizontal graph panel.

        Args:
            parent: Parent widget.
        """
        super().__init__(parent)
        self.setObjectName("HorizontalGraph")

        self._current_image: NDArray[np.float64] | None = None
        self._current_y: int = 0
        #: The column the cursor is in, kept so a changed setting can
        #: re-cut without waiting for the pointer to move again.
        self._current_x: int = 0
        #: DS9's Graph menu, which the `graph` access point sets.
        self.settings = GraphSettings()

        self._setup_ui()

    def _setup_ui(self) -> None:
        """Set up the user interface."""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        # Info label
        self._info_label = QLabel("Y: ---")
        layout.addWidget(self._info_label)

        # Graph widget
        self._graph_widget = HorizontalGraphWidget()
        self._graph_widget.settings = self.settings
        layout.addWidget(self._graph_widget)
        self._apply_size()

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

        values = cut(self._current_image, "horizontal", iy, self.settings)
        if values is None:
            self._info_label.setText("Y: ---")
            return
        self._current_y = iy
        self._graph_widget.set_data(values, ix)
        self._info_label.setText(self._describe(iy))

    def _describe(self, index: int) -> str:
        """The label above the graph: where the cut is, and how thick."""
        if self.settings.thickness > 1:
            return f"Y: {index} ({self.settings.thickness} {self.settings.method})"
        return f"Y: {index}"

    def _apply_size(self) -> None:
        """Fix the across-the-cut dimension to DS9's `graph size`."""
        self.setFixedHeight(self.settings.size)

    def _redraw(self) -> None:
        """Re-cut and repaint after a setting changed."""
        self.update_cursor_position(self._current_x, self._current_y)
        self._graph_widget.update()

    def set_grid(self, shown: bool) -> None:
        """Draw grid lines behind the curve, DS9's `graph grid`."""
        self.settings.grid = bool(shown)
        self._graph_widget.update()

    def set_log(self, log: bool) -> None:
        """Draw the value axis logarithmically, DS9's `graph log`."""
        self.settings.log = bool(log)
        self._graph_widget.update()

    def set_method(self, method: str) -> None:
        """Average or sum a thick cut, DS9's `graph method`.

        Raises:
            ValueError: If the method is neither.
        """
        if method not in ("average", "sum"):
            raise ValueError(f"a cut is averaged or summed, not {method!r}")
        self.settings.method = method
        self._redraw()

    def set_thickness(self, thickness: int) -> None:
        """How many rows or columns the cut covers, DS9's `graph thickness`."""
        self.settings.with_thickness(thickness)
        self._redraw()

    def set_size(self, size: int) -> None:
        """How big the panel is, DS9's `graph size`."""
        self.settings.with_size(size)
        self._apply_size()
