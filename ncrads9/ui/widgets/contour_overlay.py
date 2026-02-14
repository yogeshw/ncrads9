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

from typing import List, Optional, Sequence, Tuple

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
        self._image_height: int = 0
        self._color: QColor = QColor(0, 255, 0)
        self._line_width: float = 1.0
        self._line_style: Qt.PenStyle = Qt.PenStyle.SolidLine
        self._show_labels: bool = False
        self._show_direction_arrows: bool = True
        self._north_vector: Optional[Tuple[float, float]] = None
        self._east_vector: Optional[Tuple[float, float]] = None

    def set_zoom(
        self,
        zoom: float,
        offset: Tuple[float, float],
        image_height: Optional[int] = None,
    ) -> None:
        """Set zoom and offset for coordinate transform."""
        self._zoom = zoom
        self._offset = offset
        if image_height is not None:
            self._image_height = max(0, int(image_height))
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

    def set_direction_arrows(
        self,
        north_vector: Optional[Tuple[float, float]],
        east_vector: Optional[Tuple[float, float]],
        visible: bool,
    ) -> None:
        """Set direction arrow vectors and visibility."""
        self._north_vector = north_vector
        self._east_vector = east_vector
        self._show_direction_arrows = visible
        self.update()

    def _image_to_widget(self, x: float, y: float) -> QPointF:
        """Convert image coordinates (origin bottom-left) to widget coordinates."""
        if self._image_height > 0:
            top_y = self._image_height - 1 - y
        else:
            top_y = y
        return QPointF(x * self._zoom + self._offset[0], top_y * self._zoom + self._offset[1])

    def _draw_direction_arrow(
        self,
        painter: QPainter,
        anchor: QPointF,
        vector: Tuple[float, float],
        label: str,
    ) -> None:
        """Draw one direction arrow from a screen-space anchor."""
        vx, vy = vector
        svx, svy = vx, -vy  # convert image y-up to widget y-down
        norm = float(np.hypot(svx, svy))
        if norm < 1e-9:
            return
        ux, uy = svx / norm, svy / norm
        length = 28.0
        end = QPointF(anchor.x() + ux * length, anchor.y() + uy * length)
        painter.drawLine(anchor, end)
        arrow_size = 6.0
        px, py = -uy, ux
        p1 = QPointF(end.x() - ux * arrow_size + px * 3.0, end.y() - uy * arrow_size + py * 3.0)
        p2 = QPointF(end.x() - ux * arrow_size - px * 3.0, end.y() - uy * arrow_size - py * 3.0)
        painter.drawLine(end, p1)
        painter.drawLine(end, p2)
        painter.drawText(QPointF(end.x() + px * 8.0, end.y() + py * 8.0), label)

    def paintEvent(self, event) -> None:
        if (
            not self._contours
            and (
                not self._show_direction_arrows
                or self._north_vector is None
                or self._east_vector is None
            )
        ):
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

                points = [self._image_to_widget(path[i, 0], path[i, 1]) for i in range(path.shape[0])]
                if len(points) < 2:
                    continue
                painter.drawPolyline(QPolygonF(points))

                if self._show_labels and level_index < len(self._levels):
                    mid_index = len(points) // 2
                    label_point = points[mid_index]
                    painter.setFont(label_font)
                    painter.drawText(label_point, f"{self._levels[level_index]:.4g}")

        if self._show_direction_arrows and self._north_vector is not None and self._east_vector is not None:
            arrow_pen = QPen(QColor(255, 220, 0))
            arrow_pen.setWidth(2)
            painter.setPen(arrow_pen)
            painter.setFont(label_font)
            anchor = QPointF(self.width() - 40.0, self.height() - 30.0)
            self._draw_direction_arrow(painter, anchor, self._north_vector, "N")
            self._draw_direction_arrow(painter, anchor, self._east_vector, "E")

        painter.end()
