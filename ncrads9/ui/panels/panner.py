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
Panner panel showing overview with pan rectangle.

Author: Yogesh Wadadekar
"""

from typing import Optional

import numpy as np
from numpy.typing import NDArray
from PyQt6.QtCore import Qt, QRectF, pyqtSignal
from PyQt6.QtGui import QImage, QPixmap, QPainter, QPen, QColor, QMouseEvent
from PyQt6.QtWidgets import QDockWidget, QWidget, QVBoxLayout, QLabel


class PannerLabel(QLabel):
    """Label widget that handles mouse clicks for panning."""

    pan_requested = pyqtSignal(float, float)

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        """Initialize the panner label."""
        super().__init__(parent)
        self._image_size: tuple[int, int] = (1, 1)
        self._scale_factor: float = 1.0

    def set_image_size(self, width: int, height: int) -> None:
        """Set the original image size for coordinate conversion."""
        self._image_size = (width, height)

    def set_scale_factor(self, factor: float) -> None:
        """Set the scale factor for coordinate conversion."""
        self._scale_factor = factor

    def mousePressEvent(self, event: Optional[QMouseEvent]) -> None:
        """Handle mouse press for panning."""
        if event is None:
            return
        if event.button() == Qt.MouseButton.LeftButton:
            # Convert widget coordinates to image coordinates
            x = event.position().x() / self._scale_factor
            y = event.position().y() / self._scale_factor
            self.pan_requested.emit(x, y)


class PannerPanel(QDockWidget):
    """Dockable panel showing image overview with pan rectangle."""

    pan_to = pyqtSignal(float, float)

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        """
        Initialize the panner panel.

        Args:
            parent: Parent widget.
        """
        super().__init__("Panner", parent)
        self.setObjectName("PannerPanel")

        self._current_image: Optional[NDArray[np.float64]] = None
        self._view_rect: Optional[QRectF] = None
        self._thumbnail_size: int = 200

        self._setup_ui()

    def _setup_ui(self) -> None:
        """Set up the user interface."""
        container = QWidget()
        layout = QVBoxLayout(container)

        self._panner_label = PannerLabel()
        self._panner_label.setMinimumSize(self._thumbnail_size, self._thumbnail_size)
        self._panner_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._panner_label.setStyleSheet("background-color: black;")
        self._panner_label.pan_requested.connect(self._on_pan_requested)
        layout.addWidget(self._panner_label)

        self.setWidget(container)

    def _on_pan_requested(self, x: float, y: float) -> None:
        """Handle pan request from label click."""
        self.pan_to.emit(x, y)

    def set_image(self, image: NDArray[np.float64]) -> None:
        """
        Set the image data for the overview.

        Args:
            image: 2D numpy array of image data.
        """
        self._current_image = image
        self._update_thumbnail()

    def set_view_rect(self, rect: QRectF) -> None:
        """
        Set the current view rectangle.

        Args:
            rect: Rectangle representing the current view in image coordinates.
        """
        self._view_rect = rect
        self._update_thumbnail()

    def _update_thumbnail(self) -> None:
        """Update the thumbnail with view rectangle overlay."""
        if self._current_image is None:
            return

        h, w = self._current_image.shape[:2]

        # Normalize to 0-255
        vmin, vmax = np.nanmin(self._current_image), np.nanmax(self._current_image)
        if vmax > vmin:
            normalized = ((self._current_image - vmin) / (vmax - vmin) * 255).astype(
                np.uint8
            )
        else:
            normalized = np.zeros((h, w), dtype=np.uint8)

        # Create QImage
        qimage = QImage(
            normalized.data,
            w,
            h,
            normalized.strides[0],
            QImage.Format.Format_Grayscale8,
        )

        # Scale to thumbnail size
        scale = min(self._thumbnail_size / w, self._thumbnail_size / h)
        new_w = int(w * scale)
        new_h = int(h * scale)

        pixmap = QPixmap.fromImage(qimage).scaled(
            new_w,
            new_h,
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation,
        )

        self._panner_label.set_image_size(w, h)
        self._panner_label.set_scale_factor(scale)

        # Draw view rectangle
        if self._view_rect is not None:
            painter = QPainter(pixmap)
            painter.setPen(QPen(QColor(0, 255, 0), 2))
            scaled_rect = QRectF(
                self._view_rect.x() * scale,
                self._view_rect.y() * scale,
                self._view_rect.width() * scale,
                self._view_rect.height() * scale,
            )
            painter.drawRect(scaled_rect)
            painter.end()

        self._panner_label.setPixmap(pixmap)
