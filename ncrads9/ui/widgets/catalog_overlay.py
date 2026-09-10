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
The catalogue symbols drawn over the image.

A layer of its own, as it is in DS9: catalogue symbols are not regions, they
are not saved with the regions, and Region -> Delete All does not touch
them. What they do share with regions is a click: "selecting multiple
symbols on the image display will highlight the corresponding rows within
the catalog list" (`ds9/doc/ref/catalog.html`), so this emits the row a
click landed on and the catalog window highlights it.

Positions arrive as sky coordinates, because that is what a catalogue holds,
and are converted through the frame's WCS on the way in. A frame with no WCS
shows no symbols -- there is nowhere to put them.

Author: Yogesh Wadadekar
"""

from __future__ import annotations

import math

from PyQt6.QtCore import QPointF, QRectF, Qt, pyqtSignal
from PyQt6.QtGui import QColor, QFont, QPainter, QPen, QPolygonF
from PyQt6.QtWidgets import QWidget

from ...catalogs.catalog_set import DrawnSymbol
from .overlay_transform import OverlayTransformMixin

#: The colour a selected symbol is drawn in, whatever its own colour.
SELECTION_COLOR = QColor(255, 255, 0)

#: How much wider a selected symbol's pen is.
SELECTION_WIDTH = 2

#: How near a symbol a click must land to count as picking it, in pixels.
PICK_TOLERANCE = 8.0

#: How far above a symbol its label sits, in pixels.
LABEL_OFFSET = 4.0

#: A `vector` symbol's head, as a fraction of its length and an angle.
ARROW_FRACTION = 0.3
ARROW_SPREAD = math.radians(25.0)


class CatalogOverlay(OverlayTransformMixin, QWidget):
    """Draws catalogue symbols, and reports clicks on them."""

    #: Emitted with (catalog name, row index) when a symbol is clicked.
    symbol_picked = pyqtSignal(str, int)
    #: Emitted with the catalog name when a click hits no symbol.
    selection_cleared = pyqtSignal(str)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        # Clicks are wanted -- that is the two-way selection sync -- but a
        # click on no symbol must reach the region overlay underneath, so
        # `mousePressEvent` ignores the ones it does not use.
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, False)
        self.setMouseTracking(False)
        self.init_transform()

        self._symbols: list[DrawnSymbol] = []
        self._owner: str = ""
        #: How to turn a sky position into an image one. Supplied by the
        #: host, because the WCS belongs to the frame, not to a widget.
        self._to_image = None

    def set_symbols(self, symbols: list[DrawnSymbol], owner: str = "") -> None:
        """Take the symbols to draw, and which catalogue owns them."""
        self._symbols = list(symbols)
        self._owner = owner
        self.update()

    def set_projection(self, to_image) -> None:
        """Set how a sky position becomes an image position.

        Args:
            to_image: Called with (longitude, latitude) in degrees,
                returning (x, y) in image pixels, or None when the frame
                has no WCS -- in which case nothing is drawn.
        """
        self._to_image = to_image
        self.update()

    def clear(self) -> None:
        """Remove every symbol."""
        self._symbols = []
        self.update()

    @property
    def symbols(self) -> tuple[DrawnSymbol, ...]:
        """The symbols being drawn."""
        return tuple(self._symbols)

    # -- picking ---------------------------------------------------------------

    def _place(self, symbol: DrawnSymbol) -> QPointF | None:
        """Where one symbol goes on the widget, or None if nowhere."""
        if self._to_image is None:
            return None
        position = self._to_image(symbol.longitude, symbol.latitude)
        if position is None:
            return None
        x, y = position
        if not (math.isfinite(x) and math.isfinite(y)):
            return None
        return self._image_to_widget(x, y)

    def symbol_at(self, point: QPointF) -> DrawnSymbol | None:
        """The symbol nearest a widget position, within the tolerance.

        Nearest rather than first: symbols overlap in a crowded field, and
        the one whose centre is closest is the one the user aimed at.
        """
        best: DrawnSymbol | None = None
        best_distance = PICK_TOLERANCE

        for symbol in self._symbols:
            place = self._place(symbol)
            if place is None:
                continue
            distance = math.hypot(place.x() - point.x(), place.y() - point.y())
            if distance <= best_distance:
                best_distance = distance
                best = symbol
        return best

    def mousePressEvent(self, event) -> None:
        """Pick a symbol, or pass the click on to the layer below."""
        if event.button() != Qt.MouseButton.LeftButton or not self._symbols:
            event.ignore()
            return

        symbol = self.symbol_at(event.position())
        if symbol is None:
            # Not ours: the region overlay and the viewer want it.
            event.ignore()
            return

        self.symbol_picked.emit(self._owner, symbol.row)
        event.accept()

    # -- drawing ----------------------------------------------------------------

    def paintEvent(self, event) -> None:
        """Draw every symbol."""
        if not self._symbols or self._to_image is None:
            return

        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        for symbol in self._symbols:
            place = self._place(symbol)
            if place is not None:
                self._draw(painter, symbol, place)
        painter.end()

    def _draw(self, painter: QPainter, symbol: DrawnSymbol, place: QPointF) -> None:
        """Draw one symbol and its label."""
        colour = SELECTION_COLOR if symbol.selected else _color(symbol.color)
        pen = QPen(colour)
        pen.setWidth(SELECTION_WIDTH if symbol.selected else max(1, symbol.width))
        pen.setCosmetic(True)
        painter.setPen(pen)
        painter.setBrush(Qt.BrushStyle.NoBrush)

        # Sizes are in screen pixels: a catalogue symbol is a marker, and a
        # marker that shrank with the zoom would vanish when zoomed out.
        half = max(1.0, symbol.size / 2.0)
        half2 = max(1.0, symbol.size2 / 2.0)
        shape = symbol.shape.strip().lower()

        if shape.endswith("point"):
            self._draw_point(painter, shape.split()[0], place, half)
        elif shape == "circle":
            painter.drawEllipse(place, half, half)
        elif shape == "ellipse":
            self._draw_rotated_ellipse(painter, place, half, half2, symbol.angle)
        elif shape == "box":
            self._draw_rotated_box(painter, place, half, half2, symbol.angle)
        elif shape == "vector":
            self._draw_vector(painter, place, symbol.size, symbol.angle)
        elif shape == "text":
            # "one special case for shape = text and text = empty. In this
            # case, the row number is displayed" -- DS9's own words.
            label = symbol.text or str(symbol.row + 1)
            self._draw_label(painter, symbol, place, label, centred=True)
            return

        if symbol.text:
            self._draw_label(painter, symbol, place, symbol.text)

    def _draw_point(self, painter: QPainter, glyph: str, place: QPointF, half: float) -> None:
        """One of DS9's seven point glyphs."""
        x, y = place.x(), place.y()
        if glyph == "circle":
            painter.drawEllipse(place, half, half)
        elif glyph == "box":
            painter.drawRect(QRectF(x - half, y - half, 2 * half, 2 * half))
        elif glyph == "diamond":
            painter.drawPolygon(
                QPolygonF(
                    [
                        QPointF(x, y - half),
                        QPointF(x + half, y),
                        QPointF(x, y + half),
                        QPointF(x - half, y),
                    ]
                )
            )
        elif glyph == "cross":
            painter.drawLine(QPointF(x - half, y), QPointF(x + half, y))
            painter.drawLine(QPointF(x, y - half), QPointF(x, y + half))
        elif glyph == "x":
            painter.drawLine(QPointF(x - half, y - half), QPointF(x + half, y + half))
            painter.drawLine(QPointF(x - half, y + half), QPointF(x + half, y - half))
        elif glyph == "arrow":
            painter.drawLine(QPointF(x, y + half), QPointF(x, y - half))
            painter.drawLine(QPointF(x, y - half), QPointF(x - half / 2, y - half / 2))
            painter.drawLine(QPointF(x, y - half), QPointF(x + half / 2, y - half / 2))
        elif glyph == "boxcircle":
            painter.drawRect(QRectF(x - half, y - half, 2 * half, 2 * half))
            painter.drawEllipse(place, half / 1.5, half / 1.5)

    def _draw_rotated_ellipse(
        self, painter: QPainter, place: QPointF, half: float, half2: float, angle: float
    ) -> None:
        """An ellipse, turned by its position angle."""
        painter.save()
        painter.translate(place)
        painter.rotate(-angle)
        painter.drawEllipse(QPointF(0.0, 0.0), half, half2)
        painter.restore()

    def _draw_rotated_box(
        self, painter: QPainter, place: QPointF, half: float, half2: float, angle: float
    ) -> None:
        """A box, likewise."""
        painter.save()
        painter.translate(place)
        painter.rotate(-angle)
        painter.drawRect(QRectF(-half, -half2, 2 * half, 2 * half2))
        painter.restore()

    def _draw_vector(self, painter: QPainter, place: QPointF, length: float, angle: float) -> None:
        """An arrow of the given length and angle."""
        radians = math.radians(angle)
        tip = QPointF(
            place.x() + length * math.cos(radians),
            place.y() - length * math.sin(radians),
        )
        painter.drawLine(place, tip)
        head = max(3.0, length * ARROW_FRACTION)
        for spread in (ARROW_SPREAD, -ARROW_SPREAD):
            painter.drawLine(
                tip,
                QPointF(
                    tip.x() - head * math.cos(radians + spread),
                    tip.y() + head * math.sin(radians + spread),
                ),
            )

    def _draw_label(
        self,
        painter: QPainter,
        symbol: DrawnSymbol,
        place: QPointF,
        text: str,
        centred: bool = False,
    ) -> None:
        """Draw a symbol's label above it, or on it for a text symbol."""
        font = QFont(symbol.font)
        font.setPointSize(max(6, symbol.font_size))
        painter.setFont(font)
        metrics = painter.fontMetrics()
        width = metrics.horizontalAdvance(text)

        if centred:
            painter.drawText(QPointF(place.x() - width / 2.0, place.y() + metrics.ascent() / 2.0), text)
            return

        top = place.y() - max(1.0, symbol.size / 2.0) - LABEL_OFFSET
        painter.drawText(QPointF(place.x() - width / 2.0, top), text)


def _color(name: str) -> QColor:
    """One of DS9's colour names as a QColor."""
    colour = QColor(name)
    return colour if colour.isValid() else QColor(0, 255, 0)
