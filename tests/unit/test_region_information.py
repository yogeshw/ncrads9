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

"""The per-shape Get Information dialog (M6-7)."""

from __future__ import annotations

import inspect

import pytest
from astropy.io import fits

from ncrads9.core.wcs_handler import WCSHandler
from ncrads9.regions.region_parser import RegionParser
from ncrads9.ui.dialogs.region_dialog import (
    COMMON_PARAMETERS,
    DIALOG_PROPERTIES,
    PIXEL_SYSTEMS,
    RegionDialog,
    geometry_fields,
    parse_pair,
)
from ncrads9.ui.widgets.region_overlay import RegionMode, RegionOverlay

#: One of every shape, as DS9 writes them.
EVERY_SHAPE = (
    "circle(50,50,20)",
    "ellipse(50,50,20,10,30)",
    "box(50,50,20,10,15)",
    "polygon(40,40,60,40,60,60)",
    "segment(40,40,50,60,60,40)",
    "point(50,50)",
    "line(40,40,60,60)",
    "vector(40,40,20,45)",
    "ruler(40,40,60,60)",
    "compass(50,50,15)",
    "projection(40,40,60,60,8)",
    "annulus(50,50,8,18)",
    "ellipse(50,50,6,4,16,10)",
    "box(50,50,6,4,16,10)",
    "panda(50,50,0,360,4,8,18,2)",
    "epanda(50,50,0,270,3,6,4,16,10,2,20)",
    "bpanda(50,50,0,360,4,6,4,16,10,2)",
    "text(50,50) # text={label}",
)


def _parse(text: str):
    return RegionParser().parse_string(f"image\n{text}\n")[0]


@pytest.fixture
def wcs() -> WCSHandler:
    header = fits.Header(
        {
            "NAXIS": 2,
            "NAXIS1": 100,
            "NAXIS2": 100,
            "CTYPE1": "RA---TAN",
            "CTYPE2": "DEC--TAN",
            "CRPIX1": 50.0,
            "CRPIX2": 50.0,
            "CRVAL1": 150.0,
            "CRVAL2": 2.0,
            "CDELT1": -0.001,
            "CDELT2": 0.001,
        }
    )
    return WCSHandler(header)


# -- the fields come from the shape ------------------------------------------


@pytest.mark.parametrize("text", EVERY_SHAPE)
def test_every_shape_shows_all_of_its_parameters(qapp, text):
    """A field per constructor parameter -- the point of reading them off."""
    region = _parse(text)
    declared = [
        name for name in inspect.signature(type(region).__init__).parameters if name not in COMMON_PARAMETERS
    ]
    shown = [field.name for field in geometry_fields(region)]
    assert shown == declared, text


@pytest.mark.parametrize("text", EVERY_SHAPE)
def test_every_shape_opens_without_complaint(qapp, text):
    dialog = RegionDialog(_parse(text))
    assert dialog.windowTitle() == type(dialog.region).__name__


def test_a_circles_fields_are_its_centre_and_radius(qapp):
    fields = geometry_fields(_parse("circle(50,50,20)"))
    assert [(field.name, field.kind) for field in fields] == [
        ("center", "position"),
        ("radius", "length"),
    ]


def test_a_polygons_vertices_are_one_field(qapp):
    fields = geometry_fields(_parse("polygon(1,1,2,2,3,3)"))
    assert [(field.name, field.kind) for field in fields] == [("vertices", "path")]


def test_a_points_glyph_is_a_choice(qapp):
    field = next(f for f in geometry_fields(_parse("point(5,5)")) if f.name == "shape")
    assert field.kind == "choice"
    assert "diamond" in field.choices


# -- editing ------------------------------------------------------------------


def test_changing_a_radius_reaches_the_region(qapp):
    dialog = RegionDialog(_parse("circle(50,50,20)"))
    dialog._editors["radius"].setText("35")
    dialog.apply()
    assert dialog.region.radius == pytest.approx(35.0)


def test_changing_a_centre_reaches_the_region(qapp):
    dialog = RegionDialog(_parse("circle(50,50,20)"))
    dialog._editors["center"].setText("10 20")
    dialog.apply()
    assert dialog.region.center == (10.0, 20.0)


def test_an_unreadable_number_leaves_the_region_alone(qapp):
    """A half-typed radius must not silently become zero."""
    dialog = RegionDialog(_parse("circle(50,50,20)"))
    dialog._editors["radius"].setText("-")
    dialog.apply()
    assert dialog.region.radius == pytest.approx(20.0)


def test_editing_a_polygons_vertices(qapp):
    dialog = RegionDialog(_parse("polygon(1,1,2,2,3,3)"))
    dialog._editors["vertices"].setPlainText("0 0\n10 0\n10 10\n0 10")
    dialog.apply()
    assert dialog.region.vertices == [(0.0, 0.0), (10.0, 0.0), (10.0, 10.0), (0.0, 10.0)]


def test_a_single_vertex_is_refused(qapp):
    """A polygon of one point is not a polygon; keep the one we have."""
    dialog = RegionDialog(_parse("polygon(1,1,2,2,3,3)"))
    dialog._editors["vertices"].setPlainText("5 5")
    dialog.apply()
    assert len(dialog.region.vertices) == 3


