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


"""Every DS9 region shape: parse, write, reparse, compare.

The shape list is DS9's own, from the Region Descriptions table in
`ds9/doc/ref/region.html`, with one example per usage line it documents --
including the overloaded ones, where `ellipse` with four numbers is an
ellipse and with six an ellipse annulus.
"""

from __future__ import annotations

import pytest

from ncrads9.regions.region_formats import (
    FORMAT_HEADERS,
    IGNORED_SHAPES,
    RegionFormat,
    class_keyword,
    dropped_shapes,
    is_writable,
    shape_keyword,
)
from ncrads9.regions.region_parser import CoordinateSystem, RegionParser
from ncrads9.regions.region_writer import RegionWriter
from ncrads9.regions.shapes.annulus import Annulus
from ncrads9.regions.shapes.box import Box
from ncrads9.regions.shapes.box_annulus import BoxAnnulus
from ncrads9.regions.shapes.bpanda import Bpanda
from ncrads9.regions.shapes.circle import Circle
from ncrads9.regions.shapes.compass import Compass
from ncrads9.regions.shapes.composite import Composite
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

#: One example per usage line in DS9's Region Descriptions table, with the
#: class each should parse to.
DS9_EXAMPLES: tuple[tuple[str, type], ...] = (
    ("circle(100,100,20)", Circle),
    ("ellipse(200,200,20,40)", Ellipse),
    ("ellipse(200,200,20,40,30)", Ellipse),
    ("box(300,300,20,40)", Box),
    ("box(300,300,20,40,10)", Box),
    ("polygon(10,10,20,10,20,20,10,20)", Polygon),
    ("point(50,50)", Point),
    ("line(0,0,10,10)", Line),
    ("vector(5,5,20,45)", Vector),
    ("segment(1,2,3,4,5,2)", Segment),
    ("ruler(1,1,9,9)", Ruler),
    ("compass(40,40,20)", Compass),
    ("projection(0,0,10,10,3)", Projection),
    ("annulus(70,70,5,10)", Annulus),
    ("annulus(70,70,5,10,15,20)", Annulus),
    ("ellipse(200,200,10,20,30,60)", EllipseAnnulus),
    ("ellipse(200,200,10,20,30,60,45)", EllipseAnnulus),
    ("box(300,300,10,20,30,60)", BoxAnnulus),
    ("box(300,300,10,20,30,60,15)", BoxAnnulus),
    ("panda(80,80,0,360,4,5,10,2)", Panda),
    ("epanda(90,90,0,360,4,5,3,10,6,2)", Epanda),
    ("epanda(90,90,0,360,4,5,3,10,6,2,30)", Epanda),
    ("bpanda(95,95,0,360,4,5,3,10,6,2)", Bpanda),
    ("bpanda(95,95,0,360,4,5,3,10,6,2,30)", Bpanda),
)

#: How many region descriptions DS9 documents. Counted from the Usage lines
#: of the Region Descriptions table, not taken on trust: PLAN.md and TODO.md
#: both said twenty, and the table has nineteen -- Circle, Ellipse, Box,
#: Polygon, Point, Line, Vector, Segment, Text, Ruler, Compass, Projection,
#: Annulus, Ellipse Annulus, Box Annulus, Panda, Epanda, Bpanda, Composite.
DS9_SHAPE_COUNT = 19


def _parse(text: str):
    """Parse one region line in image coordinates."""
    regions = RegionParser().parse_string(f"image\n{text}\n")
    return regions[0] if regions else None


# -- every documented shape parses (M6-11) -----------------------------------


@pytest.mark.parametrize(("text", "expected"), DS9_EXAMPLES)
def test_every_documented_shape_parses(text, expected):
    region = _parse(text)
    assert region is not None, text
    assert isinstance(region, expected), f"{text} gave {type(region).__name__}"


