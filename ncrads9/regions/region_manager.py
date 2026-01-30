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
Region manager for handling collections of regions.

Author: Yogesh Wadadekar
"""

from pathlib import Path
from typing import Callable, Iterator, Optional

from .base_region import BaseRegion
from .region_parser import RegionParser
from .region_writer import RegionWriter


class RegionManager:
    """Manager for a collection of regions."""

    def __init__(self) -> None:
        """Initialize the region manager."""
        self._regions: list[BaseRegion] = []
        self._selected_indices: set[int] = set()
        self._parser = RegionParser()
        self._writer = RegionWriter()
        self._change_callbacks: list[Callable[[], None]] = []

    @property
    def regions(self) -> list[BaseRegion]:
        """Get all regions."""
        return self._regions.copy()

    @property
    def count(self) -> int:
        """Get the number of regions."""
        return len(self._regions)

    @property
    def selected_count(self) -> int:
        """Get the number of selected regions."""
        return len(self._selected_indices)

    def add_region(self, region: BaseRegion) -> int:
        """
        Add a region to the collection.

        Args:
            region: The region to add.

        Returns:
            The index of the added region.
        """
        self._regions.append(region)
        self._notify_change()
        return len(self._regions) - 1

    def remove_region(self, index: int) -> Optional[BaseRegion]:
        """
        Remove a region by index.

        Args:
            index: The index of the region to remove.

        Returns:
            The removed region or None if index is invalid.
        """
        if 0 <= index < len(self._regions):
            region = self._regions.pop(index)
            self._selected_indices.discard(index)
            # Update selected indices for removed item
            self._selected_indices = {
                i - 1 if i > index else i for i in self._selected_indices
            }
            self._notify_change()
            return region
        return None

    def get_region(self, index: int) -> Optional[BaseRegion]:
        """
        Get a region by index.

        Args:
            index: The index of the region.

        Returns:
            The region or None if index is invalid.
        """
        if 0 <= index < len(self._regions):
            return self._regions[index]
        return None

    def clear(self) -> None:
        """Remove all regions."""
        self._regions.clear()
        self._selected_indices.clear()
        self._notify_change()

    def select(self, index: int) -> None:
        """
        Select a region by index.

        Args:
            index: The index of the region to select.
        """
        if 0 <= index < len(self._regions):
            self._selected_indices.add(index)
            self._notify_change()

    def deselect(self, index: int) -> None:
        """
        Deselect a region by index.

        Args:
            index: The index of the region to deselect.
        """
        self._selected_indices.discard(index)
        self._notify_change()

    def toggle_selection(self, index: int) -> None:
        """
        Toggle selection of a region by index.

        Args:
            index: The index of the region.
        """
        if index in self._selected_indices:
            self._selected_indices.discard(index)
        elif 0 <= index < len(self._regions):
            self._selected_indices.add(index)
        self._notify_change()

    def select_all(self) -> None:
        """Select all regions."""
        self._selected_indices = set(range(len(self._regions)))
        self._notify_change()

    def deselect_all(self) -> None:
        """Deselect all regions."""
        self._selected_indices.clear()
        self._notify_change()

    def is_selected(self, index: int) -> bool:
        """
        Check if a region is selected.

        Args:
            index: The index of the region.

        Returns:
            True if the region is selected.
        """
        return index in self._selected_indices

    def get_selected_regions(self) -> list[BaseRegion]:
        """
        Get all selected regions.

        Returns:
            List of selected regions.
        """
        return [self._regions[i] for i in sorted(self._selected_indices)]

    def get_selected_indices(self) -> list[int]:
        """
        Get indices of all selected regions.

        Returns:
            List of selected region indices.
        """
        return sorted(self._selected_indices)

    def find_region_at(self, x: float, y: float) -> Optional[int]:
        """
        Find a region containing the given point.

        Args:
            x: The x coordinate.
            y: The y coordinate.

        Returns:
            The index of the first region containing the point, or None.
        """
        # Search in reverse order (top-most region first)
        for i in range(len(self._regions) - 1, -1, -1):
            if self._regions[i].contains(x, y):
                return i
        return None

    def find_regions_by_tag(self, tag: str) -> list[int]:
        """
        Find all regions with a specific tag.

        Args:
            tag: The tag to search for.

        Returns:
            List of region indices with the tag.
        """
        return [
            i for i, region in enumerate(self._regions) if tag in region.tags
        ]

    def find_regions_by_color(self, color: str) -> list[int]:
        """
        Find all regions with a specific color.

        Args:
            color: The color to search for.

        Returns:
            List of region indices with the color.
        """
        return [
            i
            for i, region in enumerate(self._regions)
            if region.color == color
        ]

    def load_file(self, filepath: str | Path) -> int:
        """
        Load regions from a file.

        Args:
            filepath: Path to the region file.

        Returns:
            The number of regions loaded.
        """
        regions = self._parser.parse_file(filepath)
        for region in regions:
            self._regions.append(region)
        self._notify_change()
        return len(regions)

    def save_file(self, filepath: str | Path) -> None:
        """
        Save all regions to a file.

        Args:
            filepath: Path to the output file.
        """
        self._writer.write_file(self._regions, filepath)

    def save_selected(self, filepath: str | Path) -> None:
        """
        Save selected regions to a file.

        Args:
            filepath: Path to the output file.
        """
        selected = self.get_selected_regions()
        self._writer.write_file(selected, filepath)

    def move_selected(self, dx: float, dy: float) -> None:
        """
        Move all selected regions.

        Args:
            dx: The offset in the x direction.
            dy: The offset in the y direction.
        """
        for i in self._selected_indices:
            self._regions[i].move(dx, dy)
        self._notify_change()

    def delete_selected(self) -> int:
        """
        Delete all selected regions.

        Returns:
            The number of regions deleted.
        """
        count = len(self._selected_indices)
        for index in sorted(self._selected_indices, reverse=True):
            self._regions.pop(index)
        self._selected_indices.clear()
        self._notify_change()
        return count

    def add_change_callback(self, callback: Callable[[], None]) -> None:
        """
        Add a callback to be called when regions change.

        Args:
            callback: The callback function.
        """
        self._change_callbacks.append(callback)

    def remove_change_callback(self, callback: Callable[[], None]) -> None:
        """
        Remove a change callback.

        Args:
            callback: The callback function to remove.
        """
        if callback in self._change_callbacks:
            self._change_callbacks.remove(callback)

    def _notify_change(self) -> None:
        """Notify all callbacks of a change."""
        for callback in self._change_callbacks:
            callback()

    def __iter__(self) -> Iterator[BaseRegion]:
        """Iterate over all regions."""
        return iter(self._regions)

    def __len__(self) -> int:
        """Get the number of regions."""
        return len(self._regions)

    def __getitem__(self, index: int) -> BaseRegion:
        """Get a region by index."""
        return self._regions[index]
