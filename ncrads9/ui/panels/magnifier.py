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

"""
Magnifier panel showing magnified view around cursor position.

Author: Yogesh Wadadekar
"""

from typing import Optional

import numpy as np
from numpy.typing import NDArray
from PyQt6.QtCore import Qt, QPointF
from PyQt6.QtGui import QImage, QPixmap, QPainter, QPen, QColor
from PyQt6.QtWidgets import (
    QDockWidget,
    QWidget,
    QVBoxLayout,
    QLabel,
    QSpinBox,
    QHBoxLayout,
)


class MagnifierPanel(QDockWidget):
    """Dockable panel showing magnified view around cursor position."""

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        """
        Initialize the magnifier panel.

        Args:
            parent: Parent widget.
        """
        super().__init__("Magnifier", parent)
        self.setObjectName("MagnifierPanel")

        self._zoom_factor: int = 4
        self._region_size: int = 64
        self._current_image: Optional[NDArray[np.float64]] = None
        self._cursor_pos: Optional[QPointF] = None

        self._setup_ui()

    def _setup_ui(self) -> None:
        """Set up the user interface."""
        container = QWidget()
        layout = QVBoxLayout(container)

        # Zoom control
        zoom_layout = QHBoxLayout()
        zoom_label = QLabel("Zoom:")
        self._zoom_spinbox = QSpinBox()
        self._zoom_spinbox.setRange(2, 16)
        self._zoom_spinbox.setValue(self._zoom_factor)
        self._zoom_spinbox.valueChanged.connect(self._on_zoom_changed)
        zoom_layout.addWidget(zoom_label)
        zoom_layout.addWidget(self._zoom_spinbox)
        zoom_layout.addStretch()
        layout.addLayout(zoom_layout)

        # Magnified view display
        self._magnifier_label = QLabel()
        self._magnifier_label.setMinimumSize(256, 256)
        self._magnifier_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._magnifier_label.setStyleSheet("background-color: black;")
        layout.addWidget(self._magnifier_label)

        self.setWidget(container)

    def _on_zoom_changed(self, value: int) -> None:
        """Handle zoom factor change."""
        self._zoom_factor = value
        self._update_magnifier()

    def set_image(self, image: NDArray[np.float64]) -> None:
        """
        Set the image data for magnification.

        Args:
            image: 2D numpy array of image data.
        """
        self._current_image = image
        self._update_magnifier()

    def update_cursor_position(self, x: float, y: float) -> None:
        """
        Update the cursor position for magnification.

        Args:
            x: X coordinate in image pixels.
            y: Y coordinate in image pixels.
        """
        self._cursor_pos = QPointF(x, y)
        self._update_magnifier()

    def _update_magnifier(self) -> None:
        """Update the magnified view."""
        if self._current_image is None or self._cursor_pos is None:
            return

        x = int(self._cursor_pos.x())
        y = int(self._cursor_pos.y())
        half_size = self._region_size // 2

        # Extract region around cursor
        h, w = self._current_image.shape[:2]
        x1 = max(0, x - half_size)
        x2 = min(w, x + half_size)
        y1 = max(0, y - half_size)
        y2 = min(h, y + half_size)

        if x1 >= x2 or y1 >= y2:
            return

        region = self._current_image[y1:y2, x1:x2]

        # Normalize to 0-255
        if region.size > 0:
            vmin, vmax = np.nanmin(region), np.nanmax(region)
            if vmax > vmin:
                normalized = ((region - vmin) / (vmax - vmin) * 255).astype(np.uint8)
            else:
                normalized = np.zeros_like(region, dtype=np.uint8)

            # Create QImage and scale
            qimage = QImage(
                normalized.data,
                normalized.shape[1],
                normalized.shape[0],
                normalized.strides[0],
                QImage.Format.Format_Grayscale8,
            )

            scaled_size = self._region_size * self._zoom_factor
            pixmap = QPixmap.fromImage(qimage).scaled(
                scaled_size,
                scaled_size,
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.FastTransformation,
            )

            # Draw crosshair
            painter = QPainter(pixmap)
            painter.setPen(QPen(QColor(255, 0, 0), 1))
            center = pixmap.width() // 2
            painter.drawLine(center, 0, center, pixmap.height())
            painter.drawLine(0, center, pixmap.width(), center)
            painter.end()

            self._magnifier_label.setPixmap(pixmap)