def test_all_of_ds9s_shapes_are_reachable():
    """Every region description DS9 documents must parse.

    The count is checked against the reference itself in
    `test_the_documented_shape_count_is_nineteen`, so this cannot quietly
    agree with a wrong number.
    """
    parsed = {type(_parse(text)).__name__ for text, _cls in DS9_EXAMPLES}
    parsed.add(type(_parse("text(1,1) # text={x}")).__name__)
    parsed.add(type(_parse("# composite(1,1,0)")).__name__)
    assert len(parsed) == DS9_SHAPE_COUNT, sorted(parsed)


def test_the_documented_shape_count_is_nineteen():
    """Counted from DS9's own reference, when it is available.

    The reference checkout is not part of a normal install, so this skips
    rather than failing when it is absent.
    """
    import re
    from pathlib import Path

    reference = Path(".tmp_sao_ds9/ds9/doc/ref/region.html")
    if not reference.exists():
        pytest.skip("the DS9 reference checkout is not present")

    import html as html_module

    text = re.sub(r"<[^>]+>", "", reference.read_text(errors="replace"))
    text = html_module.unescape(text)
    start = text.index("Region Descriptions", text.index("Region Descriptions") + 10)
    block = text[start : text.index("Region Properties", start)]
    assert len(re.findall(r"^([A-Z][A-Za-z ]+)\nUsage:", block, re.M)) == DS9_SHAPE_COUNT


def test_text_parses_with_its_label():
    region = _parse("text(60,60) # text={Hello there}")
    assert isinstance(region, Text)
    assert region.label == "Hello there"


def test_a_composite_parses_to_an_empty_container():
    region = _parse("# composite(10,20,30)")
    assert isinstance(region, Composite)


def test_an_unknown_shape_is_skipped_not_fatal():
    regions = RegionParser().parse_string("image\nsphere(1,2,3)\ncircle(4,5,6)\n")
    assert len(regions) == 1
    assert isinstance(regions[0], Circle)


def test_a_malformed_shape_is_skipped_not_fatal():
    regions = RegionParser().parse_string("image\ncircle(1)\ncircle(4,5,6)\n")
    assert [type(r).__name__ for r in regions] == ["Circle"]


# -- the overloaded keywords -------------------------------------------------


def test_ellipse_becomes_an_annulus_at_four_radii():
    assert isinstance(_parse("ellipse(0,0,1,2)"), Ellipse)
    assert isinstance(_parse("ellipse(0,0,1,2,3)"), Ellipse)
    assert isinstance(_parse("ellipse(0,0,1,2,3,4)"), EllipseAnnulus)


def test_box_becomes_an_annulus_at_four_sizes():
    assert isinstance(_parse("box(0,0,1,2)"), Box)
    assert isinstance(_parse("box(0,0,1,2,3)"), Box)
    assert isinstance(_parse("box(0,0,1,2,3,4)"), BoxAnnulus)


def test_an_odd_trailing_number_is_the_rotation():
    annulus = _parse("ellipse(0,0,1,2,3,4,45)")
    assert isinstance(annulus, EllipseAnnulus)
    assert annulus.angle == pytest.approx(45.0)


def test_a_multi_radius_annulus_keeps_its_span():
    annulus = _parse("annulus(70,70,5,10,15,20)")
    assert annulus.inner_radius == pytest.approx(5.0)
    assert annulus.outer_radius == pytest.approx(20.0)


def test_the_panda_variants_take_an_optional_rotation():
    assert _parse("epanda(0,0,0,360,4,1,2,3,4,2)").angle == pytest.approx(0.0)
    assert _parse("epanda(0,0,0,360,4,1,2,3,4,2,30)").angle == pytest.approx(30.0)


# -- point glyphs (M6-5) -----------------------------------------------------


@pytest.mark.parametrize("glyph", RegionParser.POINT_GLYPHS)
def test_every_ds9_point_glyph_parses(glyph):
    region = _parse(f"point(1,2) # point={glyph}")
    assert isinstance(region, Point)
    assert region.shape == glyph


def test_a_point_glyph_carries_its_size():
    """`point=diamond 15` puts the size after a space, which used to be lost."""
    region = _parse("point(1,2) # point=diamond 15")
    assert region.shape == "diamond"
    assert region.size == 15


