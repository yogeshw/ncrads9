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

from .annulus import Annulus
from .box import Box
from .box_annulus import BoxAnnulus
from .circle import Circle
from .compass import Compass
from .composite import Composite
from .ellipse import Ellipse
from .ellipse_annulus import EllipseAnnulus
from .line import Line
from .panda import Panda
from .point import Point
from .polygon import Polygon
from .projection import Projection
from .ruler import Ruler
from .text import Text
from .vector import Vector

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
