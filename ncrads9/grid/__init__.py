# This file is part of ncrads9.
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
DS9's coordinate grid: what it looks like, where its lines go, how its
numbers are written.

`ast_wrapper.py` used to sit here, a shim over Starlink AST that was never
called and that made the grid depend on an optional C library. The geometry
is computed from `astropy.wcs`'s own transforms instead (M7-10).

Author: Yogesh Wadadekar
"""

from .grid_config import (
    COLORS,
    ELEMENTS,
    FONTS,
    LINE_ELEMENTS,
    LINE_STYLES,
    GridConfig,
    GridElement,
    GridType,
    Placement,
)
from .grid_labels import (
    Label,
    LabelPosition,
    NumericFormat,
    default_format,
    format_coordinate,
    nice_spacing,
    parse_format,
)
from .grid_renderer import GridGeometry, GridRenderer

__all__ = [
    "COLORS",
    "ELEMENTS",
    "FONTS",
    "LINE_ELEMENTS",
    "LINE_STYLES",
    "GridConfig",
    "GridElement",
    "GridGeometry",
    "GridRenderer",
    "GridType",
    "Label",
    "LabelPosition",
    "NumericFormat",
    "Placement",
    "default_format",
    "format_coordinate",
    "nice_spacing",
    "parse_format",
]
