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
Panda (pie + annulus) region shape.

Author: Yogesh Wadadekar
"""

import math
from typing import Any, Optional

from ..base_region import BaseRegion


class Panda(BaseRegion):
    """A panda region combining pie (angular) and annulus (radial) sections."""

    def __init__(
        self,
        center: tuple[float, float],
        start_angle: float,
        stop_angle: float,
        num_angles: int,
        inner_radius: float,
        outer_radius: float,
        num_radii: int,
        color: str = "green",
        width: int = 1,
        font: str = "helvetica 10 normal roman",
        text: str = "",
        tags: Optional[list[str]] = None,
    ) -> None:
        """
        Initialize a panda region.

        Args:
            center: The (x, y) center coordinates.
            start_angle: The starting angle in degrees.
            stop_angle: The stopping angle in degrees.
            num_angles: The number of angular divisions.
            inner_radius: The inner radius.
            outer_radius: The outer radius.
            num_radii: The number of radial divisions.
            color: The color of the region outline.
            width: The line width of the region outline.
            font: The font specification for text labels.
            text: The text label for the region.
            tags: Optional list of tags for grouping regions.
        """
        super().__init__(center, color, width, font, text, tags)
        self._start_angle = start_angle
        self._stop_angle = stop_angle
        self._num_angles = num_angles
        self._inner_radius = inner_radius
        self._outer_radius = outer_radius
        self._num_radii = num_radii

    @property
    def start_angle(self) -> float:
        """Get the starting angle in degrees."""
        return self._start_angle

    @start_angle.setter
    def start_angle(self, value: float) -> None:
        """Set the starting angle in degrees."""
        self._start_angle = value

    @property
    def stop_angle(self) -> float:
        """Get the stopping angle in degrees."""
        return self._stop_angle

    @stop_angle.setter
    def stop_angle(self, value: float) -> None:
        """Set the stopping angle in degrees."""
        self._stop_angle = value

    @property
    def num_angles(self) -> int:
        """Get the number of angular divisions."""
        return self._num_angles

    @num_angles.setter
    def num_angles(self, value: int) -> None:
        """Set the number of angular divisions."""
        self._num_angles = value

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

    @property
    def num_radii(self) -> int:
        """Get the number of radial divisions."""
        return self._num_radii

    @num_radii.setter
    def num_radii(self, value: int) -> None:
        """Set the number of radial divisions."""
        self._num_radii = value

    def draw(self, context: Any) -> None:
        """
        Draw the panda on the given context.

        Args:
            context: The drawing context.
        """
        pass

    def contains(self, x: float, y: float) -> bool:
        """
        Check if a point is contained within the panda region.

        Args:
            x: The x coordinate of the point.
            y: The y coordinate of the point.

        Returns:
            True if the point is inside the panda region.
        """
        cx, cy = self.center
        dx = x - cx
        dy = y - cy
        distance = math.sqrt(dx**2 + dy**2)
        if not (self._inner_radius <= distance <= self._outer_radius):
            return False
        angle = math.degrees(math.atan2(dy, dx)) % 360
        start = self._start_angle % 360
        stop = self._stop_angle % 360
        if start <= stop:
            return start <= angle <= stop
        else:
            return angle >= start or angle <= stop

    def move(self, dx: float, dy: float) -> None:
        """
        Move the panda by the given offset.

        Args:
            dx: The offset in the x direction.
            dy: The offset in the y direction.
        """
        cx, cy = self.center
        self.center = (cx + dx, cy + dy)

    def resize(self, scale_x: float, scale_y: float) -> None:
        """
        Resize the panda by the given scale factors.

        Args:
            scale_x: The scale factor in the x direction.
            scale_y: The scale factor in the y direction.
        """
        scale = (scale_x + scale_y) / 2
        self._inner_radius *= scale
        self._outer_radius *= scale

    def to_ds9_string(self) -> str:
        """
        Convert the panda to a DS9 format string.

        Returns:
            The panda as a DS9 format string.
        """
        cx, cy = self.center
        return (
            f"panda({cx},{cy},{self._start_angle},{self._stop_angle},"
            f"{self._num_angles},{self._inner_radius},{self._outer_radius},"
            f"{self._num_radii})"
        )

    def __repr__(self) -> str:
        """Return a string representation of the panda."""
        return (
            f"Panda(center={self.center}, angles=({self._start_angle},"
            f"{self._stop_angle}), radii=({self._inner_radius},{self._outer_radius}))"
        )
