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
DS9's Tile Parameters, and its Display Size.

Two small dialogs off Frame Parameters (`frame.tcl:2178` and
`layout.tcl:1132`). Tile Parameters is the grid the frames are laid out
in; Display Size is how large the image display itself is, which matters
when a figure has to come out at a particular size.

Author: Yogesh Wadadekar
"""

from __future__ import annotations

from PyQt6.QtWidgets import (
    QButtonGroup,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QRadioButton,
    QSpinBox,
    QVBoxLayout,
)

from ...frames.tile_layout import TileSettings


class TileParametersDialog(QDialog):
    """The grid the tiled frames are laid out in."""

    def __init__(self, controller, parent=None) -> None:
        """
        Args:
            controller: The `FrameController` this drives.
            parent: The main window.
        """
        super().__init__(parent)
        self._controller = controller
        self.setWindowTitle("Tile Parameters")

        layout = QVBoxLayout(self)

        self._automatic = QRadioButton("Automatic")
        self._manual = QRadioButton("Manual")
        grid_group = QButtonGroup(self)
        grid_group.addButton(self._automatic)
        grid_group.addButton(self._manual)
        layout.addWidget(self._group("Grid", [self._automatic, self._manual]))

        self._x = QRadioButton("X")
        self._y = QRadioButton("Y")
        direction_group = QButtonGroup(self)
        direction_group.addButton(self._x)
        direction_group.addButton(self._y)
        layout.addWidget(self._group("Direction", [self._x, self._y]))

        self._columns = QSpinBox()
        self._columns.setRange(1, 100)
        self._rows = QSpinBox()
        self._rows.setRange(1, 100)
        shape = QFormLayout()
        shape.addRow("Columns:", self._columns)
        shape.addRow("Rows:", self._rows)
        holder = QGroupBox("Layout")
        holder.setLayout(shape)
        layout.addWidget(holder)
        self._layout_group = holder

        self._gap = QSpinBox()
        self._gap.setRange(0, 200)
        gap_row = QHBoxLayout()
        gap_row.addWidget(self._gap)
        gap_row.addWidget(QLabel("Pixels"))
        gap_holder = QGroupBox("Gap")
        gap_holder.setLayout(gap_row)
        layout.addWidget(gap_holder)

        self._manual.toggled.connect(lambda _checked=False: self.update_state())

        buttons = QHBoxLayout()
        #: Button name -> the button, so a test can press one.
        self.buttons: dict[str, QPushButton] = {}
        for name, label, slot in (("apply", "Apply", self.apply), ("close", "Close", self.close)):
            button = QPushButton(label)
            button.clicked.connect(slot)
            buttons.addWidget(button)
            self.buttons[name] = button
        layout.addLayout(buttons)

        self.reload()

    @staticmethod
    def _group(title: str, buttons: list[QRadioButton]) -> QGroupBox:
        """One of DS9's labelled rows of choices."""
        holder = QGroupBox(title)
        row = QHBoxLayout()
        for button in buttons:
            row.addWidget(button)
        holder.setLayout(row)
        return holder

    def reload(self) -> None:
        """Fill the dialog in from the settings."""
        settings = self._controller.tile_settings
        self._automatic.setChecked(not settings.manual)
        self._manual.setChecked(settings.manual)
        self._x.setChecked(settings.direction != "y")
        self._y.setChecked(settings.direction == "y")
        self._rows.setValue(max(1, settings.rows))
        self._columns.setValue(max(1, settings.columns))
        self._gap.setValue(max(0, settings.gap))
        self.update_state()

    def update_state(self) -> None:
        """The grid's shape is only asked for when it is not automatic."""
        self._layout_group.setEnabled(self._manual.isChecked())

    def settings(self) -> TileSettings:
        """What the dialog says the grid is."""
        return TileSettings(
            manual=self._manual.isChecked(),
            rows=self._rows.value(),
            columns=self._columns.value(),
            direction="y" if self._y.isChecked() else "x",
            gap=self._gap.value(),
        )

    def apply(self) -> None:
        """Lay the frames out as the dialog says."""
        self._controller.apply_tile_settings(self.settings())


class DisplaySizeDialog(QDialog):
    """How large the image display is, in pixels."""

    def __init__(self, width: int, height: int, parent=None) -> None:
        """
        Args:
            width: The display's width now.
            height: Its height now.
            parent: The main window.
        """
        super().__init__(parent)
        self.setWindowTitle("Display Size")

        layout = QVBoxLayout(self)
        form = QFormLayout()
        self._x = QSpinBox()
        self._x.setRange(1, 100_000)
        self._x.setValue(max(1, int(width)))
        self._y = QSpinBox()
        self._y.setRange(1, 100_000)
        self._y.setValue(max(1, int(height)))
        form.addRow("X:", self._wrap(self._x))
        form.addRow("Y:", self._wrap(self._y))
        layout.addLayout(form)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    @staticmethod
    def _wrap(box: QSpinBox) -> QGroupBox:
        """One box with DS9's `Pixels` beside it."""
        holder = QGroupBox()
        holder.setFlat(True)
        row = QHBoxLayout(holder)
        row.setContentsMargins(0, 0, 0, 0)
        row.addWidget(box)
        row.addWidget(QLabel("Pixels"))
        return holder

    def size(self) -> tuple[int, int]:
        """The size the dialog asks for."""
        return (self._x.value(), self._y.value())

    def choose(self) -> tuple[int, int] | None:
        """Ask, and say what was chosen, or None if it was cancelled."""
        if self.exec() != QDialog.DialogCode.Accepted:
            return None
        return self.size()
