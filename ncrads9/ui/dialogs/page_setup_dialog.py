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
DS9's Page Setup: orientation, scale, and the page's size.

Laid out as DS9's is (`pagesetup.tcl`), with its two groups and its own
list of sizes -- poster included, because people print mosaics on plotters.

Author: Yogesh Wadadekar
"""

from __future__ import annotations

from PyQt6.QtWidgets import (
    QButtonGroup,
    QDialog,
    QDialogButtonBox,
    QDoubleSpinBox,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QRadioButton,
    QVBoxLayout,
)

from ...printing.page_setup import PAPER_INCHES, Orientation, PageSetup, PaperSize

#: Each size and the label DS9 gives it.
SIZE_LABELS: tuple[tuple[PaperSize, str], ...] = (
    (PaperSize.LETTER, "Letter (8.5 x 11 in)"),
    (PaperSize.LEGAL, "Legal (8.5 x 14 in)"),
    (PaperSize.TABLOID, "Tabloid (11 x 17 in)"),
    (PaperSize.POSTER, "Poster (36 x 48 in)"),
    (PaperSize.A4, "A4 (210 x 297 mm)"),
    (PaperSize.OTHER, "Other (inches)"),
    (PaperSize.OTHER_MM, "Other (mm)"),
)


class PageSetupDialog(QDialog):
    """Asks what page to print on."""

    def __init__(self, setup: PageSetup | None = None, parent=None) -> None:
        """
        Args:
            setup: What to start from.
            parent: The main window.
        """
        super().__init__(parent)
        self.setWindowTitle("Page Setup")
        layout = QVBoxLayout(self)

        # Grouped explicitly, as on the Print dialog: two radio buttons in
        # different rows are not exclusive by themselves.
        self._orientation_group = QButtonGroup(self)
        self._portrait = QRadioButton("Portrait")
        self._landscape = QRadioButton("Landscape")
        self._orientation_group.addButton(self._portrait)
        self._orientation_group.addButton(self._landscape)
        self._scale = QDoubleSpinBox()
        self._scale.setRange(1.0, 1000.0)
        self._scale.setDecimals(1)
        self._scale.setSuffix(" %")

        orientation = QHBoxLayout()
        orientation.addWidget(self._portrait)
        orientation.addWidget(self._landscape)
        layout_group = QGroupBox("Layout")
        form = QFormLayout(layout_group)
        holder = QLabel()
        holder.setLayout(orientation)
        form.addRow("Orientation:", holder)
        form.addRow("Scale:", self._scale)
        layout.addWidget(layout_group)

        size_group = QGroupBox("Page Size")
        size_column = QVBoxLayout(size_group)
        self._size_group = QButtonGroup(self)
        #: Paper size -> its radio button.
        self.size_buttons: dict[PaperSize, QRadioButton] = {}
        for size, label in SIZE_LABELS:
            button = QRadioButton(label)
            button.toggled.connect(lambda _checked=False: self.update_state())
            size_column.addWidget(button)
            self._size_group.addButton(button)
            self.size_buttons[size] = button

        self._width = QDoubleSpinBox()
        self._width.setRange(0.1, 1000.0)
        self._height = QDoubleSpinBox()
        self._height.setRange(0.1, 1000.0)
        typed = QFormLayout()
        typed.addRow("Width:", self._width)
        typed.addRow("Height:", self._height)
        size_column.addLayout(typed)
        layout.addWidget(size_group)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

        self.load(setup or PageSetup())

    def load(self, setup: PageSetup) -> None:
        """Fill the dialog in."""
        self._portrait.setChecked(setup.orientation is Orientation.PORTRAIT)
        self._landscape.setChecked(setup.orientation is Orientation.LANDSCAPE)
        self._scale.setValue(setup.scale)
        self.size_buttons[setup.paper_size].setChecked(True)
        self._width.setValue(setup.width)
        self._height.setValue(setup.height)
        self.update_state()

    def update_state(self) -> None:
        """The typed size is only for the two `Other` choices."""
        typed = (
            self.size_buttons[PaperSize.OTHER].isChecked()
            or self.size_buttons[PaperSize.OTHER_MM].isChecked()
        )
        self._width.setEnabled(typed)
        self._height.setEnabled(typed)
        if not typed:
            # Show what the chosen size is, so the boxes are never stale.
            for size, button in self.size_buttons.items():
                if button.isChecked() and size in PAPER_INCHES:
                    inches = PAPER_INCHES[size]
                    self._width.setValue(inches[0])
                    self._height.setValue(inches[1])

    def setup(self) -> PageSetup:
        """What the dialog says the page is."""
        chosen = next(
            (size for size, button in self.size_buttons.items() if button.isChecked()),
            PaperSize.LETTER,
        )
        return PageSetup(
            paper_size=chosen,
            orientation=Orientation.LANDSCAPE if self._landscape.isChecked() else Orientation.PORTRAIT,
            scale=self._scale.value(),
            width=self._width.value(),
            height=self._height.value(),
        )

    def choose(self) -> PageSetup | None:
        """Ask, and say what was chosen, or None if it was cancelled."""
        if self.exec() != QDialog.DialogCode.Accepted:
            return None
        return self.setup()
