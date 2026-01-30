# This file is part of ncrads9.
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
RegionList Widget - Widget for managing regions.

Author: Yogesh Wadadekar
"""

from typing import Optional, List, Dict, Any

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QMenu,
    QGroupBox,
)


class RegionList(QWidget):
    """A widget for managing a list of regions."""

    regionSelected = pyqtSignal(int)
    regionDeleted = pyqtSignal(int)
    regionVisibilityChanged = pyqtSignal(int, bool)
    regionsCleared = pyqtSignal()

    def __init__(
        self,
        parent: Optional[QWidget] = None,
    ) -> None:
        """
        Initialize the RegionList widget.

        Args:
            parent: Parent widget.
        """
        super().__init__(parent)

        self._regions: List[Dict[str, Any]] = []
        self._setup_ui()
        self._connect_signals()

    def _setup_ui(self) -> None:
        """Set up the widget UI."""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        group = QGroupBox("Regions")
        group_layout = QVBoxLayout(group)

        # Region list
        self._list_widget = QListWidget()
        self._list_widget.setContextMenuPolicy(
            Qt.ContextMenuPolicy.CustomContextMenu
        )
        group_layout.addWidget(self._list_widget)

        # Buttons
        button_layout = QHBoxLayout()

        self._delete_button = QPushButton("Delete")
        self._delete_button.setEnabled(False)
        button_layout.addWidget(self._delete_button)

        self._clear_button = QPushButton("Clear All")
        button_layout.addWidget(self._clear_button)

        self._toggle_button = QPushButton("Toggle")
        self._toggle_button.setEnabled(False)
        button_layout.addWidget(self._toggle_button)

        group_layout.addLayout(button_layout)
        layout.addWidget(group)

    def _connect_signals(self) -> None:
        """Connect internal signals."""
        self._list_widget.currentRowChanged.connect(self._on_selection_changed)
        self._list_widget.customContextMenuRequested.connect(
            self._show_context_menu
        )
        self._delete_button.clicked.connect(self._on_delete_clicked)
        self._clear_button.clicked.connect(self._on_clear_clicked)
        self._toggle_button.clicked.connect(self._on_toggle_clicked)

    def _on_selection_changed(self, row: int) -> None:
        """Handle selection change."""
        has_selection = row >= 0
        self._delete_button.setEnabled(has_selection)
        self._toggle_button.setEnabled(has_selection)
        if has_selection:
            self.regionSelected.emit(row)

    def _on_delete_clicked(self) -> None:
        """Handle delete button click."""
        row = self._list_widget.currentRow()
        if row >= 0:
            self.removeRegion(row)

    def _on_clear_clicked(self) -> None:
        """Handle clear button click."""
        self.clearRegions()

    def _on_toggle_clicked(self) -> None:
        """Handle toggle visibility button click."""
        row = self._list_widget.currentRow()
        if row >= 0 and row < len(self._regions):
            visible = self._regions[row].get("visible", True)
            self._regions[row]["visible"] = not visible
            self._update_item_display(row)
            self.regionVisibilityChanged.emit(row, not visible)

    def _show_context_menu(self, position) -> None:
        """Show context menu for region item."""
        item = self._list_widget.itemAt(position)
        if item is None:
            return

        row = self._list_widget.row(item)
        menu = QMenu(self)

        delete_action = menu.addAction("Delete")
        toggle_action = menu.addAction("Toggle Visibility")

        action = menu.exec(self._list_widget.mapToGlobal(position))

        if action == delete_action:
            self.removeRegion(row)
        elif action == toggle_action:
            self._on_toggle_clicked()

    def _update_item_display(self, row: int) -> None:
        """Update the display of a list item."""
        if row < 0 or row >= len(self._regions):
            return

        region = self._regions[row]
        item = self._list_widget.item(row)
        if item:
            name = region.get("name", f"Region {row + 1}")
            visible = region.get("visible", True)
            prefix = "✓ " if visible else "✗ "
            item.setText(f"{prefix}{name}")

    def addRegion(self, region: Dict[str, Any]) -> int:
        """
        Add a region to the list.

        Args:
            region: Region data dictionary.

        Returns:
            Index of the added region.
        """
        if "visible" not in region:
            region["visible"] = True
        if "name" not in region:
            region["name"] = f"Region {len(self._regions) + 1}"

        self._regions.append(region)
        item = QListWidgetItem()
        self._list_widget.addItem(item)
        self._update_item_display(len(self._regions) - 1)

        return len(self._regions) - 1

    def removeRegion(self, index: int) -> None:
        """Remove a region by index."""
        if 0 <= index < len(self._regions):
            self._regions.pop(index)
            self._list_widget.takeItem(index)
            self.regionDeleted.emit(index)

    def clearRegions(self) -> None:
        """Clear all regions."""
        self._regions.clear()
        self._list_widget.clear()
        self.regionsCleared.emit()

    def regions(self) -> List[Dict[str, Any]]:
        """Get all regions."""
        return self._regions.copy()

    def regionAt(self, index: int) -> Optional[Dict[str, Any]]:
        """Get a region by index."""
        if 0 <= index < len(self._regions):
            return self._regions[index].copy()
        return None

    def count(self) -> int:
        """Get the number of regions."""
        return len(self._regions)

    def selectedIndex(self) -> int:
        """Get the currently selected region index."""
        return self._list_widget.currentRow()
