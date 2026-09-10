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

"""Drawing a region with the mouse: every shape, every gesture (M6-4)."""

from __future__ import annotations

import math

import pytest
from PyQt6.QtCore import QEvent, QPointF, Qt
from PyQt6.QtGui import QMouseEvent

from ncrads9.regions.shapes.annulus import Annulus
from ncrads9.regions.shapes.box import Box
from ncrads9.regions.shapes.box_annulus import BoxAnnulus
from ncrads9.regions.shapes.bpanda import Bpanda
from ncrads9.regions.shapes.circle import Circle
from ncrads9.regions.shapes.compass import Compass
from ncrads9.regions.shapes.ellipse import Ellipse
from ncrads9.regions.shapes.ellipse_annulus import EllipseAnnulus
from ncrads9.regions.shapes.epanda import Epanda
from ncrads9.regions.shapes.line import Line
from ncrads9.regions.shapes.panda import Panda
from ncrads9.regions.shapes.point import Point
from ncrads9.regions.shapes.polygon import Polygon
from ncrads9.regions.shapes.projection import Projection
from ncrads9.regions.shapes.ruler import Ruler
from ncrads9.regions.shapes.segment import Segment
from ncrads9.regions.shapes.text import Text
from ncrads9.regions.shapes.vector import Vector
from ncrads9.ui.menu_bar import REGION_SHAPES
from ncrads9.ui.widgets.region_overlay import (
    DEFAULT_SIZE,
    RegionMode,
    RegionOverlay,
)


@pytest.fixture
def overlay(qapp) -> RegionOverlay:
    return RegionOverlay()


#: Which class each mode's gesture has to produce. Every mode but NONE is
#: here, and a test below checks that -- adding a shape to the cascade
#: without a gesture is what M6-4 was fixing.
EXPECTED = {
    RegionMode.CIRCLE: Circle,
    RegionMode.ELLIPSE: Ellipse,
    RegionMode.BOX: Box,
    RegionMode.POLYGON: Polygon,
    RegionMode.SEGMENT: Segment,
    RegionMode.POINT: Point,
    RegionMode.TEXT: Text,
    RegionMode.LINE: Line,
    RegionMode.VECTOR: Vector,
    RegionMode.RULER: Ruler,
    RegionMode.PROJECTION: Projection,
    RegionMode.COMPASS: Compass,
    RegionMode.ANNULUS: Annulus,
    RegionMode.ELLIPSE_ANNULUS: EllipseAnnulus,
    RegionMode.BOX_ANNULUS: BoxAnnulus,
    RegionMode.PANDA: Panda,
    RegionMode.EPANDA: Epanda,
    RegionMode.BPANDA: Bpanda,
}

#: A gesture long enough to be a drag, and enough vertices for a polygon.
GESTURE = [QPointF(50, 50), QPointF(80, 50), QPointF(80, 80)]


def test_every_shape_in_the_cascade_has_a_mode():
    for name, _label in REGION_SHAPES:
        assert RegionMode(name) in EXPECTED


def test_every_mode_has_a_gesture():
    assert set(EXPECTED) | {RegionMode.NONE} == set(RegionMode)


@pytest.mark.parametrize("mode", list(EXPECTED))
def test_every_mode_builds_its_shape(overlay, mode):
    region = overlay._build_region(mode, list(GESTURE))
    assert isinstance(region, EXPECTED[mode]), mode


@pytest.mark.parametrize("mode", list(EXPECTED))
def test_a_click_makes_a_default_sized_region(overlay, mode):
    """DS9 makes a region on a click; a zero-sized one cannot be grabbed."""
    if mode in (RegionMode.POLYGON, RegionMode.SEGMENT):
        pytest.skip("built vertex by vertex, so one click is not a shape yet")

    region = overlay._build_region(mode, [QPointF(50, 50)])
    assert region is not None, mode
    if mode in (RegionMode.POINT, RegionMode.TEXT):
        assert region.center == (50.0, 50.0)
        return
    assert overlay.renderer.handle_points(region), mode


def test_a_short_drag_counts_as_a_click(overlay):
    """A hand that moves two pixels meant to click, not to draw a dot."""
    twitch = overlay._build_region(RegionMode.CIRCLE, [QPointF(50, 50), QPointF(51, 51)])
    assert twitch.radius == pytest.approx(math.hypot(DEFAULT_SIZE, DEFAULT_SIZE))


def test_a_circle_is_drawn_from_its_centre(overlay):
    circle = overlay._build_region(RegionMode.CIRCLE, [QPointF(50, 50), QPointF(80, 50)])
    assert circle.center == (50.0, 50.0)
    assert circle.radius == pytest.approx(30.0)


