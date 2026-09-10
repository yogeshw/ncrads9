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
Region groups, which in DS9 are tags.

DS9's New Group puts a tag on every selected region (`GroupCreate` in
`ds9/library/group.tcl` is two lines: ask for a name, then
`$current(frame) marker tag "{$name}"`), and the Groups dialog lists the tags
in use, selects the regions carrying one, renames a tag, or deletes it. There
is no group object anywhere: a group is exactly "the regions with this tag".

That matters for more than tidiness. Membership written as a tag survives a
round trip through a region file, because `tag={name}` is part of DS9's own
format; membership held as a list of positions does not survive anything at
all -- not Move to Front, not deleting a region, not loading a second file.
This module used to hold `RegionGroup(region_indices=[...])`, which every one
of those silently corrupted, and nothing had ever opened it
(`test_no_orphan_modules` listed it against M6-16).

The functions here take the region list rather than owning it, because the
regions belong to a frame and each frame has its own.

Author: Yogesh Wadadekar
"""

from __future__ import annotations

from .base_region import BaseRegion

#: The stem DS9 numbers its automatic group names from ("Group 1", "Group 2").
DEFAULT_STEM = "Group"


def group_names(regions: list[BaseRegion]) -> list[str]:
    """Every tag in use, in the order first met.

    Ordering by first appearance rather than alphabetically keeps a list of
    groups stable as regions are added, which a sorted list would not.
    """
    names: list[str] = []
    for region in regions:
        for tag in region.tags:
            if tag not in names:
                names.append(tag)
    return names


def default_name(regions: list[BaseRegion]) -> str:
    """The name DS9 offers for a new group: the first unused "Group N"."""
    taken = set(group_names(regions))
    number = 1
    while f"{DEFAULT_STEM} {number}" in taken:
        number += 1
    return f"{DEFAULT_STEM} {number}"


def regions_in(regions: list[BaseRegion], name: str) -> list[BaseRegion]:
    """The regions carrying one tag."""
    return [region for region in regions if name in region.tags]


def create(members: list[BaseRegion], name: str) -> int:
    """Tag every region in `members` with `name`.

    Args:
        members: The regions to put in the group -- DS9 uses the selection.
        name: The group's name.

    Returns:
        How many regions gained the tag. A region already in the group keeps
        one tag rather than gaining a second.
    """
    added = 0
    for region in members:
        if name not in region.tags:
            region.tags = [*region.tags, name]
            added += 1
    return added


def rename(regions: list[BaseRegion], old: str, new: str) -> int:
    """Rename a group, keeping each region's tag order.

    Returns:
        How many regions were retagged.
    """
    if old == new:
        return 0
    changed = 0
    for region in regions:
        if old not in region.tags:
            continue
        # A region already carrying `new` must not end up with it twice.
        tags = [tag for tag in region.tags if tag != old]
        if new not in tags:
            tags.insert(min(region.tags.index(old), len(tags)), new)
        region.tags = tags
        changed += 1
    return changed


def delete(regions: list[BaseRegion], name: str) -> int:
    """Delete a group. The regions themselves stay; only the tag goes.

    Returns:
        How many regions lost the tag.
    """
    removed = 0
    for region in regions:
        if name in region.tags:
            region.tags = [tag for tag in region.tags if tag != name]
            removed += 1
    return removed


def delete_all(regions: list[BaseRegion]) -> int:
    """Delete every group, which is DS9's Delete All Groups.

    Returns:
        How many regions lost at least one tag.
    """
    removed = 0
    for region in regions:
        if region.tags:
            region.tags = []
            removed += 1
    return removed


def select(regions: list[BaseRegion], name: str) -> int:
    """Select exactly the regions in one group, as DS9's Groups list does.

    Returns:
        How many regions ended up selected.
    """
    count = 0
    for region in regions:
        region.selected = name in region.tags
        count += bool(region.selected)
    return count
