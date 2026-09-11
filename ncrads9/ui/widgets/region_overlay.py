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

import math
from enum import Enum

from PyQt6.QtCore import QPointF, QRectF, Qt, pyqtSignal
from PyQt6.QtGui import QPainter
from PyQt6.QtWidgets import QWidget

from ...regions.base_region import BaseRegion
from ...regions.region_manager import RegionManager
from ...regions.region_renderer import HANDLE_SIZE, RegionRenderer
from ...regions.shapes.annulus import Annulus
from ...regions.shapes.box import Box
from ...regions.shapes.box_annulus import BoxAnnulus
from ...regions.shapes.bpanda import Bpanda
from ...regions.shapes.circle import Circle
from ...regions.shapes.compass import Compass
from ...regions.shapes.ellipse import Ellipse
from ...regions.shapes.ellipse_annulus import EllipseAnnulus
from ...regions.shapes.epanda import Epanda
from ...regions.shapes.line import Line
from ...regions.shapes.panda import Panda
from ...regions.shapes.point import Point
from ...regions.shapes.polygon import Polygon
from ...regions.shapes.projection import Projection
from ...regions.shapes.ruler import Ruler
from ...regions.shapes.segment import Segment
from ...regions.shapes.text import Text
from ...regions.shapes.vector import Vector
from ..view_transform import DisplayTransform


class RegionMode(Enum):
    """The shape the next gesture draws.

    The values are the keys of `MenuBar.region_shape_actions`, so the Region
    -> Shape cascade can name a mode directly rather than through a table.
    """

    NONE = "none"
    CIRCLE = "circle"
    BOX = "box"
    ELLIPSE = "ellipse"
    POLYGON = "polygon"
    POINT = "point"
    LINE = "line"
    VECTOR = "vector"
    SEGMENT = "segment"
    TEXT = "text"
    RULER = "ruler"
    COMPASS = "compass"
    PROJECTION = "projection"
    ANNULUS = "annulus"
    ELLIPSE_ANNULUS = "ellipseannulus"
    BOX_ANNULUS = "boxannulus"
    PANDA = "panda"
    EPANDA = "epanda"
    BPANDA = "bpanda"


#: Modes drawn outwards from a centre: the drag sets a radius.
_RADIUS_MODES = (
    RegionMode.CIRCLE,
    RegionMode.ANNULUS,
    RegionMode.ELLIPSE_ANNULUS,
    RegionMode.BOX_ANNULUS,
    RegionMode.PANDA,
    RegionMode.EPANDA,
    RegionMode.BPANDA,
    RegionMode.COMPASS,
)

#: Modes drawn as a bounding box: the drag sets two opposite corners.
_CORNER_MODES = (RegionMode.BOX, RegionMode.ELLIPSE)

#: Modes drawn end to end: the drag sets a start and an end.
_ENDPOINT_MODES = (
    RegionMode.LINE,
    RegionMode.VECTOR,
    RegionMode.RULER,
    RegionMode.PROJECTION,
)

#: Modes built up one vertex per click, closed by a double or right click.
_VERTEX_MODES = (RegionMode.POLYGON, RegionMode.SEGMENT)

#: Modes placed by a single click, with no drag at all.
_CLICK_MODES = (RegionMode.POINT, RegionMode.TEXT)

#: Modes finalized by dragging out a second point.
_DRAG_MODES = _RADIUS_MODES + _CORNER_MODES + _ENDPOINT_MODES

#: Default colour for newly drawn regions, matching DS9.
DEFAULT_REGION_COLOR = "green"

#: How far the cursor must travel for a gesture to count as a drag. Below
#: this a click still makes a region, at `DEFAULT_SIZE` -- DS9 does the same,
#: and without it a mis-clicked drag silently makes a zero-sized region.
MINIMUM_DRAG = 3.0

#: The size a region gets when it is clicked rather than dragged, in pixels.
DEFAULT_SIZE = 20.0

#: What a new annulus, panda or ellipse annulus takes for its inner radius,
#: as a fraction of its outer one.
INNER_FRACTION = 0.5

