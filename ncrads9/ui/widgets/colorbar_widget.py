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
Colorbar widget showing current colormap.

Author: Yogesh Wadadekar
"""

from typing import Optional
import numpy as np
from PyQt6.QtCore import Qt, QSize
from PyQt6.QtGui import QImage, QPixmap, QPainter, QFont
from PyQt6.QtWidgets import QWidget, QVBoxLayout, QLabel


class ColorbarWidget(QWidget):
    """Widget displaying a colorbar with scale values."""

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        """
        Initialize the colorbar widget.

        Args:
            parent: Optional parent widget.
        """
        super().__init__(parent)
        self.colormap_data = None
        self.vmin = 0.0
        self.vmax = 1.0
        self.colormap_name = "grey"
        self.inverted = False
        
        self.setMinimumSize(120, 200)  # Wider for labels
        self.setMaximumWidth(150)
        
        layout = QVBoxLayout()
        layout.setContentsMargins(5, 5, 5, 5)
        
        # Colormap name label
        self.name_label = QLabel(self.colormap_name)
        self.name_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.name_label)
        
        # Colorbar display
        self.colorbar_label = QLabel()
        self.colorbar_label.setMinimumHeight(150)
        layout.addWidget(self.colorbar_label, 1)
        
        self.setLayout(layout)

    def set_colormap(
        self, colormap_data: np.ndarray, vmin: float, vmax: float, name: str, inverted: bool = False
    ) -> None:
        """
        Set the colormap to display.

        Args:
            colormap_data: RGB colormap data (256, 3).
            vmin: Minimum data value.
            vmax: Maximum data value.
            name: Colormap name.
            inverted: Whether colormap is inverted.
        """
        self.colormap_data = colormap_data
        self.vmin = vmin
        self.vmax = vmax
        self.colormap_name = name
        self.inverted = inverted
        
        # Update name label
        name_display = f"{name} (inv)" if inverted else name
        self.name_label.setText(name_display)
        
        # Create colorbar image with ticks
        self._update_colorbar()

    def _update_colorbar(self) -> None:
        """Update the colorbar display with ticks and labels."""
        if self.colormap_data is None:
            return
        
        # Create vertical colorbar image (width x height)
        bar_width = 40
        tick_width = 60  # Extra space for ticks and labels
        height = self.colorbar_label.height() or 150
        
        # Ensure colormap data is uint8 (0-255 range)
        if self.colormap_data.dtype == np.float64 or self.colormap_data.dtype == np.float32:
            # Convert from 0-1 to 0-255
            cmap_uint8 = (self.colormap_data * 255).astype(np.uint8)
        else:
            cmap_uint8 = self.colormap_data.astype(np.uint8)
        
        # Create gradient by repeating colormap vertically
        colorbar = np.zeros((height, bar_width, 3), dtype=np.uint8)
        
        # Map height pixels to 256 colormap entries (flip for top=max)
        indices = np.linspace(255, 0, height).astype(int)
        for i, idx in enumerate(indices):
            colorbar[i, :] = cmap_uint8[idx]
        
        # Convert to QImage and QPixmap
        qimage = QImage(
            colorbar.tobytes(),  # Use tobytes for PyQt6
            bar_width,
            height,
            bar_width * 3,
            QImage.Format.Format_RGB888,
        )
        pixmap = QPixmap.fromImage(qimage)
        
        # Create a larger pixmap with space for ticks and labels
        full_width = bar_width + tick_width
        full_pixmap = QPixmap(full_width, height)
        full_pixmap.fill(Qt.GlobalColor.transparent)
        
        # Draw colorbar
        painter = QPainter(full_pixmap)
        painter.drawPixmap(0, 0, pixmap)
        
        # Draw tick marks and labels (7 ticks total for good spacing)
        num_ticks = 7
        tick_length = 5
        font = QFont("Arial", 8)
        painter.setFont(font)
        
        for i in range(num_ticks):
            # Calculate position from top (0) to bottom (height-1)
            y_pos = int(i * (height - 1) / (num_ticks - 1))
            
            # Calculate value (top = vmax, bottom = vmin)
            value = self.vmax - (self.vmax - self.vmin) * i / (num_ticks - 1)
            
            # Draw tick mark
            painter.drawLine(bar_width, y_pos, bar_width + tick_length, y_pos)
            
            # Draw label
            label = f"{value:.3g}"
            painter.drawText(bar_width + tick_length + 2, y_pos + 4, label)
        
        painter.end()
        
        self.colorbar_label.setPixmap(full_pixmap)
    
    def resizeEvent(self, event) -> None:
        """Handle resize events."""
        super().resizeEvent(event)
        if self.colormap_data is not None:
            self._update_colorbar()
