# NCRADS9 - NCRA DS9 Viewer
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

"""Regions must survive draw -> write -> parse without losing anything.

M1 made the overlay, the parser and the writer share one model. Before that the
overlay had its own `Region` dataclass and `main_window` converted between the
two representations, which dropped colour, width, text, tags and every DS9
property on the way through. These tests exist to keep that from coming back:
they draw with the real mouse gestures, save with `RegionWriter`, reload with
`RegionParser`, and compare.
"""

import pytest
from PyQt6.QtCore import QPointF, Qt
from PyQt6.QtGui import QMouseEvent

from ncrads9.regions.region_parser import RegionParser
from ncrads9.regions.region_writer import RegionWriter
from ncrads9.regions.shapes.box import Box
from ncrads9.regions.shapes.circle import Circle
from ncrads9.regions.shapes.ellipse import Ellipse
from ncrads9.regions.shapes.line import Line
from ncrads9.regions.shapes.point import Point
from ncrads9.regions.shapes.polygon import Polygon
from ncrads9.ui.widgets.region_overlay import RegionMode, RegionOverlay

#: The shapes the overlay can create interactively as of M1. M6 adds the rest.
CREATABLE_MODES = [
    RegionMode.CIRCLE,
    RegionMode.BOX,
    RegionMode.ELLIPSE,
    RegionMode.POLYGON,
    RegionMode.LINE,
    RegionMode.POINT,
]

EXPECTED_TYPE = {
    RegionMode.CIRCLE: Circle,
    RegionMode.BOX: Box,
    RegionMode.ELLIPSE: Ellipse,
    RegionMode.POLYGON: Polygon,
    RegionMode.LINE: Line,
    RegionMode.POINT: Point,
}


@pytest.fixture
def overlay(qapp):
    """An overlay with an identity image<->widget transform.

    zoom 1, no offset and image_height 0 makes `_image_to_widget_coords` the
    identity, so gesture coordinates are image coordinates and the assertions
    below can use round numbers.
    """
    widget = RegionOverlay()
    widget.resize(400, 400)
    widget.set_zoom(1.0, (0.0, 0.0), image_width=0, image_height=0)
    return widget


def _press(overlay, x, y, button=Qt.MouseButton.LeftButton):
    overlay.mousePressEvent(
        QMouseEvent(
            QMouseEvent.Type.MouseButtonPress,
            QPointF(x, y),
            button,
            button,
            Qt.KeyboardModifier.NoModifier,
        )
    )


def _move(overlay, x, y, buttons=Qt.MouseButton.LeftButton):
    overlay.mouseMoveEvent(
        QMouseEvent(
            QMouseEvent.Type.MouseMove,
            QPointF(x, y),
            Qt.MouseButton.NoButton,
            buttons,
            Qt.KeyboardModifier.NoModifier,
        )
    )


def _release(overlay, x, y, button=Qt.MouseButton.LeftButton):
    overlay.mouseReleaseEvent(
        QMouseEvent(
            QMouseEvent.Type.MouseButtonRelease,
            QPointF(x, y),
            button,
            Qt.MouseButton.NoButton,
            Qt.KeyboardModifier.NoModifier,
        )
    )


def _draw(overlay, mode):
    """Perform the gesture that creates one region of `mode`."""
    overlay.set_mode(mode)
    if mode == RegionMode.POINT:
        _press(overlay, 40, 60)
    elif mode == RegionMode.POLYGON:
        for x, y in ((10, 10), (50, 10), (50, 40)):
            _press(overlay, x, y)
            _release(overlay, x, y)
        _press(overlay, 50, 40, Qt.MouseButton.RightButton)
        overlay.mouseReleaseEvent(
            QMouseEvent(
                QMouseEvent.Type.MouseButtonRelease,
                QPointF(50, 40),
                Qt.MouseButton.RightButton,
                Qt.MouseButton.NoButton,
                Qt.KeyboardModifier.NoModifier,
            )
        )
    else:
        _press(overlay, 20, 30)
        _move(overlay, 60, 70)
        _release(overlay, 60, 70)


def _geometry(region):
    """A comparable summary of a region's geometry."""
    if isinstance(region, Circle):
        return ("circle", region.center, round(region.radius, 6))
    if isinstance(region, Ellipse):
        return ("ellipse", region.center, region.semi_major, region.semi_minor, region.angle)
    if isinstance(region, Box):
        return ("box", region.center, region.width_box, region.height_box, region.angle)
    if isinstance(region, Polygon):
        return ("polygon", tuple(region.vertices))
    if isinstance(region, Line):
        return ("line", region.start, region.end)
    if isinstance(region, Point):
        return ("point", region.center, region.shape, region.size)
    raise AssertionError(f"unhandled shape {type(region).__name__}")


class TestOverlayCreatesModelRegions:
    """The overlay builds `BaseRegion` subclasses, not its own dataclass."""

    @pytest.mark.parametrize("mode", CREATABLE_MODES, ids=lambda m: m.value)
    def test_gesture_creates_the_right_shape(self, overlay, mode):
        _draw(overlay, mode)
        assert len(overlay.regions) == 1
        assert isinstance(overlay.regions[0], EXPECTED_TYPE[mode])

    @pytest.mark.parametrize("mode", CREATABLE_MODES, ids=lambda m: m.value)
    def test_created_region_is_emitted(self, overlay, mode):
        seen = []
        overlay.region_created.connect(seen.append)
        _draw(overlay, mode)
        assert len(seen) == 1
        assert seen[0] is overlay.regions[0]

    def test_drag_geometry_matches_the_gesture(self, overlay):
        """A drag from (20,30) to (60,70) sets radius, bounds and endpoints."""
        _draw(overlay, RegionMode.CIRCLE)
        circle = overlay.regions[0]
        assert circle.center == (20.0, 30.0)
        assert circle.radius == pytest.approx((40**2 + 40**2) ** 0.5)

        overlay.clear_regions()
        _draw(overlay, RegionMode.BOX)
        box = overlay.regions[0]
        assert box.center == (40.0, 50.0)
        assert (box.width_box, box.height_box) == (40.0, 40.0)

        overlay.clear_regions()
        _draw(overlay, RegionMode.LINE)
        line = overlay.regions[0]
        assert (line.start, line.end) == ((20.0, 30.0), (60.0, 70.0))


