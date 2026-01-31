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
Image viewer with integrated region overlay.

Author: Yogesh Wadadekar
"""

from typing import Optional
from PyQt6.QtCore import Qt, QPoint, pyqtSignal, QSize
from PyQt6.QtGui import QPixmap, QWheelEvent, QMouseEvent
from PyQt6.QtWidgets import QWidget, QVBoxLayout
from ..image_viewer import ImageViewer
from .region_overlay import RegionOverlay, RegionMode, Region
from .contour_overlay import ContourOverlay


class ImageViewerWithRegions(QWidget):
    """Image viewer with region overlay capabilities."""
    
    # Forward signals from base viewer
    mouse_moved = pyqtSignal(int, int)
    contrast_changed = pyqtSignal(float, float)
    
    # Region signals
    region_created = pyqtSignal(object)
    region_selected = pyqtSignal(object)
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMouseTracking(True)
        
        # Create layout
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        
        # Create base image viewer
        self.image_viewer = ImageViewer(self)
        layout.addWidget(self.image_viewer)
        
        # Create region overlay on top
        self.region_overlay = RegionOverlay(self.image_viewer)

        # Create contour overlay on top
        self.contour_overlay = ContourOverlay(self.image_viewer)
        
        # Connect signals
        self.image_viewer.mouse_moved.connect(self.mouse_moved)
        self.image_viewer.contrast_changed.connect(self.contrast_changed)
        self.region_overlay.region_created.connect(self.region_created)
        self.region_overlay.region_selected.connect(self.region_selected)

        # Start in non-interactive mode so mouse events reach the image viewer
        self.set_region_mode(RegionMode.NONE)
        
        # Track when middle button is pressed for centering
        self._middle_button_for_center = False
    
    def set_image(self, pixmap: QPixmap) -> None:
        """Set image pixmap."""
        self.image_viewer.set_image(pixmap)
        self._update_overlay_geometry()
    
    def set_region_mode(self, mode: RegionMode) -> None:
        """Set region drawing mode."""
        self.region_overlay.set_mode(mode)
        
        # Enable/disable mouse events based on mode
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
        """Add a region to display."""
        self.region_overlay.add_region(region)
    
    def clear_regions(self) -> None:
        """Clear all regions."""
        self.region_overlay.clear_regions()
    
    def zoom_in(self) -> None:
        """Zoom in."""
        self.image_viewer.zoom_in()
        self._update_overlay_transform()
    
    def zoom_out(self) -> None:
        """Zoom out."""
        self.image_viewer.zoom_out()
        self._update_overlay_transform()
    
    def zoom_to(self, zoom: float) -> None:
        """Set specific zoom level."""
        self.image_viewer.zoom_to(zoom)
        self._update_overlay_transform()
    
    def zoom_fit(self, viewport_size: QSize) -> None:
        """Zoom to fit viewport."""
        self.image_viewer.zoom_fit(viewport_size)
        self._update_overlay_transform()
    
    def zoom_actual(self) -> None:
        """Zoom to 1:1."""
        self.image_viewer.zoom_actual()
        self._update_overlay_transform()
    
    def get_zoom(self) -> float:
        """Get current zoom level."""
        return self.image_viewer.get_zoom()
    
    def get_contrast_brightness(self) -> tuple:
        """Get contrast/brightness values."""
        return self.image_viewer.get_contrast_brightness()
    
    def reset_contrast_brightness(self) -> None:
        """Reset contrast/brightness."""
        self.image_viewer.reset_contrast_brightness()
    
    def pixmap(self) -> Optional[QPixmap]:
        """Get current pixmap."""
        return self.image_viewer.pixmap()
    
    def setText(self, text: str) -> None:
        """Set text (for empty state)."""
        self.image_viewer.setText(text)

    def set_background_color(self, color_hex: str) -> None:
        """Set viewer background color."""
        self.image_viewer.setStyleSheet(f"background-color: {color_hex};")
    
    def _update_overlay_geometry(self) -> None:
        """Update region overlay geometry to match image viewer."""
        self.region_overlay.setGeometry(self.image_viewer.geometry())
        self.contour_overlay.setGeometry(self.image_viewer.geometry())
        self._update_overlay_transform()
    
    def _update_overlay_transform(self) -> None:
        """Update region overlay transform (zoom/offset)."""
        # Calculate image offset within viewer
        if self.image_viewer.pixmap():
            viewer_rect = self.image_viewer.rect()
            pixmap_rect = self.image_viewer.pixmap().rect()
            
            x_offset = (viewer_rect.width() - pixmap_rect.width()) / 2
            y_offset = (viewer_rect.height() - pixmap_rect.height()) / 2
            
            self.region_overlay.set_zoom(self.image_viewer.get_zoom(), (x_offset, y_offset))
            self.contour_overlay.set_zoom(self.image_viewer.get_zoom(), (x_offset, y_offset))
    
    def resizeEvent(self, event) -> None:
        """Handle resize events."""
        super().resizeEvent(event)
        self._update_overlay_geometry()
    
    def wheelEvent(self, event: QWheelEvent) -> None:
        """Forward wheel events to image viewer."""
        self.image_viewer.wheelEvent(event)
        self._update_overlay_transform()
    
    def mousePressEvent(self, event: QMouseEvent) -> None:
        """Handle mouse press - check for middle button center."""
        # Right button is ALWAYS for contrast/brightness - forward to image viewer
        if event.button() == Qt.MouseButton.RightButton:
            self.image_viewer.mousePressEvent(event)
            return
        
        if event.button() == Qt.MouseButton.MiddleButton:
            # Check if we should center (Ctrl modifier) or pan (default)
            if event.modifiers() & Qt.KeyboardModifier.ControlModifier:
                self._middle_button_for_center = True
                self._center_on_point(event.position().x(), event.position().y())
                event.accept()
                return
            else:
                # Pan mode - forward to image viewer
                self.image_viewer.mousePressEvent(event)
                return
        
        # Left button - forward to region overlay or image viewer
        if self.region_overlay.mode != RegionMode.NONE:
            self.region_overlay.mousePressEvent(event)
        else:
            self.image_viewer.mousePressEvent(event)
    
    def mouseMoveEvent(self, event: QMouseEvent) -> None:
        """Forward mouse move events."""
        # If adjusting contrast (right button) or panning (middle button), forward to image viewer
        if self.image_viewer._adjusting_contrast or self.image_viewer._panning:
            self.image_viewer.mouseMoveEvent(event)
            return
        
        # Otherwise handle regions
        if self.region_overlay.mode != RegionMode.NONE or self.region_overlay.selected_region:
            self.region_overlay.mouseMoveEvent(event)
        else:
            self.image_viewer.mouseMoveEvent(event)
    
    def mouseReleaseEvent(self, event: QMouseEvent) -> None:
        """Forward mouse release events."""
        # Right button or middle button - forward to image viewer
        if event.button() == Qt.MouseButton.RightButton or event.button() == Qt.MouseButton.MiddleButton:
            if self._middle_button_for_center and event.button() == Qt.MouseButton.MiddleButton:
                self._middle_button_for_center = False
                event.accept()
                return
            self.image_viewer.mouseReleaseEvent(event)
            return
        
        # Left button - handle regions
        if self.region_overlay.mode != RegionMode.NONE:
            self.region_overlay.mouseReleaseEvent(event)
        else:
            self.image_viewer.mouseReleaseEvent(event)
    
    def _center_on_point(self, x: float, y: float) -> None:
        """Center image on the given point (Ctrl+Middle click)."""
        # This is a simplified version - just emit a signal
        # The main window can handle recentering the scroll area
        pass  # TODO: Implement centering logic in main window
