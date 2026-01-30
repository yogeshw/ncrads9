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
Compass region shape.

Author: Yogesh Wadadekar
"""

from typing import Any, Optional

from ..base_region import BaseRegion


class Compass(BaseRegion):
    """A compass region showing N/E directional arrows."""

    def __init__(
        self,
        center: tuple[float, float],
        length: float,
        north_angle: float = 90.0,
        east_angle: float = 0.0,
        color: str = "green",
        width: int = 1,
        font: str = "helvetica 10 normal roman",
        text: str = "",
        tags: Optional[list[str]] = None,
    ) -> None:
        """
        Initialize a compass region.

        Args:
            center: The (x, y) center coordinates.
            length: The length of the compass arrows.
            north_angle: The angle of north in degrees.
            east_angle: The angle of east in degrees.
            color: The color of the region outline.
            width: The line width of the region outline.
            font: The font specification for text labels.
            text: The text label for the region.
            tags: Optional list of tags for grouping regions.
        """
        super().__init__(center, color, width, font, text, tags)
        self._length = length
        self._north_angle = north_angle
        self._east_angle = east_angle

    @property
    def length(self) -> float:
        """Get the compass arrow length."""
        return self._length

    @length.setter
    def length(self, value: float) -> None:
        """Set the compass arrow length."""
        self._length = value

    @property
    def north_angle(self) -> float:
        """Get the north angle in degrees."""
        return self._north_angle

    @north_angle.setter
    def north_angle(self, value: float) -> None:
        """Set the north angle in degrees."""
        self._north_angle = value

    @property
    def east_angle(self) -> float:
        """Get the east angle in degrees."""
        return self._east_angle

    @east_angle.setter
    def east_angle(self, value: float) -> None:
        """Set the east angle in degrees."""
        self._east_angle = value

    def draw(self, context: Any) -> None:
        """
        Draw the compass on the given context.

        Args:
            context: The drawing context.
        """
        pass

    def contains(self, x: float, y: float) -> bool:
        """
        Check if a point is near the compass.

        Args:
            x: The x coordinate of the point.
            y: The y coordinate of the point.

        Returns:
            True if the point is within the compass area.
        """
        cx, cy = self.center
        distance = ((x - cx) ** 2 + (y - cy) ** 2) ** 0.5
        return distance <= self._length

    def move(self, dx: float, dy: float) -> None:
        """
        Move the compass by the given offset.

        Args:
            dx: The offset in the x direction.
            dy: The offset in the y direction.
        """
        cx, cy = self.center
        self.center = (cx + dx, cy + dy)

    def resize(self, scale_x: float, scale_y: float) -> None:
        """
        Resize the compass by the given scale factors.

        Args:
            scale_x: The scale factor in the x direction.
            scale_y: The scale factor in the y direction.
        """
        scale = (scale_x + scale_y) / 2
        self._length *= scale

    def to_ds9_string(self) -> str:
        """
        Convert the compass to a DS9 format string.

        Returns:
            The compass as a DS9 format string.
        """
        cx, cy = self.center
        return f"compass({cx},{cy},{self._length})"

    def __repr__(self) -> str:
        """Return a string representation of the compass."""
        return (
            f"Compass(center={self.center}, length={self._length}, "
            f"north={self._north_angle}, east={self._east_angle})"
        )
