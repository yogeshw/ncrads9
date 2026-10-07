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

The position row is DS9's (`crosshair.tcl:177`): two entries and a
coordinate menu button, so the crosshair can be read and placed in WCS (any
of `wcs`, `wcsa`..`wcsz`, in any sky frame and format), image, physical,
amplifier or detector coordinates. The dialog follows the crosshair while it
is open, as DS9's `UpdateCrosshairDialog` does.

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
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSlider,
    QVBoxLayout,
    QWidget,
)

from ...communication.xpa import positions
from ..controllers.crosshair import COLORS
from ..widgets.coord_menu_button import CoordEntry, CoordMenuButton

#: The longest crosshair arm the dialog offers, in pixels.
MAX_SIZE = 200


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
        row = QHBoxLayout()
        self._x = CoordEntry()
        self._y = CoordEntry()
        #: DS9's `crosshair system sky skyformat`.
        self.system = CoordMenuButton(self, other=1)
        self.system.changed.connect(self.reload)
        row.addWidget(self._x)
        row.addWidget(self._y)
        row.addWidget(self.system)
        form.addRow("Crosshair:", row)

        self._sky = QLabel()
        form.addRow("WCS:", self._sky)
        self._value = QLabel()
        form.addRow("Value:", self._value)

        move = QPushButton("Apply")
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

            frame = self.controller.frame
            if frame is not None and getattr(frame, "image_data", None) is not None:
                self.system.adjust_to_frame(frame)
            else:
                self.system.reset()
            placed = self.controller.position()
            if placed is None:
                self._x.clear()
                self._y.clear()
            else:
                words = positions.from_image(
                    frame,
                    placed[0],
                    placed[1],
                    self.system.system,
                    self.system.sky,
                    self.system.sky_format,
                    digits=10,
                ).split()
                self._x.setText(words[0] if words else "")
                self._y.setText(words[1] if len(words) > 1 else "")
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

    def apply_position(self) -> bool:
        """Move the crosshair to the typed coordinates, in the menu's system.

        Returns:
            Whether they could be read.
        """
        try:
            x, y = positions.to_image(
                self.controller.frame,
                self._x.text().strip(),
                self._y.text().strip(),
                self.system.system,
                self.system.sky,
            )
        except (ValueError, TypeError) as exc:
            self._sky.setText(f"Cannot apply: {exc}")
            return False
        self.controller.move_to(x, y)
        self.reload()
        return True

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
