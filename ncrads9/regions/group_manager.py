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
Group manager for region grouping functionality.

Author: Yogesh Wadadekar
"""

from dataclasses import dataclass, field
from typing import Callable, Iterator, Optional

from .base_region import BaseRegion
from .region_manager import RegionManager


@dataclass
class RegionGroup:
    """A group of regions."""

    name: str
    color: str = "green"
    visible: bool = True
    locked: bool = False
    region_indices: list[int] = field(default_factory=list)

    def __post_init__(self) -> None:
        """Initialize the region indices list if None."""
        if self.region_indices is None:
            self.region_indices = []


class GroupManager:
    """Manager for region groups."""

    def __init__(
        self, region_manager: Optional[RegionManager] = None
    ) -> None:
        """
        Initialize the group manager.

        Args:
            region_manager: Optional region manager to associate with.
        """
        self._region_manager = region_manager
        self._groups: dict[str, RegionGroup] = {}
        self._change_callbacks: list[Callable[[], None]] = []

    @property
    def groups(self) -> dict[str, RegionGroup]:
        """Get all groups."""
        return self._groups.copy()

    @property
    def group_names(self) -> list[str]:
        """Get all group names."""
        return list(self._groups.keys())

    @property
    def count(self) -> int:
        """Get the number of groups."""
        return len(self._groups)

    def set_region_manager(self, manager: RegionManager) -> None:
        """
        Set the region manager.

        Args:
            manager: The region manager to associate with.
        """
        self._region_manager = manager

    def create_group(
        self,
        name: str,
        color: str = "green",
        visible: bool = True,
        locked: bool = False,
    ) -> RegionGroup:
        """
        Create a new group.

        Args:
            name: The name of the group.
            color: The default color for the group.
            visible: Whether the group is visible.
            locked: Whether the group is locked.

        Returns:
            The created RegionGroup.

        Raises:
            ValueError: If a group with the name already exists.
        """
        if name in self._groups:
            raise ValueError(f"Group '{name}' already exists")

        group = RegionGroup(
            name=name, color=color, visible=visible, locked=locked
        )
        self._groups[name] = group
        self._notify_change()
        return group

    def delete_group(self, name: str, remove_tag: bool = True) -> bool:
        """
        Delete a group.

        Args:
            name: The name of the group to delete.
            remove_tag: Whether to remove the group tag from regions.

        Returns:
            True if the group was deleted, False if it didn't exist.
        """
        if name not in self._groups:
            return False

        group = self._groups[name]

        # Remove tag from regions if requested
        if remove_tag and self._region_manager is not None:
            for index in group.region_indices:
                region = self._region_manager.get_region(index)
                if region and name in region.tags:
                    region.tags.remove(name)

        del self._groups[name]
        self._notify_change()
        return True

    def rename_group(self, old_name: str, new_name: str) -> bool:
        """
        Rename a group.

        Args:
            old_name: The current name of the group.
            new_name: The new name for the group.

        Returns:
            True if the group was renamed, False otherwise.

        Raises:
            ValueError: If new_name already exists.
        """
        if old_name not in self._groups:
            return False

        if new_name in self._groups:
            raise ValueError(f"Group '{new_name}' already exists")

        group = self._groups.pop(old_name)
        group.name = new_name
        self._groups[new_name] = group

        # Update tags in regions
        if self._region_manager is not None:
            for index in group.region_indices:
                region = self._region_manager.get_region(index)
                if region and old_name in region.tags:
                    region.tags.remove(old_name)
                    region.tags.append(new_name)

        self._notify_change()
        return True

    def get_group(self, name: str) -> Optional[RegionGroup]:
        """
        Get a group by name.

        Args:
            name: The name of the group.

        Returns:
            The RegionGroup or None if not found.
        """
        return self._groups.get(name)

    def add_region_to_group(self, group_name: str, region_index: int) -> bool:
        """
        Add a region to a group.

        Args:
            group_name: The name of the group.
            region_index: The index of the region to add.

        Returns:
            True if successful, False otherwise.
        """
        if group_name not in self._groups:
            return False

        group = self._groups[group_name]
        if region_index not in group.region_indices:
            group.region_indices.append(region_index)

            # Add tag to region
            if self._region_manager is not None:
                region = self._region_manager.get_region(region_index)
                if region and group_name not in region.tags:
                    region.tags.append(group_name)

            self._notify_change()

        return True

    def remove_region_from_group(
        self, group_name: str, region_index: int
    ) -> bool:
        """
        Remove a region from a group.

        Args:
            group_name: The name of the group.
            region_index: The index of the region to remove.

        Returns:
            True if successful, False otherwise.
        """
        if group_name not in self._groups:
            return False

        group = self._groups[group_name]
        if region_index in group.region_indices:
            group.region_indices.remove(region_index)

            # Remove tag from region
            if self._region_manager is not None:
                region = self._region_manager.get_region(region_index)
                if region and group_name in region.tags:
                    region.tags.remove(group_name)

            self._notify_change()

        return True

    def get_regions_in_group(self, group_name: str) -> list[BaseRegion]:
        """
        Get all regions in a group.

        Args:
            group_name: The name of the group.

        Returns:
            List of regions in the group.
        """
        if group_name not in self._groups or self._region_manager is None:
            return []

        group = self._groups[group_name]
        regions: list[BaseRegion] = []

        for index in group.region_indices:
            region = self._region_manager.get_region(index)
            if region:
                regions.append(region)

        return regions

    def get_groups_for_region(self, region_index: int) -> list[str]:
        """
        Get all groups that contain a region.

        Args:
            region_index: The index of the region.

        Returns:
            List of group names containing the region.
        """
        return [
            name
            for name, group in self._groups.items()
            if region_index in group.region_indices
        ]

    def set_group_visibility(self, group_name: str, visible: bool) -> bool:
        """
        Set the visibility of a group.

        Args:
            group_name: The name of the group.
            visible: Whether the group should be visible.

        Returns:
            True if successful, False otherwise.
        """
        if group_name not in self._groups:
            return False

        self._groups[group_name].visible = visible
        self._notify_change()
        return True

    def set_group_locked(self, group_name: str, locked: bool) -> bool:
        """
        Set the locked state of a group.

        Args:
            group_name: The name of the group.
            locked: Whether the group should be locked.

        Returns:
            True if successful, False otherwise.
        """
        if group_name not in self._groups:
            return False

        self._groups[group_name].locked = locked
        self._notify_change()
        return True

    def set_group_color(self, group_name: str, color: str) -> bool:
        """
        Set the color of a group.

        Args:
            group_name: The name of the group.
            color: The color for the group.

        Returns:
            True if successful, False otherwise.
        """
        if group_name not in self._groups:
            return False

        self._groups[group_name].color = color

        # Update color of all regions in the group
        if self._region_manager is not None:
            for index in self._groups[group_name].region_indices:
                region = self._region_manager.get_region(index)
                if region:
                    region.color = color

        self._notify_change()
        return True

    def select_group(self, group_name: str) -> bool:
        """
        Select all regions in a group.

        Args:
            group_name: The name of the group.

        Returns:
            True if successful, False otherwise.
        """
        if group_name not in self._groups or self._region_manager is None:
            return False

        group = self._groups[group_name]
        for index in group.region_indices:
            self._region_manager.select(index)

        return True

    def deselect_group(self, group_name: str) -> bool:
        """
        Deselect all regions in a group.

        Args:
            group_name: The name of the group.

        Returns:
            True if successful, False otherwise.
        """
        if group_name not in self._groups or self._region_manager is None:
            return False

        group = self._groups[group_name]
        for index in group.region_indices:
            self._region_manager.deselect(index)

        return True

    def clear(self) -> None:
        """Remove all groups."""
        self._groups.clear()
        self._notify_change()

    def add_change_callback(self, callback: Callable[[], None]) -> None:
        """
        Add a callback to be called when groups change.

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

    def __iter__(self) -> Iterator[RegionGroup]:
        """Iterate over all groups."""
        return iter(self._groups.values())

    def __len__(self) -> int:
        """Get the number of groups."""
        return len(self._groups)

    def __contains__(self, name: str) -> bool:
        """Check if a group exists."""
        return name in self._groups
