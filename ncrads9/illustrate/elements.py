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
The things DS9's Illustrate layer draws.

An illustration is not a region. A region marks a place in the data and
travels with it: pan, zoom or load another frame of the same field and the
region is still around the same star. An illustration is drawn on the
canvas -- an arrow pointing at something in a figure, a caption, a logo --
and stays where it was put (`illustratebase.tcl`, where every element's
geometry is Tk canvas coordinates). So these carry no WCS and no image
coordinates at all, and their positions are in canvas pixels with y
counting down, as both Tk and Qt have it.

Author: Yogesh Wadadekar
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field, replace

#: What DS9 draws a new illustration in (`illustrate.tcl:24`).
DEFAULT_COLOR = "cyan"
DEFAULT_WIDTH = 1

#: DS9's text defaults (`illustrate.tcl:35`).
DEFAULT_FONT = "helvetica"
DEFAULT_FONT_SIZE = 12
DEFAULT_FONT_WEIGHT = "normal"
DEFAULT_FONT_SLANT = "roman"
DEFAULT_JUSTIFY = "left"

#: The size a new element is given when it is placed with a click rather
#: than dragged out (`pillustrate` defaults, `illustrate.tcl:47`).
DEFAULT_SIZES: dict[str, tuple[float, ...]] = {
    "circle": (20.0,),
    "ellipse": (40.0, 20.0),
    "box": (80.0, 40.0),
    "polygon": (20.0, 20.0),
}

#: How near a click has to be to count as on a line or a handle.
PICK_SLOP = 4.0

#: The shapes the Illustrate menu offers, in its order.
SHAPES: tuple[str, ...] = ("circle", "ellipse", "box", "polygon", "line", "text", "image")


@dataclass
class Style:
    """How an element is drawn."""

    color: str = DEFAULT_COLOR
    fill: bool = False
    width: int = DEFAULT_WIDTH
    dash: bool = False

    def properties(self) -> str:
        """The `# color = ... ` tail DS9 writes, empty when all is default.

        Only what differs from the default is written, which is what makes a
        saved file readable (`IllustrateBaseListProps`).
        """
        parts = []
        if self.color != DEFAULT_COLOR:
            parts.append(f"color = {self.color}")
        if self.fill:
            parts.append("fill = yes")
        if self.width != DEFAULT_WIDTH:
            parts.append(f"width = {self.width}")
        if self.dash:
            parts.append("dash = yes")
        return (" # " + " ".join(parts)) if parts else ""


@dataclass
class Element:
    """One illustration.

    Subclasses carry the geometry; everything here is what the layer and the
    overlay need of all of them alike.
    """

    style: Style = field(default_factory=Style)
    #: Whether the element is in the selection, which is what the menu's
    #: All/None/Invert and the selection commands work on.
    selected: bool = False

    #: The name the file format and the Shape menu use.
    kind = "element"

    # -- geometry every element has ---------------------------------------------

    def bounds(self) -> tuple[float, float, float, float]:
        """The element's extent, as (x0, y0, x1, y1)."""
        raise NotImplementedError

    def move(self, dx: float, dy: float) -> None:
        """Shift the element by a canvas offset."""
        raise NotImplementedError

    def resize(self, handle: int, x: float, y: float) -> None:
        """Drag one handle to a canvas position."""
        raise NotImplementedError

    def to_line(self) -> str:
        """The element as one line of DS9's illustrate format."""
        raise NotImplementedError

    # -- what the overlay asks --------------------------------------------------

    @property
    def center(self) -> tuple[float, float]:
        """The middle of the element's extent."""
        x0, y0, x1, y1 = self.bounds()
        return ((x0 + x1) / 2.0, (y0 + y1) / 2.0)

    def contains(self, x: float, y: float) -> bool:
        """Whether a click at a canvas position is on this element.

        The extent by default, which is right for anything filled and near
        enough for anything else; the outline shapes narrow it themselves.
        """
        x0, y0, x1, y1 = self.bounds()
        return x0 - PICK_SLOP <= x <= x1 + PICK_SLOP and y0 - PICK_SLOP <= y <= y1 + PICK_SLOP

    def handles(self) -> list[tuple[float, float]]:
        """The corners of the extent, which is what DS9 puts handles on."""
        x0, y0, x1, y1 = self.bounds()
        return [(x0, y0), (x1, y0), (x1, y1), (x0, y1)]

    def handle_at(self, x: float, y: float) -> int | None:
        """Which handle a click grabbed, if any."""
        for index, (hx, hy) in enumerate(self.handles()):
            if abs(x - hx) <= PICK_SLOP and abs(y - hy) <= PICK_SLOP:
                return index
        return None

    def copy(self) -> Element:
        """A duplicate, for Copy and Paste, unselected and independent."""
        clone = replace(self, style=replace(self.style))
        clone.selected = False
        return clone

    # -- helpers for the subclasses --------------------------------------------

    @staticmethod
    def _number(value: float) -> str:
        """A coordinate as DS9 writes it: no trailing zeros to read past."""
        return f"{value:g}"


