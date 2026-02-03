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
Histogram dialog for image analysis.

Author: Yogesh Wadadekar
"""

from typing import Optional
import numpy as np
from PyQt6.QtWidgets import (
    QDialog,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QWidget,
)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QPainter, QPen, QColor
from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg
from matplotlib.figure import Figure


class HistogramDialog(QDialog):
    """Dialog showing image histogram."""

    def __init__(
        self, image_data: np.ndarray, parent: Optional[QWidget] = None
    ) -> None:
        """
        Initialize the histogram dialog.

        Args:
            image_data: The image data to analyze.
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
        self.setWindowTitle("Image Histogram")
        self.setMinimumSize(600, 400)
        
        self._setup_ui()
        self._plot_histogram()

    def _setup_ui(self) -> None:
        """Set up the user interface."""
        layout = QVBoxLayout()
        
        # Title
        title = QLabel("Image Histogram")
        title.setStyleSheet("font-weight: bold; font-size: 14px;")
        layout.addWidget(title)
        
        # Matplotlib canvas for histogram
        self.figure = Figure(figsize=(8, 5))
        self.canvas = FigureCanvasQTAgg(self.figure)
        layout.addWidget(self.canvas)
        
        # Buttons
        button_layout = QHBoxLayout()
        button_layout.addStretch()
        
        close_button = QPushButton("Close")
        close_button.clicked.connect(self.accept)
        button_layout.addWidget(close_button)
        
        layout.addLayout(button_layout)
        self.setLayout(layout)

    def _plot_histogram(self) -> None:
        """Plot the histogram."""
        if self.image_data is None or self.image_data.size == 0:
            return
        
        # Remove NaN and Inf values
        valid_data = self.image_data[np.isfinite(self.image_data)].flatten()
        
        if valid_data.size == 0:
            return
        
        # Create histogram
        ax = self.figure.add_subplot(111)
        ax.clear()
        
        # Compute histogram with 256 bins
        counts, bins, patches = ax.hist(valid_data, bins=256, color='steelblue', 
                                         edgecolor='none', alpha=0.7)
        
        # Set labels
        ax.set_xlabel('Pixel Value')
        ax.set_ylabel('Frequency')
        ax.set_title(f'Histogram ({valid_data.size} pixels)')
        ax.grid(True, alpha=0.3)
        
        # Add statistics text
        stats_text = (
            f'Min: {np.min(valid_data):.3g}\n'
            f'Max: {np.max(valid_data):.3g}\n'
            f'Mean: {np.mean(valid_data):.3g}\n'
            f'Median: {np.median(valid_data):.3g}'
        )
        ax.text(0.98, 0.97, stats_text,
                transform=ax.transAxes,
                verticalalignment='top',
                horizontalalignment='right',
                bbox=dict(boxstyle='round', facecolor='wheat', alpha=0.5),
                fontsize=9)
        
        self.figure.tight_layout()
        self.canvas.draw()
