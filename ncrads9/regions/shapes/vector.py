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
Vector region shape.

Author: Yogesh Wadadekar
"""

import math
from typing import Any, Optional

from ..base_region import BaseRegion


class Vector(BaseRegion):
    """A vector region defined by start point, length, and angle."""

    def __init__(
        self,
        start: tuple[float, float],
        length: float,
        angle: float,
        arrow: bool = True,
        color: str = "green",
        width: int = 1,
        font: str = "helvetica 10 normal roman",
        text: str = "",
        tags: Optional[list[str]] = None,
    ) -> None:
        """
        Initialize a vector region.

        Args:
            start: The (x, y) coordinates of the start point.
            length: The length of the vector.
            angle: The angle in degrees (0 = right, 90 = up).
            arrow: Whether to display an arrowhead.
            color: The color of the region outline.
            width: The line width of the region outline.
            font: The font specification for text labels.
            text: The text label for the region.
            tags: Optional list of tags for grouping regions.
        """
        super().__init__(start, color, width, font, text, tags)
        self._start = start
        self._length = length
        self._angle = angle
        self._arrow = arrow

    @property
    def start(self) -> tuple[float, float]:
        """Get the start point coordinates."""
        return self._start

    @start.setter
    def start(self, value: tuple[float, float]) -> None:
        """Set the start point coordinates."""
        self._start = value
        self._center = value

    @property
    def length(self) -> float:
        """Get the vector length."""
        return self._length

    @length.setter
    def length(self, value: float) -> None:
        """Set the vector length."""
        self._length = value

    @property
    def angle(self) -> float:
        """Get the vector angle in degrees."""
        return self._angle

    @angle.setter
    def angle(self, value: float) -> None:
        """Set the vector angle in degrees."""
        self._angle = value

    @property
    def arrow(self) -> bool:
        """Get whether arrowhead is displayed."""
        return self._arrow

    @arrow.setter
    def arrow(self, value: bool) -> None:
        """Set whether arrowhead is displayed."""
        self._arrow = value

    def get_end(self) -> tuple[float, float]:
        """Calculate the end point of the vector."""
        rad = math.radians(self._angle)
        end_x = self._start[0] + self._length * math.cos(rad)
        end_y = self._start[1] + self._length * math.sin(rad)
        return (end_x, end_y)

    def draw(self, context: Any) -> None:
        """
        Draw the vector on the given context.

        Args:
            context: The drawing context.
        """
        pass

    def contains(self, x: float, y: float) -> bool:
        """
        Check if a point is near the vector.

        Args:
            x: The x coordinate of the point.
            y: The y coordinate of the point.

        Returns:
            True if the point is within tolerance of the vector.
        """
        x1, y1 = self._start
        x2, y2 = self.get_end()
        length = math.sqrt((x2 - x1) ** 2 + (y2 - y1) ** 2)
        if length == 0:
            return math.sqrt((x - x1) ** 2 + (y - y1) ** 2) <= self.width
        distance = abs((y2 - y1) * x - (x2 - x1) * y + x2 * y1 - y2 * x1) / length
        return distance <= self.width + 2

    def move(self, dx: float, dy: float) -> None:
        """
        Move the vector by the given offset.

        Args:
            dx: The offset in the x direction.
            dy: The offset in the y direction.
        """
        self._start = (self._start[0] + dx, self._start[1] + dy)
        cx, cy = self.center
        self.center = (cx + dx, cy + dy)

    def resize(self, scale_x: float, scale_y: float) -> None:
        """
        Resize the vector by the given scale factors.

        Args:
            scale_x: The scale factor in the x direction.
            scale_y: The scale factor in the y direction.
        """
        scale = (scale_x + scale_y) / 2
        self._length *= scale

    def to_ds9_string(self) -> str:
        """
        Convert the vector to a DS9 format string.

        Returns:
            The vector as a DS9 format string.
        """
        x, y = self._start
        arrow_flag = 1 if self._arrow else 0
        return f"vector({x},{y},{self._length},{self._angle}) # vector={arrow_flag}"

    def __repr__(self) -> str:
        """Return a string representation of the vector."""
        return (
            f"Vector(start={self._start}, length={self._length}, "
            f"angle={self._angle}, arrow={self._arrow})"
        )
