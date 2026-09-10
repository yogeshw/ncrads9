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
from PyQt6.QtCore import QPointF

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
