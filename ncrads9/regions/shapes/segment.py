# NCRADS9 - NCRA DS9-like FITS Viewer
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
Segment region shape: an open polyline.

DS9's `segment x1 y1 x2 y2 x3 y3 ...` -- the same vertices as a polygon but
not closed, so it traces a path rather than bounding an area. Nothing is
inside a segment, which is why `contains` reports proximity to the line
instead: a shape that can never be hit is a shape that can never be selected.

Author: Yogesh Wadadekar
"""

from typing import Any

from ..base_region import BaseRegion

#: How far from the path a point may be and still count as on it, in pixels.
HIT_TOLERANCE = 3.0


class Segment(BaseRegion):
    """An open polyline through a list of vertices."""

    def __init__(
        self,
        points: list[tuple[float, float]],
        color: str = "green",
        width: int = 1,
        font: str = "helvetica 10 normal roman",
        text: str = "",
        tags: list[str] | None = None,
        **kwargs: Any,
    ) -> None:
        """
        Initialize a segment region.

        Args:
            points: The vertices, in order. At least two are needed for the
                segment to have any extent.
            color: The color of the region outline.
            width: The line width of the region outline.
            font: The font specification for text labels.
            text: The text label for the region.
            tags: Optional list of tags for grouping regions.

        Raises:
            ValueError: If fewer than two vertices are given.
        """
        if len(points) < 2:
            raise ValueError(f"a segment needs at least two vertices, got {len(points)}")
        self._points = [(float(x), float(y)) for x, y in points]
        super().__init__(self._centroid(), color, width, font, text, tags, **kwargs)

    def _centroid(self) -> tuple[float, float]:
        """The mean of the vertices, which is what `center` reports."""
        count = len(self._points)
        return (
            sum(x for x, _y in self._points) / count,
            sum(y for _x, y in self._points) / count,
        )

    @property
    def points(self) -> list[tuple[float, float]]:
        """The vertices, in order."""
        return list(self._points)

    @points.setter
    def points(self, value: list[tuple[float, float]]) -> None:
        """Replace the vertices.

        Raises:
            ValueError: If fewer than two are given.
        """
        if len(value) < 2:
            raise ValueError(f"a segment needs at least two vertices, got {len(value)}")
        self._points = [(float(x), float(y)) for x, y in value]
        self.center = self._centroid()

    def draw(self, context: Any) -> None:
        """
        Draw the segment on the given context.

        Args:
            context: The drawing context.
        """

    def contains(self, x: float, y: float) -> bool:
        """
        Whether a point lies on the segment's path.

        An open path encloses nothing, so this reports proximity rather than
        containment -- within `HIT_TOLERANCE` pixels of any of its lines.

        Args:
            x: The x coordinate of the point.
            y: The y coordinate of the point.

        Returns:
            True if the point is on the path.
        """
        for first, second in zip(self._points, self._points[1:], strict=False):
            if _distance_to_line(x, y, first, second) <= HIT_TOLERANCE:
                return True
        return False

    def move(self, dx: float, dy: float) -> None:
        """
        Move the segment by the given offset.

        Args:
            dx: The offset in the x direction.
            dy: The offset in the y direction.
        """
        self._points = [(x + dx, y + dy) for x, y in self._points]
        cx, cy = self.center
        self.center = (cx + dx, cy + dy)

    def resize(self, scale_x: float, scale_y: float) -> None:
        """
        Scale the segment about its centroid.

        Args:
            scale_x: The scale factor in the x direction.
            scale_y: The scale factor in the y direction.
        """
        cx, cy = self.center
        self._points = [(cx + (x - cx) * scale_x, cy + (y - cy) * scale_y) for x, y in self._points]

    def to_ds9_string(self) -> str:
        """
        Convert the segment to a DS9 format string.

        Returns:
            The segment as a DS9 format string.
        """
        coordinates = ",".join(f"{value:g}" for point in self._points for value in point)
        return f"segment({coordinates})"

    def __repr__(self) -> str:
        """Return a string representation of the segment."""
        return f"Segment(points={self._points})"


def _distance_to_line(
    x: float,
    y: float,
    first: tuple[float, float],
    second: tuple[float, float],
) -> float:
    """The shortest distance from a point to a line *segment*.

    Clamped to the segment's ends rather than measured to the infinite line,
    so a point far off the end of a short line is not counted as on it.
    """
    x1, y1 = first
    x2, y2 = second
    dx, dy = x2 - x1, y2 - y1
    length_squared = dx * dx + dy * dy
    if length_squared == 0.0:
        return ((x - x1) ** 2 + (y - y1) ** 2) ** 0.5

    t = max(0.0, min(1.0, ((x - x1) * dx + (y - y1) * dy) / length_squared))
    nearest_x, nearest_y = x1 + t * dx, y1 + t * dy
    return ((x - nearest_x) ** 2 + (y - nearest_y) ** 2) ** 0.5
