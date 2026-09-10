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
DS9's Crosshair Parameters dialog.

Where the crosshair is, in image and in sky coordinates, and what it looks
like. The position is editable, which is the reason DS9's dialog exists:
typing a coordinate is how you put the crosshair somewhere exactly, and a
crosshair you can only drag is a crosshair you cannot place.

What it replaced: two `QInputDialog` prompts, the first asking whether the
crosshair should be on.

Author: Yogesh Wadadekar
"""

from __future__ import annotations

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QDoubleSpinBox,
    QFormLayout,
    QGroupBox,
    QLabel,
    QPushButton,
    QSlider,
    QVBoxLayout,
    QWidget,
)

from ..controllers.crosshair import COLORS

#: The longest crosshair arm the dialog offers, in pixels.
MAX_SIZE = 200

#: The largest image coordinate it offers.
MAX_COORDINATE = 100000.0


class CrosshairDialog(QDialog):
    """Place the crosshair and set its appearance.

    Args:
        controller: The crosshair controller, which owns the state.
        parent: Optional parent widget.
    """

    def __init__(self, controller, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Crosshair Parameters")
        self.controller = controller

        layout = QVBoxLayout(self)

        self._show = QCheckBox("Show crosshair")
        self._show.toggled.connect(self.controller.set_enabled)
        layout.addWidget(self._show)

        place = QGroupBox("Position")
        form = QFormLayout(place)
        self._x = QDoubleSpinBox()
        self._x.setRange(0.0, MAX_COORDINATE)
        self._x.setDecimals(3)
        form.addRow("Image x:", self._x)
        self._y = QDoubleSpinBox()
        self._y.setRange(0.0, MAX_COORDINATE)
        self._y.setDecimals(3)
        form.addRow("Image y:", self._y)

        self._sky = QLabel()
        form.addRow("WCS:", self._sky)
        self._value = QLabel()
        form.addRow("Value:", self._value)

        move = QPushButton("Move Crosshair Here")
        move.clicked.connect(self.apply_position)
        form.addRow("", move)
        centre = QPushButton("Centre")
        centre.clicked.connect(self._centre)
        form.addRow("", centre)
        layout.addWidget(place)

        look = QGroupBox("Appearance")
        form = QFormLayout(look)
        self._color = QComboBox()
        self._color.addItems(COLORS)
        self._color.currentTextChanged.connect(self._set_color)
        form.addRow("Colour:", self._color)

        self._size = QSlider(Qt.Orientation.Horizontal)
        self._size.setRange(4, MAX_SIZE)
        self._size.valueChanged.connect(self._set_size)
        form.addRow("Size:", self._size)

        self._lock = QCheckBox("Lock across frames")
        self._lock.toggled.connect(self.controller.set_locked)
        form.addRow("", self._lock)
        layout.addWidget(look)

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

        self.reload()

    def reload(self) -> None:
        """Show the crosshair's current state.

        Signals are blocked while filling in: `setValue` and `setChecked`
        emit, and a reload that emitted would move the crosshair it is
        reporting on.
        """
        for widget in (self._show, self._x, self._y, self._color, self._size, self._lock):
            widget.blockSignals(True)
        try:
            self._show.setChecked(self.controller.enabled)
            self._color.setCurrentText(self.controller.color)
            self._size.setValue(int(self.controller.size))
            self._lock.setChecked(self.controller.locked)

            placed = self.controller.position()
            if placed is not None:
                self._x.setValue(placed[0])
                self._y.setValue(placed[1])
        finally:
            for widget in (self._show, self._x, self._y, self._color, self._size, self._lock):
                widget.blockSignals(False)

        self._describe()

    def _describe(self) -> None:
        """Fill in the sky position and the pixel value."""
        placed = self.controller.position()
        if placed is None:
            self._sky.setText("(not placed)")
            self._value.setText("")
            return

        value = self.controller.value_at(*placed)
        self._value.setText("--" if value is None else f"{value:g}")

        frame = self.controller.frame
        handler = getattr(frame, "wcs_handler", None) if frame else None
        if handler is None or not getattr(handler, "is_valid", False):
            self._sky.setText("(no WCS)")
            return
        try:
            longitude, latitude = handler.pixel_to_world(*placed)
        except Exception:
            self._sky.setText("(no WCS)")
            return
        self._sky.setText(f"{float(longitude):.6f} {float(latitude):.6f}")

    def apply_position(self) -> None:
        """Move the crosshair to the typed coordinates."""
        self.controller.move_to(self._x.value(), self._y.value())
        self.reload()

    def _centre(self) -> None:
        """Put it in the middle of the frame."""
        self.controller.centre()
        self.reload()

    def _set_color(self, name: str) -> None:
        """Change its colour."""
        self.controller.color = name
        self.controller.refresh()

    def _set_size(self, size: int) -> None:
        """Change its arm length."""
        self.controller.size = int(size)
        self.controller.refresh()
