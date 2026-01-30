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
from typing import Any, Optional


class BaseRegion(ABC):
    """Abstract base class for all region shapes."""

    def __init__(
        self,
        center: tuple[float, float],
        color: str = "green",
        width: int = 1,
        font: str = "helvetica 10 normal roman",
        text: str = "",
        tags: Optional[list[str]] = None,
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
        """
        self._center = center
        self._color = color
        self._width = width
        self._font = font
        self._text = text
        self._tags = tags if tags is not None else []

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

    @abstractmethod
    def draw(self, context: Any) -> None:
        """
        Draw the region on the given context.

        Args:
            context: The drawing context (e.g., QPainter).
        """
        pass

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
        pass

    @abstractmethod
    def move(self, dx: float, dy: float) -> None:
        """
        Move the region by the given offset.

        Args:
            dx: The offset in the x direction.
            dy: The offset in the y direction.
        """
        pass

    @abstractmethod
    def resize(self, scale_x: float, scale_y: float) -> None:
        """
        Resize the region by the given scale factors.

        Args:
            scale_x: The scale factor in the x direction.
            scale_y: The scale factor in the y direction.
        """
        pass

    @abstractmethod
    def to_ds9_string(self) -> str:
        """
        Convert the region to a DS9 format string.

        Returns:
            The region as a DS9 format string.
        """
        pass

    def __repr__(self) -> str:
        """Return a string representation of the region."""
        return (
            f"{self.__class__.__name__}(center={self.center}, "
            f"color={self.color!r}, width={self.width})"
        )
