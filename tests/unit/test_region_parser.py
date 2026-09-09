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
#
# Author: Yogesh Wadadekar

"""Tests for regions.region_parser module."""

import pytest

from ncrads9.regions.region_parser import CoordinateSystem, RegionFormat, RegionParser
from ncrads9.regions.shapes.box import Box
from ncrads9.regions.shapes.circle import Circle
from ncrads9.regions.shapes.text import Text


class TestRegionParser:
    """Test cases for RegionParser class."""

    def test_parses_header_globals_and_coordinate_system(self):
        parser = RegionParser()
        parser.parse_string(
            "# Region file format: DS9 version 4.1\n" "global color=green width=2\n" "image\n"
        )
        assert parser.format is RegionFormat.DS9
        assert parser.coordinate_system is CoordinateSystem.IMAGE
        assert parser.get_global_properties()["color"] == "green"
        assert parser.get_global_properties()["width"] == "2"

    def test_parses_basic_shapes(self):
        parser = RegionParser()
        regions = parser.parse_string("image\n" "circle(100,100,20)\n" "box(10,20,30,40,15)\n")
        assert [type(r) for r in regions] == [Circle, Box]

    def test_text_region_does_not_abort_the_file(self):
        """A `text` region used to raise TypeError and abort the whole load."""
        parser = RegionParser()
        regions = parser.parse_string(
            "image\n" "circle(100,100,20)\n" "text(150,150) # text={Hello}\n" "box(10,20,30,40,0)\n"
        )
        assert [type(r) for r in regions] == [Circle, Text, Box]

    def test_text_region_label_strips_brace_delimiters(self):
        parser = RegionParser()
        (region,) = parser.parse_string("image\ntext(1,2) # text={Hello}\n")
        assert isinstance(region, Text)
        assert region.label == "Hello"

    def test_brace_delimited_value_keeps_internal_spaces(self):
        """`text={Hello World}` must not truncate at the space."""
        parser = RegionParser()
        (region,) = parser.parse_string("image\ntext(1,2) # text={Hello World}\n")
        assert region.label == "Hello World"

    def test_quoted_value_keeps_internal_spaces(self):
        parser = RegionParser()
        parser.parse_string('global font="helvetica 10 normal roman"\n')
        assert parser.get_global_properties()["font"] == "helvetica 10 normal roman"

    def test_empty_brace_value_is_an_empty_string(self):
        parser = RegionParser()
        (region,) = parser.parse_string("image\ncircle(1,2,3) # text={}\n")
        assert region.text == ""

    @pytest.mark.parametrize(
        ("line", "expected"),
        [
            ("circle(1,2,3) # color=red", "red"),
            ("circle(1,2,3) # color={red}", "red"),
            ('circle(1,2,3) # color="red"', "red"),
        ],
    )
    def test_property_delimiters_are_interchangeable(self, line, expected):
        parser = RegionParser()
        (region,) = parser.parse_string(f"image\n{line}\n")
        assert region.color == expected

    def test_malformed_region_is_skipped_not_fatal(self):
        parser = RegionParser()
        regions = parser.parse_string("image\n" "circle(nonsense)\n" "circle(100,100,20)\n")
        assert [type(r) for r in regions] == [Circle]