#: A new ellipse annulus and epanda are drawn this much narrower than they
#: are long, so the shape reads as elliptical the moment it appears.
MINOR_FRACTION = 0.6

#: DS9's defaults for a new panda: a full turn in four sectors, one annulus.
PANDA_ANGLES = (0.0, 360.0)
PANDA_SECTORS = 4
PANDA_ANNULI = 1

#: A new text region's label, which Get Information can then change.
DEFAULT_TEXT = "Text"

#: How near a handle the cursor must come to grab it, in widget pixels --
#: a little wider than the handle itself, because a six-pixel square is a
#: small target for a mouse.
HANDLE_GRAB = HANDLE_SIZE + 2.0

#: The smallest extent a drag may scale a region to. Below this the shape
#: would collapse to a point with no handle left to drag it back out by.
MINIMUM_EXTENT = 1e-6


class RegionOverlay(QWidget):
    """Overlay widget for drawing and displaying regions."""

    #: The cursor's image position on every hover, as (x, y) in image
    #: pixels. The overlay is the sole mouse owner (M9-1), so it is the
    #: only widget that knows where the pointer is -- the readout, the
    #: magnifier, the cut graphs and the pixel table all need telling, and
    #: relying on Qt to propagate an ignored move event to a sibling's
    #: wrapper did not work: none of them updated on hover at all.
    hover_moved = pyqtSignal(int, int)

    region_created = pyqtSignal(object)  # Emits the new BaseRegion
    region_selected = pyqtSignal(object)  # Emits the selected BaseRegion
    region_activated = pyqtSignal(object)  # Emits a double-clicked BaseRegion

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
        #: Image pixels per pixel of the array being drawn, under DS9's
        #: Block. Regions are stored in image pixels regardless.
        self.block_factor: int = 1
        self.rotation: float = 0.0
        self.flip_x: bool = False
        self.flip_y: bool = False

        # For moving/editing
        self.selected_region: BaseRegion | None = None
        self.drag_start: QPointF | None = None
        #: The pointer mode's handler, when a mode other than pointer or
        #: region is active. This overlay is the topmost child and the only
        #: one taking mouse events, so every mode is dispatched from here
        #: -- a second overlay taking clicks would take all of them.
        self.pointer_handler = None
        #: Called with a widget position when a click in pointer mode hits
        #: no region; returns True if something else consumed it. The
        #: catalogue layer installs this.
        self.pick_handler = None
        #: Called with (phase, widget position, button) in illustrate mode;
        #: returns True if the illustrate layer used the event. Installed by
        #: the host viewer, for the same reason `pick_handler` is: only this
        #: overlay takes mouse events.
        self.illustrate_handler = None
        #: Called with "begin" when a region is grabbed and "finish" when
        #: it is let go, so the controller can record the move for undo. A
        #: drag spans two events, which a context manager cannot.
        self.edit_notifier = None
        #: Called with an image position on the next press, once, when an
        #: interactive examine is waiting for a click. Returns True to
        #: swallow the press.
        self.examine_handler = None
        #: Which resize handle is being dragged, if any. `None` means the
        #: drag is a move (or nothing at all); an index means a reshape.
        self.dragging_handle: int | None = None
        #: True while the rotate handle is being dragged.
        self.rotating: bool = False

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
        """Convert widget coordinates to image coordinates.

        A region is stored in image pixels, so DS9's Block is undone here --
        otherwise a shape drawn under a block of four would be recorded a
        quarter of the way into the image and move when the block changed.
        """
        display_x = (widget_point.x() - self.image_offset[0]) / self.zoom
        display_y = (widget_point.y() - self.image_offset[1]) / self.zoom
        source_x, source_top_y = self._display_transform().display_to_source(display_x, display_y)
        if self.image_height > 0:
            img_y = self.image_height - 1 - source_top_y
        else:
            img_y = source_top_y
        img_x = source_x
        block = max(1, self.block_factor)
        return QPointF(img_x * block, img_y * block)

    def _image_to_widget_coords(self, image_point: QPointF) -> QPointF:
        """Convert image coordinates to widget coordinates.

        The inverse of `_widget_to_image_coords`, so Block is applied here.
        """
        block = max(1, self.block_factor)
        source_x = image_point.x() / block
        source_y = image_point.y() / block
        if self.image_height > 0:
            source_top_y = self.image_height - 1 - source_y
        else:
            source_top_y = source_y
        display_x, display_y = self._display_transform().source_to_display(
            source_x,
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

        There are four gesture families, and which one a shape belongs to is
        the constant it appears in rather than a branch here:

          `_RADIUS_MODES`    points[0] = centre, points[1] on the rim
          `_CORNER_MODES`    points[0], points[1] = opposite corners
          `_ENDPOINT_MODES`  points[0] = start, points[1] = end
          `_VERTEX_MODES`    every point is a vertex
          `_CLICK_MODES`     points[0] = position

        A click that never became a drag arrives here as a single point;
        `_sized` gives it `DEFAULT_SIZE` so it still makes a usable region,
        which is what DS9 does with a click on the frame.

        Returns:
            The region, or None if the gesture has too few points for the
            shape -- a two-vertex polygon, say.
        """
        builder = _BUILDERS.get(mode)
        if builder is None:
            return None

        if mode in _VERTEX_MODES:
            minimum = 3 if mode is RegionMode.POLYGON else 2
            return builder(self, points) if len(points) >= minimum else None
        if mode in _CLICK_MODES:
            return builder(self, points) if points else None
        if not points:
            return None
        return builder(self, self._sized(points))

    @staticmethod
    def _sized(points: list[QPointF]) -> list[QPointF]:
        """The gesture's points, with a click expanded to a default size.

        A click and a very short drag both mean "put one here": the second
        point is invented `DEFAULT_SIZE` away rather than making a region of
        no extent that cannot then be seen or grabbed.
        """
        first = points[0]
        if len(points) >= 2:
            second = points[1]
            if math.hypot(second.x() - first.x(), second.y() - first.y()) >= MINIMUM_DRAG:
                return points
        return [first, QPointF(first.x() + DEFAULT_SIZE, first.y() + DEFAULT_SIZE)]

    # -- one builder per shape ----------------------------------------------
    #
    # Each takes the gesture's points and returns the region. The colour is
    # the plain default here; `RegionController.on_created` then applies the
    # user's chosen colour, width, font and property flags.

    @staticmethod
    def _radius(points: list[QPointF]) -> float:
        """How far the drag reached from its centre."""
        centre, edge = points[0], points[1]
        return math.hypot(edge.x() - centre.x(), edge.y() - centre.y())

    @staticmethod
    def _centre(points: list[QPointF]) -> tuple[float, float]:
        """The midpoint of a corner-to-corner drag."""
        first, second = points[0], points[1]
        return ((first.x() + second.x()) / 2, (first.y() + second.y()) / 2)

    @staticmethod
    def _extent(points: list[QPointF]) -> tuple[float, float]:
        """The width and height a corner-to-corner drag spans."""
        first, second = points[0], points[1]
        return (abs(second.x() - first.x()), abs(second.y() - first.y()))

    def _build_circle(self, points: list[QPointF]) -> BaseRegion:
        centre = points[0]
        return Circle(
            center=(centre.x(), centre.y()),
            radius=self._radius(points),
            color=DEFAULT_REGION_COLOR,
        )

    def _build_ellipse(self, points: list[QPointF]) -> BaseRegion:
        width, height = self._extent(points)
        return Ellipse(
            center=self._centre(points),
            semi_major=width / 2,
            semi_minor=height / 2,
            color=DEFAULT_REGION_COLOR,
        )

    def _build_box(self, points: list[QPointF]) -> BaseRegion:
        width, height = self._extent(points)
        return Box(
            center=self._centre(points),
            width_box=width,
            height_box=height,
            color=DEFAULT_REGION_COLOR,
        )

    def _build_polygon(self, points: list[QPointF]) -> BaseRegion:
        return Polygon(
            vertices=[(point.x(), point.y()) for point in points],
            color=DEFAULT_REGION_COLOR,
        )

    def _build_segment(self, points: list[QPointF]) -> BaseRegion:
        return Segment(
            points=[(point.x(), point.y()) for point in points],
            color=DEFAULT_REGION_COLOR,
        )

    def _build_point(self, points: list[QPointF]) -> BaseRegion:
        return Point(center=(points[0].x(), points[0].y()), color=DEFAULT_REGION_COLOR)

    def _build_text(self, points: list[QPointF]) -> BaseRegion:
        # The label is a placeholder: a modal prompt in the middle of a mouse
        # gesture is worse than a region you can rename afterwards.
        return Text(
            center=(points[0].x(), points[0].y()),
            label=DEFAULT_TEXT,
            color=DEFAULT_REGION_COLOR,
        )

    def _build_line(self, points: list[QPointF]) -> BaseRegion:
        start, end = points[0], points[1]
        return Line(
            start=(start.x(), start.y()),
            end=(end.x(), end.y()),
            color=DEFAULT_REGION_COLOR,
        )

    def _build_vector(self, points: list[QPointF]) -> BaseRegion:
        start, end = points[0], points[1]
        dx, dy = end.x() - start.x(), end.y() - start.y()
        return Vector(
            start=(start.x(), start.y()),
            length=math.hypot(dx, dy),
            angle=math.degrees(math.atan2(dy, dx)),
            color=DEFAULT_REGION_COLOR,
        )

    def _build_ruler(self, points: list[QPointF]) -> BaseRegion:
        start, end = points[0], points[1]
        return Ruler(
            start=(start.x(), start.y()),
            end=(end.x(), end.y()),
            color=DEFAULT_REGION_COLOR,
        )

    def _build_projection(self, points: list[QPointF]) -> BaseRegion:
        start, end = points[0], points[1]
        return Projection(
            start=(start.x(), start.y()),
            end=(end.x(), end.y()),
            projection_width=0.0,
            color=DEFAULT_REGION_COLOR,
        )

    def _build_compass(self, points: list[QPointF]) -> BaseRegion:
        centre = points[0]
        return Compass(
            center=(centre.x(), centre.y()),
            length=self._radius(points),
            color=DEFAULT_REGION_COLOR,
        )

    def _build_annulus(self, points: list[QPointF]) -> BaseRegion:
        centre = points[0]
        outer = self._radius(points)
        return Annulus(
            center=(centre.x(), centre.y()),
            inner_radius=outer * INNER_FRACTION,
            outer_radius=outer,
            color=DEFAULT_REGION_COLOR,
        )

    def _build_ellipse_annulus(self, points: list[QPointF]) -> BaseRegion:
        centre = points[0]
        outer = self._radius(points)
        return EllipseAnnulus(
            center=(centre.x(), centre.y()),
            inner_semi_major=outer * INNER_FRACTION,
            inner_semi_minor=outer * INNER_FRACTION * MINOR_FRACTION,
            outer_semi_major=outer,
            outer_semi_minor=outer * MINOR_FRACTION,
            color=DEFAULT_REGION_COLOR,
        )

    def _build_box_annulus(self, points: list[QPointF]) -> BaseRegion:
        centre = points[0]
        outer = self._radius(points)
        return BoxAnnulus(
            center=(centre.x(), centre.y()),
            inner_width=outer * INNER_FRACTION * 2,
            inner_height=outer * INNER_FRACTION * MINOR_FRACTION * 2,
            outer_width=outer * 2,
            outer_height=outer * MINOR_FRACTION * 2,
            color=DEFAULT_REGION_COLOR,
        )

    def _build_panda(self, points: list[QPointF]) -> BaseRegion:
        centre = points[0]
        outer = self._radius(points)
        return Panda(
            center=(centre.x(), centre.y()),
            start_angle=PANDA_ANGLES[0],
            stop_angle=PANDA_ANGLES[1],
            num_angles=PANDA_SECTORS,
            inner_radius=outer * INNER_FRACTION,
            outer_radius=outer,
            num_radii=PANDA_ANNULI,
            color=DEFAULT_REGION_COLOR,
        )

    def _build_epanda(self, points: list[QPointF]) -> BaseRegion:
        return self._build_panda_variant(Epanda, points)

    def _build_bpanda(self, points: list[QPointF]) -> BaseRegion:
        return self._build_panda_variant(Bpanda, points)

    def _build_panda_variant(self, shape, points: list[QPointF]) -> BaseRegion:
        """An epanda or a bpanda: the same arguments, a different class."""
        centre = points[0]
        outer = self._radius(points)
        return shape(
            center=(centre.x(), centre.y()),
            start_angle=PANDA_ANGLES[0],
            stop_angle=PANDA_ANGLES[1],
            num_angles=PANDA_SECTORS,
            inner_major=outer * INNER_FRACTION,
            inner_minor=outer * INNER_FRACTION * MINOR_FRACTION,
            outer_major=outer,
            outer_minor=outer * MINOR_FRACTION,
            num_radii=PANDA_ANNULI,
            color=DEFAULT_REGION_COLOR,
        )

    def _finalize(self, mode: RegionMode, points: list[QPointF]) -> bool:
        """Turn a finished gesture into a region and announce it."""
        region = self._build_region(mode, points)
        if region is None:
            return False
        self.manager.add_region(region)
        self.region_created.emit(region)
        return True

    # -- handles (M6-6) ------------------------------------------------------

    def _handle_at(self, point: QPointF) -> int | None:
        """Which resize handle of the selected region `point` grabs.

        The tolerance is in *widget* pixels, not image ones: a handle is a
        six-pixel square on the screen whatever the zoom, so hit-testing in
        image coordinates would make handles impossible to grab when zoomed
        out and grabbable from across the frame when zoomed in.
        """
        region = self.selected_region
        if region is None or not region.can_edit:
            return None
        widget_point = self._image_to_widget_coords(point)
        for index, (x, y) in enumerate(self.renderer.handle_points(region)):
            handle = self._to_widget(x, y)
            if math.hypot(handle.x() - widget_point.x(), handle.y() - widget_point.y()) <= HANDLE_GRAB:
                return index
        return None

    def _rotate_handle_at(self, point: QPointF) -> bool:
        """Whether `point` grabs the selected region's rotate handle."""
        region = self.selected_region
        if region is None or not region.can_edit:
            return False
        target = self.renderer.rotate_handle(region)
        if target is None:
            return False
        widget_point = self._image_to_widget_coords(point)
        handle = self._to_widget(*target)
        return math.hypot(handle.x() - widget_point.x(), handle.y() - widget_point.y()) <= HANDLE_GRAB

    def _drag_handle(self, index: int, point: QPointF) -> None:
        """Reshape the selected region by dragging one of its handles.

        What the drag means depends on the shape, and the three cases are
        the same three the drawing gestures use:

          a polygon or segment  the dragged vertex follows the cursor
          a line-like shape     the dragged end follows the cursor
          everything else       the shape scales about its centre

        Scaling goes through each shape's own `resize`, so a shape with two
        radii keeps their ratio rather than needing a rule here.
        """
        region = self.selected_region
        if region is None:
            return

        if isinstance(region, (Polygon, Segment)):
            self._move_vertex(region, index, point)
            return
        if isinstance(region, (Line, Ruler, Projection)):
            if index == 0:
                region.start = (point.x(), point.y())
            else:
                region.end = (point.x(), point.y())
            return
        if isinstance(region, Vector):
            self._drag_vector(region, index, point)
            return

        self._scale_to(region, index, point)

    @staticmethod
    def _move_vertex(region, index: int, point: QPointF) -> None:
        """Put one vertex of a polygon or segment under the cursor."""
        if isinstance(region, Polygon):
            vertices = list(region.vertices)
            vertices[index] = (point.x(), point.y())
            region.vertices = vertices
        else:
            points = list(region.points)
            points[index] = (point.x(), point.y())
            region.points = points

    @staticmethod
    def _drag_vector(region: Vector, index: int, point: QPointF) -> None:
        """Move a vector's tail, or swing its head round."""
        if index == 0:
            region.start = (point.x(), point.y())
            return
        x, y = region.start
        dx, dy = point.x() - x, point.y() - y
        region.length = math.hypot(dx, dy)
        region.angle = math.degrees(math.atan2(dy, dx))

    def _scale_to(self, region: BaseRegion, index: int, point: QPointF) -> None:
        """Scale a region so its dragged handle lands under the cursor."""
        handles = self.renderer.handle_points(region)
        if index >= len(handles):
            return
        cx, cy = region.center
        hx, hy = handles[index]
        reach = math.hypot(hx - cx, hy - cy)
        wanted = math.hypot(point.x() - cx, point.y() - cy)
        if reach < MINIMUM_EXTENT or wanted < MINIMUM_EXTENT:
            # Scaling to (or from) nothing would collapse the region to a
            # point it could never be dragged back out of.
            return
        factor = wanted / reach
        region.resize(factor, factor)

    def _rotate_to(self, point: QPointF) -> None:
        """Turn the selected region so its rotate handle faces the cursor.

        The handle starts due north of the centre, so the angle a drag means
        is the bearing of the cursor less that quarter turn.
        """
        region = self.selected_region
        if region is None or not region.can_rotate:
            return
        cx, cy = region.center
        dx, dy = point.x() - cx, point.y() - cy
        if math.hypot(dx, dy) < MINIMUM_EXTENT:
            return
        region.angle = math.degrees(math.atan2(dy, dx)) - 90.0

    def _select(self, region: BaseRegion | None) -> None:
        """Make `region` the selection, clearing any previous one."""
        if self.selected_region is not None:
            self.selected_region.selected = False
        self.selected_region = region
        if region is not None:
            region.selected = True

    # -- mouse --------------------------------------------------------------

    # -- pointer modes (M9-1 ... M9-5) ---------------------------------------

    def _to_illustrate(self, event, phase: str) -> bool:
        """Offer one mouse event to the illustrate layer.

        Its coordinates are the canvas's, not the image's, so this hands the
        widget position over untransformed -- an illustration stays where it
        was put whatever the image does.
        """
        handler = self.illustrate_handler
        if handler is None:
            return False
        button = "left" if event.button() == Qt.MouseButton.LeftButton else "right"
        if phase == "move":
            button = "left" if event.buttons() & Qt.MouseButton.LeftButton else "none"
        return bool(handler(phase, event.position(), button))

    def _notify_edit(self, phase: str) -> None:
        """Tell the controller a region edit started or finished."""
        if self.edit_notifier is not None:
            self.edit_notifier(phase)

    def _dispatch(self, event, phase: str) -> bool:
        """Give one mouse event to the active pointer mode, if there is one.

        Returns:
            Whether the mode used it. A mode that did not is a click that
            should reach whatever is underneath.
        """
        handler = self.pointer_handler
        if handler is None:
            return False

        point = self._widget_to_image_coords(event.position())
        button = "left" if event.button() == Qt.MouseButton.LeftButton else "right"
        if phase == "press":
            used = handler.press(point.x(), point.y(), button)
        elif phase == "move":
            used = handler.move(point.x(), point.y())
        else:
            used = handler.release(point.x(), point.y())
        if handler.draws_band:
            self.update()
        return bool(used)

    def mousePressEvent(self, event) -> None:
        """Handle a press: the pointer mode first, then regions."""
        if self.examine_handler is not None:
            # An interactive examine is waiting for one click, and it wins
            # over every mode: that is what the crosshair cursor means.
            point = self._widget_to_image_coords(event.position())
            if self.examine_handler(point.x(), point.y()):
                event.accept()
                return

        if self._to_illustrate(event, "press"):
            event.accept()
            return

        if self.pointer_handler is not None:
            if self._dispatch(event, "press"):
                event.accept()
            else:
                event.ignore()
            return

        if event.button() in (Qt.MouseButton.RightButton, Qt.MouseButton.MiddleButton):
            event.ignore()
            return

        if self.mode == RegionMode.NONE:
            # Selection mode - check if clicking on existing region
            img_point = self._widget_to_image_coords(event.position())

            # A handle of the current selection wins over anything under it:
            # the handles of a small region sit on top of larger ones, and
            # grabbing one has to reshape rather than select what is behind.
            if self._rotate_handle_at(img_point):
                self.rotating = True
                self.drag_start = img_point
                self._notify_edit("begin")
                event.accept()
                return
            handle = self._handle_at(img_point)
            if handle is not None:
                self.dragging_handle = handle
                self.drag_start = img_point
                self._notify_edit("begin")
                event.accept()
                return

            for region in reversed(self.regions):  # Check from top
                if region.contains(img_point.x(), img_point.y()):
                    self._select(region)
                    self.drag_start = img_point
                    self._notify_edit("begin")
                    self.region_selected.emit(region)
                    self.update()
                    event.accept()
                    return

            # Nothing of ours under the cursor: the catalogue layer may
            # have a symbol there, and it cannot take the click itself.
            if self.pick_handler is not None and self.pick_handler(event.position()):
                event.accept()
                return

            if self.selected_region:
                self._select(None)
                self.update()
            # Ignored, not accepted: a click on bare image belongs to the
            # viewer underneath, which pans with it.
            event.ignore()
            return

        # Drawing mode
        if event.button() == Qt.MouseButton.LeftButton:
            img_point = self._widget_to_image_coords(event.position())

            if self.mode in _VERTEX_MODES:
                # Polygon and segment: accumulate vertices
                self.current_points.append(img_point)
                self.is_drawing = True
            elif self.mode in _CLICK_MODES:
                # Point and text: place immediately
                self._finalize(self.mode, [img_point])
                self.current_points = []
                self.is_drawing = False
                self.update()
                event.accept()
                return
            else:
                # Everything drawn by a drag: start one
                self.current_points = [img_point]
                self.is_drawing = True

            self.update()
            event.accept()

    def mouseMoveEvent(self, event) -> None:
        """Handle a drag: the pointer mode first, then regions.

        Whatever the mode does with the event, the position is announced
        first: everything that follows the cursor is downstream of this
        one signal, and a mode that accepts the event must not silence the
        readout.
        """
        self._announce_hover(event)

        if self._to_illustrate(event, "move"):
            event.accept()
            return

        if self.pointer_handler is not None:
            if self._dispatch(event, "move"):
                event.accept()
            else:
                event.ignore()
            return

        if event.buttons() & (Qt.MouseButton.RightButton | Qt.MouseButton.MiddleButton):
            event.ignore()
            return

        if not self.is_drawing and self.mode == RegionMode.NONE:
            img_point = self._widget_to_image_coords(event.position())

            if self.rotating:
                self._rotate_to(img_point)
                self.update()
                event.accept()
                return
            if self.dragging_handle is not None:
                self._drag_handle(self.dragging_handle, img_point)
                self.update()
                event.accept()
                return

            # Moving selected region
            if self.selected_region and self.drag_start:
                if not self.selected_region.can_move:
                    event.accept()
                    return
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

    def _announce_hover(self, event) -> None:
        """Say where the cursor is, in image pixels."""
        point = self._widget_to_image_coords(event.position())
        if point is None:
            return
        self.hover_moved.emit(int(point.x()), int(point.y()))

    def mouseReleaseEvent(self, event) -> None:
        """Handle a release: the pointer mode first, then regions."""
        if self._to_illustrate(event, "release"):
            event.accept()
            return

        if self.pointer_handler is not None:
            if self._dispatch(event, "release"):
                event.accept()
            else:
                event.ignore()
            return

        # Right-click closes a polygon, so it has to reach the branch below.
        # Every other right or middle release belongs to the viewer underneath
        # (pan, context menu), so pass those through untouched.
        finishing_polygon = self.mode in _VERTEX_MODES and event.button() == Qt.MouseButton.RightButton
        if not finishing_polygon and event.button() in (
            Qt.MouseButton.RightButton,
            Qt.MouseButton.MiddleButton,
        ):
            event.ignore()
            return

        if self.mode == RegionMode.NONE:
            if self.drag_start is not None:
                self._notify_edit("finish")
            self.drag_start = None
            self.dragging_handle = None
            self.rotating = False
            event.accept()
            return

        if event.button() == Qt.MouseButton.LeftButton and self.is_drawing:
            if self.mode in _VERTEX_MODES:
                # These continue until a double-click or a right-click
                pass
            else:
                self._finalize(self.mode, self.current_points)
                self.current_points = []
                self.is_drawing = False
                self.update()

            event.accept()

        elif event.button() == Qt.MouseButton.RightButton and self.mode in _VERTEX_MODES:
            # Close the vertex list
            self._finalize(self.mode, self.current_points)
            self.current_points = []
            self.is_drawing = False
            self.update()
            event.accept()

    def mouseDoubleClickEvent(self, event) -> None:
        """Close a vertex list, or open a region's Get Information dialog."""
        if self.mode == RegionMode.NONE and event.button() == Qt.MouseButton.LeftButton:
            # DS9 opens the region's dialog on a double click, which is how
            # most people reach it -- the menu entry is the other way.
            image_point = self._widget_to_image_coords(event.position())
            for region in reversed(self.regions):
                if region.contains(image_point.x(), image_point.y()):
                    self._select(region)
                    self.region_activated.emit(region)
                    self.update()
                    event.accept()
                    return

        if self.mode in _VERTEX_MODES and event.button() == Qt.MouseButton.LeftButton:
            self._finalize(self.mode, self.current_points)
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

        band = None if self.pointer_handler is None else self.pointer_handler.rubber_band
        if band is not None:
            x0, y0, x1, y1 = band
            first = self._to_widget(x0, y0)
            second = self._to_widget(x1, y1)
            painter.setPen(self.renderer.preview_pen())
            painter.drawRect(QRectF(first, second))

        if self.is_drawing and self.current_points:
            self.renderer.render_preview(
                painter,
                self.mode.value,
                [(p.x(), p.y()) for p in self.current_points],
                self._to_widget,
            )


#: Which builder each mode uses. Defined here rather than in the class body
#: so a shape added to `RegionMode` without a builder is a KeyError-free
#: no-op rather than a half-drawn region -- `_build_region` checks the table.
_BUILDERS = {
    RegionMode.CIRCLE: RegionOverlay._build_circle,
    RegionMode.ELLIPSE: RegionOverlay._build_ellipse,
    RegionMode.BOX: RegionOverlay._build_box,
    RegionMode.POLYGON: RegionOverlay._build_polygon,
    RegionMode.SEGMENT: RegionOverlay._build_segment,
    RegionMode.POINT: RegionOverlay._build_point,
    RegionMode.TEXT: RegionOverlay._build_text,
    RegionMode.LINE: RegionOverlay._build_line,
    RegionMode.VECTOR: RegionOverlay._build_vector,
    RegionMode.RULER: RegionOverlay._build_ruler,
    RegionMode.PROJECTION: RegionOverlay._build_projection,
    RegionMode.COMPASS: RegionOverlay._build_compass,
    RegionMode.ANNULUS: RegionOverlay._build_annulus,
    RegionMode.ELLIPSE_ANNULUS: RegionOverlay._build_ellipse_annulus,
    RegionMode.BOX_ANNULUS: RegionOverlay._build_box_annulus,
    RegionMode.PANDA: RegionOverlay._build_panda,
    RegionMode.EPANDA: RegionOverlay._build_epanda,
    RegionMode.BPANDA: RegionOverlay._build_bpanda,
}
