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
Annulus (circular ring) region shape.

Author: Yogesh Wadadekar
"""

import math
from typing import Any, Optional

from ..base_region import BaseRegion


class Annulus(BaseRegion):
    """A circular annulus region defined by center and inner/outer radii."""

    def __init__(
        self,
        center: tuple[float, float],
        inner_radius: float,
        outer_radius: float,
        color: str = "green",
        width: int = 1,
        font: str = "helvetica 10 normal roman",
        text: str = "",
        tags: Optional[list[str]] = None,
    ) -> None:
        """
        Initialize an annulus region.

        Args:
            center: The (x, y) center coordinates.
            inner_radius: The inner radius of the annulus.
            outer_radius: The outer radius of the annulus.
            color: The color of the region outline.
            width: The line width of the region outline.
            font: The font specification for text labels.
            text: The text label for the region.
            tags: Optional list of tags for grouping regions.
        """
        super().__init__(center, color, width, font, text, tags)
        self._inner_radius = inner_radius
        self._outer_radius = outer_radius

    @property
    def inner_radius(self) -> float:
        """Get the inner radius."""
        return self._inner_radius

    @inner_radius.setter
    def inner_radius(self, value: float) -> None:
        """Set the inner radius."""
        self._inner_radius = value

    @property
    def outer_radius(self) -> float:
        """Get the outer radius."""
        return self._outer_radius

    @outer_radius.setter
    def outer_radius(self, value: float) -> None:
        """Set the outer radius."""
        self._outer_radius = value

    def draw(self, context: Any) -> None:
        """
        Draw the annulus on the given context.

        Args:
            context: The drawing context.
        """
        pass

    def contains(self, x: float, y: float) -> bool:
        """
        Check if a point is contained within the annulus.

        Args:
            x: The x coordinate of the point.
            y: The y coordinate of the point.

        Returns:
            True if the point is inside the annulus (between inner and outer).
        """
        cx, cy = self.center
        distance = math.sqrt((x - cx) ** 2 + (y - cy) ** 2)
        return self._inner_radius <= distance <= self._outer_radius

    def move(self, dx: float, dy: float) -> None:
        """
        Move the annulus by the given offset.

        Args:
            dx: The offset in the x direction.
            dy: The offset in the y direction.
        """
        cx, cy = self.center
        self.center = (cx + dx, cy + dy)

    def resize(self, scale_x: float, scale_y: float) -> None:
        """
        Resize the annulus by the given scale factors.

        Args:
            scale_x: The scale factor in the x direction.
            scale_y: The scale factor in the y direction.
        """
        scale = (scale_x + scale_y) / 2
        self._inner_radius *= scale
        self._outer_radius *= scale

    def to_ds9_string(self) -> str:
        """
        Convert the annulus to a DS9 format string.

        Returns:
            The annulus as a DS9 format string.
        """
        cx, cy = self.center
        return f"annulus({cx},{cy},{self._inner_radius},{self._outer_radius})"

    def __repr__(self) -> str:
        """Return a string representation of the annulus."""
        return (
            f"Annulus(center={self.center}, inner_radius={self._inner_radius}, "
            f"outer_radius={self._outer_radius})"
        )
