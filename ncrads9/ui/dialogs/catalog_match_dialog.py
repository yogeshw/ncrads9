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
DS9's Catalog Match dialog, `CATMatchDialog` in `catmatch.tcl`.

One window: Match <catalog> and <catalog>, Error with its unit, Function
(1 and 2, 1 not 2, 2 not 1) with Unique beside it, and Return (1 and 2,
1 only, 2 only). Unique and Return mean something only to `1 and 2`, so
they are disabled for the other two functions, as DS9 disables them.

Author: Yogesh Wadadekar
"""

from __future__ import annotations

from dataclasses import dataclass

from PyQt6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QDoubleSpinBox,
    QGridLayout,
    QLabel,
    QVBoxLayout,
    QWidget,
)

from ...catalogs import sky_position

#: DS9's Function menu: value, label.
FUNCTIONS: tuple[tuple[str, str], ...] = (("1and2", "1 and 2"), ("1not2", "1 not 2"), ("2not1", "2 not 1"))

#: DS9's Return menu: value, label.
RETURNS: tuple[tuple[str, str], ...] = (("1and2", "1 and 2"), ("1only", "1 only"), ("2only", "2 only"))


@dataclass
class MatchParameters:
    """What the dialog asks for."""

    first: str
    second: str
    radius_arcsec: float
    function: str = "1and2"
    unique: bool = True
    returned: str = "1and2"


class CatalogMatchDialog(QDialog):
    """Ask which two catalogues to match, and how.

    Args:
        names: The loaded catalogues, by name.
        parameters: The values to start from -- the last match's, as DS9's
            `icat` keeps them.
        parent: Optional parent widget.
    """

    def __init__(
        self,
        names: list[str],
        parameters: MatchParameters | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle("Match")
        start = parameters or MatchParameters(
            names[0] if names else "", names[1] if len(names) > 1 else "", 2.0
        )

        layout = QVBoxLayout(self)
        grid = QGridLayout()
        layout.addLayout(grid)

        grid.addWidget(QLabel("Match"), 0, 0)
        self.first = QComboBox()
        self.first.addItems(names)
        grid.addWidget(self.first, 0, 1)
        grid.addWidget(QLabel("and"), 0, 2)
        self.second = QComboBox()
        self.second.addItems(names)
        grid.addWidget(self.second, 0, 3)
        if start.first in names:
            self.first.setCurrentText(start.first)
        if start.second in names:
            self.second.setCurrentText(start.second)
        elif len(names) > 1:
            self.second.setCurrentIndex(1)

        grid.addWidget(QLabel("Error"), 1, 0)
        self.error = QDoubleSpinBox()
        self.error.setDecimals(4)
        self.error.setRange(0.0001, 360000.0)
        grid.addWidget(self.error, 1, 1)
        self.unit = QComboBox()
        self.unit.addItems(sky_position.RADIUS_UNITS)
        self.unit.setCurrentText("arcsec")
        self.error.setValue(float(start.radius_arcsec))
        self._unit_shown = "arcsec"
        self.unit.currentTextChanged.connect(self._convert)
        grid.addWidget(self.unit, 1, 3)

        grid.addWidget(QLabel("Function"), 2, 0)
        self.function = QComboBox()
        for value, label in FUNCTIONS:
            self.function.addItem(label, value)
        self.function.setCurrentIndex(max(0, self.function.findData(start.function)))
        grid.addWidget(self.function, 2, 1)
        self.unique = QCheckBox("Unique")
        self.unique.setChecked(bool(start.unique))
        grid.addWidget(self.unique, 2, 3)

        grid.addWidget(QLabel("Return"), 3, 0)
        self.returned = QComboBox()
        for value, label in RETURNS:
            self.returned.addItem(label, value)
        self.returned.setCurrentIndex(max(0, self.returned.findData(start.returned)))
        grid.addWidget(self.returned, 3, 1)

        self.function.currentIndexChanged.connect(lambda _index: self._enable())
        self._enable()

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def _enable(self) -> None:
        """Unique and Return apply to `1 and 2` only (`CATMatchDialogFunctionMenu`)."""
        both = self.function.currentData() == "1and2"
        self.unique.setEnabled(both)
        self.returned.setEnabled(both)

    def _convert(self, unit: str) -> None:
        """Keep the same angle when the unit changes."""
        angle = sky_position.radius_quantity(self.error.value(), self._unit_shown)
        self._unit_shown = unit
        self.error.setValue(sky_position.radius_in(angle, unit))

    def radius_arcsec(self) -> float:
        """The match error, in arcseconds."""
        return sky_position.radius_in(
            sky_position.radius_quantity(self.error.value(), self.unit.currentText()), "arcsec"
        )

    def values(self) -> MatchParameters:
        """What was chosen."""
        return MatchParameters(
            first=self.first.currentText(),
            second=self.second.currentText(),
            radius_arcsec=self.radius_arcsec(),
            function=str(self.function.currentData()),
            unique=self.unique.isChecked(),
            returned=str(self.returned.currentData()),
        )
