# This file is part of ncrads9.
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
#
# Author: Yogesh Wadadekar

"""Interactive colorbar widget for ncrads9."""

from typing import Optional, Tuple
import numpy as np

from PyQt6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QLabel
from PyQt6.QtGui import QPainter, QImage, QColor, QPen, QFont
from PyQt6.QtCore import Qt, pyqtSignal, QRect

from .colormap import Colormap


class ColorbarWidget(QWidget):
    """Interactive colorbar widget for displaying and selecting colormaps.

    Signals:
        colormap_changed: Emitted when the colormap is changed.
        range_changed: Emitted when the display range is changed (vmin, vmax).
        value_selected: Emitted when user clicks on the colorbar (normalized value).
    """

    colormap_changed = pyqtSignal(Colormap)
    range_changed = pyqtSignal(float, float)
    value_selected = pyqtSignal(float)

    def __init__(
        self,
        parent: Optional[QWidget] = None,
        colormap: Optional[Colormap] = None,
        orientation: str = "horizontal",
    ) -> None:
        """Initialize the ColorbarWidget.

        Args:
            parent: Parent widget.
            colormap: Initial colormap to display.
            orientation: Orientation of the colorbar ("horizontal" or "vertical").
        """
        super().__init__(parent)

        self._colormap: Optional[Colormap] = colormap
        self._orientation: str = orientation
        self._vmin: float = 0.0
        self._vmax: float = 1.0
        self._show_labels: bool = True
        self._label_format: str = "{:.2g}"
        self._num_ticks: int = 5
        self._colorbar_image: Optional[QImage] = None

        self._setup_ui()
        self._update_colorbar_image()

    def _setup_ui(self) -> None:
        """Set up the widget UI."""
        if self._orientation == "horizontal":
            self.setMinimumSize(200, 40)
        else:
            self.setMinimumSize(40, 200)

    def set_colormap(self, colormap: Colormap) -> None:
        """Set the colormap to display.

        Args:
            colormap: The colormap to display.
        """
        self._colormap = colormap
        self._update_colorbar_image()
        self.update()
        self.colormap_changed.emit(colormap)

    def get_colormap(self) -> Optional[Colormap]:
        """Get the current colormap.

        Returns:
            The current colormap or None.
        """
        return self._colormap

    def set_range(self, vmin: float, vmax: float) -> None:
        """Set the value range for labels.

        Args:
            vmin: Minimum value.
            vmax: Maximum value.
        """
        self._vmin = vmin
        self._vmax = vmax
        self.update()
        self.range_changed.emit(vmin, vmax)

    def get_range(self) -> Tuple[float, float]:
        """Get the current value range.

        Returns:
            Tuple of (vmin, vmax).
        """
        return (self._vmin, self._vmax)

    def set_show_labels(self, show: bool) -> None:
        """Set whether to show value labels.

        Args:
            show: Whether to show labels.
        """
        self._show_labels = show
        self.update()

    def set_label_format(self, fmt: str) -> None:
        """Set the format string for labels.

        Args:
            fmt: Python format string (e.g., "{:.2f}").
        """
        self._label_format = fmt
        self.update()

    def set_num_ticks(self, num: int) -> None:
        """Set the number of tick marks.

        Args:
            num: Number of ticks.
        """
        self._num_ticks = max(2, num)
        self.update()

    def _update_colorbar_image(self) -> None:
        """Update the internal colorbar image."""
        if self._colormap is None:
            self._colorbar_image = None
            return

        lut = self._colormap.to_lut()

        if self._orientation == "horizontal":
            width = 256
            height = 1
            data = lut.reshape(1, 256, 3)
        else:
            width = 1
            height = 256
            data = lut[::-1].reshape(256, 1, 3)

        # Convert to RGBA
        rgba = np.zeros((data.shape[0], data.shape[1], 4), dtype=np.uint8)
        rgba[:, :, :3] = data
        rgba[:, :, 3] = 255

        self._colorbar_image = QImage(
            rgba.data,
            width,
            height,
            width * 4,
            QImage.Format_RGBA8888,
        ).copy()

    def paintEvent(self, event) -> None:
        """Paint the colorbar widget."""
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)

        rect = self.rect()
        margin = 5
        label_space = 20 if self._show_labels else 0

        if self._orientation == "horizontal":
            colorbar_rect = QRect(
                margin,
                margin,
                rect.width() - 2 * margin,
                rect.height() - 2 * margin - label_space,
            )
        else:
            colorbar_rect = QRect(
                margin,
                margin,
                rect.width() - 2 * margin - label_space,
                rect.height() - 2 * margin,
            )

        # Draw colorbar
        if self._colorbar_image is not None:
            scaled_image = self._colorbar_image.scaled(
                colorbar_rect.width(),
                colorbar_rect.height(),
                Qt.IgnoreAspectRatio,
                Qt.SmoothTransformation,
            )
            painter.drawImage(colorbar_rect, scaled_image)

        # Draw border
        painter.setPen(QPen(QColor(128, 128, 128), 1))
        painter.drawRect(colorbar_rect)

        # Draw labels
        if self._show_labels:
            painter.setPen(QPen(QColor(0, 0, 0), 1))
            font = QFont()
            font.setPointSize(8)
            painter.setFont(font)

            for i in range(self._num_ticks):
                t = i / (self._num_ticks - 1)
                value = self._vmin + t * (self._vmax - self._vmin)
                label = self._label_format.format(value)

                if self._orientation == "horizontal":
                    x = colorbar_rect.left() + int(t * colorbar_rect.width())
                    y = colorbar_rect.bottom() + 15
                    painter.drawText(x - 20, y, 40, 20, Qt.AlignCenter, label)
                    # Draw tick
                    painter.drawLine(x, colorbar_rect.bottom(), x, colorbar_rect.bottom() + 3)
                else:
                    x = colorbar_rect.right() + 5
                    y = colorbar_rect.bottom() - int(t * colorbar_rect.height())
                    painter.drawText(x, y - 10, 50, 20, Qt.AlignLeft | Qt.AlignVCenter, label)
                    # Draw tick
                    painter.drawLine(colorbar_rect.right(), y, colorbar_rect.right() + 3, y)

    def mousePressEvent(self, event) -> None:
        """Handle mouse press events."""
        rect = self.rect()
        margin = 5

        if self._orientation == "horizontal":
            colorbar_width = rect.width() - 2 * margin
            x = event.x() - margin
            if 0 <= x <= colorbar_width:
                normalized = x / colorbar_width
                self.value_selected.emit(normalized)
        else:
            colorbar_height = rect.height() - 2 * margin
            y = event.y() - margin
            if 0 <= y <= colorbar_height:
                normalized = 1.0 - (y / colorbar_height)
                self.value_selected.emit(normalized)

    def sizeHint(self):
        """Return the recommended size for the widget."""
        from PyQt6.QtCore import QSize
        if self._orientation == "horizontal":
            return QSize(300, 50)
        else:
            return QSize(60, 300)
