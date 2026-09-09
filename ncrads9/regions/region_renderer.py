# NCRADS9 - NCRA DS9 Viewer
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
Painting for region shapes.

Regions are held in image coordinates; painting happens in widget
coordinates. Callers pass a ``to_widget`` callable that maps one image point
to one widget point, so this module needs to know nothing about zoom, pan,
rotation or flips -- the overlay owns that transform.

Shapes are dispatched by type rather than by asking the shape to draw itself:
``BaseRegion.draw()`` would have to know about Qt, which would drag Qt into
the region model. Keeping the painting here lets the model stay pure and
gives M6's twenty shapes a single place to grow.

Author: Yogesh Wadadekar
"""

from __future__ import annotations

import math
from collections.abc import Callable, Iterable, Sequence

from PyQt6.QtCore import QPointF, QRectF, Qt
from PyQt6.QtGui import QColor, QFont, QPainter, QPen, QPolygonF

from .base_region import BaseRegion
from .shapes.box import Box
from .shapes.circle import Circle
from .shapes.ellipse import Ellipse
from .shapes.line import Line
from .shapes.point import Point
from .shapes.polygon import Polygon
from .shapes.text import Text

#: Maps one image-coordinate point to one widget-coordinate point.
ToWidget = Callable[[float, float], QPointF]

#: DS9's region colour names. Anything Qt understands also works.
DS9_COLORS: dict[str, QColor] = {
    "black": QColor(0, 0, 0),
    "white": QColor(255, 255, 255),
    "red": QColor(255, 0, 0),
    "green": QColor(0, 255, 0),
    "blue": QColor(0, 0, 255),
    "cyan": QColor(0, 255, 255),
    "magenta": QColor(255, 0, 255),
    "yellow": QColor(255, 255, 0),
}

#: Colour used to outline the selected region, matching DS9's highlight.
SELECTION_COLOR = QColor(255, 255, 0)

#: Side length, in widget pixels, of a selection handle.
HANDLE_SIZE = 6


def resolve_color(name: str) -> QColor:
    """Return a QColor for a DS9 colour name, falling back to green."""
    lowered = (name or "").strip().lower()
    if lowered in DS9_COLORS:
        return DS9_COLORS[lowered]
    color = QColor(name)
    return color if color.isValid() else DS9_COLORS["green"]


def parse_font(spec: str) -> QFont:
    """Parse a DS9 font spec, e.g. ``helvetica 10 normal roman``."""
    parts = (spec or "").split()
    font = QFont(parts[0] if parts else "Helvetica")
    if len(parts) > 1:
        try:
            font.setPointSize(int(parts[1]))
        except ValueError:
            pass
    if "bold" in parts:
        font.setBold(True)
    if "italic" in parts:
        font.setItalic(True)
    return font


class RegionRenderer:
    """Draws regions and in-progress previews onto a QPainter."""

    def __init__(self, show_labels: bool = True, antialiasing: bool = True) -> None:
        """
        Args:
            show_labels: Draw each region's text label.
            antialiasing: Enable antialiased outlines.
        """
        self.show_labels = show_labels
        self.antialiasing = antialiasing

    # -- pens ---------------------------------------------------------------

    def pen_for(self, region: BaseRegion) -> QPen:
        """Build the pen for a region, honouring selection, width and dash."""
        selected = getattr(region, "selected", False)
        color = SELECTION_COLOR if selected else resolve_color(region.color)
        pen = QPen(color, max(1, region.width) + (1 if selected else 0))
        if getattr(region, "dash", False):
            pen.setStyle(Qt.PenStyle.DashLine)
        return pen

    @staticmethod
    def preview_pen() -> QPen:
        """Pen for the dashed shape that follows the cursor while drawing."""
        return QPen(SELECTION_COLOR, 1, Qt.PenStyle.DashLine)

    # -- whole-list rendering ----------------------------------------------

    def render(
        self,
        painter: QPainter,
        regions: Iterable[BaseRegion],
        to_widget: ToWidget,
    ) -> None:
        """Draw every region, then the selection handles on top."""
        if self.antialiasing:
            painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        for region in regions:
            self.render_region(painter, region, to_widget)

    def render_region(
        self,
        painter: QPainter,
        region: BaseRegion,
        to_widget: ToWidget,
    ) -> None:
        """Draw one region, its label, and its handles if selected."""
        painter.setPen(self.pen_for(region))
        self._draw_shape(painter, region, to_widget)

        if self.show_labels and region.text:
            self._draw_label(painter, region, to_widget)

        if getattr(region, "selected", False):
            self._draw_handles(painter, region, to_widget)

    # -- per-shape painting -------------------------------------------------

    def _draw_shape(
        self,
        painter: QPainter,
        region: BaseRegion,
        to_widget: ToWidget,
    ) -> None:
        """Dispatch to the right primitive for this shape type.

        Radii are measured along +x in image space and transformed, so the
        drawn size tracks zoom. A rotated or flipped display leaves circles
        circular, which is correct: DS9 draws a circle of radius r as a circle
        whatever the display orientation.
        """
        if isinstance(region, Circle):
            center = to_widget(*region.center)
            painter.drawEllipse(center, *self._radii(region.center, region.radius, region.radius, to_widget))

        elif isinstance(region, Ellipse):
            self._draw_rotated_ellipse(
                painter,
                region.center,
                region.semi_major,
                region.semi_minor,
                region.angle,
                to_widget,
            )

        elif isinstance(region, Box):
            self._draw_rotated_box(
                painter,
                region.center,
                region.width_box,
                region.height_box,
                region.angle,
                to_widget,
            )

        elif isinstance(region, Polygon):
            if len(region.vertices) >= 2:
                painter.drawPolygon(QPolygonF([to_widget(x, y) for x, y in region.vertices]))

        elif isinstance(region, Line):
            painter.drawLine(to_widget(*region.start), to_widget(*region.end))

        elif isinstance(region, Point):
            self._draw_point(painter, region, to_widget)

        elif isinstance(region, Text):
            painter.setFont(parse_font(region.font))
            painter.drawText(to_widget(*region.center), region.label)

        else:
            # Shapes without a painter yet (annulus, panda, ruler, ...) get a
            # centre tick so they are at least visible. M6 draws them properly.
            center = to_widget(*region.center)
            painter.drawLine(
                QPointF(center.x() - 4, center.y()),
                QPointF(center.x() + 4, center.y()),
            )
            painter.drawLine(
                QPointF(center.x(), center.y() - 4),
                QPointF(center.x(), center.y() + 4),
            )

    @staticmethod
    def _radii(
        center: tuple[float, float],
        rx_image: float,
        ry_image: float,
        to_widget: ToWidget,
    ) -> tuple[float, float]:
        """Convert image-space radii to widget-space radii."""
        origin = to_widget(*center)
        along_x = to_widget(center[0] + rx_image, center[1])
        along_y = to_widget(center[0], center[1] + ry_image)
        rx = math.hypot(along_x.x() - origin.x(), along_x.y() - origin.y())
        ry = math.hypot(along_y.x() - origin.x(), along_y.y() - origin.y())
        return rx, ry

    def _draw_rotated_ellipse(
        self,
        painter: QPainter,
        center: tuple[float, float],
        semi_major: float,
        semi_minor: float,
        angle: float,
        to_widget: ToWidget,
    ) -> None:
        """Draw an ellipse, rotating the painter when the shape is rotated."""
        widget_center = to_widget(*center)
        rx, ry = self._radii(center, semi_major, semi_minor, to_widget)
        if angle:
            painter.save()
            painter.translate(widget_center)
            painter.rotate(-angle)
            painter.drawEllipse(QPointF(0, 0), rx, ry)
            painter.restore()
        else:
            painter.drawEllipse(widget_center, rx, ry)

    def _draw_rotated_box(
        self,
        painter: QPainter,
        center: tuple[float, float],
        width_box: float,
        height_box: float,
        angle: float,
        to_widget: ToWidget,
    ) -> None:
        """Draw a box, rotating the painter when the shape is rotated."""
        widget_center = to_widget(*center)
        half_w, half_h = self._radii(center, width_box / 2.0, height_box / 2.0, to_widget)
        rect = QRectF(-half_w, -half_h, half_w * 2, half_h * 2)
        painter.save()
        painter.translate(widget_center)
        if angle:
            painter.rotate(-angle)
        painter.drawRect(rect)
        painter.restore()

    @staticmethod
    def _draw_point(painter: QPainter, region: Point, to_widget: ToWidget) -> None:
        """Draw a point marker in DS9's glyph for its shape.

        Point size is in *screen* pixels in DS9, not image pixels, so it is
        not passed through ``to_widget``.
        """
        center = to_widget(*region.center)
        half = max(1.0, region.size / 2.0)
        shape = (region.shape or "circle").lower()

        if shape == "circle":
            painter.drawEllipse(center, half, half)
        elif shape == "box":
            painter.drawRect(QRectF(center.x() - half, center.y() - half, half * 2, half * 2))
        elif shape == "diamond":
            painter.drawPolygon(
                QPolygonF(
                    [
                        QPointF(center.x(), center.y() - half),
                        QPointF(center.x() + half, center.y()),
                        QPointF(center.x(), center.y() + half),
                        QPointF(center.x() - half, center.y()),
                    ]
                )
            )
        elif shape == "cross":
            painter.drawLine(QPointF(center.x() - half, center.y()), QPointF(center.x() + half, center.y()))
            painter.drawLine(QPointF(center.x(), center.y() - half), QPointF(center.x(), center.y() + half))
        elif shape == "x":
            painter.drawLine(
                QPointF(center.x() - half, center.y() - half),
                QPointF(center.x() + half, center.y() + half),
            )
            painter.drawLine(
                QPointF(center.x() - half, center.y() + half),
                QPointF(center.x() + half, center.y() - half),
            )
        elif shape == "boxcircle":
            painter.drawRect(QRectF(center.x() - half, center.y() - half, half * 2, half * 2))
            painter.drawEllipse(center, half * 0.7, half * 0.7)
        elif shape == "arrow":
            painter.drawLine(QPointF(center.x(), center.y() + half), center)
            painter.drawPolygon(
                QPolygonF(
                    [
                        center,
                        QPointF(center.x() - half * 0.5, center.y() + half * 0.5),
                        QPointF(center.x() + half * 0.5, center.y() + half * 0.5),
                    ]
                )
            )
        else:
            painter.drawEllipse(center, half, half)

    # -- decorations --------------------------------------------------------

    def _draw_label(self, painter: QPainter, region: BaseRegion, to_widget: ToWidget) -> None:
        """Draw a region's text label just above its centre."""
        painter.save()
        painter.setFont(parse_font(region.font))
        center = to_widget(*region.center)
        painter.drawText(QPointF(center.x() + HANDLE_SIZE, center.y() - HANDLE_SIZE), region.text)
        painter.restore()

    def _draw_handles(self, painter: QPainter, region: BaseRegion, to_widget: ToWidget) -> None:
        """Draw square handles at a selected region's control points."""
        painter.save()
        painter.setPen(QPen(SELECTION_COLOR, 1))
        painter.setBrush(SELECTION_COLOR)
        for x, y in self.handle_points(region):
            widget = to_widget(x, y)
            painter.drawRect(
                QRectF(
                    widget.x() - HANDLE_SIZE / 2,
                    widget.y() - HANDLE_SIZE / 2,
                    HANDLE_SIZE,
                    HANDLE_SIZE,
                )
            )
        painter.restore()

    @staticmethod
    def handle_points(region: BaseRegion) -> Sequence[tuple[float, float]]:
        """Return a region's control points, in image coordinates.

        M6 makes these draggable; for now they only indicate selection.
        """
        if isinstance(region, Polygon):
            return list(region.vertices)
        if isinstance(region, Line):
            return [region.start, region.end]
        if isinstance(region, Circle):
            cx, cy = region.center
            return [(cx + region.radius, cy)]
        if isinstance(region, Ellipse):
            cx, cy = region.center
            return [(cx + region.semi_major, cy), (cx, cy + region.semi_minor)]
        if isinstance(region, Box):
            cx, cy = region.center
            half_w, half_h = region.width_box / 2.0, region.height_box / 2.0
            return [
                (cx - half_w, cy - half_h),
                (cx + half_w, cy - half_h),
                (cx + half_w, cy + half_h),
                (cx - half_w, cy + half_h),
            ]
        return [region.center]

    # -- drawing preview ----------------------------------------------------

    def render_preview(
        self,
        painter: QPainter,
        mode: str,
        image_points: Sequence[tuple[float, float]],
        to_widget: ToWidget,
    ) -> None:
        """Draw the dashed outline that follows the cursor while drawing.

        ``mode`` is a `RegionMode` value; it is taken as a plain string so
        this module does not depend on the UI layer.
        """
        if not image_points:
            return

        painter.setPen(self.preview_pen())
        widget_points = [to_widget(x, y) for x, y in image_points]

        if mode == "circle" and len(widget_points) >= 2:
            center, edge = widget_points[0], widget_points[1]
            radius = math.hypot(edge.x() - center.x(), edge.y() - center.y())
            painter.drawEllipse(center, radius, radius)
        elif mode == "box" and len(widget_points) >= 2:
            painter.drawRect(QRectF(widget_points[0], widget_points[1]))
        elif mode == "ellipse" and len(widget_points) >= 2:
            painter.drawEllipse(QRectF(widget_points[0], widget_points[1]))
        elif mode == "polygon" and len(widget_points) >= 2:
            painter.drawPolyline(QPolygonF(widget_points))
        elif mode == "line" and len(widget_points) >= 2:
            painter.drawLine(widget_points[0], widget_points[1])
