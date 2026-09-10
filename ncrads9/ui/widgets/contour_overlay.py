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

from collections.abc import Sequence

import numpy as np
from numpy.typing import NDArray
from PyQt6.QtCore import QPointF, Qt
from PyQt6.QtGui import QColor, QFont, QPainter, QPen, QPolygonF
from PyQt6.QtWidgets import QWidget

from ...grid.grid_config import GridElement
from ...grid.grid_labels import Label, LabelPosition
from ..view_transform import DisplayTransform

#: How far an axis title sits from the edge of the widget, in pixels.
AXIS_TITLE_MARGIN = 6.0

#: How far a coordinate number sits from the edge it labels.
NUMBER_MARGIN = 4.0

#: The Qt pen style each of DS9's line styles maps to.
PEN_STYLES = {
    "solid": Qt.PenStyle.SolidLine,
    "dashed": Qt.PenStyle.DashLine,
    "dotted": Qt.PenStyle.DotLine,
}


def _color(name: str) -> QColor:
    """One of DS9's colour names as a QColor."""
    colour = QColor(name)
    return colour if colour.isValid() else QColor(255, 255, 255)


def _element_pen(element: GridElement) -> QPen:
    """The pen one grid element is drawn with."""
    pen = QPen(_color(element.color))
    pen.setWidthF(float(max(1, element.width)))
    pen.setStyle(PEN_STYLES.get(element.style, Qt.PenStyle.SolidLine))
    # A cosmetic pen keeps its width in screen pixels under any transform,
    # which is what a grid line wants: it is furniture, not data.
    pen.setCosmetic(True)
    return pen


def _element_font(element: GridElement) -> QFont:
    """The font one text element is set in."""
    font = QFont(element.font)
    font.setPointSize(int(element.font_size))
    font.setBold(element.font_weight == "bold")
    font.setItalic(element.font_slant == "italic")
    return font


def _label_point(
    label: Label,
    point: QPointF,
    metrics,
    interior: bool,
    vertical: bool,
) -> QPointF:
    """Where a coordinate number's baseline goes.

    Nudged away from its own edge so it does not sit on the border, and
    inwards or outwards per DS9's Interior/Exterior Numerics.
    """
    width = metrics.horizontalAdvance(label.text)
    height = metrics.ascent()
    away = -1.0 if interior else 1.0

    if label.position is LabelPosition.BOTTOM:
        return QPointF(point.x() - width / 2.0, point.y() + away * (height + NUMBER_MARGIN))
    if label.position is LabelPosition.TOP:
        return QPointF(point.x() - width / 2.0, point.y() - away * NUMBER_MARGIN)
    if label.position is LabelPosition.LEFT:
        offset = NUMBER_MARGIN if interior else -(width + NUMBER_MARGIN)
        return QPointF(point.x() + offset, point.y() + height / 2.0)

    offset = -(width + NUMBER_MARGIN) if interior else NUMBER_MARGIN
    if vertical:
        # DS9's Vertical Text turns the side numbers upright; without a
        # rotation the best that can be done is to keep them clear.
        offset += NUMBER_MARGIN
    return QPointF(point.x() + offset, point.y() + height / 2.0)


