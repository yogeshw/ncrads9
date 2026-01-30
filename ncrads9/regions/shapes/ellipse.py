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
Ellipse region shape.

Author: Yogesh Wadadekar
"""

import math
from typing import Any, Optional

from ..base_region import BaseRegion


class Ellipse(BaseRegion):
    """An elliptical region defined by center, semi-axes, and angle."""

    def __init__(
        self,
        center: tuple[float, float],
        semi_major: float,
        semi_minor: float,
        angle: float = 0.0,
        color: str = "green",
        width: int = 1,
        font: str = "helvetica 10 normal roman",
        text: str = "",
        tags: Optional[list[str]] = None,
    ) -> None:
        """
        Initialize an ellipse region.

        Args:
            center: The (x, y) center coordinates.
            semi_major: The semi-major axis length.
            semi_minor: The semi-minor axis length.
            angle: The rotation angle in degrees.
            color: The color of the region outline.
            width: The line width of the region outline.
            font: The font specification for text labels.
            text: The text label for the region.
            tags: Optional list of tags for grouping regions.
        """
        super().__init__(center, color, width, font, text, tags)
        self._semi_major = semi_major
        self._semi_minor = semi_minor
        self._angle = angle

    @property
    def semi_major(self) -> float:
        """Get the semi-major axis length."""
        return self._semi_major

    @semi_major.setter
    def semi_major(self, value: float) -> None:
        """Set the semi-major axis length."""
        self._semi_major = value

    @property
    def semi_minor(self) -> float:
        """Get the semi-minor axis length."""
        return self._semi_minor

    @semi_minor.setter
    def semi_minor(self, value: float) -> None:
        """Set the semi-minor axis length."""
        self._semi_minor = value

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
        Draw the ellipse on the given context.

        Args:
            context: The drawing context.
        """
        pass

    def contains(self, x: float, y: float) -> bool:
        """
        Check if a point is contained within the ellipse.

        Args:
            x: The x coordinate of the point.
            y: The y coordinate of the point.

        Returns:
            True if the point is inside the ellipse.
        """
        cx, cy = self.center
        dx = x - cx
        dy = y - cy
        rad = math.radians(self._angle)
        cos_a = math.cos(rad)
        sin_a = math.sin(rad)
        rx = dx * cos_a + dy * sin_a
        ry = -dx * sin_a + dy * cos_a
        return (rx / self._semi_major) ** 2 + (ry / self._semi_minor) ** 2 <= 1

    def move(self, dx: float, dy: float) -> None:
        """
        Move the ellipse by the given offset.

        Args:
            dx: The offset in the x direction.
            dy: The offset in the y direction.
        """
        cx, cy = self.center
        self.center = (cx + dx, cy + dy)

    def resize(self, scale_x: float, scale_y: float) -> None:
        """
        Resize the ellipse by the given scale factors.

        Args:
            scale_x: The scale factor in the x direction.
            scale_y: The scale factor in the y direction.
        """
        self._semi_major *= scale_x
        self._semi_minor *= scale_y

    def to_ds9_string(self) -> str:
        """
        Convert the ellipse to a DS9 format string.

        Returns:
            The ellipse as a DS9 format string.
        """
        cx, cy = self.center
        return f"ellipse({cx},{cy},{self._semi_major},{self._semi_minor},{self._angle})"

    def __repr__(self) -> str:
        """Return a string representation of the ellipse."""
        return (
            f"Ellipse(center={self.center}, semi_major={self._semi_major}, "
            f"semi_minor={self._semi_minor}, angle={self._angle})"
        )
