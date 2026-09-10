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
from PyQt6.QtGui import QBrush, QColor, QFont, QPainter, QPen, QPolygonF

from .base_region import BaseRegion
from .shapes.annulus import Annulus
from .shapes.box import Box
from .shapes.box_annulus import BoxAnnulus
from .shapes.bpanda import Bpanda
from .shapes.circle import Circle
from .shapes.compass import Compass
from .shapes.composite import Composite
from .shapes.ellipse import Ellipse
from .shapes.ellipse_annulus import EllipseAnnulus
from .shapes.epanda import Epanda
from .shapes.line import Line
from .shapes.panda import Panda
from .shapes.point import Point
from .shapes.polygon import Polygon
from .shapes.projection import Projection
from .shapes.ruler import Ruler
from .shapes.segment import Segment
from .shapes.text import Text
from .shapes.vector import Vector

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

#: How far past a region's own extent its rotate handle sits, in pixels.
ROTATE_OFFSET = 14.0


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


#: How opaque a filled region is, out of 255. Translucent so the data
#: underneath stays readable, which is the point of an overlay.
FILL_ALPHA = 60

#: `RegionMode` values previewed as a circle swept from the centre. Plain
#: strings, because the renderer must not depend on the UI layer.
PREVIEW_RADIUS: frozenset[str] = frozenset(
    {"circle", "annulus", "ellipseannulus", "boxannulus", "panda", "epanda", "bpanda", "compass"}
)

#: `RegionMode` values previewed as a straight line between two points.
PREVIEW_ENDPOINT: frozenset[str] = frozenset({"line", "vector", "ruler", "projection"})

#: `RegionMode` values previewed as the open path through every vertex.
PREVIEW_VERTEX: frozenset[str] = frozenset({"polygon", "segment"})

#: The diagonal DS9 strikes through an excluded region.
EXCLUSION_COLOR = QColor(255, 0, 0)
EXCLUSION_SIZE = 8.0

#: Half-length of the cross drawn for a shape with no outline.
CENTRE_TICK = 4.0

#: A vector's arrow head, in widget pixels and radians.
ARROW_LENGTH = 10.0
ARROW_SPREAD = math.radians(25.0)


