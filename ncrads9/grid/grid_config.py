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
What a coordinate grid looks like: DS9's seven elements and their settings.

"A coordinate grid is composed of Grid Lines, Axes, Border, and Title. Axes
include tick marks, title, and numbers" (`ds9/doc/ref/grid.html`), and DS9's
Grid Parameters dialog gives each of those seven its own Show, colour, and
either a line style or a font (`ds9/library/grid.tcl:581`). That is what
`GridElement` is: the same handful of settings, seven times, rather than
seven near-identical blocks of fields.

What this replaced: a config of one line colour, one label colour and a
spacing, which could not express any of it.

Author: Yogesh Wadadekar
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field, replace
from enum import Enum
from pathlib import Path
from typing import Any

#: The elements DS9's Grid Parameters dialog has a menu for, in its order.
ELEMENTS: tuple[str, ...] = (
    "grid",
    "axes",
    "numerics",
    "labels",
    "tickmarks",
    "title",
    "border",
)

#: Which of them are drawn with a line rather than set in a font.
LINE_ELEMENTS: frozenset[str] = frozenset({"grid", "axes", "tickmarks", "border"})

#: The line styles DS9's Line cascade offers.
LINE_STYLES: tuple[str, ...] = ("solid", "dashed", "dotted")

#: The widths it offers.
LINE_WIDTHS: tuple[int, ...] = (1, 2, 3, 4)

#: The colours it offers, which are the same eight as everywhere else in DS9.
COLORS: tuple[str, ...] = (
    "black",
    "white",
    "red",
    "green",
    "blue",
    "cyan",
    "magenta",
    "yellow",
)

#: The fonts and sizes its Font cascades offer.
FONTS: tuple[str, ...] = ("helvetica", "times", "courier")
FONT_SIZES: tuple[int, ...] = (9, 10, 12, 14, 16, 18, 24)
FONT_WEIGHTS: tuple[str, ...] = ("normal", "bold")
FONT_SLANTS: tuple[str, ...] = ("roman", "italic")


class GridType(Enum):
    """DS9's Type menu: how much of the grid is drawn.

    Analysis draws the lot -- a graticule across the image, for finding
    things. Publication draws a border with ticks and numbers and no lines
    over the data, for a figure.
    """

    ANALYSIS = "analysis"
    PUBLICATION = "publication"


class Placement(Enum):
    """Whether axes or numerics go inside the image or outside it."""

    INTERIOR = "interior"
    EXTERIOR = "exterior"


