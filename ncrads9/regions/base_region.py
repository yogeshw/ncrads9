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
Base region abstract class for all region shapes.

Author: Yogesh Wadadekar
"""

from abc import ABC, abstractmethod
from typing import Any


class BaseRegion(ABC):
    """Abstract base class for all region shapes."""

    def __init__(
        self,
        center: tuple[float, float],
        color: str = "green",
        width: int = 1,
        font: str = "helvetica 10 normal roman",
        text: str = "",
        tags: list[str] | None = None,
        *,
        include: bool = True,
        source: bool = True,
        fixed: bool = False,
        can_edit: bool = True,
        can_move: bool = True,
        can_rotate: bool = True,
        can_delete: bool = True,
        dash: bool = False,
        fill: bool = False,
        origin: str = "user",
    ) -> None:
        """
        Initialize a base region.

        Args:
            center: The (x, y) center coordinates of the region.
            color: The color of the region outline.
            width: The line width of the region outline.
            font: The font specification for text labels.
            text: The text label for the region.
            tags: Optional list of tags for grouping regions.
            include: False for an excluded region, written with a `-` prefix.
            source: True for `source=1`, False for `background=1`.
            fixed: `fixed=1` -- the region keeps its screen size when zooming.
            can_edit: `edit=0` when False.
            can_move: `move=0` when False.
            can_rotate: `rotate=0` when False.
            can_delete: `delete=0` when False.
            dash: `dash=1` -- draw the outline dashed.
            fill: `fill=1` -- fill the shape.
            origin: Provenance tag -- "user" for regions the user drew,
                "samp_catalog" for markers pushed in over SAMP, and so on.
                Not part of the DS9 file format; it lets the application find
                and replace the regions it generated itself. Distinct from
                `source`, which is DS9's source/background property.

        The property flags mirror DS9's region properties (see the Region
        Properties section of ds9/doc/ref/region.html). They are keyword-only:
        every shape subclass forwards **kwargs here, so adding a property does
        not disturb the positional geometry arguments each shape defines.

        `can_move`, `can_edit`, `can_rotate` and `can_delete` are spelled with
        the `can_` prefix because `move` is already a method on this class;
        they serialize to DS9's bare `move=`, `edit=`, `rotate=`, `delete=`.
        """
        self._center = center
        self._color = color
        self._width = width
        self._font = font
        self._text = text
        self._tags = tags if tags is not None else []

        self.include = include
        self.source = source
        self.fixed = fixed
        self.can_edit = can_edit
        self.can_move = can_move
        self.can_rotate = can_rotate
        self.can_delete = can_delete
        self.dash = dash
        self.fill = fill
        self.origin = origin

        #: Runtime selection state. Not part of the DS9 file format.
        self.selected = False

    @property
    def center(self) -> tuple[float, float]:
        """Get the center coordinates of the region."""
        return self._center

    @center.setter
    def center(self, value: tuple[float, float]) -> None:
        """Set the center coordinates of the region."""
        self._center = value

    @property
    def color(self) -> str:
        """Get the color of the region."""
        return self._color

    @color.setter
    def color(self, value: str) -> None:
        """Set the color of the region."""
        self._color = value

    @property
    def width(self) -> int:
        """Get the line width of the region."""
        return self._width

    @width.setter
    def width(self, value: int) -> None:
        """Set the line width of the region."""
        self._width = value

    @property
    def font(self) -> str:
        """Get the font specification."""
        return self._font

    @font.setter
    def font(self, value: str) -> None:
        """Set the font specification."""
        self._font = value

    @property
    def text(self) -> str:
        """Get the text label."""
        return self._text

    @text.setter
    def text(self, value: str) -> None:
        """Set the text label."""
        self._text = value

    @property
    def tags(self) -> list[str]:
        """Get the tags for this region."""
        return self._tags

    @tags.setter
    def tags(self, value: list[str]) -> None:
        """Set the tags for this region."""
        self._tags = value

    #: DS9 property keyword -> (attribute, value that is the DS9 default).
    #: Only non-default values are written, matching DS9's own output.
    _DS9_PROPERTY_DEFAULTS: tuple[tuple[str, str, bool], ...] = (
        ("fixed", "fixed", False),
        ("edit", "can_edit", True),
        ("move", "can_move", True),
        ("rotate", "can_rotate", True),
        ("delete", "can_delete", True),
        ("dash", "dash", False),
        ("fill", "fill", False),
    )

    def ds9_properties(self) -> list[str]:
        """Return the non-default DS9 property tokens for this region.

        `source`/`background` is emitted only when the region is a background
        region, since `source=1` is DS9's default. `include` is not emitted as
        a property at all -- exclusion is the `-` prefix on the shape line.
        """
        props = [
            f"{keyword}={int(getattr(self, attribute))}"
            for keyword, attribute, default in self._DS9_PROPERTY_DEFAULTS
            if getattr(self, attribute) != default
        ]
        if not self.source:
            props.append("background")
        return props

    @property
    def prefix(self) -> str:
        """Return the DS9 shape-line prefix: `-` for an excluded region."""
        return "" if self.include else "-"

    @abstractmethod
    def draw(self, context: Any) -> None:
        """
        Draw the region on the given context.

        Args:
            context: The drawing context (e.g., QPainter).
        """

    @abstractmethod
    def contains(self, x: float, y: float) -> bool:
        """
        Check if a point is contained within the region.

        Args:
            x: The x coordinate of the point.
            y: The y coordinate of the point.

        Returns:
            True if the point is inside the region, False otherwise.
        """

    @abstractmethod
    def move(self, dx: float, dy: float) -> None:
        """
        Move the region by the given offset.

        Args:
            dx: The offset in the x direction.
            dy: The offset in the y direction.
        """

    @abstractmethod
    def resize(self, scale_x: float, scale_y: float) -> None:
        """
        Resize the region by the given scale factors.

        Args:
            scale_x: The scale factor in the x direction.
            scale_y: The scale factor in the y direction.
        """

    @abstractmethod
    def to_ds9_string(self) -> str:
        """
        Convert the region to a DS9 format string.

        Returns:
            The region as a DS9 format string.
        """

    def __repr__(self) -> str:
        """Return a string representation of the region."""
        return (
            f"{self.__class__.__name__}(center={self.center}, " f"color={self.color!r}, width={self.width})"
        )
