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
Point region shape.

Author: Yogesh Wadadekar
"""

from typing import Any, Optional

from ..base_region import BaseRegion


class Point(BaseRegion):
    """A point region marking a single location."""

    # Point shape types supported by DS9
    SHAPES = ("circle", "box", "diamond", "cross", "x", "arrow", "boxcircle")

    def __init__(
        self,
        center: tuple[float, float],
        shape: str = "circle",
        size: int = 11,
        color: str = "green",
        width: int = 1,
        font: str = "helvetica 10 normal roman",
        text: str = "",
        tags: Optional[list[str]] = None,
    ) -> None:
        """
        Initialize a point region.

        Args:
            center: The (x, y) coordinates of the point.
            shape: The shape of the point marker.
            size: The size of the point marker.
            color: The color of the region outline.
            width: The line width of the region outline.
            font: The font specification for text labels.
            text: The text label for the region.
            tags: Optional list of tags for grouping regions.
        """
        super().__init__(center, color, width, font, text, tags)
        self._shape = shape
        self._size = size

    @property
    def shape(self) -> str:
        """Get the point shape type."""
        return self._shape

    @shape.setter
    def shape(self, value: str) -> None:
        """Set the point shape type."""
        self._shape = value

    @property
    def size(self) -> int:
        """Get the point marker size."""
        return self._size

    @size.setter
    def size(self, value: int) -> None:
        """Set the point marker size."""
        self._size = value

    def draw(self, context: Any) -> None:
        """
        Draw the point on the given context.

        Args:
            context: The drawing context.
        """
        pass

    def contains(self, x: float, y: float) -> bool:
        """
        Check if a point is near this point marker.

        Args:
            x: The x coordinate of the point.
            y: The y coordinate of the point.

        Returns:
            True if within the point marker's clickable area.
        """
        cx, cy = self.center
        tolerance = self._size / 2
        return abs(x - cx) <= tolerance and abs(y - cy) <= tolerance

    def move(self, dx: float, dy: float) -> None:
        """
        Move the point by the given offset.

        Args:
            dx: The offset in the x direction.
            dy: The offset in the y direction.
        """
        cx, cy = self.center
        self.center = (cx + dx, cy + dy)

    def resize(self, scale_x: float, scale_y: float) -> None:
        """
        Resize the point marker by the given scale factors.

        Args:
            scale_x: The scale factor in the x direction.
            scale_y: The scale factor in the y direction.
        """
        scale = (scale_x + scale_y) / 2
        self._size = int(self._size * scale)

    def to_ds9_string(self) -> str:
        """
        Convert the point to a DS9 format string.

        Returns:
            The point as a DS9 format string.
        """
        cx, cy = self.center
        return f"point({cx},{cy}) # point={self._shape} {self._size}"

    def __repr__(self) -> str:
        """Return a string representation of the point."""
        return f"Point(center={self.center}, shape={self._shape!r}, size={self._size})"
