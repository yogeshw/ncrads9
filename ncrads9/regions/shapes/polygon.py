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
Polygon region shape.

Author: Yogesh Wadadekar
"""

from typing import Any, Optional

from ..base_region import BaseRegion


class Polygon(BaseRegion):
    """A polygon region defined by a list of vertices."""

    def __init__(
        self,
        vertices: list[tuple[float, float]],
        color: str = "green",
        width: int = 1,
        font: str = "helvetica 10 normal roman",
        text: str = "",
        tags: Optional[list[str]] = None,
    ) -> None:
        """
        Initialize a polygon region.

        Args:
            vertices: List of (x, y) vertex coordinates.
            color: The color of the region outline.
            width: The line width of the region outline.
            font: The font specification for text labels.
            text: The text label for the region.
            tags: Optional list of tags for grouping regions.
        """
        center = self._compute_centroid(vertices)
        super().__init__(center, color, width, font, text, tags)
        self._vertices = vertices

    @staticmethod
    def _compute_centroid(
        vertices: list[tuple[float, float]]
    ) -> tuple[float, float]:
        """Compute the centroid of the polygon vertices."""
        if not vertices:
            return (0.0, 0.0)
        x_sum = sum(v[0] for v in vertices)
        y_sum = sum(v[1] for v in vertices)
        n = len(vertices)
        return (x_sum / n, y_sum / n)

    @property
    def vertices(self) -> list[tuple[float, float]]:
        """Get the list of vertices."""
        return self._vertices

    @vertices.setter
    def vertices(self, value: list[tuple[float, float]]) -> None:
        """Set the list of vertices."""
        self._vertices = value
        self._center = self._compute_centroid(value)

    def draw(self, context: Any) -> None:
        """
        Draw the polygon on the given context.

        Args:
            context: The drawing context.
        """
        pass

    def contains(self, x: float, y: float) -> bool:
        """
        Check if a point is contained within the polygon using ray casting.

        Args:
            x: The x coordinate of the point.
            y: The y coordinate of the point.

        Returns:
            True if the point is inside the polygon.
        """
        n = len(self._vertices)
        inside = False
        j = n - 1
        for i in range(n):
            xi, yi = self._vertices[i]
            xj, yj = self._vertices[j]
            if ((yi > y) != (yj > y)) and (
                x < (xj - xi) * (y - yi) / (yj - yi) + xi
            ):
                inside = not inside
            j = i
        return inside

    def move(self, dx: float, dy: float) -> None:
        """
        Move the polygon by the given offset.

        Args:
            dx: The offset in the x direction.
            dy: The offset in the y direction.
        """
        self._vertices = [(vx + dx, vy + dy) for vx, vy in self._vertices]
        cx, cy = self.center
        self.center = (cx + dx, cy + dy)

    def resize(self, scale_x: float, scale_y: float) -> None:
        """
        Resize the polygon by the given scale factors around the centroid.

        Args:
            scale_x: The scale factor in the x direction.
            scale_y: The scale factor in the y direction.
        """
        cx, cy = self.center
        self._vertices = [
            (cx + (vx - cx) * scale_x, cy + (vy - cy) * scale_y)
            for vx, vy in self._vertices
        ]

    def to_ds9_string(self) -> str:
        """
        Convert the polygon to a DS9 format string.

        Returns:
            The polygon as a DS9 format string.
        """
        coords = ",".join(f"{vx},{vy}" for vx, vy in self._vertices)
        return f"polygon({coords})"

    def __repr__(self) -> str:
        """Return a string representation of the polygon."""
        return f"Polygon(vertices={self._vertices}, color={self.color!r})"