def test_style_and_properties_reach_the_region(qapp):
    dialog = RegionDialog(_parse("circle(50,50,20)"))
    dialog._color.setCurrentText("magenta")
    dialog._width.setCurrentText("3")
    dialog._font.setCurrentText("courier")
    dialog._font_size.setCurrentText("18")
    dialog._property_boxes["dash"].setChecked(True)
    dialog._property_boxes["include"].setChecked(False)
    dialog.apply()

    assert dialog.region.color == "magenta"
    assert dialog.region.width == 3
    assert dialog.region.font == "courier 18 normal roman"
    assert dialog.region.dash is True
    assert dialog.region.include is False


def test_every_ds9_property_flag_has_a_box(qapp):
    dialog = RegionDialog(_parse("circle(50,50,20)"))
    assert set(dialog._property_boxes) == {name for name, _label in DIALOG_PROPERTIES}


def test_the_dialog_opens_showing_what_the_region_holds(qapp):
    dialog = RegionDialog(_parse("circle(50,50,20) # color=red width=2 dash=1 text={a note}"))
    assert dialog._color.currentText() == "red"
    assert dialog._width.currentText() == "2"
    assert dialog._property_boxes["dash"].isChecked()
    assert dialog._text.text() == "a note"


def test_a_text_regions_label_and_id_stay_one_string(qapp):
    """They were two copies, so editing one silently diverged from the other."""
    region = _parse("text(50,50) # text={before}")
    dialog = RegionDialog(region)
    dialog._editors["label"].setText("after")
    dialog.apply()
    assert region.text == "after"
    assert "text={after}" in region.to_ds9_string()


def test_applying_announces_the_change(qapp):
    dialog = RegionDialog(_parse("circle(50,50,20)"))
    seen = []
    dialog.region_changed.connect(seen.append)
    dialog.apply()
    assert seen == [dialog.region]


def test_delete_is_refused_when_the_region_forbids_it(qapp):
    region = _parse("circle(50,50,20) # delete=0")
    dialog = RegionDialog(region)
    seen = []
    dialog.region_deleted.connect(seen.append)
    dialog._delete()
    assert seen == []


# -- coordinate systems --------------------------------------------------------


def test_without_a_wcs_only_the_pixel_systems_are_offered(qapp):
    dialog = RegionDialog(_parse("circle(50,50,20)"))
    assert dialog.systems() == PIXEL_SYSTEMS
    assert not dialog._format.isEnabled()


def test_with_a_wcs_every_sky_frame_is_offered(qapp, wcs):
    dialog = RegionDialog(_parse("circle(50,50,20)"), wcs)
    assert set(dialog.systems()) > set(PIXEL_SYSTEMS)
    assert "galactic" in dialog.systems()


def test_switching_to_a_sky_frame_restates_the_position(qapp, wcs):
    dialog = RegionDialog(_parse("circle(50,50,20)"), wcs)
    in_pixels = dialog._editors["center"].text()
    dialog._system.setCurrentText("fk5")
    assert dialog._format.isEnabled()
    assert dialog._editors["center"].text() != in_pixels
    assert ":" in dialog._editors["center"].text()


def test_degrees_and_sexagesimal_differ(qapp, wcs):
    dialog = RegionDialog(_parse("circle(50,50,20)"), wcs)
    dialog._system.setCurrentText("fk5")
    sexagesimal = dialog._editors["center"].text()
    dialog._format.setCurrentText("degrees")
    assert dialog._editors["center"].text() != sexagesimal
    assert ":" not in dialog._editors["center"].text()


def test_a_sky_position_round_trips_back_to_the_same_pixel(qapp, wcs):
    """Shown in fk5 and applied unchanged, the region must not move."""
    dialog = RegionDialog(_parse("circle(50,50,20)"), wcs)
    dialog._system.setCurrentText("fk5")
    dialog.apply()
    assert dialog.region.center[0] == pytest.approx(50.0, abs=0.01)
    assert dialog.region.center[1] == pytest.approx(50.0, abs=0.01)


@pytest.mark.parametrize(
    "text,expected",
    [
        ("10 20", (10.0, 20.0)),
        ("10, 20", (10.0, 20.0)),
        ("10:00:00 +02:00:00", (150.0, 2.0)),
        ("nonsense", None),
        ("", None),
    ],
)
def test_parse_pair(text, expected):
    result = parse_pair(text)
    if expected is None:
        assert result is None
    else:
        assert result == pytest.approx(expected)


# -- reaching the dialog --------------------------------------------------------


def test_a_double_click_asks_for_the_dialog(qapp):
    """Double-clicking a region is how most people open Get Information."""
    from PyQt6.QtCore import QEvent, Qt
    from PyQt6.QtGui import QMouseEvent

    overlay = RegionOverlay()
    overlay.mode = RegionMode.NONE
    circle = _parse("circle(50,50,20)")
    overlay.manager.add_region(circle)

    seen = []
    overlay.region_activated.connect(seen.append)
    point = overlay._to_widget(50, 50)
    overlay.mouseDoubleClickEvent(
        QMouseEvent(
            QEvent.Type.MouseButtonDblClick,
            point,
            point,
            Qt.MouseButton.LeftButton,
            Qt.MouseButton.LeftButton,
            Qt.KeyboardModifier.NoModifier,
        )
    )
    assert seen == [circle]
