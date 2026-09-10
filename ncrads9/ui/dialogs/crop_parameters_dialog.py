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
DS9's Crop Parameters dialog: a centre, a size, and a slice range.

Laid out as DS9's is (`crop.tcl:82`), with the same Apply, Reset and Close.

Author: Yogesh Wadadekar
"""

from __future__ import annotations

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QDialog,
    QDoubleSpinBox,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
)

#: How large a crop the spin boxes allow, which is larger than any image.
LIMIT = 1_000_000.0


class CropParametersDialog(QDialog):
    """Where the crop can be typed rather than dragged."""

    def __init__(self, controller, parent=None) -> None:
        """
        Args:
            controller: The `CropController` this dialog drives.
            parent: The main window.
        """
        super().__init__(parent)
        self._controller = controller
        self.setWindowTitle("Crop Parameters")
        self.setWindowModality(Qt.WindowModality.NonModal)
        self.setMinimumWidth(360)
        self._build()
        self.reload()

    def _build(self) -> None:
        """Lay the dialog out."""
        layout = QVBoxLayout(self)
        form = QFormLayout()

        self._center_x = self._number()
        self._center_y = self._number()
        centre = QHBoxLayout()
        centre.addWidget(self._center_x)
        centre.addWidget(self._center_y)
        form.addRow("Center:", centre)

        self._width = self._number(minimum=1.0, value=100.0)
        self._height = self._number(minimum=1.0, value=100.0)
        size = QHBoxLayout()
        size.addWidget(self._width)
        size.addWidget(self._height)
        form.addRow("Size:", size)

        # DS9 shows the 3d row only for a cube; ours is always there and says
        # so, because the row is where you learn the feature exists.
        self._z_low = self._number(minimum=0.0, value=0.0)
        self._z_high = self._number(minimum=0.0, value=0.0)
        slices = QHBoxLayout()
        slices.addWidget(self._z_low)
        slices.addWidget(self._z_high)
        form.addRow("3D slices:", slices)

        layout.addLayout(form)

        self._summary = QLabel()
        self._summary.setWordWrap(True)
        layout.addWidget(self._summary)

        buttons = QHBoxLayout()
        #: Button name -> the button, so a test can press one.
        self.buttons: dict[str, QPushButton] = {}
        for name, label, slot in (
            ("apply", "Apply", self.apply_crop),
            ("reset", "Reset", self.reset_crop),
            ("close", "Close", self.close),
        ):
            button = QPushButton(label)
            button.clicked.connect(slot)
            buttons.addWidget(button)
            self.buttons[name] = button
        layout.addLayout(buttons)

    def _number(
        self,
        minimum: float = -LIMIT,
        value: float = 0.0,
    ) -> QDoubleSpinBox:
        """One of the dialog's coordinate boxes."""
        box = QDoubleSpinBox()
        box.setRange(minimum, LIMIT)
        box.setDecimals(3)
        box.setValue(value)
        return box

    # -- what it shows ---------------------------------------------------------

    def reload(self) -> None:
        """Fill the dialog in from the frame."""
        shape = self._controller.shape()
        crop = self._controller.region()
        if shape is None:
            self._summary.setText("No image loaded.")
            return

        if crop is None:
            center_x, center_y = shape[1] / 2.0 + 0.5, shape[0] / 2.0 + 0.5
            width, height = float(shape[1]), float(shape[0])
            self._summary.setText(f"Whole image: {shape[1]} x {shape[0]} pixels.")
        else:
            center_x, center_y = crop.center
            width, height = crop.width, crop.height
            self._summary.setText(f"Cropped to {width:g} x {height:g} pixels of {shape[1]} x {shape[0]}.")

        frame = self._controller.frame
        z_range = getattr(frame, "crop_z", None) if frame is not None else None
        for box, value in (
            (self._center_x, center_x),
            (self._center_y, center_y),
            (self._width, width),
            (self._height, height),
            (self._z_low, z_range[0] if z_range else 0.0),
            (self._z_high, z_range[1] if z_range else 0.0),
        ):
            # Blocked, because setValue emits and a reload that emitted would
            # change the crop it is reporting.
            box.blockSignals(True)
            box.setValue(float(value))
            box.blockSignals(False)

    # -- what its buttons do ----------------------------------------------------

    def apply_crop(self) -> None:
        """Crop to the typed centre and size."""
        from ...frames.crop import CropRegion

        # Every box is read before anything is applied: applying refills the
        # dialog from the frame, which would otherwise wipe the row that has
        # not been read yet.
        wanted = CropRegion.from_center(
            self._center_x.value(),
            self._center_y.value(),
            self._width.value(),
            self._height.value(),
        )
        low, high = self._z_low.value(), self._z_high.value()

        self._controller.set_region(wanted)
        self._controller.set_slice_range(*(None, None) if low == high == 0.0 else (low, high))
        self.reload()

    def reset_crop(self) -> None:
        """Go back to displaying the whole image."""
        self._controller.reset()
        self._controller.set_slice_range(None, None)
        self.reload()
