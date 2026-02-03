# NCRADS9 - VO Query Dialog
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
VO query dialog for SIAP and catalog queries.

Author: Yogesh Wadadekar
"""

from typing import Optional, Tuple

from PyQt6.QtWidgets import (
    QDialog,
    QVBoxLayout,
    QFormLayout,
    QDoubleSpinBox,
    QDialogButtonBox,
)

from ..widgets.coordinate_entry import CoordinateEntry


class VOQueryDialog(QDialog):
    """Dialog for entering VO query parameters."""

    def __init__(
        self,
        parent: Optional[QDialog] = None,
        ra: Optional[float] = None,
        dec: Optional[float] = None,
        radius_deg: float = 0.1,
        title: str = "VO Query",
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle(title)
        self.setMinimumWidth(350)
        self._setup_ui(ra, dec, radius_deg)

    def _setup_ui(
        self,
        ra: Optional[float],
        dec: Optional[float],
        radius_deg: float,
    ) -> None:
        layout = QVBoxLayout(self)
        form = QFormLayout()

        self._coord_entry = CoordinateEntry(self)
        if ra is not None and dec is not None:
            self._coord_entry.setCoordinates(ra, dec)
        form.addRow("Coordinates:", self._coord_entry)

        self._radius_spin = QDoubleSpinBox()
        self._radius_spin.setRange(0.0001, 10.0)
        self._radius_spin.setDecimals(4)
        self._radius_spin.setValue(radius_deg)
        self._radius_spin.setSuffix(" deg")
        form.addRow("Radius:", self._radius_spin)

        layout.addLayout(form)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def values(self) -> Tuple[float, float, float]:
        """Return (ra, dec, radius_deg)."""
        ra, dec = self._coord_entry.coordinates()
        radius = self._radius_spin.value()
        return ra, dec, radius
