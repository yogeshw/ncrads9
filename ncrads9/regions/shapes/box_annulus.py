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
Box annulus region shape.

Author: Yogesh Wadadekar
"""

import math
from typing import Any, Optional

from ..base_region import BaseRegion


class BoxAnnulus(BaseRegion):
    """A box annulus region with inner and outer rectangles."""

    def __init__(
        self,
        center: tuple[float, float],
        inner_width: float,
        inner_height: float,
        outer_width: float,
        outer_height: float,
        angle: float = 0.0,
        color: str = "green",
        width: int = 1,
        font: str = "helvetica 10 normal roman",
        text: str = "",
        tags: Optional[list[str]] = None,
    ) -> None:
        """
        Initialize a box annulus region.

        Args:
            center: The (x, y) center coordinates.
            inner_width: The inner box width.
            inner_height: The inner box height.
            outer_width: The outer box width.
            outer_height: The outer box height.
            angle: The rotation angle in degrees.
            color: The color of the region outline.
            width: The line width of the region outline.
            font: The font specification for text labels.
            text: The text label for the region.
            tags: Optional list of tags for grouping regions.
        """
        super().__init__(center, color, width, font, text, tags)
        self._inner_width = inner_width
        self._inner_height = inner_height
        self._outer_width = outer_width
        self._outer_height = outer_height
        self._angle = angle

    @property
    def inner_width(self) -> float:
        """Get the inner box width."""
        return self._inner_width

    @inner_width.setter
    def inner_width(self, value: float) -> None:
        """Set the inner box width."""
        self._inner_width = value

    @property
    def inner_height(self) -> float:
        """Get the inner box height."""
        return self._inner_height

    @inner_height.setter
    def inner_height(self, value: float) -> None:
        """Set the inner box height."""
        self._inner_height = value

    @property
    def outer_width(self) -> float:
        """Get the outer box width."""
        return self._outer_width

    @outer_width.setter
    def outer_width(self, value: float) -> None:
        """Set the outer box width."""
        self._outer_width = value

    @property
    def outer_height(self) -> float:
        """Get the outer box height."""
        return self._outer_height

    @outer_height.setter
    def outer_height(self, value: float) -> None:
        """Set the outer box height."""
        self._outer_height = value

    @property
    def angle(self) -> float:
        """Get the rotation angle in degrees."""
        return self._angle

    @angle.setter
    def angle(self, value: float) -> None:
        """Set the rotation angle in degrees."""
        self._angle = value

    def _box_contains(
        self, x: float, y: float, box_width: float, box_height: float
    ) -> bool:
        """Check if point is inside a box with given dimensions."""
        cx, cy = self.center
        dx = x - cx
        dy = y - cy
        rad = math.radians(self._angle)
        cos_a = math.cos(rad)
        sin_a = math.sin(rad)
        rx = dx * cos_a + dy * sin_a
        ry = -dx * sin_a + dy * cos_a
        return abs(rx) <= box_width / 2 and abs(ry) <= box_height / 2

    def draw(self, context: Any) -> None:
        """
        Draw the box annulus on the given context.

        Args:
            context: The drawing context.
        """
        pass

    def contains(self, x: float, y: float) -> bool:
        """
        Check if a point is contained within the box annulus.

        Args:
            x: The x coordinate of the point.
            y: The y coordinate of the point.

        Returns:
            True if the point is between inner and outer boxes.
        """
        in_outer = self._box_contains(x, y, self._outer_width, self._outer_height)
        in_inner = self._box_contains(x, y, self._inner_width, self._inner_height)
        return in_outer and not in_inner

    def move(self, dx: float, dy: float) -> None:
        """
        Move the box annulus by the given offset.

        Args:
            dx: The offset in the x direction.
            dy: The offset in the y direction.
        """
        cx, cy = self.center
        self.center = (cx + dx, cy + dy)

    def resize(self, scale_x: float, scale_y: float) -> None:
        """
        Resize the box annulus by the given scale factors.

        Args:
            scale_x: The scale factor in the x direction.
            scale_y: The scale factor in the y direction.
        """
        self._inner_width *= scale_x
        self._inner_height *= scale_y
        self._outer_width *= scale_x
        self._outer_height *= scale_y

    def to_ds9_string(self) -> str:
        """
        Convert the box annulus to a DS9 format string.

        Returns:
            The box annulus as a DS9 format string.
        """
        cx, cy = self.center
        return (
            f"box({cx},{cy},{self._inner_width},{self._inner_height},"
            f"{self._outer_width},{self._outer_height},{self._angle})"
        )

    def __repr__(self) -> str:
        """Return a string representation of the box annulus."""
        return (
            f"BoxAnnulus(center={self.center}, "
            f"inner=({self._inner_width},{self._inner_height}), "
            f"outer=({self._outer_width},{self._outer_height}))"
        )
