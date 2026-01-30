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
Composite region shape containing multiple regions.

Author: Yogesh Wadadekar
"""

from typing import Any, Optional

from ..base_region import BaseRegion


class Composite(BaseRegion):
    """A composite region containing multiple child regions."""

    def __init__(
        self,
        regions: Optional[list[BaseRegion]] = None,
        color: str = "green",
        width: int = 1,
        font: str = "helvetica 10 normal roman",
        text: str = "",
        tags: Optional[list[str]] = None,
    ) -> None:
        """
        Initialize a composite region.

        Args:
            regions: List of child regions.
            color: The color of the region outline.
            width: The line width of the region outline.
            font: The font specification for text labels.
            text: The text label for the region.
            tags: Optional list of tags for grouping regions.
        """
        self._regions: list[BaseRegion] = regions if regions is not None else []
        center = self._compute_center()
        super().__init__(center, color, width, font, text, tags)

    def _compute_center(self) -> tuple[float, float]:
        """Compute the center from all child regions."""
        if not self._regions:
            return (0.0, 0.0)
        x_sum = sum(r.center[0] for r in self._regions)
        y_sum = sum(r.center[1] for r in self._regions)
        n = len(self._regions)
        return (x_sum / n, y_sum / n)

    @property
    def regions(self) -> list[BaseRegion]:
        """Get the list of child regions."""
        return self._regions

    @regions.setter
    def regions(self, value: list[BaseRegion]) -> None:
        """Set the list of child regions."""
        self._regions = value
        self._center = self._compute_center()

    def add_region(self, region: BaseRegion) -> None:
        """
        Add a region to the composite.

        Args:
            region: The region to add.
        """
        self._regions.append(region)
        self._center = self._compute_center()

    def remove_region(self, region: BaseRegion) -> None:
        """
        Remove a region from the composite.

        Args:
            region: The region to remove.
        """
        if region in self._regions:
            self._regions.remove(region)
            self._center = self._compute_center()

    def clear(self) -> None:
        """Remove all regions from the composite."""
        self._regions.clear()
        self._center = (0.0, 0.0)

    def draw(self, context: Any) -> None:
        """
        Draw all child regions on the given context.

        Args:
            context: The drawing context.
        """
        for region in self._regions:
            region.draw(context)

    def contains(self, x: float, y: float) -> bool:
        """
        Check if a point is contained within any child region.

        Args:
            x: The x coordinate of the point.
            y: The y coordinate of the point.

        Returns:
            True if the point is inside any child region.
        """
        return any(region.contains(x, y) for region in self._regions)

    def move(self, dx: float, dy: float) -> None:
        """
        Move all child regions by the given offset.

        Args:
            dx: The offset in the x direction.
            dy: The offset in the y direction.
        """
        for region in self._regions:
            region.move(dx, dy)
        cx, cy = self.center
        self.center = (cx + dx, cy + dy)

    def resize(self, scale_x: float, scale_y: float) -> None:
        """
        Resize all child regions by the given scale factors.

        Args:
            scale_x: The scale factor in the x direction.
            scale_y: The scale factor in the y direction.
        """
        for region in self._regions:
            region.resize(scale_x, scale_y)

    def to_ds9_string(self) -> str:
        """
        Convert the composite to a DS9 format string.

        Returns:
            The composite as DS9 format strings joined by newlines.
        """
        lines = ["# composite"]
        for region in self._regions:
            lines.append(region.to_ds9_string())
        return "\n".join(lines)

    def __repr__(self) -> str:
        """Return a string representation of the composite."""
        return f"Composite(num_regions={len(self._regions)})"

    def __len__(self) -> int:
        """Return the number of child regions."""
        return len(self._regions)

    def __iter__(self):
        """Iterate over child regions."""
        return iter(self._regions)

    def __getitem__(self, index: int) -> BaseRegion:
        """Get a child region by index."""
        return self._regions[index]