def test_a_box_is_drawn_corner_to_corner(overlay):
    box = overlay._build_region(RegionMode.BOX, [QPointF(40, 40), QPointF(60, 70)])
    assert box.center == (50.0, 55.0)
    assert (box.width_box, box.height_box) == (20.0, 30.0)


def test_a_vector_takes_its_angle_from_the_drag(overlay):
    vector = overlay._build_region(RegionMode.VECTOR, [QPointF(50, 50), QPointF(70, 70)])
    assert vector.angle == pytest.approx(45.0)
    assert vector.length == pytest.approx(math.hypot(20, 20))


def test_an_annulus_is_drawn_with_an_inner_radius(overlay):
    """An annulus whose radii matched would draw as a single circle."""
    annulus = overlay._build_region(RegionMode.ANNULUS, [QPointF(50, 50), QPointF(90, 50)])
    assert annulus.outer_radius == pytest.approx(40.0)
    assert 0 < annulus.inner_radius < annulus.outer_radius


@pytest.mark.parametrize("mode", [RegionMode.PANDA, RegionMode.EPANDA, RegionMode.BPANDA])
def test_a_new_panda_spans_a_full_turn(overlay, mode):
    panda = overlay._build_region(mode, [QPointF(50, 50), QPointF(90, 50)])
    assert (panda.start_angle, panda.stop_angle) == (0.0, 360.0)
    assert panda.num_angles == 4


def test_a_polygon_needs_three_vertices(overlay):
    assert overlay._build_region(RegionMode.POLYGON, GESTURE[:2]) is None
    assert overlay._build_region(RegionMode.POLYGON, GESTURE) is not None


def test_a_segment_needs_only_two(overlay):
    """It is an open path, so two vertices already draw something."""
    assert overlay._build_region(RegionMode.SEGMENT, GESTURE[:1]) is None
    assert overlay._build_region(RegionMode.SEGMENT, GESTURE[:2]) is not None


def test_a_new_text_region_carries_a_label(overlay):
    """An empty one would be invisible and unselectable."""
    assert overlay._build_region(RegionMode.TEXT, [QPointF(50, 50)]).text


@pytest.mark.parametrize("mode", list(EXPECTED))
def test_a_finished_gesture_reaches_the_frame(overlay, mode):
    seen = []
    overlay.region_created.connect(seen.append)
    assert overlay._finalize(mode, list(GESTURE)) is True
    assert len(seen) == 1
    assert seen[0] in overlay.regions


# -- selection handles (M6-6) ------------------------------------------------


def _grab(overlay, region, index: int, to: QPointF) -> None:
    """Select `region` and drag its handle `index` to `to`."""
    overlay._select(region)
    overlay.dragging_handle = index
    overlay._drag_handle(index, to)


@pytest.mark.parametrize("mode", list(EXPECTED))
def test_every_shape_offers_a_handle_to_resize_by(overlay, mode):
    """A shape with only a centre handle can be moved but never reshaped."""
    region = overlay._build_region(mode, list(GESTURE))
    handles = overlay.renderer.handle_points(region)
    assert handles
    if mode in (RegionMode.POINT, RegionMode.TEXT):
        return  # These have no extent of their own to drag.
    assert list(handles) != [region.center], mode


def test_dragging_a_circles_handle_resizes_it(overlay):
    circle = Circle(center=(50, 50), radius=10)
    _grab(overlay, circle, 0, QPointF(80, 50))
    assert circle.radius == pytest.approx(30.0)
    assert circle.center == (50.0, 50.0)


def test_an_annulus_keeps_the_ratio_of_its_radii(overlay):
    """Scaling goes through the shape's own resize, so both radii follow."""
    annulus = Annulus(center=(50, 50), inner_radius=5, outer_radius=10)
    _grab(overlay, annulus, 1, QPointF(70, 50))
    assert annulus.outer_radius == pytest.approx(20.0)
    assert annulus.inner_radius == pytest.approx(10.0)


def test_dragging_a_polygon_vertex_moves_only_that_vertex(overlay):
    polygon = Polygon(vertices=[(0, 0), (10, 0), (10, 10)])
    _grab(overlay, polygon, 1, QPointF(30, 5))
    assert polygon.vertices[1] == (30.0, 5.0)
    assert polygon.vertices[0] == (0.0, 0.0)


def test_dragging_a_segment_vertex_moves_only_that_vertex(overlay):
    segment = Segment(points=[(0, 0), (10, 0), (10, 10)])
    _grab(overlay, segment, 2, QPointF(4, 9))
    assert segment.points[2] == (4.0, 9.0)