class TestRoundTrip:
    """draw -> write -> parse preserves geometry and properties."""

    @pytest.mark.parametrize("mode", CREATABLE_MODES, ids=lambda m: m.value)
    def test_geometry_survives(self, overlay, mode, tmp_path):
        _draw(overlay, mode)
        original = overlay.regions[0]

        path = tmp_path / "regions.reg"
        RegionWriter().write_file(overlay.regions, path)
        reloaded = RegionParser().parse_file(path)

        assert len(reloaded) == 1
        assert _geometry(reloaded[0]) == _geometry(original)

    def test_all_six_shapes_survive_one_file(self, overlay, tmp_path):
        for mode in CREATABLE_MODES:
            _draw(overlay, mode)
        assert len(overlay.regions) == len(CREATABLE_MODES)

        path = tmp_path / "all.reg"
        RegionWriter().write_file(overlay.regions, path)
        reloaded = RegionParser().parse_file(path)

        assert [_geometry(r) for r in reloaded] == [_geometry(r) for r in overlay.regions]

    def test_appearance_survives(self, tmp_path):
        """Colour, width, text, font and tags used to be dropped."""
        original = Circle(
            center=(12.5, 34.5),
            radius=7.25,
            color="red",
            width=3,
            text="NGC 1234",
            font="times 14 bold roman",
            tags=["group-a"],
        )
        path = tmp_path / "appearance.reg"
        RegionWriter().write_file([original], path)
        (reloaded,) = RegionParser().parse_file(path)

        assert reloaded.color == "red"
        assert reloaded.width == 3
        assert reloaded.text == "NGC 1234"
        assert reloaded.font == "times 14 bold roman"
        assert reloaded.tags == ["group-a"]

    @pytest.mark.parametrize(
        "flags",
        [
            {"include": False},
            {"source": False},
            {"fixed": True},
            {"can_edit": False},
            {"can_move": False},
            {"can_rotate": False},
            {"can_delete": False},
            {"dash": True},
            {"fill": True},
        ],
        ids=lambda f: next(iter(f)),
    )
    def test_each_ds9_property_survives(self, flags, tmp_path):
        original = Circle(center=(1.0, 2.0), radius=3.0, **flags)
        path = tmp_path / "flags.reg"
        RegionWriter().write_file([original], path)
        (reloaded,) = RegionParser().parse_file(path)

        for name, value in flags.items():
            assert getattr(reloaded, name) == value, name

    def test_defaults_are_not_written(self, tmp_path):
        """A plain region emits no property comment, as DS9 does."""
        path = tmp_path / "plain.reg"
        RegionWriter().write_file([Circle(center=(1.0, 2.0), radius=3.0)], path)
        shape_lines = [
            line
            for line in path.read_text().splitlines()
            if line and not line.startswith("#") and line != "image"
        ]
        assert len(shape_lines) == 1
        # No `#` comment at all: every property is at its default.
        assert "#" not in shape_lines[0]
        assert shape_lines[0].startswith("circle(")


class TestOverlayModelIntegration:
    """The overlay stores regions in a RegionManager and honours properties."""

    def test_regions_come_from_the_manager(self, overlay):
        _draw(overlay, RegionMode.CIRCLE)
        # RegionManager.regions returns a copy, so compare contents.
        assert overlay.regions == overlay.manager.regions
        assert overlay.regions[0] is overlay.manager.get_region(0)
        assert overlay.manager.count == 1

    def test_regions_setter_replaces_everything(self, overlay):
        _draw(overlay, RegionMode.CIRCLE)
        overlay.regions = [Point(center=(1.0, 2.0))]
        assert len(overlay.regions) == 1
        assert isinstance(overlay.regions[0], Point)

    def test_selection_uses_the_shape_hit_test(self, overlay):
        overlay.add_region(Circle(center=(50.0, 50.0), radius=20.0))
        overlay.set_mode(RegionMode.NONE)

        _press(overlay, 50, 50)
        assert overlay.selected_region is overlay.regions[0]
        assert overlay.regions[0].selected is True

        _press(overlay, 300, 300)  # empty space
        assert overlay.selected_region is None

    def test_a_region_that_cannot_move_does_not_move(self, overlay):
        region = Circle(center=(50.0, 50.0), radius=20.0, can_move=False)
        overlay.add_region(region)
        overlay.set_mode(RegionMode.NONE)

        _press(overlay, 50, 50)
        _move(overlay, 90, 90)
        assert region.center == (50.0, 50.0)

    def test_a_movable_region_moves(self, overlay):
        region = Circle(center=(50.0, 50.0), radius=20.0)
        overlay.add_region(region)
        overlay.set_mode(RegionMode.NONE)

        _press(overlay, 50, 50)
        _move(overlay, 60, 70)
        assert region.center == pytest.approx((60.0, 70.0))