@dataclass
class Circle(Element):
    """A circle, as DS9's `circle xc yc r`."""

    x: float = 0.0
    y: float = 0.0
    radius: float = DEFAULT_SIZES["circle"][0]

    kind = "circle"

    def bounds(self) -> tuple[float, float, float, float]:
        return (self.x - self.radius, self.y - self.radius, self.x + self.radius, self.y + self.radius)

    def move(self, dx: float, dy: float) -> None:
        self.x += dx
        self.y += dy

    def resize(self, handle: int, x: float, y: float) -> None:
        """A circle has one radius, so any handle sets it."""
        self.radius = max(1.0, math.hypot(x - self.x, y - self.y) / math.sqrt(2.0))

    def contains(self, x: float, y: float) -> bool:
        distance = math.hypot(x - self.x, y - self.y)
        if self.style.fill:
            return distance <= self.radius + PICK_SLOP
        return abs(distance - self.radius) <= PICK_SLOP + self.style.width

    def to_line(self) -> str:
        return (
            f"circle {self._number(self.x)} {self._number(self.y)} "
            f"{self._number(self.radius)}{self.style.properties()}"
        )


@dataclass
class Ellipse(Element):
    """An ellipse, as DS9's `ellipse xc yc r1 r2`."""

    x: float = 0.0
    y: float = 0.0
    radius1: float = DEFAULT_SIZES["ellipse"][0]
    radius2: float = DEFAULT_SIZES["ellipse"][1]

    kind = "ellipse"

    def bounds(self) -> tuple[float, float, float, float]:
        return (
            self.x - self.radius1,
            self.y - self.radius2,
            self.x + self.radius1,
            self.y + self.radius2,
        )

    def move(self, dx: float, dy: float) -> None:
        self.x += dx
        self.y += dy

    def resize(self, handle: int, x: float, y: float) -> None:
        self.radius1 = max(1.0, abs(x - self.x))
        self.radius2 = max(1.0, abs(y - self.y))

    def contains(self, x: float, y: float) -> bool:
        dx = (x - self.x) / max(self.radius1, 1e-6)
        dy = (y - self.y) / max(self.radius2, 1e-6)
        radial = math.hypot(dx, dy)
        if self.style.fill:
            return radial <= 1.0 + PICK_SLOP / max(self.radius1, self.radius2)
        return abs(radial - 1.0) <= PICK_SLOP / min(self.radius1, self.radius2)

    def to_line(self) -> str:
        return (
            f"ellipse {self._number(self.x)} {self._number(self.y)} "
            f"{self._number(self.radius1)} {self._number(self.radius2)}"
            f"{self.style.properties()}"
        )


@dataclass
class Box(Element):
    """A rectangle, as DS9's `box xc yc r1 r2` -- radii, not width and height."""

    x: float = 0.0
    y: float = 0.0
    radius1: float = DEFAULT_SIZES["box"][0]
    radius2: float = DEFAULT_SIZES["box"][1]

    kind = "box"

    def bounds(self) -> tuple[float, float, float, float]:
        return (
            self.x - self.radius1,
            self.y - self.radius2,
            self.x + self.radius1,
            self.y + self.radius2,
        )

    def move(self, dx: float, dy: float) -> None:
        self.x += dx
        self.y += dy

    def resize(self, handle: int, x: float, y: float) -> None:
        self.radius1 = max(1.0, abs(x - self.x))
        self.radius2 = max(1.0, abs(y - self.y))

    def contains(self, x: float, y: float) -> bool:
        x0, y0, x1, y1 = self.bounds()
        inside = x0 <= x <= x1 and y0 <= y <= y1
        if self.style.fill:
            return inside
        near_edge = (
            abs(x - x0) <= PICK_SLOP
            or abs(x - x1) <= PICK_SLOP
            or abs(y - y0) <= PICK_SLOP
            or abs(y - y1) <= PICK_SLOP
        )
        return near_edge and super().contains(x, y)

    def to_line(self) -> str:
        return (
            f"box {self._number(self.x)} {self._number(self.y)} "
            f"{self._number(self.radius1)} {self._number(self.radius2)}"
            f"{self.style.properties()}"
        )


