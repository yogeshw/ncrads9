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
Region overlay for drawing and displaying regions.

The overlay owns three things: the image<->widget coordinate transform, the
mouse gestures that create and move regions, and a `RegionManager` holding the
regions themselves. Painting is delegated to `RegionRenderer`.

Regions are `BaseRegion` subclasses -- the same objects the parser produces and
the writer consumes -- so nothing is converted on the way in or out. Before M1
this widget had its own `Region` dataclass holding a `RegionMode` and a list of
`QPointF`, and `main_window` translated between the two representations; that
round trip silently dropped colour, width, text, tags and every DS9 property.

Author: Yogesh Wadadekar
"""

from enum import Enum

from PyQt6.QtCore import QPointF, Qt, pyqtSignal
from PyQt6.QtGui import QPainter
from PyQt6.QtWidgets import QWidget

from ...regions.base_region import BaseRegion
from ...regions.region_manager import RegionManager
from ...regions.region_renderer import RegionRenderer
from ...regions.shapes.box import Box
from ...regions.shapes.circle import Circle
from ...regions.shapes.ellipse import Ellipse
from ...regions.shapes.line import Line
from ...regions.shapes.point import Point
from ...regions.shapes.polygon import Polygon
from ..view_transform import DisplayTransform


class RegionMode(Enum):
    """Region drawing modes."""

    NONE = "none"
    CIRCLE = "circle"
    BOX = "box"
    ELLIPSE = "ellipse"
    POLYGON = "polygon"
    POINT = "point"
    LINE = "line"


#: Modes finalized by dragging out a second point.
_DRAG_MODES = (RegionMode.CIRCLE, RegionMode.BOX, RegionMode.ELLIPSE, RegionMode.LINE)

#: Default colour for newly drawn regions, matching DS9.
DEFAULT_REGION_COLOR = "green"


class RegionOverlay(QWidget):
    """Overlay widget for drawing and displaying regions."""

    region_created = pyqtSignal(object)  # Emits the new BaseRegion
    region_selected = pyqtSignal(object)  # Emits the selected BaseRegion

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, False)
        self.setMouseTracking(True)

        self.mode: RegionMode = RegionMode.NONE
        self.manager = RegionManager()
        self.renderer = RegionRenderer()

        self.current_points: list[QPointF] = []
        self.is_drawing: bool = False
        self.zoom: float = 1.0
        self.image_offset: tuple[float, float] = (0, 0)
        self.image_width: int = 0
        self.image_height: int = 0
        self.rotation: float = 0.0
        self.flip_x: bool = False
        self.flip_y: bool = False

        # For moving/editing
        self.selected_region: BaseRegion | None = None
        self.drag_start: QPointF | None = None

    # -- region collection --------------------------------------------------

    @property
    def regions(self) -> list[BaseRegion]:
        """The regions on this overlay, in draw order."""
        return self.manager.regions

    @regions.setter
    def regions(self, value: list[BaseRegion]) -> None:
        """Replace every region on the overlay."""
        self.manager.clear()
        for region in value:
            self.manager.add_region(region)
        self.selected_region = None
        self.update()

    def add_region(self, region: BaseRegion) -> None:
        """Add a completed region."""
        self.manager.add_region(region)
        self.update()

    def clear_regions(self) -> None:
        """Clear all regions."""
        self.manager.clear()
        self.selected_region = None
        self.update()

    # -- view state ---------------------------------------------------------

    def set_mode(self, mode: RegionMode) -> None:
        """Set region drawing mode."""
        self.mode = mode
        self.current_points = []
        self.is_drawing = False
        self.update()

    def set_zoom(
        self,
        zoom: float,
        offset: tuple[float, float],
        image_width: int | None = None,
        image_height: int | None = None,
        rotation: float = 0.0,
        flip_x: bool = False,
        flip_y: bool = False,
    ) -> None:
        """Update zoom and offset for coordinate transformation."""
        self.zoom = zoom
        self.image_offset = offset
        if image_width is not None:
            self.image_width = max(0, int(image_width))
        if image_height is not None:
            self.image_height = max(0, int(image_height))
        self.rotation = rotation
        self.flip_x = flip_x
        self.flip_y = flip_y
        self.update()

    def _display_transform(self) -> DisplayTransform:
        return DisplayTransform(
            width=self.image_width,
            height=self.image_height,
            rotation=self.rotation,
            flip_x=self.flip_x,
            flip_y=self.flip_y,
        )

    # -- coordinates --------------------------------------------------------

    def _widget_to_image_coords(self, widget_point: QPointF) -> QPointF:
        """Convert widget coordinates to image coordinates."""
        display_x = (widget_point.x() - self.image_offset[0]) / self.zoom
        display_y = (widget_point.y() - self.image_offset[1]) / self.zoom
        source_x, source_top_y = self._display_transform().display_to_source(display_x, display_y)
        if self.image_height > 0:
            img_y = self.image_height - 1 - source_top_y
        else:
            img_y = source_top_y
        img_x = source_x
        return QPointF(img_x, img_y)

    def _image_to_widget_coords(self, image_point: QPointF) -> QPointF:
        """Convert image coordinates to widget coordinates."""
        if self.image_height > 0:
            source_top_y = self.image_height - 1 - image_point.y()
        else:
            source_top_y = image_point.y()
        display_x, display_y = self._display_transform().source_to_display(
            image_point.x(),
            source_top_y,
        )
        widget_x = display_x * self.zoom + self.image_offset[0]
        widget_y = display_y * self.zoom + self.image_offset[1]
        return QPointF(widget_x, widget_y)

    def _to_widget(self, x: float, y: float) -> QPointF:
        """Adapter matching `RegionRenderer.ToWidget`."""
        return self._image_to_widget_coords(QPointF(x, y))

    # -- shape construction -------------------------------------------------

    def _build_region(self, mode: RegionMode, points: list[QPointF]) -> BaseRegion | None:
        """Build the concrete shape a finished gesture describes.

        Gesture conventions, unchanged from the pre-M1 overlay:
          circle          points[0] = centre, points[1] = a point on the rim
          box / ellipse   points[0], points[1] = opposite corners of the bounds
          line            points[0] = start, points[1] = end
          point           points[0] = position
          polygon         every point is a vertex
        """
        color = DEFAULT_REGION_COLOR

        if mode == RegionMode.CIRCLE and len(points) >= 2:
            center, edge = points[0], points[1]
            radius = ((edge.x() - center.x()) ** 2 + (edge.y() - center.y()) ** 2) ** 0.5
            return Circle(center=(center.x(), center.y()), radius=radius, color=color)

        if mode == RegionMode.ELLIPSE and len(points) >= 2:
            p1, p2 = points[0], points[1]
            return Ellipse(
                center=((p1.x() + p2.x()) / 2, (p1.y() + p2.y()) / 2),
                semi_major=abs(p2.x() - p1.x()) / 2,
                semi_minor=abs(p2.y() - p1.y()) / 2,
                color=color,
            )

        if mode == RegionMode.BOX and len(points) >= 2:
            p1, p2 = points[0], points[1]
            return Box(
                center=((p1.x() + p2.x()) / 2, (p1.y() + p2.y()) / 2),
                width_box=abs(p2.x() - p1.x()),
                height_box=abs(p2.y() - p1.y()),
                color=color,
            )

        if mode == RegionMode.LINE and len(points) >= 2:
            p1, p2 = points[0], points[1]
            return Line(start=(p1.x(), p1.y()), end=(p2.x(), p2.y()), color=color)

        if mode == RegionMode.POINT and len(points) >= 1:
            return Point(center=(points[0].x(), points[0].y()), color=color)

        if mode == RegionMode.POLYGON and len(points) >= 3:
            return Polygon(vertices=[(p.x(), p.y()) for p in points], color=color)

        return None

    def _finalize(self, mode: RegionMode, points: list[QPointF]) -> bool:
        """Turn a finished gesture into a region and announce it."""
        region = self._build_region(mode, points)
        if region is None:
            return False
        self.manager.add_region(region)
        self.region_created.emit(region)
        return True

    def _select(self, region: BaseRegion | None) -> None:
        """Make `region` the selection, clearing any previous one."""
        if self.selected_region is not None:
            self.selected_region.selected = False
        self.selected_region = region
        if region is not None:
            region.selected = True

    # -- mouse --------------------------------------------------------------

    def mousePressEvent(self, event) -> None:
        """Handle mouse press for region drawing."""
        if event.button() in (Qt.MouseButton.RightButton, Qt.MouseButton.MiddleButton):
            event.ignore()
            return

        if self.mode == RegionMode.NONE:
            # Selection mode - check if clicking on existing region
            img_point = self._widget_to_image_coords(event.position())
            for region in reversed(self.regions):  # Check from top
                if region.contains(img_point.x(), img_point.y()):
                    self._select(region)
                    self.drag_start = img_point
                    self.region_selected.emit(region)
                    self.update()
                    event.accept()
                    return

            # Clicked on empty space - deselect
            if self.selected_region:
                self._select(None)
                self.update()
            event.accept()
            return

        # Drawing mode
        if event.button() == Qt.MouseButton.LeftButton:
            img_point = self._widget_to_image_coords(event.position())

            if self.mode == RegionMode.POLYGON:
                # Polygon: accumulate points
                self.current_points.append(img_point)
                self.is_drawing = True
            elif self.mode == RegionMode.POINT:
                # Point: place immediately
                self._finalize(self.mode, [img_point])
                self.current_points = []
                self.is_drawing = False
                self.update()
                event.accept()
                return
            else:
                # Circle, Box, Ellipse, Line: start new region
                self.current_points = [img_point]
                self.is_drawing = True

            self.update()
            event.accept()

    def mouseMoveEvent(self, event) -> None:
        """Handle mouse move for region preview or editing."""
        if event.buttons() & (Qt.MouseButton.RightButton | Qt.MouseButton.MiddleButton):
            event.ignore()
            return

        if not self.is_drawing and self.mode == RegionMode.NONE:
            # Moving selected region
            if self.selected_region and self.drag_start:
                if not self.selected_region.can_move:
                    event.accept()
                    return
                img_point = self._widget_to_image_coords(event.position())
                self.selected_region.move(
                    img_point.x() - self.drag_start.x(),
                    img_point.y() - self.drag_start.y(),
                )
                self.drag_start = img_point
                self.update()
            event.accept()
            return

        if self.is_drawing and len(self.current_points) > 0:
            # Update preview
            img_point = self._widget_to_image_coords(event.position())

            if self.mode in _DRAG_MODES:
                # For these, we update the second point
                if len(self.current_points) == 1:
                    self.current_points.append(img_point)
                else:
                    self.current_points[1] = img_point

            self.update()
            event.accept()

    def mouseReleaseEvent(self, event) -> None:
        """Handle mouse release to finalize region."""
        # Right-click closes a polygon, so it has to reach the branch below.
        # Every other right or middle release belongs to the viewer underneath
        # (pan, context menu), so pass those through untouched.
        finishing_polygon = self.mode == RegionMode.POLYGON and event.button() == Qt.MouseButton.RightButton
        if not finishing_polygon and event.button() in (
            Qt.MouseButton.RightButton,
            Qt.MouseButton.MiddleButton,
        ):
            event.ignore()
            return

        if self.mode == RegionMode.NONE:
            self.drag_start = None
            event.accept()
            return

        if event.button() == Qt.MouseButton.LeftButton and self.is_drawing:
            if self.mode == RegionMode.POLYGON:
                # Polygon continues until double-click or right-click
                pass
            else:
                self._finalize(self.mode, self.current_points)
                self.current_points = []
                self.is_drawing = False
                self.update()

            event.accept()

        elif event.button() == Qt.MouseButton.RightButton and self.mode == RegionMode.POLYGON:
            # Finalize polygon
            self._finalize(RegionMode.POLYGON, self.current_points)
            self.current_points = []
            self.is_drawing = False
            self.update()
            event.accept()

    def mouseDoubleClickEvent(self, event) -> None:
        """Handle double click to finalize polygon."""
        if self.mode == RegionMode.POLYGON and event.button() == Qt.MouseButton.LeftButton:
            self._finalize(RegionMode.POLYGON, self.current_points)
            self.current_points = []
            self.is_drawing = False
            self.update()
            event.accept()
            return
        super().mouseDoubleClickEvent(event)

    # -- painting -----------------------------------------------------------

    def paintEvent(self, event) -> None:
        """Paint regions on overlay."""
        painter = QPainter(self)
        self.renderer.render(painter, self.regions, self._to_widget)

        if self.is_drawing and self.current_points:
            self.renderer.render_preview(
                painter,
                self.mode.value,
                [(p.x(), p.y()) for p in self.current_points],
                self._to_widget,
            )
