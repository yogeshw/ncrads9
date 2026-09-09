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
The extension chooser: which HDU of a multi-extension file to display.

DS9 never asks. It applies the algorithm in `ds9/doc/ref/file.html` -- primary
HDU if it is an image, else the first extension that is or can become one --
and offers `File -> Open As -> Multiple Extension Cube` and
`Multiple Extension Frames` for the cases where you want all of them. That
silently picks one of several science extensions, which for an instrument file
with SCI, ERR and DQ is a coin toss, so NCRADS9 asks when, and only when,
there is more than one displayable HDU. `Edit -> Preferences` turns the prompt
off for anyone who wants DS9's behaviour exactly.

The dialog also carries the two "all extensions" choices, since a chooser
already listing them is the natural place to load them together.

This module used to hold a second file-open dialog: a list of paths with a
header preview beside it, driven by `QFileDialog.getOpenFileName` internally,
which is what `FileController.open_file` calls directly. It was never
constructed. Replaced rather than extended -- an HDU chooser is what M4-2
needs from this module.

Author: Yogesh Wadadekar
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from pathlib import Path

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QAbstractItemView,
    QDialog,
    QDialogButtonBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QPushButton,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
    QWidget,
)

from ...core.fits_handler import HDUInfo

#: The columns of the chooser, in order.
COLUMNS: tuple[str, ...] = ("HDU", "Name", "Type", "Dimensions", "BITPIX")


class HDUChoice(Enum):
    """What the user asked for."""

    #: Load the highlighted extension into the current frame.
    SINGLE = "single"
    #: One frame per displayable extension (DS9's Multiple Extension Frames).
    ALL_FRAMES = "frames"
    #: Every displayable extension stacked as a cube (Multiple Extension Cube).
    ALL_CUBE = "cube"


@dataclass(frozen=True)
class HDUSelection:
    """The chooser's outcome."""

    choice: HDUChoice
    #: The chosen HDU's index, for `HDUChoice.SINGLE`; None otherwise.
    index: int | None = None


class OpenDialog(QDialog):
    """Choose which extension of a FITS file to display.

    Args:
        path: The file being opened, for the title.
        extensions: Every HDU in the file, from `FITSHandler.extensions()`.
        default_index: The HDU DS9's algorithm would pick, preselected.
        parent: Optional parent widget.
    """

    def __init__(
        self,
        path: Path | str,
        extensions: list[HDUInfo],
        default_index: int | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle(f"Extensions — {Path(path).name}")
        self.setMinimumSize(560, 320)

        self._extensions = extensions
        self._selection: HDUSelection | None = None

        layout = QVBoxLayout(self)
        layout.addWidget(
            QLabel(
                f"{Path(path).name} has {len(self.displayable)} displayable "
                "extensions. Choose one, or load them all."
            )
        )

        self._tree = QTreeWidget()
        self._tree.setColumnCount(len(COLUMNS))
        self._tree.setHeaderLabels(list(COLUMNS))
        self._tree.setRootIsDecorated(False)
        self._tree.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self._tree.itemDoubleClicked.connect(lambda *_: self._choose(HDUChoice.SINGLE))
        layout.addWidget(self._tree, 1)
        self._fill(default_index)

        header = self._tree.header()
        if header is not None:
            header.setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)

        buttons = QHBoxLayout()
        self._frames_button = QPushButton("All as Frames")
        self._frames_button.setToolTip("One frame per extension (DS9: Multiple Extension Frames)")
        self._frames_button.clicked.connect(lambda: self._choose(HDUChoice.ALL_FRAMES))
        buttons.addWidget(self._frames_button)

        self._cube_button = QPushButton("All as Cube")
        self._cube_button.setToolTip("Stack the extensions into a cube (DS9: Multiple Extension Cube)")
        self._cube_button.clicked.connect(lambda: self._choose(HDUChoice.ALL_CUBE))
        buttons.addWidget(self._cube_button)
        buttons.addStretch(1)

        box = QDialogButtonBox(QDialogButtonBox.StandardButton.Open | QDialogButtonBox.StandardButton.Cancel)
        box.accepted.connect(lambda: self._choose(HDUChoice.SINGLE))
        box.rejected.connect(self.reject)
        buttons.addWidget(box)
        layout.addLayout(buttons)

        # Stacking extensions of different shapes is not a cube.
        self._cube_button.setEnabled(self.stackable)

    # -- contents ------------------------------------------------------------

    @property
    def displayable(self) -> list[HDUInfo]:
        """The extensions the loader could display."""
        return [info for info in self._extensions if info.displayable]

    @property
    def stackable(self) -> bool:
        """Whether every displayable extension has the same 2D shape."""
        shapes = {info.shape[-2:] for info in self.displayable if len(info.shape) >= 2}
        return len(shapes) == 1 and len(self.displayable) > 1

    def _fill(self, default_index: int | None) -> None:
        """List every HDU, greying out the ones that cannot be shown."""
        for info in self._extensions:
            item = QTreeWidgetItem(
                [
                    str(info.index),
                    info.name or "-",
                    info.kind.value,
                    info.dimensions,
                    "" if info.bitpix is None else str(info.bitpix),
                ]
            )
            item.setData(0, Qt.ItemDataRole.UserRole, info.index)
            if not info.displayable:
                item.setDisabled(True)
                item.setToolTip(0, f"a {info.kind.value} HDU cannot be displayed")
            self._tree.addTopLevelItem(item)
            if info.index == default_index:
                item.setSelected(True)
                self._tree.setCurrentItem(item)

        for column in range(len(COLUMNS)):
            self._tree.resizeColumnToContents(column)

    # -- outcome -------------------------------------------------------------

    def _choose(self, choice: HDUChoice) -> None:
        """Record a choice and close, ignoring a non-displayable row."""
        if choice is not HDUChoice.SINGLE:
            self._selection = HDUSelection(choice)
            self.accept()
            return

        item = self._tree.currentItem()
        if item is None or item.isDisabled():
            return
        self._selection = HDUSelection(HDUChoice.SINGLE, int(item.data(0, Qt.ItemDataRole.UserRole)))
        self.accept()

    def selection(self) -> HDUSelection | None:
        """What the user chose, or None if they cancelled."""
        return self._selection