@dataclass
class Polygon(Element):
    """A closed run of points, as DS9's `polygon x1 y1 x2 y2 ...`."""

    points: list[tuple[float, float]] = field(default_factory=list)

    kind = "polygon"

    def bounds(self) -> tuple[float, float, float, float]:
        if not self.points:
            return (0.0, 0.0, 0.0, 0.0)
        xs = [p[0] for p in self.points]
        ys = [p[1] for p in self.points]
        return (min(xs), min(ys), max(xs), max(ys))

    def move(self, dx: float, dy: float) -> None:
        self.points = [(x + dx, y + dy) for x, y in self.points]

    def handles(self) -> list[tuple[float, float]]:
        """Its own points, so a polygon is reshaped vertex by vertex."""
        return list(self.points)

    def resize(self, handle: int, x: float, y: float) -> None:
        if 0 <= handle < len(self.points):
            self.points[handle] = (x, y)

    def contains(self, x: float, y: float) -> bool:
        if self.style.fill:
            return _inside_polygon(x, y, self.points)
        closed = list(self.points) + self.points[:1]
        return any(_near_segment(x, y, closed[index], closed[index + 1]) for index in range(len(closed) - 1))

    def copy(self) -> Element:
        clone = super().copy()
        clone.points = list(self.points)  # type: ignore[attr-defined]
        return clone

    def to_line(self) -> str:
        coords = " ".join(f"{self._number(x)} {self._number(y)}" for x, y in self.points)
        return f"polygon {coords}{self.style.properties()}"


@dataclass
class Line(Element):
    """An open run of points, with an arrowhead at either end or both."""

    points: list[tuple[float, float]] = field(default_factory=list)
    arrow_first: bool = False
    arrow_last: bool = False

    kind = "line"

    def bounds(self) -> tuple[float, float, float, float]:
        if not self.points:
            return (0.0, 0.0, 0.0, 0.0)
        xs = [p[0] for p in self.points]
        ys = [p[1] for p in self.points]
        return (min(xs), min(ys), max(xs), max(ys))

    def move(self, dx: float, dy: float) -> None:
        self.points = [(x + dx, y + dy) for x, y in self.points]

    def handles(self) -> list[tuple[float, float]]:
        """Its ends, which is what a line is dragged by."""
        return list(self.points)

    def resize(self, handle: int, x: float, y: float) -> None:
        if 0 <= handle < len(self.points):
            self.points[handle] = (x, y)

    def contains(self, x: float, y: float) -> bool:
        return any(
            _near_segment(x, y, self.points[index], self.points[index + 1])
            for index in range(len(self.points) - 1)
        )

    def copy(self) -> Element:
        clone = super().copy()
        clone.points = list(self.points)  # type: ignore[attr-defined]
        return clone

    def to_line(self) -> str:
        coords = " ".join(f"{self._number(x)} {self._number(y)}" for x, y in self.points)
        parts = []
        if self.style.color != DEFAULT_COLOR:
            parts.append(f"color = {self.style.color}")
        if self.style.width != DEFAULT_WIDTH:
            parts.append(f"width = {self.style.width}")
        if self.style.dash:
            parts.append("dash = yes")
        if self.arrow_first or self.arrow_last:
            parts.append(f"line = {int(self.arrow_first)} {int(self.arrow_last)}")
        tail = (" # " + " ".join(parts)) if parts else ""
        return f"line {coords}{tail}"


