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
What a raw array needs told: its dimensions, its numbers, its header.

A raw array is pixels and nothing else, so unlike every other import this
one cannot work it out. DS9 asks in a dialog of exactly these fields
(`ds9/library/array.tcl`, and the Array section of `file.html`), and takes
the same values in the filename -- so this dialog is seeded from a
specification when the filename carried one.

Author: Yogesh Wadadekar
"""

from __future__ import annotations

from PyQt6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QLabel,
    QSpinBox,
    QVBoxLayout,
)

from ...io.array_reader import BITPIX_TYPES, ArraySpec

#: The BITPIX values DS9's dialog offers, in its order.
BITPIX_CHOICES: tuple[int, ...] = (8, 16, -16, 32, 64, -32, -64)

#: What each one is, for the menu's labels.
BITPIX_LABELS: dict[int, str] = {
    8: "8 (unsigned byte)",
    16: "16 (short)",
    -16: "-16 (unsigned short)",
    32: "32 (int)",
    64: "64 (long)",
    -32: "-32 (float)",
    -64: "-64 (double)",
}


class ArrayDialog(QDialog):
    """Asks for an array's shape and number format."""

    def __init__(self, spec: ArraySpec | None = None, parent=None, exporting: bool = False) -> None:
        """
        Args:
            spec: What to start from -- a specification from the filename,
                from `$DS9_ARRAY`, or None for DS9's defaults.
            parent: The main window.
            exporting: Whether this is Export, which chooses only the byte
                order because the dimensions are the frame's.
        """
        super().__init__(parent)
        self.setWindowTitle("Export Array" if exporting else "Import Array")
        self._exporting = exporting

        layout = QVBoxLayout(self)
        layout.addWidget(
            QLabel(
                "A raw array holds no header, so its shape has to be given."
                if not exporting
                else "A raw array holds no header, so note these to read it back."
            )
        )
        form = QFormLayout()

        self._x = QSpinBox()
        self._x.setRange(1, 1_000_000)
        self._y = QSpinBox()
        self._y.setRange(1, 1_000_000)
        self._z = QSpinBox()
        self._z.setRange(1, 100_000)
        self._skip = QSpinBox()
        self._skip.setRange(0, 1_000_000)

        self._bitpix = QComboBox()
        for value in BITPIX_CHOICES:
            self._bitpix.addItem(BITPIX_LABELS[value], value)

        self._little = QCheckBox("Little-endian (Intel)")

        if not exporting:
            form.addRow("X dimension:", self._x)
            form.addRow("Y dimension:", self._y)
            form.addRow("Z dimension:", self._z)
            form.addRow("Header bytes to skip:", self._skip)
            form.addRow("BITPIX:", self._bitpix)
        form.addRow("", self._little)
        layout.addLayout(form)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

        self.load(spec)

    def load(self, spec: ArraySpec | None) -> None:
        """Fill the dialog in from a specification."""
        if spec is None:
            self._x.setValue(512)
            self._y.setValue(512)
            self._z.setValue(1)
            self._bitpix.setCurrentIndex(BITPIX_CHOICES.index(-32))
            return
        self._x.setValue(max(1, spec.xdim))
        self._y.setValue(max(1, spec.ydim))
        self._z.setValue(max(1, spec.zdim))
        self._skip.setValue(max(0, spec.skip))
        if spec.bitpix in BITPIX_TYPES:
            self._bitpix.setCurrentIndex(BITPIX_CHOICES.index(spec.bitpix))
        self._little.setChecked(not spec.big_endian)

    def spec(self) -> ArraySpec:
        """What the dialog says the array is."""
        return ArraySpec(
            xdim=self._x.value(),
            ydim=self._y.value(),
            zdim=self._z.value(),
            bitpix=int(self._bitpix.currentData()),
            skip=self._skip.value(),
            big_endian=not self._little.isChecked(),
        )

    def choose(self) -> ArraySpec | None:
        """Ask, and say what was chosen, or None if it was cancelled."""
        if self.exec() != QDialog.DialogCode.Accepted:
            return None
        return self.spec()
