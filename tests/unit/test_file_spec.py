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


"""DS9's file specification: `foo.fits[2][100:200,*,4]`.

Every example in `ds9/doc/ref/file.html` under FITS Image and FITS Binary
Events Table appears below, so the parser is checked against DS9's own
documented syntax rather than against what seemed reasonable.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from ncrads9.core.file_spec import (
    BIN_KEYWORDS,
    DEFAULT_BIN_COLUMNS,
    AxisSpec,
    BinSpec,
    FileSpecError,
    Section,
    parse,
)

# -- DS9's own examples ------------------------------------------------------


def test_plain_filename_has_no_specification():
    spec = parse("foo.fits")
    assert spec.path == Path("foo.fits")
    assert not spec.has_specification
    assert spec.extension is None


@pytest.mark.parametrize(
    ("text", "extension"),
    [
        ("foo.fits[1]", 1),
        ("foo.fits[0]", 0),
        ("foo.fits[BCKGRD]", "BCKGRD"),
        ("foo.fits[events]", "events"),
        ("foo.fits[SCI.1]", "SCI.1"),
    ],
)
def test_extension_by_number_or_name(text, extension):
    assert parse(text).extension == extension


@pytest.mark.parametrize(
    ("text", "x", "y", "block", "z"),
    [
        ("foo.fits[10:200,40:100]", (10, 200), (40, 100), 1, None),
        ("foo.fits[10:200,40:100,2]", (10, 200), (40, 100), 2, None),
        ("foo.fits[*,40:100]", None, (40, 100), 1, None),
        ("foo.fits[10:200,*]", (10, 200), None, 1, None),
        ("foo.fits[10:200,40:100,5:20]", (10, 200), (40, 100), 1, (5, 20)),
        ("foo.fits[*,40:100,5:20]", None, (40, 100), 1, (5, 20)),
        ("foo.fits[*,*,2]", None, None, 2, None),
        ("foo.fits[*,*,5:20]", None, None, 1, (5, 20)),
        ("foo.fits[*,*,2,5:20]", None, None, 2, (5, 20)),
    ],
)
def test_sections_from_the_documented_grammar(text, x, y, block, z):
    section = parse(text).section
    assert section is not None
    assert (section.x.lo, section.x.hi) == (x if x else (None, None))
    assert (section.y.lo, section.y.hi) == (y if y else (None, None))
    assert section.block == block
    if z is None:
        assert section.z is None
    else:
        assert (section.z.lo, section.z.hi) == z


def test_centred_section():
    """DS9's `[256@512@512]`: a 256-pixel box centred on 512,512."""
    section = parse("foo.fits[256@512@512]").section
    assert section is not None
    assert (section.x.lo, section.x.hi) == (384, 639)
    assert (section.y.lo, section.y.hi) == (384, 639)


def test_centred_axes_separately():
    section = parse("foo.fits[100@50,20@10]").section
    # width // 2 below the centre, then `width` pixels: 50-50=0 .. 99.
    assert (section.x.lo, section.x.hi) == (0, 99)
    assert (section.y.lo, section.y.hi) == (0, 19)


def test_extension_and_section_in_separate_groups():
    spec = parse("foo.fits[2][100:200,100:200]")
    assert spec.extension == 2
    assert (spec.section.x.lo, spec.section.x.hi) == (100, 200)


def test_extension_and_section_in_one_group():
    """DS9's `filename[ext,sect]`."""
    spec = parse("foo.fits[EVENTS,100:200,*]")
    assert spec.extension == "EVENTS"
    assert spec.section.y.is_wildcard


def test_cube_section_with_block_and_extension():
    spec = parse("foo.fits[2][100:200,100:200,2,5:20]")
    assert spec.extension == 2
    assert spec.section.block == 2
    assert (spec.section.z.lo, spec.section.z.hi) == (5, 20)


def test_physical_section():
    assert parse("foo.fits[10:200,40:100p]").section.physical
    assert not parse("foo.fits[10:200,40:100]").section.physical


@pytest.mark.parametrize(
    ("text", "columns"),
    [
        ("foo.fits[bin=detx,dety]", ("detx", "dety")),
        ("foo.fits[bin=x,y,pha]", ("x", "y", "pha")),
        ("foo.fits[bin=pi]", (*DEFAULT_BIN_COLUMNS, "pi")),
    ],
)
def test_bin_groups(text, columns):
    assert parse(text).bin.columns == columns


def test_bin_with_extension_in_one_group():
    spec = parse("foo.fits[bg_events,bin=rawx,rawy]")
    assert spec.extension == "bg_events"
    assert spec.bin.columns == ("rawx", "rawy")


def test_bin_and_extension_in_separate_groups():
    spec = parse("foo.fits[2][bin=rawx,rawy]")
    assert spec.extension == 2
    assert spec.bin.columns == ("rawx", "rawy")


