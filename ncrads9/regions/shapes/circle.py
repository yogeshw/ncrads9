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
Circle region shape.

Author: Yogesh Wadadekar
"""

import math
from typing import Any, Optional

from ..base_region import BaseRegion


class Circle(BaseRegion):
    """A circular region defined by center and radius."""

    def __init__(
        self,
        center: tuple[float, float],
        radius: float,
        color: str = "green",
        width: int = 1,
        font: str = "helvetica 10 normal roman",
        text: str = "",
        tags: Optional[list[str]] = None,
    ) -> None:
        """
        Initialize a circle region.

        Args:
            center: The (x, y) center coordinates.
            radius: The radius of the circle.
            color: The color of the region outline.
            width: The line width of the region outline.
            font: The font specification for text labels.
            text: The text label for the region.
            tags: Optional list of tags for grouping regions.
        """
        super().__init__(center, color, width, font, text, tags)
        self._radius = radius

    @property
    def radius(self) -> float:
        """Get the radius of the circle."""
        return self._radius

    @radius.setter
    def radius(self, value: float) -> None:
        """Set the radius of the circle."""
        self._radius = value

    def draw(self, context: Any) -> None:
        """
        Draw the circle on the given context.

        Args:
            context: The drawing context.
        """
        pass

    def contains(self, x: float, y: float) -> bool:
        """
        Check if a point is contained within the circle.

        Args:
            x: The x coordinate of the point.
            y: The y coordinate of the point.

        Returns:
            True if the point is inside the circle.
        """
        cx, cy = self.center
        distance = math.sqrt((x - cx) ** 2 + (y - cy) ** 2)
        return distance <= self._radius

    def move(self, dx: float, dy: float) -> None:
        """
        Move the circle by the given offset.

        Args:
            dx: The offset in the x direction.
            dy: The offset in the y direction.
        """
        cx, cy = self.center
        self.center = (cx + dx, cy + dy)

    def resize(self, scale_x: float, scale_y: float) -> None:
        """
        Resize the circle by the given scale factors.

        Args:
            scale_x: The scale factor in the x direction.
            scale_y: The scale factor in the y direction.
        """
        scale = (scale_x + scale_y) / 2
        self._radius *= scale

    def to_ds9_string(self) -> str:
        """
        Convert the circle to a DS9 format string.

        Returns:
            The circle as a DS9 format string.
        """
        cx, cy = self.center
        return f"circle({cx},{cy},{self._radius})"

    def __repr__(self) -> str:
        """Return a string representation of the circle."""
        return (
            f"Circle(center={self.center}, radius={self._radius}, "
            f"color={self.color!r})"
        )