@dataclass
class Text(Element):
    """A caption, as DS9's `text x y "the words"`."""

    x: float = 0.0
    y: float = 0.0
    text: str = ""
    font: str = DEFAULT_FONT
    font_size: int = DEFAULT_FONT_SIZE
    font_weight: str = DEFAULT_FONT_WEIGHT
    font_slant: str = DEFAULT_FONT_SLANT
    angle: float = 0.0
    justify: str = DEFAULT_JUSTIFY

    kind = "text"

    def bounds(self) -> tuple[float, float, float, float]:
        """Guessed from the font, since the layer has no font metrics.

        The overlay measures it properly when it draws; this only has to be
        close enough to click on.
        """
        lines = self.text.split("\n") or [""]
        width = max((len(line) for line in lines), default=0) * self.font_size * 0.6
        height = len(lines) * self.font_size * 1.2
        return (self.x - width / 2.0, self.y - height / 2.0, self.x + width / 2.0, self.y + height / 2.0)

    def move(self, dx: float, dy: float) -> None:
        self.x += dx
        self.y += dy

    def resize(self, handle: int, x: float, y: float) -> None:
        """Dragging a corner sets the font size, there being nothing else."""
        height = max(4.0, abs(y - self.y) * 2.0)
        self.font_size = int(round(height / max(1, len(self.text.split("\n"))) / 1.2))
        self.font_size = max(4, min(200, self.font_size))

    def to_line(self) -> str:
        escaped = self.text.replace("\\", "\\\\").replace('"', '\\"').replace("\n", "\\n")
        parts = []
        if self.style.color != DEFAULT_COLOR:
            parts.append(f"color = {self.style.color}")
        if self.font != DEFAULT_FONT:
            parts.append(f"font = {self.font}")
        if self.font_size != DEFAULT_FONT_SIZE:
            parts.append(f"fontsize = {self.font_size}")
        if self.font_weight != DEFAULT_FONT_WEIGHT:
            parts.append(f"fontweight = {self.font_weight}")
        if self.font_slant != DEFAULT_FONT_SLANT:
            parts.append(f"fontslant = {self.font_slant}")
        if self.angle:
            parts.append(f"angle = {self._number(self.angle)}")
        if self.justify != DEFAULT_JUSTIFY:
            parts.append(f"justify = {self.justify}")
        tail = (" # " + " ".join(parts)) if parts else ""
        return f'text {self._number(self.x)} {self._number(self.y)} "{escaped}"{tail}'


@dataclass
class Image(Element):
    """A picture placed on the canvas, as DS9's `image x y "file" w h`."""

    x: float = 0.0
    y: float = 0.0
    path: str = ""
    width: float = 0.0
    height: float = 0.0

    kind = "image"

    def bounds(self) -> tuple[float, float, float, float]:
        return (
            self.x - self.width / 2.0,
            self.y - self.height / 2.0,
            self.x + self.width / 2.0,
            self.y + self.height / 2.0,
        )

    def move(self, dx: float, dy: float) -> None:
        self.x += dx
        self.y += dy

    def resize(self, handle: int, x: float, y: float) -> None:
        """Kept to its aspect ratio, as DS9 does (`IllustrateImageEdit`)."""
        ratio = (self.height / self.width) if self.width else 1.0
        self.width = max(4.0, abs(x - self.x) * 2.0)
        self.height = max(4.0, self.width * ratio)

    def contains(self, x: float, y: float) -> bool:
        x0, y0, x1, y1 = self.bounds()
        return x0 <= x <= x1 and y0 <= y <= y1

    def to_line(self) -> str:
        return (
            f'image {self._number(self.x)} {self._number(self.y)} "{self.path}" '
            f"{self._number(self.width)} {self._number(self.height)}"
        )


#: Shape name -> its class, for the file reader and the Shape menu.
ELEMENTS: dict[str, type[Element]] = {
    "circle": Circle,
    "ellipse": Ellipse,
    "box": Box,
    "polygon": Polygon,
    "line": Line,
    "text": Text,
    "image": Image,
}


def _near_segment(
    x: float,
    y: float,
    start: tuple[float, float],
    end: tuple[float, float],
) -> bool:
    """Whether a point is within picking distance of a line segment."""
    (x0, y0), (x1, y1) = start, end
    dx, dy = x1 - x0, y1 - y0
    length = math.hypot(dx, dy)
    if length < 1e-9:
        return math.hypot(x - x0, y - y0) <= PICK_SLOP
    along = max(0.0, min(1.0, ((x - x0) * dx + (y - y0) * dy) / (length * length)))
    return math.hypot(x - (x0 + along * dx), y - (y0 + along * dy)) <= PICK_SLOP


def _inside_polygon(x: float, y: float, points: list[tuple[float, float]]) -> bool:
    """Whether a point is inside a polygon, by the crossing count."""
    if len(points) < 3:
        return False
    inside = False
    for index in range(len(points)):
        x0, y0 = points[index]
        x1, y1 = points[(index + 1) % len(points)]
        if (y0 > y) != (y1 > y):
            crossing = x0 + (y - y0) / (y1 - y0) * (x1 - x0)
            if x < crossing:
                inside = not inside
    return inside
