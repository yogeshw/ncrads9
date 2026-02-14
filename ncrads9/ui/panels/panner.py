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
        if event.button() != Qt.MouseButton.LeftButton or self._scale_factor <= 0:
            return

        pixmap = self.pixmap()
        if pixmap is None:
            return

        x_offset = max(0.0, (self.width() - pixmap.width()) / 2.0)
        y_offset = max(0.0, (self.height() - pixmap.height()) / 2.0)
        local_x = event.position().x() - x_offset
        local_y = event.position().y() - y_offset
        if local_x < 0 or local_y < 0 or local_x >= pixmap.width() or local_y >= pixmap.height():
            return

        max_x = max(0.0, self._image_size[0] - 1)
        max_y = max(0.0, self._image_size[1] - 1)
        x = min(max(local_x / self._scale_factor, 0.0), max_x)
        y = min(max(local_y / self._scale_factor, 0.0), max_y)
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

    def set_view_rect(self, rect: Optional[QRectF]) -> None:
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
        is_rgb = len(self._current_image.shape) == 3 and self._current_image.shape[2] == 3
        if is_rgb:
            if self._current_image.dtype == np.uint8:
                normalized = self._current_image
            else:
                vmin, vmax = np.nanmin(self._current_image), np.nanmax(self._current_image)
                if vmax > vmin:
                    normalized = ((self._current_image - vmin) / (vmax - vmin) * 255).astype(np.uint8)
                else:
                    normalized = np.zeros((h, w, 3), dtype=np.uint8)
            if not normalized.flags["C_CONTIGUOUS"]:
                normalized = np.ascontiguousarray(normalized)
            qimage = QImage(
                normalized.data,
                w,
                h,
                3 * w,
                QImage.Format.Format_RGB888,
            )
        else:
            vmin, vmax = np.nanmin(self._current_image), np.nanmax(self._current_image)
            if vmax > vmin:
                normalized = ((self._current_image - vmin) / (vmax - vmin) * 255).astype(
                    np.uint8
                )
            else:
                normalized = np.zeros((h, w), dtype=np.uint8)
            if not normalized.flags["C_CONTIGUOUS"]:
                normalized = np.ascontiguousarray(normalized)
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
        if self._view_rect is not None and self._view_rect.width() > 0 and self._view_rect.height() > 0:
            view_cover_x = self._view_rect.width() / max(w, 1)
            view_cover_y = self._view_rect.height() / max(h, 1)
            if view_cover_x >= 0.98 and view_cover_y >= 0.98:
                self._panner_label.setPixmap(pixmap)
                return

            if is_rgb:
                gray = (
                    normalized[..., 0].astype(np.float32) * 0.2126
                    + normalized[..., 1].astype(np.float32) * 0.7152
                    + normalized[..., 2].astype(np.float32) * 0.0722
                )
            else:
                gray = normalized.astype(np.float32)

            x0 = max(0, min(w - 1, int(self._view_rect.x())))
            y0 = max(0, min(h - 1, int(self._view_rect.y())))
            x1 = max(x0 + 1, min(w, int(self._view_rect.x() + self._view_rect.width())))
            y1 = max(y0 + 1, min(h, int(self._view_rect.y() + self._view_rect.height())))
            local_mean = float(np.nanmean(gray[y0:y1, x0:x1]))
            rect_color = QColor(255, 255, 255) if local_mean < 128.0 else QColor(0, 0, 0)

            painter = QPainter(pixmap)
            painter.setPen(QPen(rect_color, 2))
            scaled_rect = QRectF(
                self._view_rect.x() * scale,
                self._view_rect.y() * scale,
                self._view_rect.width() * scale,
                self._view_rect.height() * scale,
            )
            painter.drawRect(scaled_rect)
            painter.end()

        self._panner_label.setPixmap(pixmap)
