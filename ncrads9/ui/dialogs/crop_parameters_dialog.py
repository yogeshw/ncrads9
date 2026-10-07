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

Laid out as DS9's is (`crop.tcl:82`), with the same Apply, Reset and Close,
and the same three menu buttons: the centre in any coordinate system, the
size in pixels or an angle, and the 3D range in image slices or the slice
axis's world coordinate. Changing a menu rewrites the current crop in the
new system, as DS9's `UpdateCropDialog` does.

Author: Yogesh Wadadekar
"""

from __future__ import annotations

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QDialog,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
)

from ...communication.xpa import positions
from ..widgets.coord_menu_button import CoordEntry, CoordMenuButton, DistMenuButton

#: Entry width in characters, DS9's `-width 14`.
ENTRY_WIDTH = 14


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
        self.setMinimumWidth(420)
        self._build()
        self.reload()

    def _build(self) -> None:
        """Lay the dialog out."""
        layout = QVBoxLayout(self)
        grid = QGridLayout()

        self._center_x = self._entry()
        self._center_y = self._entry()
        #: DS9's `crop system sky skyformat`.
        self.center_system = CoordMenuButton(self, other=1)
        self._row(grid, 0, "Center", self._center_x, self._center_y, self.center_system)

        self._width = self._entry()
        self._height = self._entry()
        #: DS9's `crop dcoord dformat`.
        self.size_system = DistMenuButton(self)
        self._row(grid, 1, "Size", self._width, self._height, self.size_system)

        # DS9 shows the 3d row only for a cube; ours is always there and says
        # so, because the row is where you learn the feature exists.
        self._z_low = self._entry()
        self._z_high = self._entry()
        #: DS9's `crop rcoord`: image slices or the slice axis's WCS.
        self.range_system = CoordMenuButton(self, other=2, sky=False, sky_format=False)
        self._row(grid, 2, "3D", self._z_low, self._z_high, self.range_system)

        for button in (self.center_system, self.size_system, self.range_system):
            button.changed.connect(self.reload)

        layout.addLayout(grid)

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

    @staticmethod
    def _entry() -> CoordEntry:
        """One of the dialog's coordinate boxes."""
        entry = CoordEntry()
        entry.setMinimumWidth(entry.fontMetrics().averageCharWidth() * ENTRY_WIDTH)
        return entry

    @staticmethod
    def _row(grid: QGridLayout, row: int, title: str, first, second, menu) -> None:
        grid.addWidget(QLabel(title), row, 0)
        grid.addWidget(first, row, 1)
        grid.addWidget(second, row, 2)
        grid.addWidget(menu, row, 3)

    # -- what it shows ---------------------------------------------------------

    def _cube(self):
        """The current frame's cube handler, or None."""
        cube = getattr(self._controller, "cube", None)
        return cube() if callable(cube) else None

    def _range_key(self) -> str:
        """The WCS letter of the 3D menu's system, "" for the primary."""
        return self.range_system.system[3:]

    def _adjust_menus(self, frame) -> None:
        """Grey out the WCSs the frame lacks, and fall back as DS9 does."""
        if frame is None or getattr(frame, "image_data", None) is None:
            for button in (self.center_system, self.size_system, self.range_system):
                button.reset()
            return
        self.center_system.adjust_to_frame(frame)
        self.size_system.adjust_to_frame(frame)
        cube = self._cube()
        order = getattr(frame, "axis_order", "123")

        def has_3d(system: str) -> bool:
            return cube is not None and cube.image_to_world_z(1, order, system[3:]) is not None

        self.range_system.adjust(has_3d, fallback="image", celestial=lambda _name: False)

    def reload(self) -> None:
        """Fill the dialog in from the frame, in the chosen systems."""
        frame = self._controller.frame
        self._adjust_menus(frame)
        shape = self._controller.shape()
        crop = self._controller.region()
        if shape is None:
            self._summary.setText("No image loaded.")
            for entry in (
                self._center_x,
                self._center_y,
                self._width,
                self._height,
                self._z_low,
                self._z_high,
            ):
                entry.clear()
            return

        if crop is None:
            center_x, center_y = shape[1] / 2.0 + 0.5, shape[0] / 2.0 + 0.5
            width, height = float(shape[1]), float(shape[0])
            self._summary.setText(f"Whole image: {shape[1]} x {shape[0]} pixels.")
        else:
            center_x, center_y = crop.center
            width, height = crop.width, crop.height
            self._summary.setText(f"Cropped to {width:g} x {height:g} pixels of {shape[1]} x {shape[0]}.")

        centre = self.center_system
        words = positions.from_image(
            frame, center_x, center_y, centre.system, centre.sky, centre.sky_format, digits=10
        ).split()
        self._center_x.setText(words[0] if words else "")
        self._center_y.setText(words[1] if len(words) > 1 else "")

        size = self.size_system
        shown_w, shown_h = positions.distance_from_image(
            frame, width, height, size.system, size.distance_format
        )
        self._width.setValue(shown_w)
        self._height.setValue(shown_h)

        z_range = getattr(frame, "crop_z", None) if frame is not None else None
        if self.range_system.system == "image":
            low, high = z_range if z_range else (0.0, 0.0)
            self._z_low.setValue(low)
            self._z_high.setValue(high)
        elif z_range:
            self._z_low.setValue(self._z_to_world(z_range[0]))
            self._z_high.setValue(self._z_to_world(z_range[1]))
        else:
            # No slice crop: empty, so Apply leaves it that way.
            self._z_low.clear()
            self._z_high.clear()

    def _z_to_world(self, z: float) -> float:
        cube = self._cube()
        order = getattr(self._controller.frame, "axis_order", "123")
        world = cube.image_to_world_z(z, order, self._range_key()) if cube is not None else None
        return z if world is None else world[0]

    def _z_to_image(self, value: float) -> float:
        cube = self._cube()
        order = getattr(self._controller.frame, "axis_order", "123")
        z = cube.world_to_image_z(value, order, self._range_key()) if cube is not None else None
        if z is None:
            raise ValueError(f"the cube has no {self.range_system.system} slice coordinates")
        return z

    # -- what its buttons do ----------------------------------------------------

    def apply_crop(self) -> bool:
        """Crop to the typed centre and size, read in the chosen systems.

        Returns:
            Whether the typed values could be read.
        """
        from ...frames.crop import CropRegion

        frame = self._controller.frame
        # Every box is read before anything is applied: applying refills the
        # dialog from the frame, which would otherwise wipe the row that has
        # not been read yet.
        try:
            centre = self.center_system
            center_x, center_y = positions.to_image(
                frame, self._center_x.text().strip(), self._center_y.text().strip(), centre.system, centre.sky
            )
            size = self.size_system
            width, height = positions.distance_to_image(
                frame, self._width.value(), self._height.value(), size.system, size.distance_format
            )
            z_range = self._typed_range()
        except (ValueError, TypeError) as exc:
            self._summary.setText(f"Cannot apply: {exc}")
            return False

        wanted = CropRegion.from_center(center_x, center_y, width, height)
        self._controller.set_region(wanted)
        self._controller.set_slice_range(*z_range)
        self.reload()
        return True

    def _typed_range(self) -> tuple[float | None, float | None]:
        """The 3D row as image slices; (None, None) for no slice crop."""
        low_text, high_text = self._z_low.text().strip(), self._z_high.text().strip()
        if not low_text or not high_text:
            return None, None
        low, high = float(low_text), float(high_text)
        if self.range_system.system == "image":
            return (None, None) if low == high == 0.0 else (low, high)
        return self._z_to_image(low), self._z_to_image(high)

    def reset_crop(self) -> None:
        """Go back to displaying the whole image."""
        self._controller.reset()
        self._controller.set_slice_range(None, None)
        self.reload()
