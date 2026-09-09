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
Colorbar widget showing the current colour table, or several of them.

DS9 shows more than one bar in two cases (`ds9/library/colorbar.tcl`): with
`View -> Multiple Colorbars` on and frames tiled, one bar per tiled frame;
and for an RGB, HSV or HLS frame, one bar per channel. Both are the same
thing -- a list of bars rather than one -- so `set_colorbars` takes a list
and `set_colormap` is the one-entry case.

Author: Yogesh Wadadekar
"""


from dataclasses import dataclass

import numpy as np
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QFont, QImage, QPainter, QPixmap
from PyQt6.QtWidgets import QLabel, QVBoxLayout, QWidget

#: Room left below (or beside) the bar for its tick labels.
NUMERICS_ALLOWANCE = 22
#: Room left for the colormap-name label above the bar.
NAME_ALLOWANCE = 20
#: Extra width a vertical colorbar needs, its labels being written across.
VERTICAL_LABEL_ALLOWANCE = 44
#: The bar never gets thinner than this along its long edge, nor wider.
MIN_LONG_EDGE = 120
MAX_LONG_EDGE = 16777215

#: Gap between stacked bars, in pixels.
BAR_GAP = 2

#: How many bars are drawn at most, so a hundred tiled frames do not make a
#: hundred unreadable slivers.
MAX_BARS = 8


@dataclass(frozen=True)
class ColorbarEntry:
    """One bar: its colour table, its limits and its label."""

    colors: object
    vmin: float = 0.0
    vmax: float = 1.0
    label: str = ""


class ColorbarWidget(QWidget):
    """Widget displaying a colorbar with scale values."""

    #: Emitted with a 0-to-1 position along the bar when it is clicked.
    #: DS9's Colorbar edit mode turns that into a colour tag.
    clicked: pyqtSignal = pyqtSignal(float)

    def __init__(self, parent: QWidget | None = None) -> None:
        """
        Initialize the colorbar widget.

        Args:
            parent: Optional parent widget.
        """
        super().__init__(parent)
        self.colormap_data = None
        self.vmin = 0.0
        self.vmax = 1.0
        self.colormap_name = "grey"
        self.inverted = False
        #: Every bar to draw. One entry is the ordinary case; several come
        #: from Multiple Colorbars or a colour frame's channels.
        self._entries: list[ColorbarEntry] = []
        # DS9 lays the colorbar out horizontally under the canvas.
        self.orientation = "horizontal"
        self.show_numerics = True
        self.spacing_mode = "value"
        self.tick_count = 7
        self.bar_size = 40
        self.label_font_size = 8

        layout = QVBoxLayout()
        layout.setContentsMargins(5, 5, 5, 5)

        # Colormap name label
        self.name_label = QLabel(self.colormap_name)
        self.name_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.name_label)

        # Colorbar display
        self.colorbar_label = QLabel()
        layout.addWidget(self.colorbar_label, 1)

        self.setLayout(layout)
        self._apply_size_constraints()

    def mousePressEvent(self, event) -> None:
        """Report where on the bar the user clicked, as a 0-to-1 position.

        DS9's Colorbar edit mode uses this to create and edit colour tags.
        The position is measured along the bar's long axis, from the low end
        -- the left of a horizontal bar, the bottom of a vertical one.
        """
        if event is None:
            super().mousePressEvent(event)
            return

        label = self.colorbar_label
        origin = label.mapFrom(self, event.position().toPoint())
        pixmap = label.pixmap()
        if pixmap is None or pixmap.isNull():
            super().mousePressEvent(event)
            return

        if self.orientation == "horizontal":
            span = max(1, pixmap.width())
            position = origin.x() / span
        else:
            span = max(1, pixmap.height())
            # A vertical bar runs high at the top, so invert.
            position = 1.0 - origin.y() / span

        self.clicked.emit(max(0.0, min(float(position), 1.0)))
        event.accept()

    def set_colormap(
        self, colormap_data: np.ndarray, vmin: float, vmax: float, name: str, inverted: bool = False
    ) -> None:
        """
        Set the colormap to display.

        Args:
            colormap_data: RGB colormap data (256, 3).
            vmin: Minimum data value.
            vmax: Maximum data value.
            name: Colormap name.
            inverted: Whether colormap is inverted.
        """
        self.set_colorbars(
            [ColorbarEntry(colors=colormap_data, vmin=vmin, vmax=vmax, label=name)],
            inverted=inverted,
        )

    def set_colorbars(
        self,
        entries: "list[ColorbarEntry]",
        inverted: bool = False,
    ) -> None:
        """Show one bar per entry, stacked across the bar's short axis.

        DS9 draws several bars for Multiple Colorbars and for a colour
        frame's three channels; both arrive here as a list.

        Args:
            entries: The bars, in the order they should be drawn. An empty
                list clears the widget.
            inverted: Whether the colormap is inverted, for the name label.
        """
        self._entries = list(entries)[:MAX_BARS]
        first = self._entries[0] if self._entries else None

        # The single-bar attributes stay meaningful, since XPA and the
        # Colormap Parameters dialog read them.
        self.colormap_data = None if first is None else first.colors
        self.vmin = 0.0 if first is None else first.vmin
        self.vmax = 1.0 if first is None else first.vmax
        self.colormap_name = "" if first is None else first.label
        self.inverted = inverted

        labels = " · ".join(entry.label for entry in self._entries if entry.label)
        self.name_label.setText(f"{labels} (inv)" if inverted and labels else labels)
        self._apply_size_constraints()
        self._update_colorbar()

    @property
    def bar_count(self) -> int:
        """How many bars are being drawn."""
        return max(1, len(self._entries))

    @staticmethod
    def _as_bytes(colors: np.ndarray) -> np.ndarray:
        """A colour table as uint8, whatever it arrived as."""
        array = np.asarray(colors)
        if array.dtype in (np.float64, np.float32):
            return (array * 255).astype(np.uint8)
        return array.astype(np.uint8)

    def _update_colorbar(self) -> None:
        """Redraw every bar, with ticks and labels."""
        if not self._entries:
            self.colorbar_label.clear()
            return
        if len(self._entries) > 1:
            self._draw_multiple()
            return

        cmap_uint8 = self._as_bytes(self._entries[0].colors)

        if self.orientation == "horizontal":
            bar_height = max(14, self.bar_size)
            bar_width = max(180, self.colorbar_label.width() - 10)
            colorbar = np.zeros((bar_height, bar_width, 3), dtype=np.uint8)
            indices = np.linspace(0, 255, bar_width).astype(int)
            for i, idx in enumerate(indices):
                colorbar[:, i] = cmap_uint8[idx]

            qimage = QImage(
                colorbar.tobytes(),
                bar_width,
                bar_height,
                bar_width * 3,
                QImage.Format.Format_RGB888,
            )
            pixmap = QPixmap.fromImage(qimage)

            tick_height = 36 if self.show_numerics else 8
            full_pixmap = QPixmap(bar_width, bar_height + tick_height)
            full_pixmap.fill(Qt.GlobalColor.transparent)

            painter = QPainter(full_pixmap)
            painter.drawPixmap(0, 0, pixmap)
            self._draw_horizontal_ticks(painter, bar_width, bar_height)
            painter.end()
            self.colorbar_label.setPixmap(full_pixmap)
            return

        # Default vertical orientation
        bar_width = max(14, self.bar_size)
        tick_width = 68 if self.show_numerics else 8
        height = max(140, self.colorbar_label.height() - 4)
        colorbar = np.zeros((height, bar_width, 3), dtype=np.uint8)
        indices = np.linspace(255, 0, height).astype(int)
        for i, idx in enumerate(indices):
            colorbar[i, :] = cmap_uint8[idx]

        qimage = QImage(
            colorbar.tobytes(),
            bar_width,
            height,
            bar_width * 3,
            QImage.Format.Format_RGB888,
        )
        pixmap = QPixmap.fromImage(qimage)
        full_pixmap = QPixmap(bar_width + tick_width, height)
        full_pixmap.fill(Qt.GlobalColor.transparent)

        painter = QPainter(full_pixmap)
        painter.drawPixmap(0, 0, pixmap)
        self._draw_vertical_ticks(painter, bar_width, height)
        painter.end()
        self.colorbar_label.setPixmap(full_pixmap)

    def _tick_values(self) -> np.ndarray:
        """Return tick values according to the selected spacing mode."""
        count = max(2, int(self.tick_count))
        if self.spacing_mode == "value" and self.vmin > 0 and self.vmax > 0 and self.vmax > self.vmin:
            ratio = self.vmax / self.vmin
            if ratio > 100:
                return np.geomspace(self.vmax, self.vmin, count)
        return np.linspace(self.vmax, self.vmin, count)

    def _draw_vertical_ticks(self, painter: QPainter, bar_width: int, bar_height: int) -> None:
        """Draw vertical orientation ticks and labels."""
        if not self.show_numerics:
            return
        tick_length = 5
        font = QFont("Arial", self.label_font_size)
        painter.setFont(font)
        values = self._tick_values()
        for value in values:
            norm = 0.0 if self.vmax == self.vmin else (self.vmax - value) / (self.vmax - self.vmin)
            y_pos = int(np.clip(norm, 0, 1) * (bar_height - 1))
            painter.drawLine(bar_width, y_pos, bar_width + tick_length, y_pos)
            painter.drawText(bar_width + tick_length + 2, y_pos + 4, f"{value:.3g}")

    def _draw_horizontal_ticks(self, painter: QPainter, bar_width: int, bar_height: int) -> None:
        """Draw horizontal orientation ticks and labels."""
        if not self.show_numerics:
            return
        tick_length = 5
        font = QFont("Arial", self.label_font_size)
        painter.setFont(font)
        values = np.linspace(self.vmin, self.vmax, max(2, int(self.tick_count)))
        for value in values:
            norm = 0.0 if self.vmax == self.vmin else (value - self.vmin) / (self.vmax - self.vmin)
            x_pos = int(np.clip(norm, 0, 1) * (bar_width - 1))
            painter.drawLine(x_pos, bar_height, x_pos, bar_height + tick_length)
            # Keep the end labels inside the bar: centred on the tick they
            # would hang off both edges, which is what the first and last
            # numbers used to do once the bar spanned the whole canvas.
            text = f"{value:.3g}"
            text_width = painter.fontMetrics().horizontalAdvance(text)
            left = int(np.clip(x_pos - text_width / 2, 0, max(0, bar_width - text_width)))
            painter.drawText(left, bar_height + tick_length + 12, text)

    def set_orientation(self, orientation: str) -> None:
        """Set colorbar orientation (vertical or horizontal)."""
        orientation_l = orientation.lower()
        if orientation_l not in {"vertical", "horizontal"}:
            return
        self.orientation = orientation_l
        self._apply_size_constraints()
        self._update_colorbar()

    def set_show_numerics(self, show: bool) -> None:
        """Toggle tick labels visibility."""
        self.show_numerics = bool(show)
        self._update_colorbar()

    def set_spacing_mode(self, mode: str) -> None:
        """Set spacing mode: value or distance."""
        mode_l = mode.lower()
        if mode_l not in {"value", "distance"}:
            return
        self.spacing_mode = mode_l
        self._update_colorbar()

    def set_tick_count(self, count: int) -> None:
        """Set number of displayed ticks."""
        self.tick_count = max(2, int(count))
        self._update_colorbar()

    def set_bar_size(self, size: int) -> None:
        """Set bar thickness/height depending on orientation."""
        self.bar_size = max(12, int(size))
        self._apply_size_constraints()
        self._update_colorbar()

    def set_label_font_size(self, size: int) -> None:
        """Set numeric label font size."""
        self.label_font_size = max(6, int(size))
        self._update_colorbar()

    def _draw_multiple(self) -> None:
        """Draw several bars stacked across the widget's short axis.

        Each gets its own strip and its own tick labels, since the frames or
        channels they belong to have their own limits. The strips are thinner
        than a single bar would be so the whole stack still fits the space
        `_apply_size_constraints` asked for.
        """
        count = len(self._entries)
        horizontal = self.orientation == "horizontal"
        thickness = max(4, (self.bar_size - (count - 1) * BAR_GAP) // count)

        if horizontal:
            width = max(MIN_LONG_EDGE, self.colorbar_label.width() - 10)
            height = count * thickness + (count - 1) * BAR_GAP
            allowance = NUMERICS_ALLOWANCE if self.show_numerics else BAR_GAP
            pixmap = QPixmap(width, height + allowance)
        else:
            height = max(MIN_LONG_EDGE, self.colorbar_label.height() - 4)
            width = count * thickness + (count - 1) * BAR_GAP
            allowance = VERTICAL_LABEL_ALLOWANCE if self.show_numerics else BAR_GAP
            pixmap = QPixmap(width + allowance, height)
        pixmap.fill(Qt.GlobalColor.transparent)

        painter = QPainter(pixmap)
        try:
            for index, entry in enumerate(self._entries):
                offset = index * (thickness + BAR_GAP)
                self._draw_one(painter, entry, offset, thickness, width, height, horizontal)
        finally:
            painter.end()
        self.colorbar_label.setPixmap(pixmap)

    def _draw_one(
        self,
        painter: QPainter,
        entry: "ColorbarEntry",
        offset: int,
        thickness: int,
        width: int,
        height: int,
        horizontal: bool,
    ) -> None:
        """Draw one strip of a multi-bar colorbar, and its end labels."""
        colors = self._as_bytes(entry.colors)
        if colors.size == 0:
            return

        if horizontal:
            strip = np.zeros((thickness, width, 3), dtype=np.uint8)
            indices = np.linspace(0, len(colors) - 1, width).astype(int)
            strip[:, :] = colors[indices][None, :, :]
        else:
            strip = np.zeros((height, thickness, 3), dtype=np.uint8)
            indices = np.linspace(len(colors) - 1, 0, height).astype(int)
            strip[:, :] = colors[indices][:, None, :]

        rows, columns = strip.shape[:2]
        image = QImage(
            np.ascontiguousarray(strip).tobytes(),
            columns,
            rows,
            columns * 3,
            QImage.Format.Format_RGB888,
        )
        if horizontal:
            painter.drawPixmap(0, offset, QPixmap.fromImage(image))
        else:
            painter.drawPixmap(offset, 0, QPixmap.fromImage(image))

        painter.setFont(QFont("Arial", max(6, self.label_font_size - 1)))
        if not self.show_numerics or thickness < painter.fontMetrics().height():
            # Several thin strips leave no room for a number inside each; a
            # label drawn anyway lands on its neighbour.
            return

        painter.setPen(Qt.GlobalColor.black)
        low, high = f"{entry.vmin:.3g}", f"{entry.vmax:.3g}"
        if horizontal:
            baseline = offset + thickness - 2
            painter.drawText(2, baseline, low)
            painter.drawText(width - painter.fontMetrics().horizontalAdvance(high) - 2, baseline, high)
        else:
            left = width + 2
            painter.drawText(left, height - 2, low)
            painter.drawText(left, 10, high)

    def _apply_size_constraints(self) -> None:
        """Pin the thin dimension and let the long one stretch.

        The widget used to be sized for a dock down the right-hand edge -- a
        140x200 minimum -- which, once it sits under the canvas in the window
        shell, would take a fifth of the window's height. DS9's colorbar is a
        strip as wide as the canvas and only as tall as the bar plus its tick
        labels.
        """
        thickness = self.bar_size + NUMERICS_ALLOWANCE + NAME_ALLOWANCE
        if self.orientation == "horizontal":
            self.setMaximumHeight(thickness)
            self.setMinimumHeight(thickness)
            self.setMinimumWidth(MIN_LONG_EDGE)
            self.setMaximumWidth(MAX_LONG_EDGE)
        else:
            self.setMaximumWidth(thickness + VERTICAL_LABEL_ALLOWANCE)
            self.setMinimumWidth(thickness + VERTICAL_LABEL_ALLOWANCE)
            self.setMinimumHeight(MIN_LONG_EDGE)
            self.setMaximumHeight(MAX_LONG_EDGE)

    def resizeEvent(self, event) -> None:
        """Handle resize events."""
        super().resizeEvent(event)
        if self.colormap_data is not None:
            self._update_colorbar()
