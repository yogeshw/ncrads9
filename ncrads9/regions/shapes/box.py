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
Box region shape.

Author: Yogesh Wadadekar
"""

import math
from typing import Any, Optional

from ..base_region import BaseRegion


class Box(BaseRegion):
    """A rectangular box region defined by center, dimensions, and angle."""

    def __init__(
        self,
        center: tuple[float, float],
        width_box: float,
        height_box: float,
        angle: float = 0.0,
        color: str = "green",
        width: int = 1,
        font: str = "helvetica 10 normal roman",
        text: str = "",
        tags: Optional[list[str]] = None,
    ) -> None:
        """
        Initialize a box region.

        Args:
            center: The (x, y) center coordinates.
            width_box: The width of the box.
            height_box: The height of the box.
            angle: The rotation angle in degrees.
            color: The color of the region outline.
            width: The line width of the region outline.
            font: The font specification for text labels.
            text: The text label for the region.
            tags: Optional list of tags for grouping regions.
        """
        super().__init__(center, color, width, font, text, tags)
        self._width_box = width_box
        self._height_box = height_box
        self._angle = angle

    @property
    def width_box(self) -> float:
        """Get the width of the box."""
        return self._width_box

    @width_box.setter
    def width_box(self, value: float) -> None:
        """Set the width of the box."""
        self._width_box = value

    @property
    def height_box(self) -> float:
        """Get the height of the box."""
        return self._height_box

    @height_box.setter
    def height_box(self, value: float) -> None:
        """Set the height of the box."""
        self._height_box = value

    @property
    def angle(self) -> float:
        """Get the rotation angle in degrees."""
        return self._angle

    @angle.setter
    def angle(self, value: float) -> None:
        """Set the rotation angle in degrees."""
        self._angle = value

    def draw(self, context: Any) -> None:
        """
        Draw the box on the given context.

        Args:
            context: The drawing context.
        """
        pass

    def contains(self, x: float, y: float) -> bool:
        """
        Check if a point is contained within the box.

        Args:
            x: The x coordinate of the point.
            y: The y coordinate of the point.

        Returns:
            True if the point is inside the box.
        """
        cx, cy = self.center
        dx = x - cx
        dy = y - cy
        rad = math.radians(self._angle)
        cos_a = math.cos(rad)
        sin_a = math.sin(rad)
        rx = dx * cos_a + dy * sin_a
        ry = -dx * sin_a + dy * cos_a
        return abs(rx) <= self._width_box / 2 and abs(ry) <= self._height_box / 2

    def move(self, dx: float, dy: float) -> None:
        """
        Move the box by the given offset.

        Args:
            dx: The offset in the x direction.
            dy: The offset in the y direction.
        """
        cx, cy = self.center
        self.center = (cx + dx, cy + dy)

    def resize(self, scale_x: float, scale_y: float) -> None:
        """
        Resize the box by the given scale factors.

        Args:
            scale_x: The scale factor in the x direction.
            scale_y: The scale factor in the y direction.
        """
        self._width_box *= scale_x
        self._height_box *= scale_y

    def to_ds9_string(self) -> str:
        """
        Convert the box to a DS9 format string.

        Returns:
            The box as a DS9 format string.
        """
        cx, cy = self.center
        return f"box({cx},{cy},{self._width_box},{self._height_box},{self._angle})"

    def __repr__(self) -> str:
        """Return a string representation of the box."""
        return (
            f"Box(center={self.center}, width={self._width_box}, "
            f"height={self._height_box}, angle={self._angle})"
        )
