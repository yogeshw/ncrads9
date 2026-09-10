# NCRADS9 - NCRA DS9-like FITS Viewer
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
The illustrate layer, drawn.

No coordinate transform of any kind: an illustration is placed on the canvas
and stays where it was put, so its coordinates are already this widget's.
That is what separates it from the region, catalogue and contour overlays,
all three of which live in image coordinates and follow the data around.

Like the catalogue overlay, this one is transparent to the mouse. Only the
region overlay takes mouse events -- a Qt event a child ignores goes to its
parent rather than to a sibling, so a second overlay accepting clicks would
starve the first -- and it hands presses here through `handle_event`.

Author: Yogesh Wadadekar
"""

from __future__ import annotations

import math
from pathlib import Path

from PyQt6.QtCore import QPointF, QRectF, Qt
from PyQt6.QtGui import (
    QColor,
    QFont,
    QImage,
    QPainter,
    QPen,
    QPixmap,
    QPolygonF,
)
from PyQt6.QtWidgets import QWidget

from ...illustrate.elements import (
    Box,
    Circle,
    Element,
    Ellipse,
    Image,
    Line,
    Polygon,
    Text,
)
from ...illustrate.layer import IllustrateLayer

#: The colour a selected element's handles are drawn in.
HANDLE_COLOR = QColor(255, 255, 255)

#: How big a handle is, in pixels.
HANDLE_SIZE = 6

#: DS9's dash pattern for a dashed element (`illustrate.tcl:29`).
DASH_PATTERN = (8.0, 3.0)

#: How long an arrowhead is and how wide it spreads.
ARROW_LENGTH = 12.0
ARROW_SPREAD = math.radians(20.0)

#: How far a click may be from where a drag began and still be a click.
CLICK_SLOP = 3.0


class IllustrateOverlay(QWidget):
    """Draws the illustrate layer and edits it with the mouse."""

    def __init__(self, layer: IllustrateLayer | None = None, parent: QWidget | None = None) -> None:
        """
        Args:
            layer: The layer to draw. One is made if none is given.
            parent: The viewer this sits over.
        """
        super().__init__(parent)
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
        self.setAttribute(Qt.WidgetAttribute.WA_NoSystemBackground, True)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        #: What is drawn.
        self.layer = layer if layer is not None else IllustrateLayer()
        #: Whether presses reach the layer at all; off outside the mode.
        self.editing = False
        #: Called with an element when one is picked, so the controller can
        #: keep its dialog on the right one.
        self.on_selected = None

        self._drag_from: tuple[float, float] | None = None
        self._drag_last: tuple[float, float] | None = None
        self._resizing: tuple[Element, int] | None = None
        self._pixmaps: dict[str, QPixmap] = {}

    # -- the mouse ----------------------------------------------------------------

    def handle_event(self, phase: str, point: QPointF, button: str = "left") -> bool:
        """One mouse event from the region overlay.

        Args:
            phase: "press", "move" or "release".
            point: Where, in this widget's coordinates.
            button: Which button, for a press.

        Returns:
            Whether the layer used it. A press that hits nothing is not
            used, so the click reaches the viewer and pans as usual.
        """
        if not self.editing or button != "left":
            return False
        x, y = point.x(), point.y()
        if phase == "press":
            return self._press(x, y)
        if phase == "move":
            return self._move(x, y)
        return self._release(x, y)

    def _press(self, x: float, y: float) -> bool:
        """Grab a handle, pick an element, or start a new one."""
        grabbed = self.layer.handle_at(x, y)
        if grabbed is not None:
            self._resizing = grabbed
            self._drag_from = (x, y)
            self._drag_last = (x, y)
            return True

        found = self.layer.at(x, y)
        self.layer.select_only(found)
        self._resizing = None
        self._drag_from = (x, y)
        self._drag_last = (x, y)
        self.update()
        if found is not None and callable(self.on_selected):
            self.on_selected(found)
        # A press on bare canvas is still ours: releasing there makes a new
        # element, which is how the Shape menu's choice gets used.
        return True

    def _move(self, x: float, y: float) -> bool:
        """Reshape or move whatever the press grabbed."""
        if self._drag_last is None:
            return False
        if self._resizing is not None:
            element, handle = self._resizing
            element.resize(handle, x, y)
        elif self.layer.selection():
            self.layer.move_selection(x - self._drag_last[0], y - self._drag_last[1])
        else:
            # An empty drag draws the new element's extent.
            self._drag_last = (x, y)
            self.update()
            return True
        self._drag_last = (x, y)
        self.update()
        return True

    def _release(self, x: float, y: float) -> bool:
        """Finish the gesture, making a new element if that is what it was."""
        start = self._drag_from
        self._drag_from = None
        self._drag_last = None
        resizing, self._resizing = self._resizing, None
        if start is None:
            return False
        if resizing is not None or self.layer.selection():
            self.update()
            return True

        made = self._create(start, (x, y))
        self.layer.select_only(made)
        self.update()
        if callable(self.on_selected):
            self.on_selected(made)
        return True

    def _create(self, start: tuple[float, float], end: tuple[float, float]) -> Element:
        """A new element of the chosen shape from a click or a drag."""
        (x0, y0), (x1, y1) = start, end
        dragged = math.hypot(x1 - x0, y1 - y0) > CLICK_SLOP
        shape = self.layer.shape
        centre = ((x0 + x1) / 2.0, (y0 + y1) / 2.0) if dragged else (x0, y0)

        if not dragged:
            return self.layer.create(shape, centre[0], centre[1])

        half_w = max(1.0, abs(x1 - x0) / 2.0)
        half_h = max(1.0, abs(y1 - y0) / 2.0)
        if shape == "circle":
            return self.layer.create(shape, centre[0], centre[1], radius=max(half_w, half_h))
        if shape in ("ellipse", "box"):
            return self.layer.create(shape, centre[0], centre[1], radius1=half_w, radius2=half_h)
        if shape == "line":
            return self.layer.create(shape, centre[0], centre[1], points=[(x0, y0), (x1, y1)])
        if shape == "polygon":
            return self.layer.create(
                shape,
                centre[0],
                centre[1],
                points=[(x0, y0), (x1, y0), (x1, y1), (x0, y1)],
            )
        return self.layer.create(shape, centre[0], centre[1])

    # -- drawing --------------------------------------------------------------------

    def paintEvent(self, event) -> None:
        """Draw every element, then the selection's handles."""
        if not self.layer.visible or not self.layer.elements:
            return
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        for element in self.layer.elements:
            self._draw(painter, element)
        for element in self.layer.selection():
            self._draw_handles(painter, element)
        if self._drag_from is not None and self._drag_last is not None and not self.layer.selection():
            self._draw_band(painter)
        painter.end()

    def _pen(self, element: Element) -> QPen:
        """The pen one element is drawn with."""
        pen = QPen(QColor(element.style.color))
        pen.setWidthF(max(1.0, float(element.style.width)))
        if element.style.dash:
            pen.setStyle(Qt.PenStyle.CustomDashLine)
            pen.setDashPattern(list(DASH_PATTERN))
        return pen

    def _draw(self, painter: QPainter, element: Element) -> None:
        """Draw one element."""
        painter.setPen(self._pen(element))
        colour = QColor(element.style.color)
        painter.setBrush(colour if element.style.fill else Qt.BrushStyle.NoBrush)

        if isinstance(element, Circle):
            painter.drawEllipse(QPointF(element.x, element.y), element.radius, element.radius)
        elif isinstance(element, Ellipse):
            painter.drawEllipse(QPointF(element.x, element.y), element.radius1, element.radius2)
        elif isinstance(element, Box):
            x0, y0, x1, y1 = element.bounds()
            painter.drawRect(QRectF(x0, y0, x1 - x0, y1 - y0))
        elif isinstance(element, Polygon):
            painter.drawPolygon(QPolygonF([QPointF(x, y) for x, y in element.points]))
        elif isinstance(element, Line):
            self._draw_line(painter, element)
        elif isinstance(element, Text):
            self._draw_text(painter, element)
        elif isinstance(element, Image):
            self._draw_image(painter, element)

    def _draw_line(self, painter: QPainter, element: Line) -> None:
        """Draw a line and whichever arrowheads it has."""
        points = [QPointF(x, y) for x, y in element.points]
        if len(points) < 2:
            return
        painter.drawPolyline(QPolygonF(points))
        painter.setBrush(QColor(element.style.color))
        if element.arrow_first:
            self._draw_arrow(painter, points[1], points[0], element)
        if element.arrow_last:
            self._draw_arrow(painter, points[-2], points[-1], element)

    def _draw_arrow(self, painter: QPainter, back: QPointF, tip: QPointF, element: Line) -> None:
        """Draw one arrowhead pointing from `back` to `tip`."""
        angle = math.atan2(tip.y() - back.y(), tip.x() - back.x())
        length = ARROW_LENGTH + element.style.width
        head = QPolygonF(
            [
                tip,
                QPointF(
                    tip.x() - length * math.cos(angle - ARROW_SPREAD),
                    tip.y() - length * math.sin(angle - ARROW_SPREAD),
                ),
                QPointF(
                    tip.x() - length * math.cos(angle + ARROW_SPREAD),
                    tip.y() - length * math.sin(angle + ARROW_SPREAD),
                ),
            ]
        )
        painter.drawPolygon(head)

    def _draw_text(self, painter: QPainter, element: Text) -> None:
        """Draw a caption, turned if it has an angle."""
        font = QFont(element.font, element.font_size)
        font.setBold(element.font_weight == "bold")
        font.setItalic(element.font_slant == "italic")
        painter.setFont(font)
        painter.setPen(QPen(QColor(element.style.color)))

        alignment = {
            "left": Qt.AlignmentFlag.AlignLeft,
            "center": Qt.AlignmentFlag.AlignHCenter,
            "right": Qt.AlignmentFlag.AlignRight,
        }.get(element.justify, Qt.AlignmentFlag.AlignLeft)

        metrics = painter.fontMetrics()
        lines = element.text.split("\n")
        height = metrics.height() * len(lines)
        width = max((metrics.horizontalAdvance(line) for line in lines), default=0)

        painter.save()
        painter.translate(element.x, element.y)
        if element.angle:
            painter.rotate(-element.angle)
        painter.drawText(
            QRectF(-width / 2.0, -height / 2.0, width, height),
            int(alignment | Qt.AlignmentFlag.AlignVCenter),
            element.text,
        )
        painter.restore()

    def _draw_image(self, painter: QPainter, element: Image) -> None:
        """Draw a placed picture, or its outline if it will not load."""
        pixmap = self._pixmap(element.path)
        x0, y0, x1, y1 = element.bounds()
        target = QRectF(x0, y0, x1 - x0, y1 - y0)
        if pixmap is None:
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.drawRect(target)
            painter.drawText(target, int(Qt.AlignmentFlag.AlignCenter), "?")
            return
        painter.drawPixmap(target, pixmap, QRectF(pixmap.rect()))

    def _pixmap(self, path: str) -> QPixmap | None:
        """A placed picture, loaded once and kept."""
        if not path:
            return None
        if path in self._pixmaps:
            pixmap = self._pixmaps[path]
            return pixmap if not pixmap.isNull() else None
        if not Path(path).exists():
            self._pixmaps[path] = QPixmap()
            return None
        pixmap = QPixmap.fromImage(QImage(path))
        self._pixmaps[path] = pixmap
        return pixmap if not pixmap.isNull() else None

    def _draw_handles(self, painter: QPainter, element: Element) -> None:
        """Draw one element's selection handles."""
        painter.setPen(QPen(HANDLE_COLOR))
        painter.setBrush(HANDLE_COLOR)
        half = HANDLE_SIZE / 2.0
        for x, y in element.handles():
            painter.drawRect(QRectF(x - half, y - half, HANDLE_SIZE, HANDLE_SIZE))

    def _draw_band(self, painter: QPainter) -> None:
        """Draw the rectangle a new element is being dragged out in."""
        (x0, y0), (x1, y1) = self._drag_from, self._drag_last  # type: ignore[misc]
        pen = QPen(HANDLE_COLOR)
        pen.setStyle(Qt.PenStyle.DashLine)
        painter.setPen(pen)
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawRect(QRectF(min(x0, x1), min(y0, y1), abs(x1 - x0), abs(y1 - y0)))
