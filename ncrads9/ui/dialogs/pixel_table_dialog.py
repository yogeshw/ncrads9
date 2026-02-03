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

from typing import Optional
import numpy as np
from PyQt6.QtWidgets import (
    QDialog,
    QVBoxLayout,
    QHBoxLayout,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QLabel,
    QWidget,
)
from PyQt6.QtCore import Qt


class PixelTableDialog(QDialog):
    """Dialog showing pixel values in a table."""

    def __init__(
        self, image_data: np.ndarray, x: int, y: int, size: int = 11, 
        parent: Optional[QWidget] = None
    ) -> None:
        """
        Initialize the pixel table dialog.

        Args:
            image_data: The image data.
            x: Center x coordinate.
            y: Center y coordinate.
            size: Size of region to display (odd number).
            parent: Optional parent widget.
        """
        # Pass None as parent to make dialog independent
        super().__init__(None)
        
        # Set window flags for independent draggable window
        self.setWindowFlags(
            Qt.WindowType.Window |
            Qt.WindowType.WindowCloseButtonHint |
            Qt.WindowType.WindowTitleHint |
            Qt.WindowType.WindowStaysOnTopHint
        )
        self.setWindowModality(Qt.WindowModality.NonModal)
        
        self.image_data = image_data
        self.center_x = x
        self.center_y = y
        self.size = size if size % 2 == 1 else size + 1  # Ensure odd
        
        self.setWindowTitle("Pixel Table")
        self.setMinimumSize(600, 400)
        
        self._setup_ui()
        self._populate_table()

    def _setup_ui(self) -> None:
        """Set up the user interface."""
        layout = QVBoxLayout()
        
        # Title
        title = QLabel(f"Pixel Values at ({self.center_x}, {self.center_y})")
        title.setStyleSheet("font-weight: bold; font-size: 14px;")
        layout.addWidget(title)
        
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

    def _populate_table(self) -> None:
        """Populate the table with pixel values."""
        if self.image_data is None or self.image_data.size == 0:
            return
        
        half = self.size // 2
        height, width = self.image_data.shape
        
        # Set headers
        col_headers = [str(self.center_x - half + i) for i in range(self.size)]
        row_headers = [str(self.center_y - half + i) for i in range(self.size)]
        self.table.setHorizontalHeaderLabels(col_headers)
        self.table.setVerticalHeaderLabels(row_headers)
        
        # Fill table
        for i in range(self.size):
            for j in range(self.size):
                y = self.center_y - half + i
                x = self.center_x - half + j
                
                if 0 <= y < height and 0 <= x < width:
                    value = self.image_data[y, x]
                    item = QTableWidgetItem(f"{value:.6g}")
                    
                    # Highlight center pixel
                    if i == half and j == half:
                        item.setBackground(Qt.GlobalColor.yellow)
                else:
                    item = QTableWidgetItem("--")
                
                item.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
                self.table.setItem(i, j, item)
        
        # Resize columns to content
        self.table.resizeColumnsToContents()
