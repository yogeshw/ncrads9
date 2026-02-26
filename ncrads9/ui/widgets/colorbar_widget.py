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
Colorbar widget showing current colormap.

Author: Yogesh Wadadekar
"""

from typing import Optional
import numpy as np
from PyQt6.QtCore import Qt, QSize
from PyQt6.QtGui import QImage, QPixmap, QPainter, QFont
from PyQt6.QtWidgets import QWidget, QVBoxLayout, QLabel


class ColorbarWidget(QWidget):
    """Widget displaying a colorbar with scale values."""

    def __init__(self, parent: Optional[QWidget] = None) -> None:
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
        self.orientation = "vertical"
        self.show_numerics = True
        self.spacing_mode = "value"
        self.tick_count = 7
        self.bar_size = 40
        self.label_font_size = 8
        
        self.setMinimumSize(140, 200)
        
        layout = QVBoxLayout()
        layout.setContentsMargins(5, 5, 5, 5)
        
        # Colormap name label
        self.name_label = QLabel(self.colormap_name)
        self.name_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.name_label)
        
        # Colorbar display
        self.colorbar_label = QLabel()
        self.colorbar_label.setMinimumHeight(150)
        self.colorbar_label.setMinimumWidth(120)
        layout.addWidget(self.colorbar_label, 1)
        
        self.setLayout(layout)

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
        self.colormap_data = colormap_data
        self.vmin = vmin
        self.vmax = vmax
        self.colormap_name = name
        self.inverted = inverted
        
        # Update name label
        name_display = f"{name} (inv)" if inverted else name
        self.name_label.setText(name_display)
        
        # Create colorbar image with ticks
        self._update_colorbar()

    def _update_colorbar(self) -> None:
        """Update the colorbar display with ticks and labels."""
        if self.colormap_data is None:
            return
        
        # Ensure colormap data is uint8 (0-255 range)
        if self.colormap_data.dtype == np.float64 or self.colormap_data.dtype == np.float32:
            # Convert from 0-1 to 0-255
            cmap_uint8 = (self.colormap_data * 255).astype(np.uint8)
        else:
            cmap_uint8 = self.colormap_data.astype(np.uint8)

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
            painter.drawText(x_pos - 16, bar_height + tick_length + 12, f"{value:.3g}")

    def set_orientation(self, orientation: str) -> None:
        """Set colorbar orientation (vertical or horizontal)."""
        orientation_l = orientation.lower()
        if orientation_l not in {"vertical", "horizontal"}:
            return
        self.orientation = orientation_l
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
        self._update_colorbar()

    def set_label_font_size(self, size: int) -> None:
        """Set numeric label font size."""
        self.label_font_size = max(6, int(size))
        self._update_colorbar()
    
    def resizeEvent(self, event) -> None:
        """Handle resize events."""
        super().resizeEvent(event)
        if self.colormap_data is not None:
            self._update_colorbar()
