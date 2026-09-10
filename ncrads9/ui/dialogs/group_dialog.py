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
DS9's Groups dialog: the tags in use, and what can be done to them.

A list of the group names, and DS9's five operations on the chosen one --
Update (retag the current selection with it), Edit Group Name, Delete Group,
Delete All Groups, and Select None. Choosing a name in the list selects that
group's regions on the frame, which is how the dialog is mostly used: as a
way of getting a set of regions back.

Author: Yogesh Wadadekar
"""

from __future__ import annotations

from PyQt6.QtCore import pyqtSignal
from PyQt6.QtWidgets import (
    QDialog,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QListWidget,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from ...regions import group_manager


class GroupDialog(QDialog):
    """The list of groups on the current frame.

    Args:
        regions: The frame's regions. Held by reference, not copied, so the
            dialog keeps working as regions come and go -- `refresh` rereads
            it rather than being handed a new list.
        parent: Optional parent widget.
    """

    #: Emitted whenever the dialog changes a tag or a selection, so the
    #: overlay redraws and the status bar can say what happened.
    groups_changed = pyqtSignal(str)

    def __init__(self, regions: list, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Groups")
        self.regions = regions

        layout = QVBoxLayout(self)
        layout.addWidget(QLabel("Choosing a group selects its regions."))

        self._list = QListWidget()
        self._list.currentTextChanged.connect(self._on_chosen)
        layout.addWidget(self._list)

        layout.addLayout(self._buttons())
        self.refresh()

    def _buttons(self) -> QHBoxLayout:
        """DS9's five group commands, plus Close."""
        row = QHBoxLayout()
        for label, handler in (
            ("Update", self.update_group),
            ("Rename", self.rename_group),
            ("Delete", self.delete_group),
            ("Delete All", self.delete_all_groups),
            ("None", self.select_none),
            ("Close", self.accept),
        ):
            button = QPushButton(label)
            button.clicked.connect(handler)
            row.addWidget(button)
        return row

    # -- the list ------------------------------------------------------------

    @property
    def chosen(self) -> str:
        """The group currently highlighted, or "" if none is."""
        item = self._list.currentItem()
        return item.text() if item is not None else ""

    def refresh(self) -> None:
        """Reread the tags, keeping the highlight where it was if it lasted."""
        wanted = self.chosen
        self._list.blockSignals(True)
        self._list.clear()
        names = group_manager.group_names(self.regions)
        for name in names:
            self._list.addItem(f"{name}")
        self._list.blockSignals(False)
        if wanted in names:
            self._list.setCurrentRow(names.index(wanted))

    def _on_chosen(self, name: str) -> None:
        """Select the group's regions, as DS9 does on a list click."""
        if not name:
            return
        count = group_manager.select(self.regions, name)
        self.groups_changed.emit(f"{name}: {count} region{'s' if count != 1 else ''} selected")

    # -- the commands ----------------------------------------------------------

    def selected_regions(self) -> list:
        """The regions currently selected on the frame."""
        return [region for region in self.regions if getattr(region, "selected", False)]

    def update_group(self) -> None:
        """Put the current selection into the chosen group."""
        name = self.chosen
        if not name:
            return
        added = group_manager.create(self.selected_regions(), name)
        self.refresh()
        self.groups_changed.emit(f"{name}: {added} region{'s' if added != 1 else ''} added")

    def rename_group(self) -> None:
        """Rename the chosen group, which renames its tag on every region."""
        name = self.chosen
        if not name:
            return
        new, accepted = QInputDialog.getText(self, "Group Name", "Enter group name:", text=name)
        new = new.strip()
        if not accepted or not new or new == name:
            return
        changed = group_manager.rename(self.regions, name, new)
        self.refresh()
        self.groups_changed.emit(f"Renamed {name} to {new} on {changed} regions")

    def delete_group(self) -> None:
        """Delete the chosen group. Its regions stay; only the tag goes."""
        name = self.chosen
        if not name:
            return
        removed = group_manager.delete(self.regions, name)
        self.refresh()
        self.groups_changed.emit(f"Deleted group {name} from {removed} regions")

    def delete_all_groups(self) -> None:
        """Delete every group, after asking -- as DS9 asks."""
        if not group_manager.group_names(self.regions):
            return
        confirm = QMessageBox.question(
            self,
            "Delete All Groups",
            "Delete all groups?\n\nThe regions themselves are not deleted.",
        )
        if confirm != QMessageBox.StandardButton.Yes:
            return
        removed = group_manager.delete_all(self.regions)
        self.refresh()
        self.groups_changed.emit(f"Deleted every group from {removed} regions")

    def select_none(self) -> None:
        """Clear the selection and the highlight."""
        for region in self.regions:
            region.selected = False
        self._list.setCurrentRow(-1)
        self.groups_changed.emit("Selected none")