def test_dragging_a_lines_end_moves_that_end(overlay):
    line = Line(start=(0, 0), end=(10, 10))
    _grab(overlay, line, 1, QPointF(20, 5))
    assert line.end == (20.0, 5.0)
    assert line.start == (0.0, 0.0)


def test_dragging_a_vectors_head_swings_it_round(overlay):
    vector = Vector(start=(0, 0), length=10, angle=0)
    _grab(overlay, vector, 1, QPointF(0, 20))
    assert vector.length == pytest.approx(20.0)
    assert vector.angle == pytest.approx(90.0)


def test_a_handle_drag_to_the_centre_is_ignored(overlay):
    """Scaling to nothing leaves no handle to drag the shape back out by."""
    circle = Circle(center=(50, 50), radius=10)
    _grab(overlay, circle, 0, QPointF(50, 50))
    assert circle.radius == pytest.approx(10.0)


def test_a_region_that_forbids_editing_has_no_grabbable_handle(overlay):
    circle = Circle(center=(50, 50), radius=10)
    circle.can_edit = False
    overlay._select(circle)
    assert overlay._handle_at(QPointF(60, 50)) is None


def test_a_handle_is_grabbed_by_its_screen_distance(overlay):
    """In image coordinates a handle is ungrabbable zoomed out and huge in."""
    circle = Circle(center=(50, 50), radius=10)
    overlay._select(circle)
    overlay.zoom = 8.0
    assert overlay._handle_at(QPointF(60, 50)) == 0
    # One image pixel away is eight screen pixels at this zoom: too far.
    assert overlay._handle_at(QPointF(62, 50)) is None


# -- rotating ----------------------------------------------------------------


def test_only_shapes_with_an_angle_offer_a_rotate_handle(overlay):
    assert overlay.renderer.rotate_handle(Box(center=(0, 0), width_box=4, height_box=2)) is not None
    assert overlay.renderer.rotate_handle(Circle(center=(0, 0), radius=4)) is None


def test_a_region_that_forbids_rotating_has_no_rotate_handle(overlay):
    box = Box(center=(0, 0), width_box=4, height_box=2)
    box.can_rotate = False
    assert overlay.renderer.rotate_handle(box) is None


def test_the_rotate_handle_sits_clear_of_the_resize_ones(overlay):
    """Overlapping handles cannot be told apart by a mouse."""
    box = Box(center=(0, 0), width_box=10, height_box=6)
    _x, y = overlay.renderer.rotate_handle(box)
    assert y > max(hy for _hx, hy in overlay.renderer.handle_points(box))


def test_dragging_the_rotate_handle_turns_the_region(overlay):
    box = Box(center=(0, 0), width_box=10, height_box=6, angle=0)
    overlay._select(box)
    overlay.rotating = True
    overlay._rotate_to(QPointF(20, 0))
    # The handle starts due north, so pulling it east is a quarter turn back.
    assert box.angle == pytest.approx(-90.0)


def test_rotating_is_refused_when_the_region_forbids_it(overlay):
    box = Box(center=(0, 0), width_box=10, height_box=6, angle=30)
    box.can_rotate = False
    overlay._select(box)
    overlay._rotate_to(QPointF(20, 0))
    assert box.angle == pytest.approx(30.0)


# -- the whole gesture, through the event handlers ---------------------------


def _mouse(kind, point: QPointF, button=Qt.MouseButton.LeftButton):
    return QMouseEvent(kind, point, point, button, button, Qt.KeyboardModifier.NoModifier)


def test_a_press_and_drag_on_a_handle_resizes_through_the_events(overlay):
    """The pieces above are only useful if the mouse actually reaches them."""
    circle = Circle(center=(50, 50), radius=10)
    overlay.manager.add_region(circle)
    overlay._select(circle)
    overlay.mode = RegionMode.NONE

    overlay.mousePressEvent(_mouse(QEvent.Type.MouseButtonPress, overlay._to_widget(60, 50)))
    assert overlay.dragging_handle == 0
    overlay.mouseMoveEvent(_mouse(QEvent.Type.MouseMove, overlay._to_widget(90, 50)))
    assert circle.radius == pytest.approx(40.0)
    overlay.mouseReleaseEvent(_mouse(QEvent.Type.MouseButtonRelease, overlay._to_widget(90, 50)))
    assert overlay.dragging_handle is None


def test_a_press_away_from_a_handle_still_selects(overlay):
    """Handle grabbing must not swallow ordinary clicks."""
    circle = Circle(center=(50, 50), radius=10)
    overlay.manager.add_region(circle)
    overlay.mode = RegionMode.NONE

    overlay.mousePressEvent(_mouse(QEvent.Type.MouseButtonPress, overlay._to_widget(50, 50)))
    assert overlay.dragging_handle is None
    assert overlay.selected_region is circle