def _steps(inner: float, outer: float, count: int) -> list[float]:
    """`count` evenly spaced radii from inner to outer, both included."""
    if count < 1:
        return [inner, outer]
    return [inner + (outer - inner) * index / count for index in range(count + 1)]


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

    @staticmethod
    def _fixed_transform(region: BaseRegion, to_widget: ToWidget) -> ToWidget:
        """A transform that places the region but does not scale it.

        The centre still goes where the image says; everything measured from
        it is treated as widget pixels, so a `fixed` region is the same size
        on screen however far the image is zoomed.
        """
        origin = to_widget(*region.center)
        cx, cy = region.center

        def transform(x: float, y: float) -> QPointF:
            # Screen y grows downward where image y grows up, so the offset
            # is negated to keep a fixed shape the right way up.
            return QPointF(origin.x() + (x - cx), origin.y() - (y - cy))

        return transform

    def brush_for(self, region: BaseRegion) -> QBrush:
        """The brush for a region, honouring DS9's `fill` property.

        DS9 fills a closed shape with its own colour when `fill=1`. The fill
        is translucent here so the data underneath stays readable, which is
        the point of drawing a region over an image at all.
        """
        if not getattr(region, "fill", False):
            return QBrush(Qt.BrushStyle.NoBrush)
        color = QColor(resolve_color(region.color))
        color.setAlpha(FILL_ALPHA)
        return QBrush(color)

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
        """Draw one region, its label, and its handles if selected.

        A region marked `fixed` keeps its size on the screen rather than in
        the image, so it stays legible at any zoom -- DS9's "fixed in size".
        That is done by drawing it through a transform that ignores the
        zoom, which is why `to_widget` is replaced rather than every shape
        being told about the property.
        """
        if getattr(region, "fixed", False):
            to_widget = self._fixed_transform(region, to_widget)

        painter.setPen(self.pen_for(region))
        painter.setBrush(self.brush_for(region))
        self._draw_shape(painter, region, to_widget)
        painter.setBrush(Qt.BrushStyle.NoBrush)

        if not region.include:
            # DS9 strikes an excluded region through, so include and exclude
            # can be told apart at a glance.
            self._draw_exclusion(painter, region, to_widget)

        # A Text region *is* its label, drawn by `_draw_shape`; drawing
        # `region.text` as well put the same string on the canvas twice.
        if self.show_labels and region.text and not isinstance(region, Text):
            self._draw_label(painter, region, to_widget)

        if getattr(region, "selected", False):
            self._draw_handles(painter, region, to_widget)
            self._draw_rotate_handle(painter, region, to_widget)

    def _draw_exclusion(
        self,
        painter: QPainter,
        region: BaseRegion,
        to_widget: ToWidget,
    ) -> None:
        """Strike a diagonal through an excluded region, as DS9 does."""
        center = to_widget(*region.center)
        pen = QPen(EXCLUSION_COLOR, max(1, region.width))
        painter.save()
        painter.setPen(pen)
        painter.drawLine(
            QPointF(center.x() - EXCLUSION_SIZE, center.y() + EXCLUSION_SIZE),
            QPointF(center.x() + EXCLUSION_SIZE, center.y() - EXCLUSION_SIZE),
        )
        painter.restore()

    def _draw_centre_tick(self, painter: QPainter, center: QPointF) -> None:
        """A small cross, for a shape with no outline of its own."""
        painter.drawLine(
            QPointF(center.x() - CENTRE_TICK, center.y()),
            QPointF(center.x() + CENTRE_TICK, center.y()),
        )
        painter.drawLine(
            QPointF(center.x(), center.y() - CENTRE_TICK),
            QPointF(center.x(), center.y() + CENTRE_TICK),
        )

    def _draw_panda(self, painter: QPainter, region: Panda, to_widget: ToWidget) -> None:
        """A panda: concentric circles crossed by radial spokes."""
        radii = _steps(region.inner_radius, region.outer_radius, region.num_radii)
        for radius in radii:
            painter.drawEllipse(
                to_widget(*region.center), *self._radii(region.center, radius, radius, to_widget)
            )
        self._draw_spokes(
            painter,
            region.center,
            region.start_angle,
            region.stop_angle,
            region.num_angles,
            region.inner_radius,
            region.outer_radius,
            0.0,
            to_widget,
        )

    def _draw_panda_variant(self, painter: QPainter, region: Epanda | Bpanda, to_widget: ToWidget) -> None:
        """An epanda or a bpanda: the same, with elliptical or box annuli."""
        majors = _steps(region.inner_major, region.outer_major, region.num_radii)
        minors = _steps(region.inner_minor, region.outer_minor, region.num_radii)
        box = type(region).__name__.lower().startswith("b")
        for major, minor in zip(majors, minors, strict=True):
            if box:
                self._draw_rotated_box(painter, region.center, major * 2, minor * 2, region.angle, to_widget)
            else:
                self._draw_rotated_ellipse(painter, region.center, major, minor, region.angle, to_widget)
        self._draw_spokes(
            painter,
            region.center,
            region.start_angle,
            region.stop_angle,
            region.num_angles,
            min(region.inner_major, region.inner_minor),
            max(region.outer_major, region.outer_minor),
            region.angle,
            to_widget,
        )

    def _draw_spokes(
        self,
        painter: QPainter,
        center: tuple[float, float],
        start: float,
        stop: float,
        count: int,
        inner: float,
        outer: float,
        rotation: float,
        to_widget: ToWidget,
    ) -> None:
        """The radial dividers between a panda's wedges."""
        if count < 1:
            return
        span = stop - start
        # A full circle's first and last spoke coincide, so one is dropped.
        edges = count if abs(span) >= 360.0 else count + 1
        cx, cy = center
        for index in range(edges):
            angle = math.radians(rotation + start + span * index / count)
            painter.drawLine(
                to_widget(cx + inner * math.cos(angle), cy + inner * math.sin(angle)),
                to_widget(cx + outer * math.cos(angle), cy + outer * math.sin(angle)),
            )

    def _draw_vector(self, painter: QPainter, region: Vector, to_widget: ToWidget) -> None:
        """A line with an arrow head, if the vector asks for one."""
        cx, cy = region.start
        angle = math.radians(region.angle)
        tip = (cx + region.length * math.cos(angle), cy + region.length * math.sin(angle))
        start, end = to_widget(cx, cy), to_widget(*tip)
        painter.drawLine(start, end)
        if not getattr(region, "arrow", True):
            return

        # The head is drawn in widget space, so it stays the same size at
        # any zoom -- which is what makes it readable when zoomed out.
        screen_angle = math.atan2(end.y() - start.y(), end.x() - start.x())
        for side in (-1, 1):
            wing = screen_angle + side * ARROW_SPREAD
            painter.drawLine(
                end,
                QPointF(
                    end.x() - ARROW_LENGTH * math.cos(wing),
                    end.y() - ARROW_LENGTH * math.sin(wing),
                ),
            )

    def _draw_projection_rails(self, painter: QPainter, region: Projection, to_widget: ToWidget) -> None:
        """The two rails marking a projection's width."""
        (x1, y1), (x2, y2) = region.start, region.end
        length = math.hypot(x2 - x1, y2 - y1)
        if length <= 0:
            return
        half = region.projection_width / 2.0
        nx, ny = -(y2 - y1) / length * half, (x2 - x1) / length * half
        for sign in (-1, 1):
            painter.drawLine(
                to_widget(x1 + sign * nx, y1 + sign * ny),
                to_widget(x2 + sign * nx, y2 + sign * ny),
            )

    def _draw_compass(self, painter: QPainter, region: Compass, to_widget: ToWidget) -> None:
        """Two labelled arms, north and east."""
        cx, cy = region.center
        origin = to_widget(cx, cy)
        for angle, label in (
            (region.north_angle, "N"),
            (region.east_angle, "E"),
        ):
            radians = math.radians(angle)
            tip = to_widget(
                cx + region.length * math.cos(radians),
                cy + region.length * math.sin(radians),
            )
            painter.drawLine(origin, tip)
            painter.drawText(QPointF(tip.x() + 2, tip.y() - 2), label)

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

        elif isinstance(region, Segment):
            if len(region.points) >= 2:
                # An open path: a polyline, not a polygon.
                painter.drawPolyline(QPolygonF([to_widget(x, y) for x, y in region.points]))

        elif isinstance(region, Annulus):
            for radius in (region.inner_radius, region.outer_radius):
                painter.drawEllipse(
                    to_widget(*region.center), *self._radii(region.center, radius, radius, to_widget)
                )

        elif isinstance(region, EllipseAnnulus):
            for major, minor in (
                (region.inner_semi_major, region.inner_semi_minor),
                (region.outer_semi_major, region.outer_semi_minor),
            ):
                self._draw_rotated_ellipse(painter, region.center, major, minor, region.angle, to_widget)

        elif isinstance(region, BoxAnnulus):
            for width, height in (
                (region.inner_width, region.inner_height),
                (region.outer_width, region.outer_height),
            ):
                self._draw_rotated_box(painter, region.center, width, height, region.angle, to_widget)

        elif isinstance(region, Panda):
            self._draw_panda(painter, region, to_widget)

        elif isinstance(region, (Epanda, Bpanda)):
            self._draw_panda_variant(painter, region, to_widget)

        elif isinstance(region, Vector):
            self._draw_vector(painter, region, to_widget)

        elif isinstance(region, (Ruler, Projection)):
            # Both are a line between two points; the projection adds its
            # width as a pair of rails.
            start, end = to_widget(*region.start), to_widget(*region.end)
            painter.drawLine(start, end)
            if isinstance(region, Projection):
                self._draw_projection_rails(painter, region, to_widget)

        elif isinstance(region, Compass):
            self._draw_compass(painter, region, to_widget)

        elif isinstance(region, Composite):
            # A composite is drawn by its children; a cross marks its origin
            # so an empty one is still visible and selectable.
            self._draw_centre_tick(painter, to_widget(*region.center))

        else:
            # Anything with no painter of its own gets a centre tick, so a
            # shape added later is visible before it is drawn properly.
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
        """A region's control points, in image coordinates.

        Dragging one of these is how a region is resized, so every shape
        needs them: a shape that returns only its centre can be moved but
        never reshaped. What a drag then means depends on the shape --
        `RegionOverlay` moves a vertex for a polygon, an end for a line, and
        scales everything else about its centre.
        """
        if isinstance(region, Polygon):
            return list(region.vertices)
        if isinstance(region, Segment):
            return list(region.points)
        if isinstance(region, (Line, Ruler, Projection)):
            return [region.start, region.end]
        if isinstance(region, Vector):
            angle = math.radians(region.angle)
            x, y = region.start
            return [
                (x, y),
                (x + region.length * math.cos(angle), y + region.length * math.sin(angle)),
            ]
        if isinstance(region, Circle):
            cx, cy = region.center
            return [(cx + region.radius, cy)]
        if isinstance(region, Annulus):
            cx, cy = region.center
            return [(cx + region.inner_radius, cy), (cx + region.outer_radius, cy)]
        if isinstance(region, Compass):
            cx, cy = region.center
            return [(cx + region.length, cy)]
        if isinstance(region, Ellipse):
            cx, cy = region.center
            return [(cx + region.semi_major, cy), (cx, cy + region.semi_minor)]
        if isinstance(region, EllipseAnnulus):
            cx, cy = region.center
            return [
                (cx + region.inner_semi_major, cy),
                (cx + region.outer_semi_major, cy),
                (cx, cy + region.outer_semi_minor),
            ]
        if isinstance(region, Panda):
            cx, cy = region.center
            return [(cx + region.inner_radius, cy), (cx + region.outer_radius, cy)]
        if isinstance(region, (Epanda, Bpanda)):
            cx, cy = region.center
            return [
                (cx + region.inner_major, cy),
                (cx + region.outer_major, cy),
                (cx, cy + region.outer_minor),
            ]
        if isinstance(region, BoxAnnulus):
            cx, cy = region.center
            return [
                (cx + region.inner_width / 2.0, cy),
                (cx + region.outer_width / 2.0, cy),
                (cx, cy + region.outer_height / 2.0),
            ]
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

    @staticmethod
    def rotate_handle(region: BaseRegion) -> tuple[float, float] | None:
        """Where a selected region's rotate handle sits, if it has one.

        Only the shapes with an angle of their own get one, and only when
        `rotate=1`: offering a handle that cannot turn the shape is worse
        than offering none. It sits `ROTATE_OFFSET` beyond the topmost
        resize handle so the two cannot be grabbed by mistake.
        """
        if not hasattr(region, "angle") or not getattr(region, "can_rotate", True):
            return None
        cx, cy = region.center
        reach = max(
            (abs(y - cy) for _x, y in RegionRenderer.handle_points(region)),
            default=0.0,
        )
        return (cx, cy + reach + ROTATE_OFFSET)

    def _draw_rotate_handle(self, painter: QPainter, region: BaseRegion, to_widget: ToWidget) -> None:
        """Draw the rotate handle as a circle, so it reads as not-a-corner."""
        point = self.rotate_handle(region)
        if point is None:
            return
        painter.save()
        painter.setPen(QPen(SELECTION_COLOR, 1))
        painter.setBrush(Qt.BrushStyle.NoBrush)
        centre = to_widget(*point)
        painter.drawLine(to_widget(*region.center), centre)
        painter.drawEllipse(centre, HANDLE_SIZE / 2, HANDLE_SIZE / 2)
        painter.restore()

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

        if mode in PREVIEW_VERTEX and len(widget_points) >= 2:
            painter.drawPolyline(QPolygonF(widget_points))
            return
        if len(widget_points) < 2:
            return

        first, second = widget_points[0], widget_points[1]
        if mode in PREVIEW_RADIUS:
            # Every shape drawn outwards from a centre previews as the circle
            # the drag sweeps out: the outer bound of whatever it becomes.
            radius = math.hypot(second.x() - first.x(), second.y() - first.y())
            painter.drawEllipse(first, radius, radius)
        elif mode == "box":
            painter.drawRect(QRectF(first, second))
        elif mode == "ellipse":
            painter.drawEllipse(QRectF(first, second))
        elif mode in PREVIEW_ENDPOINT:
            painter.drawLine(first, second)