def test_a_point_without_a_glyph_takes_ds9s_default():
    region = _parse("point(1,2)")
    assert region.shape == "circle"
    assert region.size == RegionParser.DEFAULT_POINT_SIZE


def test_an_unknown_glyph_falls_back_to_circle():
    assert _parse("point(1,2) # point=squiggle").shape == "circle"


def test_a_nonsense_point_size_falls_back():
    assert _parse("point(1,2) # point=box wide").size == RegionParser.DEFAULT_POINT_SIZE


# -- round trip (M6-13) ------------------------------------------------------


@pytest.mark.parametrize(("text", "expected"), DS9_EXAMPLES)
def test_every_shape_round_trips_through_ds9_format(text, expected):
    """Parse, write, reparse: the same class and the same numbers."""
    first = _parse(text)
    assert first is not None

    written = RegionWriter().to_string([first])
    again = RegionParser().parse_string(written)
    assert len(again) == 1, written
    assert isinstance(again[0], expected)
    assert again[0].to_ds9_string() == first.to_ds9_string()


def test_properties_round_trip():
    text = (
        "circle(1,2,3) # color=red width=3 text={a note} "
        "font={times 12 bold roman} dash=1 fill=1 edit=0 move=0 rotate=0 delete=0 fixed=1"
    )
    first = _parse(text)
    written = RegionWriter().to_string([first])
    again = RegionParser().parse_string(written)[0]

    assert again.color == "red"
    assert again.width == 3
    assert again.text == "a note"
    assert again.dash and again.fill and again.fixed
    assert not (again.can_edit or again.can_move or again.can_rotate or again.can_delete)


def test_text_with_both_quote_characters_round_trips():
    """DS9's own advice: use braces, which survive either quote."""
    note = "has both a \" and ' in it"
    first = _parse(f"circle(1,2,3) # text={{{note}}}")
    assert first.text == note
    written = RegionWriter().to_string([first])
    assert RegionParser().parse_string(written)[0].text == note


def test_exclusion_round_trips():
    first = _parse("-circle(1,2,3)")
    assert not first.include
    written = RegionWriter().to_string([first])
    assert "-circle" in written
    assert not RegionParser().parse_string(written)[0].include


def test_tags_round_trip():
    first = _parse("circle(1,2,3) # tag={group one} tag={other}")
    written = RegionWriter().to_string([first])
    assert set(RegionParser().parse_string(written)[0].tags) == {"group one", "other"}


def test_a_whole_file_round_trips():
    source = "\n".join(text for text, _cls in DS9_EXAMPLES)
    regions = RegionParser().parse_string(f"image\n{source}\n")
    assert len(regions) == len(DS9_EXAMPLES)

    written = RegionWriter().to_string(regions)
    again = RegionParser().parse_string(written)
    assert [type(r).__name__ for r in again] == [type(r).__name__ for r in regions]
    assert [r.to_ds9_string() for r in again] == [r.to_ds9_string() for r in regions]


def test_round_trip_is_stable_after_two_passes():
    """A second write must equal the first, or the format is not a fixed point."""
    regions = RegionParser().parse_string("image\n" + "\n".join(text for text, _cls in DS9_EXAMPLES) + "\n")
    once = RegionWriter().to_string(regions)
    twice = RegionWriter().to_string(RegionParser().parse_string(once))
    assert once == twice


def test_a_file_round_trips_through_the_disk(tmp_path):
    regions = RegionParser().parse_string("image\ncircle(1,2,3) # color=red\n")
    path = tmp_path / "regions.reg"
    RegionWriter().write_file(regions, path)
    assert RegionParser().parse_file(path)[0].color == "red"


# -- the other formats (M6-12) -----------------------------------------------


def test_every_format_has_a_header_entry():
    assert set(FORMAT_HEADERS) == set(RegionFormat)
    assert set(IGNORED_SHAPES) == set(RegionFormat)


def test_only_ds9s_own_format_loses_nothing():
    assert IGNORED_SHAPES[RegionFormat.DS9] == frozenset()
    for region_format in RegionFormat:
        if region_format in (RegionFormat.DS9, RegionFormat.XY):
            continue
        assert IGNORED_SHAPES[region_format], region_format


