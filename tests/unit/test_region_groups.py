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

"""Region groups, which DS9 keeps as tags (M6-16)."""

from __future__ import annotations

import pytest

from ncrads9.regions import group_manager
from ncrads9.regions.region_parser import RegionParser
from ncrads9.regions.region_writer import RegionWriter
from ncrads9.ui.dialogs.group_dialog import GroupDialog


def _regions(*texts: str) -> list:
    return RegionParser().parse_string("image\n" + "\n".join(texts) + "\n")


@pytest.fixture
def regions() -> list:
    return _regions(
        "circle(10,10,5) # tag={Group 1}",
        "box(20,20,6,6) # tag={Group 1}",
        "circle(30,30,5) # tag={faint}",
        "ellipse(40,40,6,3)",
    )


# -- the model ----------------------------------------------------------------


def test_the_groups_are_the_tags_in_use(regions):
    assert group_manager.group_names(regions) == ["Group 1", "faint"]


def test_a_group_is_the_regions_carrying_its_tag(regions):
    assert len(group_manager.regions_in(regions, "Group 1")) == 2
    assert group_manager.regions_in(regions, "nobody") == []


def test_the_default_name_skips_the_ones_in_use(regions):
    assert group_manager.default_name(regions) == "Group 2"
    assert group_manager.default_name([]) == "Group 1"


def test_creating_a_group_tags_its_members(regions):
    assert group_manager.create(regions[2:], "bright") == 2
    assert group_manager.group_names(regions) == ["Group 1", "faint", "bright"]


def test_a_region_joins_a_group_only_once(regions):
    assert group_manager.create(regions[:2], "Group 1") == 0
    assert regions[0].tags == ["Group 1"]


def test_renaming_a_group_retags_every_member(regions):
    assert group_manager.rename(regions, "Group 1", "bright") == 2
    assert group_manager.group_names(regions) == ["bright", "faint"]


def test_renaming_onto_an_existing_group_merges_without_duplicating(regions):
    group_manager.create([regions[0]], "faint")
    group_manager.rename(regions, "Group 1", "faint")
    assert regions[0].tags == ["faint"]
    assert len(group_manager.regions_in(regions, "faint")) == 3


def test_deleting_a_group_keeps_its_regions(regions):
    assert group_manager.delete(regions, "Group 1") == 2
    assert len(regions) == 4
    assert group_manager.group_names(regions) == ["faint"]


def test_delete_all_clears_every_tag(regions):
    assert group_manager.delete_all(regions) == 3
    assert group_manager.group_names(regions) == []


def test_selecting_a_group_selects_exactly_it(regions):
    regions[3].selected = True
    assert group_manager.select(regions, "Group 1") == 2
    assert [region.selected for region in regions] == [True, True, False, False]


def test_a_group_survives_a_round_trip_through_a_region_file(regions, tmp_path):
    """Membership as a tag round-trips; membership as an index cannot."""
    path = tmp_path / "groups.reg"
    RegionWriter().write_file(regions, str(path))
    reloaded = RegionParser().parse_file(str(path))
    assert group_manager.group_names(reloaded) == ["Group 1", "faint"]


def test_a_group_survives_reordering(regions):
    """Move to Front reorders the list, which index-based groups could not
    survive -- the old GroupManager kept a list of positions."""
    regions.append(regions.pop(0))
    assert len(group_manager.regions_in(regions, "Group 1")) == 2


# -- the dialog ----------------------------------------------------------------


@pytest.fixture
def dialog(qapp, regions) -> GroupDialog:
    return GroupDialog(regions)


def test_the_dialog_lists_every_group(dialog):
    assert [dialog._list.item(row).text() for row in range(dialog._list.count())] == [
        "Group 1",
        "faint",
    ]


def test_choosing_a_group_selects_its_regions(dialog, regions):
    dialog._list.setCurrentRow(0)
    assert [region.selected for region in regions] == [True, True, False, False]


def test_update_puts_the_selection_into_the_chosen_group(dialog, regions):
    dialog._list.setCurrentRow(1)
    for region in regions:
        region.selected = False
    regions[3].selected = True
    dialog.update_group()
    assert "faint" in regions[3].tags


def test_delete_removes_the_group_from_the_list(dialog, regions):
    dialog._list.setCurrentRow(0)
    dialog.delete_group()
    assert [dialog._list.item(row).text() for row in range(dialog._list.count())] == ["faint"]


def test_delete_all_asks_first(dialog, regions, monkeypatch):
    from PyQt6.QtWidgets import QMessageBox

    monkeypatch.setattr(QMessageBox, "question", staticmethod(lambda *a, **k: QMessageBox.StandardButton.No))
    dialog.delete_all_groups()
    assert group_manager.group_names(regions) == ["Group 1", "faint"]

    monkeypatch.setattr(QMessageBox, "question", staticmethod(lambda *a, **k: QMessageBox.StandardButton.Yes))
    dialog.delete_all_groups()
    assert group_manager.group_names(regions) == []


def test_rename_goes_through_the_prompt(dialog, regions, monkeypatch):
    from PyQt6.QtWidgets import QInputDialog

    monkeypatch.setattr(QInputDialog, "getText", staticmethod(lambda *a, **k: ("bright", True)))
    dialog._list.setCurrentRow(0)
    dialog.rename_group()
    assert group_manager.group_names(regions) == ["bright", "faint"]


def test_a_cancelled_rename_changes_nothing(dialog, regions, monkeypatch):
    from PyQt6.QtWidgets import QInputDialog

    monkeypatch.setattr(QInputDialog, "getText", staticmethod(lambda *a, **k: ("bright", False)))
    dialog._list.setCurrentRow(0)
    dialog.rename_group()
    assert group_manager.group_names(regions) == ["Group 1", "faint"]


def test_none_clears_the_selection(dialog, regions):
    dialog._list.setCurrentRow(0)
    dialog.select_none()
    assert not any(region.selected for region in regions)


def test_every_change_is_announced(dialog, regions):
    said = []
    dialog.groups_changed.connect(said.append)
    dialog._list.setCurrentRow(0)
    dialog.delete_group()
    assert len(said) == 2