@pytest.mark.parametrize("keyword", BIN_KEYWORDS)
def test_every_bin_keyword_is_accepted(keyword):
    spec = parse(f"foo.fits[{keyword}=colx,coly]")
    assert spec.bin.columns == ("colx", "coly")
    assert spec.bin.keyword == keyword


def test_filter_expression():
    spec = parse("foo.fits[ccd_id==3&&energy>4000]")
    assert spec.filters == ("ccd_id==3&&energy>4000",)
    assert spec.extension is None


def test_quoted_specification():
    """DS9's examples are quoted to get them past the shell."""
    spec = parse("'foo.fits[ccd_id==3 && energy>4000]'")
    assert spec.path == Path("foo.fits")
    assert "ccd_id==3" in spec.filter_expression


def test_comma_in_a_filter_group_means_and():
    spec = parse("foo.fits[events][pha>5,pi<2]")
    assert spec.extension == "events"
    assert spec.filter_expression == "pha>5&&pi<2"


def test_bin_filter_joins_the_filter_expression():
    spec = parse("foo.fits[bin=x,y,pha>5]")
    assert spec.bin.columns == ("x", "y")
    assert spec.filter_expression == "pha>5"


# -- paths and edge cases ----------------------------------------------------


def test_a_bracket_in_the_path_is_not_a_specification():
    spec = parse("/data/[run3]/foo.fits[2]")
    assert spec.path == Path("/data/[run3]/foo.fits")
    assert spec.extension == 2


def test_a_bracket_in_the_path_with_no_specification():
    spec = parse("/data/[run3]/foo.fits")
    assert spec.path == Path("/data/[run3]/foo.fits")
    assert not spec.has_specification


def test_whitespace_is_ignored():
    assert parse("  foo.fits[2]  ").extension == 2


def test_empty_group_is_ignored():
    assert not parse("foo.fits[]").has_specification


@pytest.mark.parametrize(
    "text",
    [
        "foo.fits[2][3]",
        "foo.fits[1:2,3:4][5:6,7:8]",
        "foo.fits[bin=x,y][bin=a,b]",
        "[2]",
        "foo.fits[",
        "foo.fits[nonsense group]",
    ],
)
def test_contradictions_and_nonsense_are_rejected(text):
    with pytest.raises(FileSpecError):
        parse(text)


def test_round_trip():
    """`str(spec)` reparses to the same thing."""
    for text in (
        "foo.fits",
        "foo.fits[2]",
        "foo.fits[SCI]",
        "foo.fits[10:200,40:100,2]",
        "foo.fits[bin=x,y,pha]",
        "foo.fits[2][*,40:100]",
        "foo.fits[ccd_id==3]",
    ):
        first = parse(text)
        assert parse(str(first)) == first


# -- AxisSpec ----------------------------------------------------------------


def test_wildcard_resolves_to_the_whole_axis():
    assert AxisSpec.wildcard().resolve(512) == (1, 512)


def test_range_is_clipped_to_the_axis():
    assert AxisSpec.between(10, 20).resolve(512) == (10, 20)
    assert AxisSpec.between(-5, 20).resolve(512) == (1, 20)
    assert AxisSpec.between(500, 900).resolve(512) == (500, 512)


def test_reversed_range_is_normalised():
    assert AxisSpec.between(20, 10) == AxisSpec.between(10, 20)


def test_centred_width_puts_the_centre_in_the_middle():
    assert AxisSpec.centred(5, 10).resolve(100) == (8, 12)
    # An even width takes its extra pixel below the centre.
    assert AxisSpec.centred(4, 10).resolve(100) == (8, 11)


def test_centred_box_always_contains_its_centre():
    for width in range(1, 12):
        for centre in range(20, 30):
            lo, hi = AxisSpec.centred(width, centre).resolve(1000)
            assert lo <= centre <= hi, (width, centre)
            assert hi - lo + 1 == width, (width, centre)


def test_centred_box_does_not_depend_on_the_centre_parity():
    """Rounding halves to even used to shift even-width boxes about."""
    offsets = {centre - AxisSpec.centred(4, centre).lo for centre in range(10, 20)}
    assert len(offsets) == 1


def test_zero_width_is_rejected():
    with pytest.raises(FileSpecError):
        AxisSpec.centred(0, 10)


def test_section_str_omits_a_unit_block():
    assert str(Section(AxisSpec.between(1, 2), AxisSpec.between(3, 4))) == "1:2,3:4"
    assert str(Section(AxisSpec.wildcard(), AxisSpec.wildcard(), block=4)) == "*,*,4"


def test_bin_spec_str_round_trips():
    assert str(BinSpec(("x", "y", "pha"))) == "bin=x,y,pha"
    assert str(BinSpec(("x", "y"), filter="pi<3")) == "bin=x,y,pi<3"
