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

"""
Shapes subpackage for region shapes.

This package contains concrete implementations of region shapes
such as circles, boxes, ellipses, polygons, etc.

Author: Yogesh Wadadekar
"""

from .circle import Circle
from .ellipse import Ellipse
from .box import Box
from .polygon import Polygon
from .annulus import Annulus
from .ellipse_annulus import EllipseAnnulus
from .box_annulus import BoxAnnulus
from .panda import Panda
from .point import Point
from .line import Line
from .vector import Vector
from .text import Text
from .ruler import Ruler
from .compass import Compass
from .projection import Projection
from .composite import Composite

__all__: list[str] = [
    "Circle",
    "Ellipse",
    "Box",
    "Polygon",
    "Annulus",
    "EllipseAnnulus",
    "BoxAnnulus",
    "Panda",
    "Point",
    "Line",
    "Vector",
    "Text",
    "Ruler",
    "Compass",
    "Projection",
    "Composite",
]