def test_ciao_drops_what_ds9_says_it_drops():
    """DS9's own table, transcribed in `region_formats.py`."""
    for text in ("line(0,0,1,1)", "vector(0,0,1,1)", "text(1,1) # text={x}"):
        assert not is_writable(_parse(text), RegionFormat.CIAO), text
    assert is_writable(_parse("circle(1,2,3)"), RegionFormat.CIAO)


def test_ciao_calls_a_panda_a_pie():
    written = RegionWriter(region_format=RegionFormat.CIAO).to_string([_parse("panda(80,80,0,360,4,5,10,2)")])
    assert "pie(" in written
    assert "panda(" not in written


def test_saoimage_and_pros_drop_the_panda_too():
    panda = _parse("panda(80,80,0,360,4,5,10,2)")
    assert not is_writable(panda, RegionFormat.SAOIMAGE)
    assert not is_writable(panda, RegionFormat.PROS)
    # Funtools keeps it.
    assert is_writable(panda, RegionFormat.FUNTOOLS)


def test_a_non_ds9_format_carries_no_properties():
    written = RegionWriter(region_format=RegionFormat.CIAO).to_string(
        [_parse("circle(1,2,3) # color=red text={note}")]
    )
    assert "color" not in written
    assert "note" not in written
    assert "circle(1,2,3)" in written.replace(".0", "")


def test_a_non_ds9_format_still_marks_an_exclusion():
    written = RegionWriter(region_format=RegionFormat.CIAO).to_string([_parse("-circle(1,2,3)")])
    assert "-circle" in written


def test_the_xy_format_is_positions_only():
    regions = RegionParser().parse_string("image\ncircle(1,2,3)\nbox(4,5,6,7)\n")
    written = RegionWriter(region_format=RegionFormat.XY).to_string(regions)
    assert written.splitlines() == ["1 2", "4 5"]


def test_dropped_shapes_reports_what_is_lost():
    regions = RegionParser().parse_string("image\ncircle(1,2,3)\nline(0,0,1,1)\nvector(0,0,1,1)\n")
    assert dropped_shapes(regions, RegionFormat.CIAO) == ["line", "vector"]
    assert dropped_shapes(regions, RegionFormat.DS9) == []


def test_a_format_can_be_named_by_string():
    assert RegionWriter(region_format="ciao").region_format is RegionFormat.CIAO
    with pytest.raises(ValueError):
        RegionWriter(region_format="fortran")


def test_the_keyword_helpers_agree_with_the_shapes():
    assert shape_keyword(_parse("ellipse(0,0,1,2,3,4)")) == "ellipse"
    assert class_keyword(_parse("ellipse(0,0,1,2,3,4)")) == "ellipseannulus"


# -- the new shapes (M6-1, M6-2, M6-3) ---------------------------------------


def test_a_segment_needs_two_vertices():
    with pytest.raises(ValueError, match="at least two"):
        Segment([(0.0, 0.0)])


def test_a_segment_reports_points_on_its_path():
    segment = Segment([(0.0, 0.0), (10.0, 0.0)])
    assert segment.contains(5.0, 0.0)
    assert segment.contains(5.0, 2.0)
    assert not segment.contains(5.0, 20.0)
    # Clamped to the ends, so a point beyond the line is off it.
    assert not segment.contains(50.0, 0.0)


def test_a_segment_moves_and_scales_every_vertex():
    segment = Segment([(0.0, 0.0), (10.0, 0.0), (10.0, 10.0)])
    segment.move(5.0, 5.0)
    assert segment.points[0] == (5.0, 5.0)
    before = segment.points
    segment.resize(2.0, 2.0)
    assert segment.points != before


@pytest.mark.parametrize("shape", [Epanda, Bpanda])
def test_the_panda_variants_contain_their_ring(shape):
    region = shape((0.0, 0.0), 0.0, 360.0, 4, 2.0, 2.0, 10.0, 10.0, 2)
    assert region.contains(6.0, 0.0)
    assert not region.contains(0.5, 0.0)
    assert not region.contains(20.0, 0.0)


