# NCRADS9 - NCRA DS9 Visualization Tool
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
Coordinate systems and transformations for NCRADS9.

`CoordinateContext` is the single place a coordinate is transformed and
formatted; `PhysicalTransform` reads a header's `LTV*`/`LTM*` mapping. The
five per-system value objects that used to sit here -- `WCSCoords`,
`ImageCoords` and the `fk4_fk5`, `galactic` and `ecliptic` function pairs --
were each a thin wrapper over `astropy.coordinates.SkyCoord`, unreachable
from the application since before M0 and superseded by `CoordinateContext` in
M1. M3's information panel, which was the milestone meant to adopt them, was
finished without any of them, so they were deleted rather than carried
further. See TODO.md under M3 for the reasoning.

Author: Yogesh Wadadekar
"""

from .coord_system import (
    CoordFrame,
    CoordinateContext,
    CoordSystem,
    CoordSystemType,
    SkyFormat,
    SkyFrame,
)
from .physical_coords import PhysicalCoords, PhysicalTransform
from .sexagesimal import degrees_to_dms, degrees_to_hms, parse_sexagesimal

__all__ = [
    "CoordFrame",
    "CoordSystem",
    "CoordSystemType",
    "CoordinateContext",
    "PhysicalCoords",
    "PhysicalTransform",
    "SkyFormat",
    "SkyFrame",
    "degrees_to_dms",
    "degrees_to_hms",
    "parse_sexagesimal",
]
