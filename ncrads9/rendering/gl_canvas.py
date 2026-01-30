# NCRADS9 - OpenGL Canvas Widget
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

"""
OpenGL canvas widget for astronomical image display.

Provides a QOpenGLWidget-based canvas with zoom, pan, and image rendering
capabilities optimized for astronomical data visualization.
"""

from typing import Optional, Tuple

import numpy as np
from numpy.typing import NDArray
from PyQt6.QtCore import Qt, QPointF, pyqtSignal
from PyQt6.QtGui import QMouseEvent, QWheelEvent
from PyQt6.QtOpenGLWidgets import QOpenGLWidget


class GLCanvas(QOpenGLWidget):
    """
    OpenGL canvas for displaying astronomical images with zoom and pan.

    Attributes:
        zoom_changed: Signal emitted when zoom level changes.
        pan_changed: Signal emitted when pan position changes.
        cursor_moved: Signal emitted with image coordinates under cursor.
    """

    zoom_changed = pyqtSignal(float)
    pan_changed = pyqtSignal(float, float)
    cursor_moved = pyqtSignal(float, float, float)  # x, y, value

    def __init__(self, parent: Optional[object] = None) -> None:
        """
        Initialize the GLCanvas.

        Args:
            parent: Parent widget.
        """
        super().__init__(parent)
        self._zoom: float = 1.0
        self._pan_x: float = 0.0
        self._pan_y: float = 0.0
        self._last_mouse_pos: Optional[QPointF] = None
        self._image_data: Optional[NDArray[np.float32]] = None
        self._texture_id: Optional[int] = None
        self._min_zoom: float = 0.1
        self._max_zoom: float = 100.0

        self.setMouseTracking(True)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)

    @property
    def zoom(self) -> float:
        """Get current zoom level."""
        return self._zoom

    @zoom.setter
    def zoom(self, value: float) -> None:
        """Set zoom level with bounds checking."""
        self._zoom = max(self._min_zoom, min(self._max_zoom, value))
        self.zoom_changed.emit(self._zoom)
        self.update()

    @property
    def pan_offset(self) -> Tuple[float, float]:
        """Get current pan offset (x, y)."""
        return (self._pan_x, self._pan_y)

    def set_image(self, data: NDArray[np.float32]) -> None:
        """
        Set the image data to display.

        Args:
            data: 2D numpy array of image data.
        """
        self._image_data = data.astype(np.float32)
        self._upload_texture()
        self.update()

    def reset_view(self) -> None:
        """Reset zoom and pan to default values."""
        self._zoom = 1.0
        self._pan_x = 0.0
        self._pan_y = 0.0
        self.zoom_changed.emit(self._zoom)
        self.pan_changed.emit(self._pan_x, self._pan_y)
        self.update()

    def zoom_to_fit(self) -> None:
        """Adjust zoom to fit entire image in view."""
        if self._image_data is None:
            return
        img_h, img_w = self._image_data.shape[:2]
        view_w, view_h = self.width(), self.height()
        self._zoom = min(view_w / img_w, view_h / img_h)
        self._pan_x = 0.0
        self._pan_y = 0.0
        self.zoom_changed.emit(self._zoom)
        self.update()

    def screen_to_image(self, screen_x: float, screen_y: float) -> Tuple[float, float]:
        """
        Convert screen coordinates to image coordinates.

        Args:
            screen_x: X position in screen pixels.
            screen_y: Y position in screen pixels.

        Returns:
            Tuple of (image_x, image_y) coordinates.
        """
        center_x = self.width() / 2.0
        center_y = self.height() / 2.0
        img_x = (screen_x - center_x) / self._zoom + self._pan_x
        img_y = (screen_y - center_y) / self._zoom + self._pan_y
        return (img_x, img_y)

    def image_to_screen(self, img_x: float, img_y: float) -> Tuple[float, float]:
        """
        Convert image coordinates to screen coordinates.

        Args:
            img_x: X position in image pixels.
            img_y: Y position in image pixels.

        Returns:
            Tuple of (screen_x, screen_y) coordinates.
        """
        center_x = self.width() / 2.0
        center_y = self.height() / 2.0
        screen_x = (img_x - self._pan_x) * self._zoom + center_x
        screen_y = (img_y - self._pan_y) * self._zoom + center_y
        return (screen_x, screen_y)

    def initializeGL(self) -> None:
        """Initialize OpenGL context and resources."""
        pass  # Implementation depends on OpenGL version

    def resizeGL(self, width: int, height: int) -> None:
        """
        Handle widget resize.

        Args:
            width: New width in pixels.
            height: New height in pixels.
        """
        pass  # Update viewport

    def paintGL(self) -> None:
        """Render the image with current zoom and pan."""
        pass  # Render textured quad

    def wheelEvent(self, event: QWheelEvent) -> None:
        """
        Handle mouse wheel for zooming.

        Args:
            event: Wheel event.
        """
        delta = event.angleDelta().y()
        zoom_factor = 1.1 if delta > 0 else 0.9
        self.zoom = self._zoom * zoom_factor

    def mousePressEvent(self, event: QMouseEvent) -> None:
        """
        Handle mouse press for pan start.

        Args:
            event: Mouse event.
        """
        if event.button() == Qt.MouseButton.LeftButton:
            self._last_mouse_pos = event.position()

    def mouseMoveEvent(self, event: QMouseEvent) -> None:
        """
        Handle mouse move for panning and cursor tracking.

        Args:
            event: Mouse event.
        """
        pos = event.position()

        # Emit cursor position
        img_x, img_y = self.screen_to_image(pos.x(), pos.y())
        if self._image_data is not None:
            h, w = self._image_data.shape[:2]
            ix, iy = int(img_x), int(img_y)
            if 0 <= ix < w and 0 <= iy < h:
                value = float(self._image_data[iy, ix])
                self.cursor_moved.emit(img_x, img_y, value)

        # Handle panning
        if self._last_mouse_pos is not None:
            dx = (pos.x() - self._last_mouse_pos.x()) / self._zoom
            dy = (pos.y() - self._last_mouse_pos.y()) / self._zoom
            self._pan_x -= dx
            self._pan_y -= dy
            self._last_mouse_pos = pos
            self.pan_changed.emit(self._pan_x, self._pan_y)
            self.update()

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:
        """
        Handle mouse release for pan end.

        Args:
            event: Mouse event.
        """
        if event.button() == Qt.MouseButton.LeftButton:
            self._last_mouse_pos = None

    def _upload_texture(self) -> None:
        """Upload image data to GPU texture."""
        pass  # Implementation depends on OpenGL version
