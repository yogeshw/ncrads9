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
from typing import Any

from ..base_region import BaseRegion


def generate_radii(inner: float, outer: float, count: int, method: str = "dist") -> list[float]:
    """`count` annuli from `inner` to `outer`: DS9's Generate.

    The arithmetic of `MarkerBaseAnnulusGenerateCircle` in
    `ds9/library/markerbaseannulus.tcl`: "dist" spaces the radii equally,
    "area" gives every ring the same area.
    """
    count = max(1, int(count))
    inner, outer = float(inner), float(outer)
    if method == "area":
        area = math.pi * (outer * outer - inner * inner) / count
        radii = [inner]
        for _ring in range(count):
            radii.append(math.sqrt((area + math.pi * radii[-1] ** 2) / math.pi))
        return radii
    step = (outer - inner) / count
    return [inner + step * index for index in range(count + 1)]


class Annulus(BaseRegion):
    """A circular annulus: a centre and a list of radii, smallest first.

    DS9's annulus is any number of concentric rings -- `annulus(x,y,r1,r2,
    r3,...)` -- and its dialog edits them as a list with a Generate button.
    `inner_radius` and `outer_radius` are its two ends.
    """

    def __init__(
        self,
        center: tuple[float, float],
        inner_radius: float,
        outer_radius: float,
        color: str = "green",
        width: int = 1,
        font: str = "helvetica 10 normal roman",
        text: str = "",
        tags: list[str] | None = None,
        radii: list[float] | None = None,
        **kwargs: Any,
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
            radii: Every radius, smallest first, when there are more than
                two. Its ends override `inner_radius` and `outer_radius`.
        """
        super().__init__(center, color, width, font, text, tags, **kwargs)
        self._radii: list[float] = [float(inner_radius), float(outer_radius)]
        if radii is not None:
            self.radii = radii

    @property
    def radii(self) -> list[float]:
        """Every radius, smallest first."""
        return list(self._radii)

    @radii.setter
    def radii(self, values: list[float]) -> None:
        """Set every radius. Fewer than two is not an annulus and is ignored."""
        cleaned = sorted(values, key=float)
        if len(cleaned) >= 2:
            self._radii = cleaned

    @property
    def inner_radius(self) -> float:
        """Get the inner radius."""
        return self._radii[0]

    @inner_radius.setter
    def inner_radius(self, value: float) -> None:
        """Set the inner radius, keeping the rings still inside the span."""
        outer = self._radii[-1]
        between = [radius for radius in self._radii[1:-1] if value < radius < outer]
        self._radii = [value, *between, outer]

    @property
    def outer_radius(self) -> float:
        """Get the outer radius."""
        return self._radii[-1]

    @outer_radius.setter
    def outer_radius(self, value: float) -> None:
        """Set the outer radius, keeping the rings still inside the span."""
        inner = self._radii[0]
        between = [radius for radius in self._radii[1:-1] if inner < radius < value]
        self._radii = [inner, *between, value]

    def draw(self, context: Any) -> None:
        """
        Draw the annulus on the given context.

        Args:
            context: The drawing context.
        """

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
        return self.inner_radius <= distance <= self.outer_radius

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
        self._radii = [radius * scale for radius in self._radii]

    def to_ds9_string(self) -> str:
        """
        Convert the annulus to a DS9 format string.

        Returns:
            The annulus as a DS9 format string.
        """
        cx, cy = self.center
        return f"annulus({cx},{cy},{','.join(str(radius) for radius in self._radii)})"

    def __repr__(self) -> str:
        """Return a string representation of the annulus."""
        return (
            f"Annulus(center={self.center}, radii={self._radii})"
        )
