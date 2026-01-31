# NCRADS9 - Contour Overlay Widget
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

"""Contour overlay for drawing contour paths on images."""

from __future__ import annotations

from typing import List, Sequence, Tuple

import numpy as np
from numpy.typing import NDArray
from PyQt6.QtCore import Qt, QPointF
from PyQt6.QtGui import QPainter, QPen, QColor, QPolygonF, QFont
from PyQt6.QtWidgets import QWidget


class ContourOverlay(QWidget):
    """Overlay widget for drawing contour paths."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
        self.setMouseTracking(False)
        self._contours: List[List[NDArray[np.float64]]] = []
        self._levels: List[float] = []
        self._zoom: float = 1.0
        self._offset: Tuple[float, float] = (0.0, 0.0)
        self._color: QColor = QColor(0, 255, 0)
        self._line_width: float = 1.0
        self._line_style: Qt.PenStyle = Qt.PenStyle.SolidLine
        self._show_labels: bool = False

    def set_zoom(self, zoom: float, offset: Tuple[float, float]) -> None:
        """Set zoom and offset for coordinate transform."""
        self._zoom = zoom
        self._offset = offset
        self.update()

    def set_contours(
        self,
        contours: List[List[NDArray[np.float64]]],
        levels: Sequence[float],
    ) -> None:
        """Set contour paths and levels."""
        self._contours = contours
        self._levels = list(levels)
        self.update()

    def clear(self) -> None:
        """Clear all contours."""
        self._contours = []
        self._levels = []
        self.update()

    def set_style(
        self,
        color: QColor,
        line_width: float,
        line_style: Qt.PenStyle,
        show_labels: bool,
    ) -> None:
        """Update contour style."""
        self._color = color
        self._line_width = line_width
        self._line_style = line_style
        self._show_labels = show_labels
        self.update()

    def paintEvent(self, event) -> None:
        if not self._contours:
            return

        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)

        pen = QPen(self._color)
        pen.setWidthF(self._line_width)
        pen.setStyle(self._line_style)
        painter.setPen(pen)

        label_font = QFont()
        label_font.setPointSize(8)

        for level_index, level_paths in enumerate(self._contours):
            for path in level_paths:
                if path.size == 0:
                    continue
                if path.ndim != 2 or path.shape[1] != 2:
                    continue

                points = [
                    QPointF(
                        path[i, 0] * self._zoom + self._offset[0],
                        path[i, 1] * self._zoom + self._offset[1],
                    )
                    for i in range(path.shape[0])
                ]
                if len(points) < 2:
                    continue
                painter.drawPolyline(QPolygonF(points))

                if self._show_labels and level_index < len(self._levels):
                    mid_index = len(points) // 2
                    label_point = points[mid_index]
                    painter.setFont(label_font)
                    painter.drawText(label_point, f"{self._levels[level_index]:.4g}")

        painter.end()
