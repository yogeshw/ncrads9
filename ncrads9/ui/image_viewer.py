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
Interactive image viewer widget with DS9-style mouse controls.

Author: Yogesh Wadadekar
"""

from typing import Optional
import numpy as np
from numpy.typing import NDArray

from PyQt6.QtCore import Qt, QPoint, QSize, pyqtSignal
from PyQt6.QtGui import QImage, QPixmap, QPainter, QTransform, QWheelEvent, QMouseEvent
from PyQt6.QtWidgets import QLabel

from .view_transform import DisplayTransform, normalize_rotation


class ImageViewer(QLabel):
    """Interactive image viewer with zoom, pan, and contrast/brightness controls."""
    
    # Signals
    mouse_moved = pyqtSignal(int, int)  # pixel x, y
    mouse_clicked = pyqtSignal(int, int, int)  # pixel x, y, button value
    contrast_changed = pyqtSignal(float, float)  # contrast, brightness
    
    def __init__(self, parent=None):
        super().__init__(parent)
        
        self.setMouseTracking(True)
        self.setScaledContents(True)
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        
        # Set size policy to expand in both directions
        from PyQt6.QtWidgets import QSizePolicy
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.setMinimumSize(100, 100)
        
        # Image data
        self._pixmap: Optional[QPixmap] = None
        self._source_pixmap: Optional[QPixmap] = None
        self._transform_cache_key: Optional[tuple[int, float, bool, bool]] = None
        self._zoom = 1.0
        self._rotation = 0.0
        self._flip_x = False
        self._flip_y = False
        
        # Mouse interaction state
        self._panning = False
        self._adjusting_contrast = False
        self._last_pos = QPoint()
        self._pan_offset = QPoint(0, 0)
        
        # Contrast/brightness adjustments (used by parent to re-render)
        self._contrast_scale = 1.0
        self._brightness_offset = 0.0
        
    def set_image(self, pixmap: QPixmap) -> None:
        """Set the image to display."""
        self._source_pixmap = pixmap
        self._transform_cache_key = None
        self._update_display()

    def set_view_transform(self, rotation: float, flip_x: bool, flip_y: bool) -> None:
        """Set display rotation and flip state."""
        self._rotation = normalize_rotation(rotation)
        self._flip_x = bool(flip_x)
        self._flip_y = bool(flip_y)
        self._update_display()

    def get_view_transform(self) -> DisplayTransform:
        """Return the current display transform."""
        width = self._source_pixmap.width() if self._source_pixmap is not None else 0
        height = self._source_pixmap.height() if self._source_pixmap is not None else 0
        return DisplayTransform(
            width=width,
            height=height,
            rotation=self._rotation,
            flip_x=self._flip_x,
            flip_y=self._flip_y,
        )
    
    def _update_display(self) -> None:
        """Update the displayed image with current zoom and pan."""
        if self._source_pixmap is None:
            return

        cache_key = (
            int(self._source_pixmap.cacheKey()),
            self._rotation,
            self._flip_x,
            self._flip_y,
        )
        if cache_key != self._transform_cache_key:
            transform = QTransform()
            transform.scale(-1.0 if self._flip_x else 1.0, -1.0 if self._flip_y else 1.0)
            if self._rotation:
                transform.rotate(self._rotation)

            self._pixmap = self._source_pixmap.transformed(
                transform,
                Qt.TransformationMode.SmoothTransformation,
            )
            self._transform_cache_key = cache_key

        if self._pixmap is None:
            return

        scaled_size = self._pixmap.size() * self._zoom
        self.setPixmap(self._pixmap)
        self.resize(scaled_size)
    
    def zoom_in(self) -> None:
        """Zoom in by 20%."""
        self._zoom *= 1.2
        self._update_display()
    
    def zoom_out(self) -> None:
        """Zoom out by 20%."""
        self._zoom /= 1.2
        self._update_display()
    
    def zoom_to(self, zoom: float) -> None:
        """Set specific zoom level."""
        self._zoom = max(0.1, min(zoom, 20.0))
        self._update_display()
    
    def zoom_fit(self, container_size: QSize) -> None:
        """Zoom to fit container."""
        if self._source_pixmap is None:
            return

        display_w, display_h = self.get_display_image_size()
        if display_w <= 0 or display_h <= 0:
            return
        width_ratio = container_size.width() / display_w
        height_ratio = container_size.height() / display_h
        self._zoom = min(width_ratio, height_ratio) * 0.95
        self._update_display()
    
    def zoom_actual(self) -> None:
        """Zoom to 1:1 (actual size)."""
        self._zoom = 1.0
        self._update_display()
    
    def get_zoom(self) -> float:
        """Get current zoom level."""
        return self._zoom

    def get_image_size(self) -> tuple[int, int]:
        """Get original image size (width, height)."""
        if self._source_pixmap is None:
            return (0, 0)
        return (self._source_pixmap.width(), self._source_pixmap.height())

    def get_display_image_size(self) -> tuple[int, int]:
        """Get displayed image size before zoom scaling."""
        if self._source_pixmap is None:
            return (0, 0)
        transform = self.get_view_transform()
        return (int(round(transform.display_width)), int(round(transform.display_height)))
    
    def get_contrast_brightness(self) -> tuple[float, float]:
        """Get current contrast and brightness adjustments."""
        return self._contrast_scale, self._brightness_offset

    def set_contrast_brightness(self, contrast: float, brightness: float) -> None:
        """Set contrast and brightness adjustments."""
        self._contrast_scale = max(0.1, min(contrast, 10.0))
        self._brightness_offset = max(-1.0, min(brightness, 1.0))
    
    def reset_contrast_brightness(self) -> None:
        """Reset contrast and brightness to defaults."""
        self._contrast_scale = 1.0
        self._brightness_offset = 0.0
    
    def wheelEvent(self, event: QWheelEvent) -> None:
        """Handle mouse wheel for zooming."""
        # Get zoom delta
        delta = event.angleDelta().y()
        
        if delta > 0:
            self.zoom_in()
        else:
            self.zoom_out()
        
        event.accept()
    
    def mousePressEvent(self, event: QMouseEvent) -> None:
        """Handle mouse button press."""
        coords = self._event_to_image_coords(event)
        if coords is not None:
            self.mouse_clicked.emit(coords[0], coords[1], int(event.button().value))

        if event.button() == Qt.MouseButton.MiddleButton:
            self._panning = True
            self._last_pos = event.pos()
            self.setCursor(Qt.CursorShape.ClosedHandCursor)
        
        elif event.button() == Qt.MouseButton.RightButton:
            self._adjusting_contrast = True
            self._last_pos = event.pos()
            self.setCursor(Qt.CursorShape.SizeAllCursor)
        
        event.accept()
    
    def mouseReleaseEvent(self, event: QMouseEvent) -> None:
        """Handle mouse button release."""
        if event.button() == Qt.MouseButton.MiddleButton:
            self._panning = False
            self.setCursor(Qt.CursorShape.ArrowCursor)
        
        elif event.button() == Qt.MouseButton.RightButton:
            self._adjusting_contrast = False
            self.setCursor(Qt.CursorShape.ArrowCursor)
        
        event.accept()
    
    def mouseMoveEvent(self, event: QMouseEvent) -> None:
        """Handle mouse movement."""
        if self._pixmap is None:
            return
        
        # Emit pixel coordinates for status bar
        coords = self._event_to_image_coords(event)
        if coords is not None:
            self.mouse_moved.emit(*coords)
        
        # Handle panning
        if self._panning:
            delta = event.pos() - self._last_pos
            self._pan_offset += delta
            self._last_pos = event.pos()
            # Pan would require scroll area manipulation
        
        # Handle contrast/brightness adjustment
        elif self._adjusting_contrast:
            delta = event.pos() - self._last_pos
            
            # Horizontal movement = contrast (scale)
            # Vertical movement = brightness (offset)
            contrast_delta = delta.x() * 0.002
            brightness_delta = -delta.y() * 0.002
            
            self._contrast_scale = max(0.1, min(self._contrast_scale + contrast_delta, 10.0))
            self._brightness_offset = max(-1.0, min(self._brightness_offset + brightness_delta, 1.0))
            
            self._last_pos = event.pos()
            
            # Emit signal to trigger re-render
            self.contrast_changed.emit(self._contrast_scale, self._brightness_offset)
        
        event.accept()

    def _event_to_image_coords(self, event: QMouseEvent) -> Optional[tuple[int, int]]:
        """Convert a mouse event position to image pixel coordinates."""
        return self.map_widget_to_image_coords(event.position().x(), event.position().y())

    def map_widget_to_image_coords(self, x: float, y: float) -> Optional[tuple[int, int]]:
        """Convert widget coordinates to source image coordinates."""
        if self._source_pixmap is None or self.pixmap() is None:
            return None

        label_rect = self.rect()
        pixmap_rect = self.pixmap().rect()
        x_offset = (label_rect.width() - pixmap_rect.width()) / 2
        y_offset = (label_rect.height() - pixmap_rect.height()) / 2
        display_x = (x - x_offset) / self._zoom
        display_y = (y - y_offset) / self._zoom
        transform = self.get_view_transform()
        source_x, source_y = transform.display_to_source(display_x, display_y)
        if 0 <= source_x < self._source_pixmap.width() and 0 <= source_y < self._source_pixmap.height():
            img_x = int(source_x)
            img_y = int(self._source_pixmap.height() - 1 - source_y)
            return (img_x, img_y)
        return None

    def map_image_to_display_coords(self, x: float, y: float) -> Optional[tuple[float, float]]:
        """Convert source image coordinates (bottom-left origin) to display coordinates."""
        if self._source_pixmap is None:
            return None
        source_top_y = self._source_pixmap.height() - 1 - float(y)
        return self.get_view_transform().source_to_display(float(x), source_top_y)
