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

Author: Yogesh Wadadekar
"""

from .coord_system import CoordSystem, CoordSystemType
from .image_coords import ImageCoords
from .physical_coords import PhysicalCoords
from .wcs_coords import WCSCoords
from .fk4_fk5 import convert_fk4_to_fk5, convert_fk5_to_fk4
from .galactic import equatorial_to_galactic, galactic_to_equatorial
from .ecliptic import equatorial_to_ecliptic, ecliptic_to_equatorial
from .sexagesimal import degrees_to_hms, degrees_to_dms, parse_sexagesimal

__all__ = [
    "CoordSystem",
    "CoordSystemType",
    "ImageCoords",
    "PhysicalCoords",
    "WCSCoords",
    "convert_fk4_to_fk5",
    "convert_fk5_to_fk4",
    "equatorial_to_galactic",
    "galactic_to_equatorial",
    "equatorial_to_ecliptic",
    "ecliptic_to_equatorial",
    "degrees_to_hms",
    "degrees_to_dms",
    "parse_sexagesimal",
]
