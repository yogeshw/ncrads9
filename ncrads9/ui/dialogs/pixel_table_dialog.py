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
Pixel table dialog for examining pixel values.

Author: Yogesh Wadadekar
"""


import numpy as np
from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QComboBox,
    QDialog,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from ...analysis.pixel_table import PixelTable

#: The table sizes DS9 offers (`ds9/library/pixel.tcl:72`).
TABLE_SIZES: tuple[int, ...] = (3, 5, 7, 9)

#: Which of them it opens at.
DEFAULT_TABLE_SIZE = 5


class PixelTableDialog(QDialog):
    """Dialog showing pixel values in a table."""

    def __init__(
        self,
        image_data: np.ndarray,
        x: int,
        y: int,
        size: int = DEFAULT_TABLE_SIZE,
        parent: QWidget | None = None,
        wcs_handler=None,
    ) -> None:
        """
        Initialize the pixel table dialog.

        Args:
            image_data: The image data.
            x: Center x coordinate.
            y: Center y coordinate.
            size: One of DS9's sizes -- 3, 5, 7 or 9. Anything else falls
                back to the default rather than being rounded, since a
                4x4 table has no centre pixel to be a table *about*.
            parent: Optional parent widget.
            wcs_handler: The frame's WCS, so the centre pixel can be
                reported in sky coordinates as DS9 does.
        """
        # Pass None as parent to make dialog independent
        super().__init__(None)

        # Set window flags for independent draggable window
        # An ordinary, movable, non-modal window. It used to carry
        # `WindowStaysOnTopHint`, which is what made it impossible to get
        # out of the way: it floated over the image whatever the user did,
        # could not be sent behind the main window, and on a small screen
        # there was nowhere to put it. The min/max buttons are asked for
        # too, since naming flags explicitly replaces the default set and
        # dropped them.
        self.setWindowFlags(
            Qt.WindowType.Window
            | Qt.WindowType.WindowTitleHint
            | Qt.WindowType.WindowSystemMenuHint
            | Qt.WindowType.WindowMinMaxButtonsHint
            | Qt.WindowType.WindowCloseButtonHint
        )
        self.setWindowModality(Qt.WindowModality.NonModal)

        self.image_data = image_data
        self.center_x = x
        self.center_y = y
        self.size = size if size in TABLE_SIZES else DEFAULT_TABLE_SIZE
        #: The reader `analysis/pixel_table.py` provides -- it already does
        #: the bounds checking and the world-coordinate lookup, which this
        #: dialog used to do again by hand (M7-26).
        self.reader = PixelTable(image_data) if image_data is not None else None
        self.wcs_handler = wcs_handler

        self.setWindowTitle("Pixel Table")
        self.setMinimumSize(600, 400)

        self._setup_ui()
        self._populate_table()

    def _setup_ui(self) -> None:
        """Set up the user interface."""
        layout = QVBoxLayout()

        # Title
        self._title = QLabel()
        self._title.setStyleSheet("font-weight: bold; font-size: 14px;")
        layout.addWidget(self._title)

        #: The centre pixel's coordinates, in image and in sky.
        self._coordinates = QLabel()
        layout.addWidget(self._coordinates)

        # DS9 offers 3x3 up to 9x9 (`pixel.tcl:72`).
        size_row = QHBoxLayout()
        size_row.addWidget(QLabel("Size:"))
        self._size_combo = QComboBox()
        self._size_combo.addItems([f"{size}x{size}" for size in TABLE_SIZES])
        self._size_combo.setCurrentText(f"{self.size}x{self.size}")
        self._size_combo.currentTextChanged.connect(self._on_size_changed)
        size_row.addWidget(self._size_combo)
        size_row.addStretch()
        layout.addLayout(size_row)

        # Table widget
        self.table = QTableWidget()
        self.table.setColumnCount(self.size)
        self.table.setRowCount(self.size)
        layout.addWidget(self.table)

        # Buttons
        button_layout = QHBoxLayout()
        button_layout.addStretch()

        close_button = QPushButton("Close")
        close_button.clicked.connect(self.accept)
        button_layout.addWidget(close_button)

        layout.addLayout(button_layout)
        self.setLayout(layout)

    def _on_size_changed(self, label: str) -> None:
        """Switch to another of DS9's table sizes."""
        self.size = int(label.split("x")[0])
        self.table.setColumnCount(self.size)
        self.table.setRowCount(self.size)
        self._populate_table()

    def set_center(self, x: int, y: int) -> None:
        """Move the table to another pixel, which is how DS9 tracks the cursor."""
        self.center_x = int(x)
        self.center_y = int(y)
        self._populate_table()

    def _populate_table(self) -> None:
        """Fill the table from `PixelTable`, which does the bounds checking."""
        self._title.setText(f"Pixel Values at ({self.center_x}, {self.center_y})")
        self._coordinates.setText(self._describe_center())

        if self.reader is None:
            return

        half = self.size // 2
        self.table.setHorizontalHeaderLabels(
            [str(self.center_x - half + index) for index in range(self.size)]
        )
        self.table.setVerticalHeaderLabels([str(self.center_y - half + index) for index in range(self.size)])

        values = self.reader.get_region(self.center_x, self.center_y, self.size)
        for row in range(self.size):
            for column in range(self.size):
                value = values[row, column] if values.shape == (self.size, self.size) else np.nan
                # A pixel off the edge of the image comes back as NaN, which
                # reads as "--" rather than as a data value of nan.
                text = "--" if not np.isfinite(value) else f"{value:.6g}"
                item = QTableWidgetItem(text)
                if row == half and column == half:
                    item.setBackground(Qt.GlobalColor.yellow)
                item.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
                self.table.setItem(row, column, item)

        self.table.resizeColumnsToContents()

    def _describe_center(self) -> str:
        """The centre pixel's coordinates, and its sky position if there is one."""
        parts = [f"Image: {self.center_x} {self.center_y}"]
        if self.reader is not None:
            value = self.reader.get_pixel(self.center_x, self.center_y)
            parts.append("Value: --" if value is None or not np.isfinite(value) else f"Value: {value:.6g}")
        if self.wcs_handler is not None and getattr(self.wcs_handler, "is_valid", False):
            try:
                longitude, latitude = self.wcs_handler.pixel_to_world(self.center_x, self.center_y)
                parts.append(f"WCS: {float(longitude):.6f} {float(latitude):.6f}")
            except Exception:
                pass
        return "    ".join(parts)