class ContourOverlay(QWidget):
    """Overlay widget for drawing contour paths."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
        self.setMouseTracking(False)
        self._contours: list[list[NDArray[np.float64]]] = []
        self._levels: list[float] = []
        self._zoom: float = 1.0
        self._offset: tuple[float, float] = (0.0, 0.0)
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
        self._north_vector: tuple[float, float] | None = None
        self._east_vector: tuple[float, float] | None = None
        self._grid_visible: bool = False
        #: The computed graticule, and the settings it was computed for.
        self._grid_geometry = None
        self._grid_config = None
        self._grid_spacing_x: int = 64
        self._grid_spacing_y: int = 64
        self._grid_color: QColor = QColor(128, 128, 128)
        self._grid_line_width: float = 1.0
        self._grid_show_labels: bool = True
        self._grid_label_font_size: int = 10
        self._crosshair_visible: bool = False
        self._crosshair_color: QColor = QColor(255, 0, 0)
        self._crosshair_size: int = 24
        self._crosshair_position: tuple[float, float] | None = None

    def set_zoom(
        self,
        zoom: float,
        offset: tuple[float, float],
        image_width: int | None = None,
        image_height: int | None = None,
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
        contours: list[list[NDArray[np.float64]]],
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
        north_vector: tuple[float, float] | None,
        east_vector: tuple[float, float] | None,
        visible: bool,
    ) -> None:
        """Set direction arrow vectors and visibility."""
        self._north_vector = north_vector
        self._east_vector = east_vector
        self._show_direction_arrows = visible
        self.update()

    def set_grid(self, visible: bool, settings: dict | None = None) -> None:
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
        position: tuple[float, float] | None = None,
        color: QColor | None = None,
        size: int | None = None,
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
        vector: tuple[float, float],
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

    # -- the coordinate grid (M7-10, M7-11) ----------------------------------

    def set_grid_geometry(self, geometry, config) -> None:
        """Take a computed graticule to draw.

        The geometry is worked out by `grid.GridRenderer`, which needs the
        WCS and knows nothing about widgets; this draws what it produced.
        """
        self._grid_geometry = geometry
        self._grid_config = config
        self.update()

    def _paint_grid(self, painter: QPainter) -> None:
        """Draw the coordinate grid, element by element."""
        geometry = self._grid_geometry
        config = self._grid_config
        if geometry is None or config is None:
            return

        if config.shows("grid"):
            self._paint_grid_lines(painter, geometry.lines, config.element("grid"))
        if config.shows("border"):
            self._paint_grid_lines(painter, [geometry.border], config.element("border"))
        if config.shows("tickmarks"):
            self._paint_ticks(painter, geometry, config.element("tickmarks"))
        if config.shows("numerics"):
            self._paint_numbers(painter, geometry, config)
        if config.shows("labels"):
            self._paint_axis_titles(painter, geometry, config.element("labels"))
        if config.shows("title") and config.title:
            self._paint_title(painter, config)

    def _paint_grid_lines(self, painter: QPainter, lines, element) -> None:
        """Draw one element's polylines."""
        painter.setPen(_element_pen(element))
        for line in lines:
            points = [self._image_to_widget(x, y) for x, y in line]
            if len(points) > 1:
                painter.drawPolyline(QPolygonF(points))

    def _paint_ticks(self, painter: QPainter, geometry, element) -> None:
        """Draw the tick marks where the lines meet the border."""
        painter.setPen(_element_pen(element))
        for x, y, dx, dy in geometry.ticks:
            start = self._image_to_widget(x, y)
            # The tick length is in screen pixels, so it is added after the
            # transform: a tick that scaled with the zoom would be a streak.
            painter.drawLine(start, QPointF(start.x() + dx, start.y() - dy))

    def _paint_numbers(self, painter: QPainter, geometry, config) -> None:
        """Draw the coordinate numbers along the edges."""
        element = config.element("numerics")
        painter.setPen(QPen(_color(element.color)))
        painter.setFont(_element_font(element))
        metrics = painter.fontMetrics()
        interior = config.numerics_placement.value == "interior"

        for label in geometry.labels:
            point = self._image_to_widget(label.x, label.y)
            painter.drawText(_label_point(label, point, metrics, interior, config.vertical_text), label.text)

    def _paint_axis_titles(self, painter: QPainter, geometry, element) -> None:
        """Draw the two axis titles, outside the numbers along each edge.

        Placed relative to the image's own edges rather than the widget's:
        the widget is usually larger than the image, so a title pinned to
        the bottom of the widget lands on the numbers when the image is
        small and floats away from them when it is large.
        """
        painter.setPen(QPen(_color(element.color)))
        painter.setFont(_element_font(element))
        metrics = painter.fontMetrics()

        left, top, right, bottom = self._image_edges(geometry)
        clearance = metrics.height() + 2.0 * NUMBER_MARGIN

        if geometry.x_title:
            width = metrics.horizontalAdvance(geometry.x_title)
            # Its own lane, below the numbers'. Not clamped to the widget:
            # clamping put it back on top of the numbers whenever the image
            # nearly filled the viewport, which is exactly when it matters.
            baseline = bottom + clearance + metrics.ascent()
            painter.drawText(QPointF((left + right - width) / 2.0, baseline), geometry.x_title)

        if geometry.y_title:
            # Turned on its side, as every plotting convention has it.
            width = metrics.horizontalAdvance(geometry.y_title)
            x = left - clearance
            painter.save()
            painter.translate(x, (top + bottom) / 2.0)
            painter.rotate(-90.0)
            painter.drawText(QPointF(-width / 2.0, 0.0), geometry.y_title)
            painter.restore()

    def _image_edges(self, geometry) -> tuple[float, float, float, float]:
        """The image's outline in widget pixels, as (left, top, right, bottom)."""
        points = [self._image_to_widget(x, y) for x, y in geometry.border] or [
            QPointF(0.0, 0.0),
            QPointF(float(self.width()), float(self.height())),
        ]
        xs = [point.x() for point in points]
        ys = [point.y() for point in points]
        return (min(xs), min(ys), max(xs), max(ys))

    def _paint_title(self, painter: QPainter, config) -> None:
        """Draw the grid's title across the top."""
        element = config.element("title")
        painter.setPen(QPen(_color(element.color)))
        painter.setFont(_element_font(element))
        metrics = painter.fontMetrics()
        width = metrics.horizontalAdvance(config.title)
        painter.drawText(
            QPointF((self.width() - width) / 2.0, metrics.height() + AXIS_TITLE_MARGIN),
            config.title,
        )

    def paintEvent(self, event) -> None:
        if (
            not self._contours
            and not self._grid_visible
            and not self._crosshair_visible
            and (not self._show_direction_arrows or self._north_vector is None or self._east_vector is None)
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
            self._paint_grid(painter)
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
