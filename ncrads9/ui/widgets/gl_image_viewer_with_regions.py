# NCRADS9 - OpenGL Image Viewer with Regions
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
OpenGL image viewer widget with region overlay support.
"""

from typing import Optional, Callable

import numpy as np
from numpy.typing import NDArray
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QColor
from PyQt6.QtWidgets import QWidget, QVBoxLayout

from ...rendering.gl_canvas import GLCanvas
from .region_overlay import RegionOverlay, RegionMode, Region
from .contour_overlay import ContourOverlay


class GLImageViewerWithRegions(QWidget):
    """OpenGL-based image viewer with region overlay capabilities."""

    mouse_moved = pyqtSignal(int, int)
    contrast_changed = pyqtSignal(float, float)
    region_created = pyqtSignal(object)
    region_selected = pyqtSignal(object)

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.setMouseTracking(True)

        self._contrast_scale = 1.0
        self._brightness_offset = 0.0
        self._adjusting_contrast = False
        self._last_pos = None

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        self.gl_canvas = GLCanvas(self)
        layout.addWidget(self.gl_canvas)

        self.region_overlay = RegionOverlay(self.gl_canvas)
        self.contour_overlay = ContourOverlay(self.gl_canvas)

        self.gl_canvas.cursor_moved.connect(self._on_cursor_moved)
        self.gl_canvas.zoom_changed.connect(lambda _: self._update_overlay_transform())
        self.gl_canvas.pan_changed.connect(lambda *_: self._update_overlay_transform())
        self.region_overlay.region_created.connect(self.region_created)
        self.region_overlay.region_selected.connect(self.region_selected)

        self.set_region_mode(RegionMode.NONE)

    def _on_cursor_moved(self, x: float, y: float, value: float) -> None:
        self.mouse_moved.emit(int(x), int(y))

    def set_tile_provider(
        self,
        width: int,
        height: int,
        data_provider: Callable[[int, int, int, int], NDArray[np.uint8]],
    ) -> None:
        self.gl_canvas.set_tile_provider(width, height, data_provider)
        self._update_overlay_transform()

    def set_tile_size(self, tile_size: int) -> None:
        self.gl_canvas.set_tile_size(tile_size)

    def set_cache_size_mb(self, cache_size_mb: int) -> None:
        self.gl_canvas.set_cache_size_mb(cache_size_mb)

    def set_value_source(self, data: NDArray[np.float32]) -> None:
        self.gl_canvas.set_value_source(data)

    def set_region_mode(self, mode: RegionMode) -> None:
        self.region_overlay.set_mode(mode)
        if mode == RegionMode.NONE:
            self.region_overlay.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
        else:
            self.region_overlay.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, False)

    def set_contours(self, contours, levels, style) -> None:
        """Set contour paths and styling."""
        self.contour_overlay.set_contours(contours, levels)
        self.contour_overlay.set_style(*style)

    def clear_contours(self) -> None:
        """Clear contours overlay."""
        self.contour_overlay.clear()

    def add_region(self, region: Region) -> None:
        self.region_overlay.add_region(region)

    def clear_regions(self) -> None:
        self.region_overlay.clear_regions()

    def zoom_in(self) -> None:
        self.gl_canvas.zoom = self.gl_canvas.zoom * 1.2

    def zoom_out(self) -> None:
        self.gl_canvas.zoom = self.gl_canvas.zoom / 1.2

    def zoom_to(self, zoom: float) -> None:
        self.gl_canvas.zoom = zoom

    def zoom_fit(self, viewport_size) -> None:
        self.gl_canvas.zoom_to_fit()

    def zoom_actual(self) -> None:
        self.gl_canvas.zoom = 1.0

    def get_zoom(self) -> float:
        return self.gl_canvas.zoom

    def get_contrast_brightness(self) -> tuple[float, float]:
        return (self._contrast_scale, self._brightness_offset)

    def set_contrast_brightness(self, contrast: float, brightness: float) -> None:
        self._contrast_scale = max(0.1, min(contrast, 10.0))
        self._brightness_offset = max(-1.0, min(brightness, 1.0))

    def reset_contrast_brightness(self) -> None:
        self._contrast_scale = 1.0
        self._brightness_offset = 0.0

    def set_pan(self, pan_x: float, pan_y: float) -> None:
        self.gl_canvas.pan_offset = (pan_x, pan_y)
        self.gl_canvas.pan_changed.emit(pan_x, pan_y)
        self.gl_canvas.update()

    def mousePressEvent(self, event) -> None:
        if event.button() == Qt.MouseButton.RightButton:
            self._adjusting_contrast = True
            self._last_pos = event.position()
            event.accept()
            return
        self.gl_canvas.mousePressEvent(event)

    def mouseMoveEvent(self, event) -> None:
        if self._adjusting_contrast and self._last_pos is not None:
            delta = event.position() - self._last_pos
            contrast_delta = delta.x() * 0.002
            brightness_delta = -delta.y() * 0.002

            self._contrast_scale = max(0.1, min(self._contrast_scale + contrast_delta, 10.0))
            self._brightness_offset = max(-1.0, min(self._brightness_offset + brightness_delta, 1.0))
            self._last_pos = event.position()
            self.contrast_changed.emit(self._contrast_scale, self._brightness_offset)
            event.accept()
            return
        self.gl_canvas.mouseMoveEvent(event)

    def mouseReleaseEvent(self, event) -> None:
        if event.button() == Qt.MouseButton.RightButton:
            self._adjusting_contrast = False
            self._last_pos = None
            event.accept()
            return
        self.gl_canvas.mouseReleaseEvent(event)

    def pixmap(self):
        return None

    def setText(self, text: str) -> None:
        return

    def set_background_color(self, color_hex: str) -> None:
        color = QColor(color_hex)
        if color.isValid():
            self.gl_canvas.set_background_color(
                (color.redF(), color.greenF(), color.blueF(), 1.0)
            )

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        self.region_overlay.setGeometry(self.gl_canvas.geometry())
        self.contour_overlay.setGeometry(self.gl_canvas.geometry())
        self._update_overlay_transform()

    def _update_overlay_transform(self) -> None:
        x_offset, y_offset = self.gl_canvas.image_to_screen(0.0, 0.0)
        self.region_overlay.set_zoom(self.gl_canvas.zoom, (x_offset, y_offset))
        self.contour_overlay.set_zoom(self.gl_canvas.zoom, (x_offset, y_offset))
