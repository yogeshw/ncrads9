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
The region file formats DS9 writes, and what each of them loses.

DS9's own words (`ds9/doc/ref/region.html`, External Region Files): "Not all
formats support all the functionality of DS9 regions. Therefore, the user may
loose some information when writing and then reading back from a region file
in a format other that DS9."

The tables below are that loss, transcribed. CIAO cannot express a line, a
vector, a projection, a segment, text, a ruler, a compass, an ellipse
annulus, a box annulus, an epanda or a bpanda, and calls a panda a pie;
SAOimage and PROS lose those and the plain panda too; funtools loses the
seven open shapes; X Y keeps only positions.

Writing a region a format cannot express is not an error -- DS9 drops it
silently. `dropped_shapes` says which went, so a caller can tell the user
rather than leaving them to notice.

Author: Yogesh Wadadekar
"""

from __future__ import annotations

from enum import Enum

from .base_region import BaseRegion


class RegionFormat(Enum):
    """A region file format DS9 can write."""

    #: DS9's own, the only one that loses nothing.
    DS9 = "ds9"
    CIAO = "ciao"
    #: DS9's menu calls this SAOtng; its documentation calls it SAOimage.
    SAOIMAGE = "saoimage"
    PROS = "pros"
    FUNTOOLS = "funtools"
    #: One `x y` per line, positions and nothing else.
    XY = "xy"


#: The seven open shapes: every non-DS9 format drops all of them.
_OPEN_SHAPES: frozenset[str] = frozenset(
    {"line", "vector", "projection", "segment", "text", "ruler", "compass"}
)

#: The shapes with no equivalent, per format, from DS9's own table.
IGNORED_SHAPES: dict[RegionFormat, frozenset[str]] = {
    RegionFormat.DS9: frozenset(),
    RegionFormat.CIAO: _OPEN_SHAPES | {"ellipseannulus", "boxannulus", "epanda", "bpanda"},
    RegionFormat.SAOIMAGE: _OPEN_SHAPES | {"ellipseannulus", "boxannulus", "panda", "epanda", "bpanda"},
    RegionFormat.PROS: _OPEN_SHAPES | {"ellipseannulus", "boxannulus", "panda", "epanda", "bpanda"},
    RegionFormat.FUNTOOLS: _OPEN_SHAPES,
    RegionFormat.XY: frozenset(),
}

#: Shapes a format spells differently. DS9: "PANDA is translated into PIE".
SHAPE_TRANSLATIONS: dict[RegionFormat, dict[str, str]] = {
    RegionFormat.CIAO: {"panda": "pie"},
}

#: Formats that carry a region's properties. Only DS9's own does.
FORMATS_WITH_PROPERTIES: frozenset[RegionFormat] = frozenset({RegionFormat.DS9})

#: The header each format opens with, if any.
FORMAT_HEADERS: dict[RegionFormat, str] = {
    RegionFormat.DS9: "# Region file format: DS9 version 4.1",
    RegionFormat.CIAO: "# Region file format: CIAO version 1.0",
    RegionFormat.SAOIMAGE: "# Region file format: SAOimage version 1.0",
    RegionFormat.PROS: "# Region file format: PROS version 1.0",
    RegionFormat.FUNTOOLS: "# Region file format: Funtools version 1.0",
    RegionFormat.XY: "",
}


def shape_keyword(region: BaseRegion) -> str:
    """The keyword a region's DS9 line starts with.

    Read off the shape's own `to_ds9_string`, so a shape and its keyword
    cannot drift apart -- an ellipse annulus writes `ellipse(...)`, and this
    reports `ellipse`, which is what a format table has to match on.
    """
    text = region.to_ds9_string().strip()
    keyword = text.split("(", 1)[0].split()[0] if text else ""
    return keyword.strip().lower()


def class_keyword(region: BaseRegion) -> str:
    """The region's own name, lowercased and unspaced.

    `to_ds9_string` cannot tell an ellipse from an ellipse annulus, both
    writing `ellipse`, so the ignore tables key on the class instead.
    """
    return type(region).__name__.replace("_", "").lower()


def is_writable(region: BaseRegion, region_format: RegionFormat) -> bool:
    """Whether a format can express one region.

    Args:
        region: The region.
        region_format: The format to write.

    Returns:
        False when the format has no equivalent for the shape, in which case
        DS9 drops it.
    """
    ignored = IGNORED_SHAPES.get(region_format, frozenset())
    return class_keyword(region) not in ignored and shape_keyword(region) not in ignored


def dropped_shapes(
    regions: list[BaseRegion],
    region_format: RegionFormat,
) -> list[str]:
    """Which shapes a format would silently drop.

    Args:
        regions: The regions about to be written.
        region_format: The format to write.

    Returns:
        The distinct shape names dropped, in the order first met, so a caller
        can say what is being lost.
    """
    lost: list[str] = []
    for region in regions:
        if is_writable(region, region_format):
            continue
        name = class_keyword(region)
        if name not in lost:
            lost.append(name)
    return lost


def translate(keyword: str, region_format: RegionFormat) -> str:
    """The name a format gives one shape."""
    return SHAPE_TRANSLATIONS.get(region_format, {}).get(keyword, keyword)
