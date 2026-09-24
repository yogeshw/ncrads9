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


from PyQt6.QtCore import QEvent, QSize, Qt, pyqtSignal
from PyQt6.QtGui import QMouseEvent, QPixmap, QWheelEvent
from PyQt6.QtWidgets import QScrollArea, QVBoxLayout, QWidget

from ...regions.base_region import BaseRegion
from ..image_viewer import ImageViewer
from .catalog_overlay import CatalogOverlay
from .contour_overlay import ContourOverlay
from .illustrate_overlay import IllustrateOverlay
from .region_overlay import RegionMode, RegionOverlay


class ImageViewerWithRegions(QWidget):
    """Image viewer with region overlay capabilities."""

    # Forward signals from base viewer
    mouse_moved = pyqtSignal(int, int)
    mouse_clicked = pyqtSignal(int, int, int)
    contrast_changed = pyqtSignal(float, float)
    #: A wheel notch: +1 to zoom in, -1 to zoom out. Routed through the zoom
    #: controller rather than zooming the widget directly, so it respects tile
    #: mode -- where a scroll zooms the current frame, not the whole mosaic.
    zoom_requested = pyqtSignal(int)
    #: The viewer was resized (the window changed size). The zoom controller
    #: refits the view so the frames grow and shrink with the available space.
    viewport_resized = pyqtSignal()

    # Region signals
    region_created = pyqtSignal(object)
    region_activated = pyqtSignal(object)
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
        # Catalogue symbols are a layer of their own, as in DS9: not
        # regions, not saved with them, not deleted by Region -> Delete All.
        self.catalog_overlay = CatalogOverlay(self.image_viewer)
        # The illustrate layer is drawn on the canvas rather than on the
        # data, so it takes no transform and follows nothing.
        self.illustrate_overlay = IllustrateOverlay(parent=self.image_viewer)
        # Topmost, because it owns the mouse: a Qt event a child ignores
        # goes to the parent, not to a sibling, so whichever overlay is on
        # top has to be the one that dispatches.
        self.region_overlay.raise_()
        self.catalog_overlay.pick_handler = None
        self.region_overlay.pick_handler = self.catalog_overlay.pick
        self.region_overlay.illustrate_handler = self.illustrate_overlay.handle_event

        # Connect signals
        # The overlay owns the mouse, so its hover is the one that reaches
        # the readout. The inner viewer's `mouse_moved` is kept connected
        # for the paths that still call its handler directly -- a contrast
        # drag, a pan -- but on a plain hover it never fires, which is why
        # the magnifier, the cut graphs and the pixel table all sat empty.
        self.region_overlay.hover_moved.connect(self.mouse_moved)
        self.image_viewer.mouse_moved.connect(self.mouse_moved)
        self.image_viewer.mouse_clicked.connect(self.mouse_clicked)
        self.image_viewer.contrast_changed.connect(self.contrast_changed)
        self.region_overlay.region_created.connect(self.region_created)
        self.region_overlay.region_activated.connect(self.region_activated)
        self.region_overlay.region_selected.connect(self.region_selected)

        # The inner viewer resizes *itself* when the image or the zoom
        # changes, and the overlays are sized from its geometry, so the
        # wrapper has to hear about it.
        self.image_viewer.installEventFilter(self)

        # Start in non-interactive mode so mouse events reach the image viewer
        self.set_region_mode(RegionMode.NONE)

        # Track when middle button is pressed for centering
        self._middle_button_for_center = False
        self._rotation = 0.0
        self._flip_x = False
        self._flip_y = False

    def set_image(self, pixmap: QPixmap) -> None:
        """Set image pixmap."""
        self.image_viewer.set_image(pixmap)
        self._update_overlay_geometry()

    def clear_image(self) -> None:
        """Blank the viewer, for a frame with no data."""
        self.image_viewer.clear_image()
        self._update_overlay_geometry()

    def set_block_factor(self, factor: int) -> None:
        """Pass DS9's Block factor to the viewer and its region overlay.

        Both map between widget and image coordinates, and both must agree on
        how many image pixels one drawn pixel holds.
        """
        block = max(1, int(factor))
        self.image_viewer.set_block_factor(block)
        self.region_overlay.block_factor = block
        self.region_overlay.update()

    def set_region_mode(self, mode: RegionMode) -> None:
        """Set region drawing mode."""
        self.region_overlay.set_mode(mode)

        # The overlay keeps the mouse in every mode. It used to be made
        # transparent in RegionMode.NONE so a click could fall through to
        # the viewer and pan -- which also meant an existing region could
        # not be selected, moved, resized or opened, since those all happen
        # in that mode. It ignores the clicks it does not want instead,
        # which reaches the viewer just the same.

    def set_contours(self, contours, levels, style) -> None:
        """Set contour paths and styling."""
        self.contour_overlay.set_contours(contours, levels)
        self.contour_overlay.set_style(*style)

    def clear_contours(self) -> None:
        """Clear contours overlay."""
        self.contour_overlay.clear()

    def set_direction_arrows(
        self,
        north_vector: tuple[float, float] | None,
        east_vector: tuple[float, float] | None,
        visible: bool,
    ) -> None:
        """Set WCS direction arrow vectors/visibility."""
        self.contour_overlay.set_direction_arrows(north_vector, east_vector, visible)

    def set_grid(self, visible: bool, settings: dict | None = None) -> None:
        """Set coordinate grid overlay visibility/settings."""
        self.contour_overlay.set_grid(visible, settings)

    def set_crosshair(
        self,
        visible: bool,
        position: tuple[float, float] | None = None,
        color=None,
        size: int | None = None,
    ) -> None:
        """Set crosshair overlay visibility/style."""
        self.contour_overlay.set_crosshair(visible, position=position, color=color, size=size)

    def add_region(self, region: BaseRegion) -> None:
        """Add a region to display."""
        self.region_overlay.add_region(region)

    def clear_regions(self) -> None:
        """Clear all regions."""
        self.region_overlay.clear_regions()

    def zoom_in(self) -> None:
        """Zoom in."""
        self.image_viewer.zoom_in()
        self._update_overlay_geometry()

    def zoom_out(self) -> None:
        """Zoom out."""
        self.image_viewer.zoom_out()
        self._update_overlay_geometry()

    def zoom_to(self, zoom: float) -> None:
        """Set specific zoom level."""
        self.image_viewer.zoom_to(zoom)
        self._update_overlay_geometry()

    def zoom_fit(self, viewport_size: QSize) -> None:
        """Zoom to fit viewport."""
        self.image_viewer.zoom_fit(viewport_size)
        self._update_overlay_geometry()

    def zoom_actual(self) -> None:
        """Zoom to 1:1."""
        self.image_viewer.zoom_actual()
        self._update_overlay_geometry()

    def set_view_transform(self, rotation: float, flip_x: bool, flip_y: bool) -> None:
        """Set display rotation and flip state."""
        self._rotation = rotation
        self._flip_x = flip_x
        self._flip_y = flip_y
        self.image_viewer.set_view_transform(rotation, flip_x, flip_y)
        # A quarter turn swaps the viewer's width and height, so the
        # overlays need resizing, not only re-transforming.
        self._update_overlay_geometry()

    def get_display_image_size(self) -> tuple[int, int]:
        """Get display image size after orientation/rotation."""
        return self.image_viewer.get_display_image_size()

    def get_zoom(self) -> float:
        """Get current zoom level."""
        return self.image_viewer.get_zoom()

    def get_contrast_brightness(self) -> tuple:
        """Get contrast/brightness values."""
        return self.image_viewer.get_contrast_brightness()

    def reset_contrast_brightness(self) -> None:
        """Reset contrast/brightness."""
        self.image_viewer.reset_contrast_brightness()

    def pixmap(self) -> QPixmap | None:
        """Get current pixmap."""
        return self.image_viewer.pixmap()

    def setText(self, text: str) -> None:
        """Set text (for empty state)."""
        self.image_viewer.setText(text)

    def set_background_color(self, color_hex: str) -> None:
        """Set viewer background color."""
        self.image_viewer.setStyleSheet(f"background-color: {color_hex};")

    def _update_overlay_geometry(self) -> None:
        """Size every overlay to the inner viewer, and refresh its transform.

        The viewer resizes itself whenever the image or the zoom changes,
        and the overlays are sized from it -- so anything that changes
        either has to come through here. Calling only
        `_update_overlay_transform` updates the zoom and the offset but
        leaves the overlay its old *size*, which is how regions, contours,
        catalogue symbols and illustrations came to be clipped to the
        widget's 100x100 minimum until the window was next resized.
        """
        self.region_overlay.setGeometry(self.image_viewer.geometry())
        self.contour_overlay.setGeometry(self.image_viewer.geometry())
        self.catalog_overlay.setGeometry(self.image_viewer.geometry())
        self.illustrate_overlay.setGeometry(self.image_viewer.geometry())
        self._update_overlay_transform()

    def _update_overlay_transform(self) -> None:
        """Update region overlay transform (zoom/offset)."""
        # Calculate image offset within viewer
        if self.image_viewer.pixmap():
            viewer_rect = self.image_viewer.rect()
            pixmap_rect = self.image_viewer.pixmap().rect()

            x_offset = (viewer_rect.width() - pixmap_rect.width()) / 2
            y_offset = (viewer_rect.height() - pixmap_rect.height()) / 2
            _, image_height = self.image_viewer.get_image_size()
            self.region_overlay.set_zoom(
                self.image_viewer.get_zoom(),
                (x_offset, y_offset),
                image_width=self.image_viewer.get_image_size()[0],
                image_height=image_height,
                rotation=self._rotation,
                flip_x=self._flip_x,
                flip_y=self._flip_y,
            )
            self.contour_overlay.set_zoom(
                self.image_viewer.get_zoom(),
                (x_offset, y_offset),
                image_width=self.image_viewer.get_image_size()[0],
                image_height=image_height,
                rotation=self._rotation,
                flip_x=self._flip_x,
                flip_y=self._flip_y,
            )
            self.catalog_overlay.set_zoom(
                self.image_viewer.get_zoom(),
                (x_offset, y_offset),
                image_width=self.image_viewer.get_image_size()[0],
                image_height=image_height,
                rotation=self._rotation,
                flip_x=self._flip_x,
                flip_y=self._flip_y,
            )

    def resizeEvent(self, event) -> None:
        """Handle resize events."""
        super().resizeEvent(event)
        self._update_overlay_geometry()
        self.viewport_resized.emit()

    def eventFilter(self, watched, event) -> bool:
        """Follow the inner viewer's own resizes.

        The overlays are sized from `image_viewer.geometry()`, and the
        inner viewer resizes *itself* -- `_update_display` calls `resize`
        whenever the image or the zoom changes. Nothing told the wrapper,
        so the overlays kept whatever geometry they had when the window
        was last resized: after loading an image they sat at the widget's
        100x100 minimum while the viewer was eight hundred pixels wide,
        and every region, contour, catalogue symbol and illustration was
        clipped to that corner.

        Never consumes the event.
        """
        if watched is self.image_viewer and event is not None:
            if event.type() in (QEvent.Type.Resize, QEvent.Type.Move):
                self._update_overlay_geometry()
        return False

    def wheelEvent(self, event: QWheelEvent) -> None:
        """Zoom on the wheel, through the controller so tile mode is honoured."""
        self.zoom_requested.emit(1 if event.angleDelta().y() > 0 else -1)
        event.accept()

    def mousePressEvent(self, event: QMouseEvent) -> None:
        """Handle mouse press - check for middle button center."""
        # Right button is ALWAYS for contrast/brightness - forward to image viewer
        if event.button() == Qt.MouseButton.RightButton:
            self.image_viewer.mousePressEvent(event)
            return

        if event.button() == Qt.MouseButton.MiddleButton:
            # Middle-click centers image at cursor (DS9 style)
            self._middle_button_for_center = True
            self._center_on_point(event.position().x(), event.position().y())
            event.accept()
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
        """Center image on the given point (Middle click, DS9 style)."""
        if self.image_viewer.pixmap() is None:
            return

        # Convert widget coordinates to image coordinates
        coords = self.image_viewer.map_widget_to_image_coords(x, y)
        if coords is None:
            return
        img_x, img_y = coords
        display_coords = self.image_viewer.map_image_to_display_coords(img_x, img_y)
        if display_coords is None:
            return
        display_x, display_y = display_coords

        # For scroll area-based viewer, we need to scroll to center this point
        # Get the scroll area from parent hierarchy
        parent = self.parent()
        while parent and not isinstance(parent, QScrollArea):
            parent = parent.parent()

        if parent and isinstance(parent, QScrollArea):
            # Calculate the scroll position to center this image point
            viewport_size = parent.viewport().size()
            zoom = self.image_viewer.get_zoom()

            # Position in zoomed coordinates where clicked point is
            zoomed_x = display_x * zoom
            zoomed_y = display_y * zoom

            # Scroll to center this point in viewport
            scroll_x = int(zoomed_x - viewport_size.width() / 2)
            scroll_y = int(zoomed_y - viewport_size.height() / 2)

            parent.horizontalScrollBar().setValue(scroll_x)
            parent.verticalScrollBar().setValue(scroll_y)
