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

"""DS9's Illustrate layer: annotations drawn on the canvas, not on the sky."""

from .elements import (
    ELEMENTS,
    SHAPES,
    Box,
    Circle,
    Element,
    Ellipse,
    Image,
    Line,
    Polygon,
    Style,
    Text,
)
from .illustrate_file import HEADER, load, parse, save, serialise
from .layer import IllustrateLayer

__all__ = [
    "ELEMENTS",
    "HEADER",
    "SHAPES",
    "Box",
    "Circle",
    "Element",
    "Ellipse",
    "IllustrateLayer",
    "Image",
    "Line",
    "Polygon",
    "Style",
    "Text",
    "load",
    "parse",
    "save",
    "serialise",
]