@dataclass
class GridElement:
    """One part of the grid, and how it is drawn.

    Attributes:
        show: Whether it is drawn.
        color: One of `COLORS`.
        width: Line width, for the line elements.
        style: solid, dashed or dotted, likewise.
        font, font_size, font_weight, font_slant: for the text elements.
    """

    show: bool = True
    color: str = "cyan"
    width: int = 1
    style: str = "solid"
    font: str = "helvetica"
    font_size: int = 10
    font_weight: str = "normal"
    font_slant: str = "roman"

    def to_dict(self) -> dict[str, Any]:
        """The element as plain data."""
        return {
            "show": self.show,
            "color": self.color,
            "width": self.width,
            "style": self.style,
            "font": self.font,
            "font_size": self.font_size,
            "font_weight": self.font_weight,
            "font_slant": self.font_slant,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> GridElement:
        """Read an element back, keeping the defaults for anything absent."""
        blank = cls()
        return cls(
            show=bool(data.get("show", blank.show)),
            color=str(data.get("color", blank.color)),
            width=int(data.get("width", blank.width)),
            style=str(data.get("style", blank.style)),
            font=str(data.get("font", blank.font)),
            font_size=int(data.get("font_size", blank.font_size)),
            font_weight=str(data.get("font_weight", blank.font_weight)),
            font_slant=str(data.get("font_slant", blank.font_slant)),
        )


def _default_elements() -> dict[str, GridElement]:
    """One element per name, with DS9's own defaults.

    The grid lines are dashed and the rest solid, which is DS9's look: a
    solid graticule over an image competes with the data.
    """
    made = {name: GridElement() for name in ELEMENTS}
    made["grid"].style = "dashed"
    made["title"].font_size = 12
    return made


@dataclass
class GridConfig:
    """Everything DS9's Grid Parameters dialog can set.

    Attributes:
        visible: Whether the grid is drawn at all -- the Analysis menu's
            Coordinate Grid toggle, as opposed to each element's own Show.
        grid_type: Analysis or Publication.
        axes_placement, numerics_placement: interior or exterior.
        vertical_text: Turn the y-axis numbers upright.
        system: The coordinate system -- image, physical, or wcs.
        sky: The sky frame, when the system is wcs.
        sky_format: sexagesimal or degrees.
        elements: The seven elements, by name.
        title, x_title, y_title: The three titles. Empty means "derive one
            from the coordinate system", which is what DS9 shows.
        x_format, y_format: DS9's numeric format strings, e.g. `hms.1`.
            Empty means the default for the system.
        auto_spacing: Choose the interval from the image, as DS9 does.
        x_spacing, y_spacing: The interval in degrees when it is not
            automatic.
        target_lines: About how many lines to draw per axis when spacing is
            automatic.
    """

    visible: bool = False
    grid_type: GridType = GridType.ANALYSIS
    axes_placement: Placement = Placement.EXTERIOR
    numerics_placement: Placement = Placement.EXTERIOR
    vertical_text: bool = False

    system: str = "wcs"
    sky: str = "fk5"
    sky_format: str = "sexagesimal"

    elements: dict[str, GridElement] = field(default_factory=_default_elements)

    title: str = ""
    x_title: str = ""
    y_title: str = ""
    x_format: str = ""
    y_format: str = ""

    auto_spacing: bool = True
    x_spacing: float | None = None
    y_spacing: float | None = None
    target_lines: int = 6

    def element(self, name: str) -> GridElement:
        """One element by name.

        Raises:
            KeyError: If there is no such element.
        """
        return self.elements[name]

    def shows(self, name: str) -> bool:
        """Whether one element is drawn, given the grid type.

        Publication turns the grid lines off however their own Show is set:
        that is what makes it a publication grid rather than an analysis
        one, and leaving the lines on would make the choice meaningless.
        """
        if not self.visible:
            return False
        if name == "grid" and self.grid_type is GridType.PUBLICATION:
            return False
        return self.elements[name].show

    def copy(self) -> GridConfig:
        """An independent copy, elements included."""
        return replace(
            self,
            elements={name: replace(element) for name, element in self.elements.items()},
        )

    # -- saving and restoring (M7-13) ----------------------------------------

    def to_dict(self) -> dict[str, Any]:
        """The whole configuration as plain data."""
        return {
            "visible": self.visible,
            "grid_type": self.grid_type.value,
            "axes_placement": self.axes_placement.value,
            "numerics_placement": self.numerics_placement.value,
            "vertical_text": self.vertical_text,
            "system": self.system,
            "sky": self.sky,
            "sky_format": self.sky_format,
            "elements": {name: element.to_dict() for name, element in self.elements.items()},
            "title": self.title,
            "x_title": self.x_title,
            "y_title": self.y_title,
            "x_format": self.x_format,
            "y_format": self.y_format,
            "auto_spacing": self.auto_spacing,
            "x_spacing": self.x_spacing,
            "y_spacing": self.y_spacing,
            "target_lines": self.target_lines,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> GridConfig:
        """Read a configuration back.

        Anything missing keeps its default, so a file written by an earlier
        version still loads rather than being rejected wholesale.
        """
        blank = cls()
        elements = _default_elements()
        for name, entry in (data.get("elements") or {}).items():
            if name in elements:
                elements[name] = GridElement.from_dict(entry)

        return cls(
            visible=bool(data.get("visible", blank.visible)),
            grid_type=GridType(data.get("grid_type", blank.grid_type.value)),
            axes_placement=Placement(data.get("axes_placement", blank.axes_placement.value)),
            numerics_placement=Placement(data.get("numerics_placement", blank.numerics_placement.value)),
            vertical_text=bool(data.get("vertical_text", blank.vertical_text)),
            system=str(data.get("system", blank.system)),
            sky=str(data.get("sky", blank.sky)),
            sky_format=str(data.get("sky_format", blank.sky_format)),
            elements=elements,
            title=str(data.get("title", "")),
            x_title=str(data.get("x_title", "")),
            y_title=str(data.get("y_title", "")),
            x_format=str(data.get("x_format", "")),
            y_format=str(data.get("y_format", "")),
            auto_spacing=bool(data.get("auto_spacing", blank.auto_spacing)),
            x_spacing=data.get("x_spacing"),
            y_spacing=data.get("y_spacing"),
            target_lines=int(data.get("target_lines", blank.target_lines)),
        )

    def save(self, path: str | Path) -> None:
        """Write the configuration to a file, DS9's Save.

        Raises:
            OSError: If it cannot be written.
        """
        Path(path).write_text(json.dumps(self.to_dict(), indent=2))

    @classmethod
    def load(cls, path: str | Path) -> GridConfig:
        """Read a configuration back, DS9's Load.

        Raises:
            ValueError: If the file is not a saved grid configuration.
            OSError: If it cannot be read.
        """
        data = json.loads(Path(path).read_text())
        if not isinstance(data, dict) or "elements" not in data:
            raise ValueError("not a saved grid configuration")
        return cls.from_dict(data)
