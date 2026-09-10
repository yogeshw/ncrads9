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
DS9's Centroid Parameters dialog: the iteration count and the radius.

Two numbers, and they are the two the algorithm takes -- how far around a
region to look for flux, and how many times to walk towards it
(`ds9/library/mregion.tcl:418`).

Author: Yogesh Wadadekar
"""

from __future__ import annotations

from PyQt6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QDoubleSpinBox,
    QFormLayout,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from ...analysis.centroid import DEFAULT_ITERATIONS, DEFAULT_RADIUS

#: The widest aperture the dialog offers, in pixels.
MAX_RADIUS = 1000.0

#: The most passes it offers. More than this is a hang, not a setting.
MAX_ITERATIONS = 1000


class CentroidDialog(QDialog):
    """Ask for the centroid radius and iteration count.

    Args:
        radius: The aperture radius currently in use, in pixels.
        iterations: How many passes the walk currently makes.
        parent: Optional parent widget.
    """

    def __init__(
        self,
        radius: float = DEFAULT_RADIUS,
        iterations: int = DEFAULT_ITERATIONS,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle("Centroid Parameters")

        layout = QVBoxLayout(self)
        form = QFormLayout()
        layout.addLayout(form)

        self._iterations = QSpinBox()
        self._iterations.setRange(1, MAX_ITERATIONS)
        self._iterations.setValue(int(iterations))
        form.addRow("Iteration:", self._iterations)

        self._radius = QDoubleSpinBox()
        self._radius.setRange(0.5, MAX_RADIUS)
        self._radius.setDecimals(2)
        self._radius.setValue(float(radius))
        form.addRow("Radius:", self._radius)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def values(self) -> tuple[float, int]:
        """The radius and iteration count the user chose."""
        return (float(self._radius.value()), int(self._iterations.value()))