@pytest.mark.parametrize("shape", [Epanda, Bpanda])
def test_the_panda_variants_honour_their_angular_span(shape):
    region = shape((0.0, 0.0), 0.0, 90.0, 1, 2.0, 2.0, 10.0, 10.0, 1)
    assert region.contains(5.0, 5.0)
    assert not region.contains(5.0, -5.0)


@pytest.mark.parametrize("shape", [Epanda, Bpanda])
def test_the_panda_variants_move_and_scale(shape):
    region = shape((0.0, 0.0), 0.0, 360.0, 4, 2.0, 2.0, 10.0, 10.0, 2)
    region.move(3.0, 4.0)
    assert region.center == (3.0, 4.0)
    region.resize(2.0, 1.0)
    assert region.outer_major == pytest.approx(20.0)
    assert region.outer_minor == pytest.approx(10.0)


def test_a_full_span_contains_every_angle():
    region = Epanda((0.0, 0.0), 0.0, 360.0, 4, 2.0, 2.0, 10.0, 10.0, 2)
    for x, y in ((6.0, 0.0), (0.0, 6.0), (-6.0, 0.0), (0.0, -6.0), (4.0, 4.0)):
        assert region.contains(x, y), (x, y)


# -- the parts of DS9's format its own templates use (M6-18) -----------------


def test_a_unit_suffix_is_read_as_an_angle():
    """`16"` is sixteen arcseconds; DS9 writes its templates that way."""
    box = RegionParser().parse_string('fk5\nbox(150,2,16",32",0)\n')[0]
    assert box.width_box == pytest.approx(16 / 3600)
    assert box.height_box == pytest.approx(32 / 3600)


def test_arcminutes_too():
    circle = RegionParser().parse_string("fk5\ncircle(150,2,3')\n")[0]
    assert circle.radius == pytest.approx(0.05)


def test_a_unit_suffix_in_pixels_is_left_alone():
    """There is nothing to convert an arcsecond to in image pixels."""
    box = RegionParser().parse_string('image\nbox(50,50,16",16",0)\n')[0]
    assert box.width_box == pytest.approx(16.0)


def test_parameters_may_be_separated_by_spaces():
    """DS9's own documentation gives `circle 100 100 10`."""
    circle = RegionParser().parse_string("image\ncircle(100 100 10)\n")[0]
    assert (circle.center, circle.radius) == ((100.0, 100.0), 10.0)


def test_a_coordinate_system_may_share_the_line():
    regions = RegionParser().parse_string("image; circle(10,10,5)\n")
    assert len(regions) == 1


def test_a_shape_written_behind_a_hash_is_still_a_shape():
    """DS9 writes text, vector, ruler, compass and projection that way."""
    regions = RegionParser().parse_string("image\n# text(10,10) textangle=30 text={I0}\n")
    assert [type(region).__name__ for region in regions] == ["Text"]
    assert regions[0].text == "I0"


def test_composite_members_are_gathered_by_their_bars():
    """`||` means "or'd with the next", so the last member has none."""
    regions = RegionParser().parse_string(
        "image\n"
        "# composite(0,0,0) || composite=1\n"
        "circle(10,10,5) || # color=red\n"
        "box(20,20,4,4)\n"
        "circle(99,99,1)\n"
    )
    assert [type(region).__name__ for region in regions] == ["Composite", "Circle"]
    assert len(regions[0].regions) == 2


def test_wcs0_marks_a_file_as_relative():
    """DS9's template system: positions are offsets, in the frame beside it."""
    parser = RegionParser()
    parser.parse_string("wcs0;fk5\ncircle(0.1,0.1,0.01)\n")
    assert parser.relative is True
    assert parser.coordinate_system is CoordinateSystem.FK5


def test_an_ordinary_file_is_not_relative():
    parser = RegionParser()
    parser.parse_string("fk5\ncircle(150,2,0.01)\n")
    assert parser.relative is False
