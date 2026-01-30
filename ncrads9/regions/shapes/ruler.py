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
Ruler region shape.

Author: Yogesh Wadadekar
"""

import math
from typing import Any, Optional

from ..base_region import BaseRegion


class Ruler(BaseRegion):
    """A ruler region for measuring distances."""

    def __init__(
        self,
        start: tuple[float, float],
        end: tuple[float, float],
        color: str = "green",
        width: int = 1,
        font: str = "helvetica 10 normal roman",
        text: str = "",
        tags: Optional[list[str]] = None,
    ) -> None:
        """
        Initialize a ruler region.

        Args:
            start: The (x, y) coordinates of the start point.
            end: The (x, y) coordinates of the end point.
            color: The color of the region outline.
            width: The line width of the region outline.
            font: The font specification for text labels.
            text: The text label for the region.
            tags: Optional list of tags for grouping regions.
        """
        center = ((start[0] + end[0]) / 2, (start[1] + end[1]) / 2)
        super().__init__(center, color, width, font, text, tags)
        self._start = start
        self._end = end

    @property
    def start(self) -> tuple[float, float]:
        """Get the start point coordinates."""
        return self._start

    @start.setter
    def start(self, value: tuple[float, float]) -> None:
        """Set the start point coordinates."""
        self._start = value
        self._update_center()

    @property
    def end(self) -> tuple[float, float]:
        """Get the end point coordinates."""
        return self._end

    @end.setter
    def end(self, value: tuple[float, float]) -> None:
        """Set the end point coordinates."""
        self._end = value
        self._update_center()

    def _update_center(self) -> None:
        """Update center based on endpoints."""
        self._center = (
            (self._start[0] + self._end[0]) / 2,
            (self._start[1] + self._end[1]) / 2,
        )

    def get_length(self) -> float:
        """Calculate the length of the ruler."""
        dx = self._end[0] - self._start[0]
        dy = self._end[1] - self._start[1]
        return math.sqrt(dx**2 + dy**2)

    def draw(self, context: Any) -> None:
        """
        Draw the ruler on the given context.

        Args:
            context: The drawing context.
        """
        pass

    def contains(self, x: float, y: float) -> bool:
        """
        Check if a point is near the ruler.

        Args:
            x: The x coordinate of the point.
            y: The y coordinate of the point.

        Returns:
            True if the point is within tolerance of the ruler.
        """
        x1, y1 = self._start
        x2, y2 = self._end
        length = self.get_length()
        if length == 0:
            return math.sqrt((x - x1) ** 2 + (y - y1) ** 2) <= self.width
        distance = abs((y2 - y1) * x - (x2 - x1) * y + x2 * y1 - y2 * x1) / length
        return distance <= self.width + 2

    def move(self, dx: float, dy: float) -> None:
        """
        Move the ruler by the given offset.

        Args:
            dx: The offset in the x direction.
            dy: The offset in the y direction.
        """
        self._start = (self._start[0] + dx, self._start[1] + dy)
        self._end = (self._end[0] + dx, self._end[1] + dy)
        self._update_center()

    def resize(self, scale_x: float, scale_y: float) -> None:
        """
        Resize the ruler by the given scale factors from the center.

        Args:
            scale_x: The scale factor in the x direction.
            scale_y: The scale factor in the y direction.
        """
        cx, cy = self.center
        self._start = (
            cx + (self._start[0] - cx) * scale_x,
            cy + (self._start[1] - cy) * scale_y,
        )
        self._end = (
            cx + (self._end[0] - cx) * scale_x,
            cy + (self._end[1] - cy) * scale_y,
        )

    def to_ds9_string(self) -> str:
        """
        Convert the ruler to a DS9 format string.

        Returns:
            The ruler as a DS9 format string.
        """
        x1, y1 = self._start
        x2, y2 = self._end
        return f"ruler({x1},{y1},{x2},{y2})"

    def __repr__(self) -> str:
        """Return a string representation of the ruler."""
        return f"Ruler(start={self._start}, end={self._end}, length={self.get_length():.2f})"
