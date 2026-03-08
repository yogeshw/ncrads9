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

from ..view_transform import DisplayTransform


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
        self._image_width: int = 0
        self._image_height: int = 0
        self._rotation: float = 0.0
        self._flip_x: bool = False
        self._flip_y: bool = False
        self._color: QColor = QColor(0, 255, 0)
        self._line_width: float = 1.0
        self._line_style: Qt.PenStyle = Qt.PenStyle.SolidLine
        self._show_labels: bool = False
        self._show_direction_arrows: bool = True
        self._north_vector: Optional[Tuple[float, float]] = None
        self._east_vector: Optional[Tuple[float, float]] = None
        self._grid_visible: bool = False
        self._grid_spacing_x: int = 64
        self._grid_spacing_y: int = 64
        self._grid_color: QColor = QColor(128, 128, 128)
        self._grid_line_width: float = 1.0
        self._grid_show_labels: bool = True
        self._grid_label_font_size: int = 10
        self._crosshair_visible: bool = False
        self._crosshair_color: QColor = QColor(255, 0, 0)
        self._crosshair_size: int = 24
        self._crosshair_position: Optional[Tuple[float, float]] = None

    def set_zoom(
        self,
        zoom: float,
        offset: Tuple[float, float],
        image_width: Optional[int] = None,
        image_height: Optional[int] = None,
        rotation: float = 0.0,
        flip_x: bool = False,
        flip_y: bool = False,
    ) -> None:
        """Set zoom and offset for coordinate transform."""
        self._zoom = zoom
        self._offset = offset
        if image_width is not None:
            self._image_width = max(0, int(image_width))
        if image_height is not None:
            self._image_height = max(0, int(image_height))
        self._rotation = rotation
        self._flip_x = flip_x
        self._flip_y = flip_y
        self.update()

    def _display_transform(self) -> DisplayTransform:
        return DisplayTransform(
            width=self._image_width,
            height=self._image_height,
            rotation=self._rotation,
            flip_x=self._flip_x,
            flip_y=self._flip_y,
        )

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

    def set_grid(self, visible: bool, settings: Optional[dict] = None) -> None:
        """Set pixel grid overlay visibility and style settings."""
        self._grid_visible = visible
        if settings is not None:
            auto_spacing = bool(settings.get("auto_spacing", True))
            if auto_spacing:
                width = max(1, self._image_width)
                height = max(1, self._image_height)
                self._grid_spacing_x = max(8, width // 8)
                self._grid_spacing_y = max(8, height // 8)
            else:
                self._grid_spacing_x = max(2, int(float(settings.get("ra_spacing", 1.0)) * 20))
                self._grid_spacing_y = max(2, int(float(settings.get("dec_spacing", 1.0)) * 20))
            self._grid_color = QColor(str(settings.get("grid_color", "#808080")))
            self._grid_line_width = float(settings.get("line_width", 1.0))
            self._grid_show_labels = bool(settings.get("show_labels", True))
            self._grid_label_font_size = int(settings.get("font_size", 10))
        self.update()

    def set_crosshair(
        self,
        visible: bool,
        position: Optional[Tuple[float, float]] = None,
        color: Optional[QColor] = None,
        size: Optional[int] = None,
    ) -> None:
        """Set crosshair overlay visibility/style and optional position."""
        self._crosshair_visible = visible
        if position is not None:
            self._crosshair_position = position
        if color is not None:
            self._crosshair_color = QColor(color)
        if size is not None:
            self._crosshair_size = max(4, int(size))
        self.update()

    def _image_to_widget(self, x: float, y: float) -> QPointF:
        """Convert image coordinates (origin bottom-left) to widget coordinates."""
        if self._image_height > 0:
            source_top_y = self._image_height - 1 - y
        else:
            source_top_y = y
        display_x, display_y = self._display_transform().source_to_display(x, source_top_y)
        return QPointF(display_x * self._zoom + self._offset[0], display_y * self._zoom + self._offset[1])

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
            and not self._grid_visible
            and not self._crosshair_visible
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

        if self._grid_visible and self._image_width > 0 and self._image_height > 0:
            grid_pen = QPen(self._grid_color)
            grid_pen.setWidthF(self._grid_line_width)
            grid_pen.setStyle(Qt.PenStyle.DotLine)
            painter.setPen(grid_pen)

            x_step = max(2, self._grid_spacing_x)
            y_step = max(2, self._grid_spacing_y)
            for x in range(0, self._image_width, x_step):
                p1 = self._image_to_widget(float(x), 0.0)
                p2 = self._image_to_widget(float(x), float(self._image_height - 1))
                painter.drawLine(p1, p2)
                if self._grid_show_labels:
                    label_font.setPointSize(self._grid_label_font_size)
                    painter.setFont(label_font)
                    painter.drawText(QPointF(p1.x() + 2.0, p1.y() - 2.0), str(x))
            for y in range(0, self._image_height, y_step):
                p1 = self._image_to_widget(0.0, float(y))
                p2 = self._image_to_widget(float(self._image_width - 1), float(y))
                painter.drawLine(p1, p2)
                if self._grid_show_labels:
                    label_font.setPointSize(self._grid_label_font_size)
                    painter.setFont(label_font)
                    painter.drawText(QPointF(p1.x() + 2.0, p1.y() - 2.0), str(y))

            painter.setPen(pen)
            label_font.setPointSize(8)
            painter.setFont(label_font)

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

        if self._crosshair_visible and self._crosshair_position is not None:
            cx, cy = self._crosshair_position
            center = self._image_to_widget(cx, cy)
            cross_pen = QPen(self._crosshair_color)
            cross_pen.setWidth(1)
            painter.setPen(cross_pen)
            half_size = max(2, self._crosshair_size // 2)
            painter.drawLine(
                QPointF(center.x() - half_size, center.y()),
                QPointF(center.x() + half_size, center.y()),
            )
            painter.drawLine(
                QPointF(center.x(), center.y() - half_size),
                QPointF(center.x(), center.y() + half_size),
            )

        painter.end()
