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
DS9's Graph Parameters window (`GraphDialog`, `graph.tcl`).

File (Apply, Close), Axis (Linear, Log) and Method (Average, Sum, Median)
menus over Grid, Size and Thickness, with Apply and Close. The settings
reach both cut graphs, as DS9's do. Which graphs are shown stays on the
View menu, where DS9 has it; the two checkboxes here are a convenience.

Author: Yogesh Wadadekar
"""

from __future__ import annotations

from typing import Any

from PyQt6.QtGui import QAction, QActionGroup, QKeySequence
from PyQt6.QtWidgets import (
    QCheckBox,
    QDialog,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMenuBar,
    QPushButton,
    QVBoxLayout,
)

from .modeless import make_modeless


class GraphDialog(QDialog):
    """The Graph Parameters window.

    Args:
        parent: The main window, whose `horizontal_graph` and
            `vertical_graph` panels the settings go to.
    """

    def __init__(self, parent: Any | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Graph Parameters")
        make_modeless(self)
        self._window = parent
        layout = QVBoxLayout(self)
        layout.setMenuBar(self._build_menus())

        grid = QGridLayout()
        self.grid_check = QCheckBox("Grid")
        grid.addWidget(self.grid_check, 0, 0)
        grid.addWidget(QLabel("Size"), 1, 0)
        self.size_entry = QLineEdit()
        grid.addWidget(self.size_entry, 1, 1)
        grid.addWidget(QLabel("Thickness"), 2, 0)
        self.thickness_entry = QLineEdit()
        grid.addWidget(self.thickness_entry, 2, 1)
        self.show_horizontal = QCheckBox("Horizontal Graph")
        self.show_vertical = QCheckBox("Vertical Graph")
        grid.addWidget(self.show_horizontal, 3, 0)
        grid.addWidget(self.show_vertical, 3, 1)
        layout.addLayout(grid)

        self.message = QLabel()
        layout.addWidget(self.message)

        buttons = QHBoxLayout()
        for label, slot in (("Apply", self.apply), ("Close", self.close)):
            button = QPushButton(label)
            button.clicked.connect(lambda _checked=False, s=slot: s())
            buttons.addWidget(button)
        layout.addLayout(buttons)
        self.sync()

    def _build_menus(self) -> QMenuBar:
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

        axis = bar.addMenu("&Axis")
        self._axis = QActionGroup(self)
        self.axis_actions: dict[str, QAction] = {}
        for name, label in (("linear", "Linear"), ("log", "Log")):
            action = QAction(label, self, checkable=True)
            self._axis.addAction(action)
            axis.addAction(action)
            action.triggered.connect(lambda _checked=False, n=name: self._each("set_log", n == "log"))
            self.axis_actions[name] = action

        method = bar.addMenu("&Method")
        self._method = QActionGroup(self)
        self.method_actions: dict[str, QAction] = {}
        for name in ("average", "sum", "median"):
            action = QAction(name.title(), self, checkable=True)
            self._method.addAction(action)
            method.addAction(action)
            action.triggered.connect(lambda _checked=False, n=name: self._each("set_method", n))
            self.method_actions[name] = action
        return bar

    def _graphs(self) -> list:
        return [
            graph
            for graph in (getattr(self._window, "horizontal_graph", None), getattr(self._window, "vertical_graph", None))
            if graph is not None
        ]

    def _each(self, method: str, value) -> None:
        for graph in self._graphs():
            getattr(graph, method)(value)

    def sync(self) -> None:
        """Show the settings in force."""
        graphs = self._graphs()
        if not graphs:
            return
        settings = graphs[0].settings
        self.grid_check.setChecked(bool(settings.grid))
        self.size_entry.setText(str(settings.size))
        self.thickness_entry.setText(str(settings.thickness))
        self.axis_actions["log" if settings.log else "linear"].setChecked(True)
        self.method_actions.get(settings.method, self.method_actions["average"]).setChecked(True)
        self.show_horizontal.setChecked(graphs[0].isVisible())
        self.show_vertical.setChecked(len(graphs) > 1 and graphs[1].isVisible())

    def apply(self) -> None:
        """DS9's Apply: grid, size and thickness to both graphs."""
        try:
            size, thickness = int(self.size_entry.text()), int(self.thickness_entry.text())
        except ValueError:
            self.message.setText("Size and thickness are whole numbers.")
            return
        if size < 1 or thickness < 1:
            self.message.setText("Size and thickness are at least 1.")
            return
        self.message.clear()
        self._each("set_grid", self.grid_check.isChecked())
        self._each("set_size", size)
        self._each("set_thickness", thickness)
        analysis = getattr(self._window, "analysis", None)
        if analysis is not None:
            horizontal, vertical = self.show_horizontal.isChecked(), self.show_vertical.isChecked()
            mode = {(True, True): "Both", (True, False): "Horizontal", (False, True): "Vertical"}.get(
                (horizontal, vertical), "None"
            )
            analysis.set_graph_visibility(mode)
