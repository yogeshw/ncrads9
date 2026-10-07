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
DS9's Block Parameters window (`BlockDialog`, `block.tcl`).

File (Apply, Close) and Block menus over a Block row of two entries, x and
y, with Apply and Close. The Block menu holds the main window's own Block
In, Block Out, Block Fit and preset actions, so a tick in one is a tick in
the other. NCRADS9 blocks both axes together, so two different factors
are refused rather than half applied.

Author: Yogesh Wadadekar
"""

from __future__ import annotations

from typing import Any

from PyQt6.QtCore import pyqtSignal
from PyQt6.QtGui import QAction, QKeySequence
from PyQt6.QtWidgets import (
    QDialog,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMenuBar,
    QPushButton,
    QVBoxLayout,
)

from .modeless import make_modeless


class BlockDialog(QDialog):
    """The Block Parameters window.

    Args:
        parent: The main window, whose Block menu actions it shows.
        factor: The block factor in force.
    """

    #: Apply: the factor to block by.
    block_requested = pyqtSignal(int)

    def __init__(self, parent: Any | None = None, factor: int = 1) -> None:
        super().__init__(parent)
        self.setWindowTitle("Block Parameters")
        make_modeless(self)
        layout = QVBoxLayout(self)
        layout.setMenuBar(self._build_menus(getattr(parent, "menu_bar", None)))

        row = QHBoxLayout()
        row.addWidget(QLabel("Block"))
        self.block_x = QLineEdit()
        self.block_y = QLineEdit()
        for entry in (self.block_x, self.block_y):
            entry.setFixedWidth(70)
            entry.returnPressed.connect(self.apply)
            row.addWidget(entry)
        layout.addLayout(row)

        self.message = QLabel()
        layout.addWidget(self.message)

        buttons = QHBoxLayout()
        for label, slot in (("Apply", self.apply), ("Close", self.close)):
            button = QPushButton(label)
            button.clicked.connect(lambda _checked=False, s=slot: s())
            buttons.addWidget(button)
        layout.addLayout(buttons)
        self.set_factor(factor)

    def _build_menus(self, menu) -> QMenuBar:
        bar = QMenuBar(self)
        file_menu = bar.addMenu("&File")
        apply = QAction("Apply", self)
        apply.triggered.connect(lambda _checked=False: self.apply())
        file_menu.addAction(apply)
        file_menu.addSeparator()
        close = QAction("Close", self)
        close.setShortcut(QKeySequence(QKeySequence.StandardKey.Close))
        close.triggered.connect(self.close)
        file_menu.addAction(close)
        if menu is not None and hasattr(menu, "analysis_block_menu"):
            # The main window's own Block menu, shared rather than copied.
            block_menu = bar.addMenu("&Block")
            for action in menu.analysis_block_menu.actions():
                block_menu.addAction(action)
        return bar

    def set_factor(self, factor: int) -> None:
        """Show the factor in force."""
        self.block_x.setText(str(int(factor)))
        self.block_y.setText(str(int(factor)))
        self.message.clear()

    def factor(self) -> int | None:
        """The factor typed, or None (and a message) if it cannot be used."""
        try:
            x, y = int(self.block_x.text()), int(self.block_y.text())
        except ValueError:
            self.message.setText("The block factors are whole numbers.")
            return None
        if x != y:
            self.message.setText("Blocking x and y by different factors is not supported.")
            return None
        if x < 1:
            self.message.setText("A block factor is at least 1.")
            return None
        self.message.clear()
        return x

    def apply(self) -> None:
        """DS9's Apply: block by the factor typed."""
        factor = self.factor()
        if factor is not None:
            self.block_requested.emit(factor)
