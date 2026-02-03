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
Statistics dialog for image analysis.

Author: Yogesh Wadadekar
"""

from typing import Optional
import numpy as np
from PyQt6.QtWidgets import (
    QDialog,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QTextEdit,
    QPushButton,
    QWidget,
)
from PyQt6.QtCore import Qt


class StatisticsDialog(QDialog):
    """Dialog showing image statistics."""

    def __init__(
        self, image_data: np.ndarray, parent: Optional[QWidget] = None
    ) -> None:
        """
        Initialize the statistics dialog.

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
        self.setWindowTitle("Image Statistics")
        self.setMinimumSize(400, 300)
        
        self._setup_ui()
        self._compute_statistics()

    def _setup_ui(self) -> None:
        """Set up the user interface."""
        layout = QVBoxLayout()
        
        # Title
        title = QLabel("Image Statistics")
        title.setStyleSheet("font-weight: bold; font-size: 14px;")
        layout.addWidget(title)
        
        # Statistics display
        self.stats_text = QTextEdit()
        self.stats_text.setReadOnly(True)
        self.stats_text.setMinimumHeight(200)
        layout.addWidget(self.stats_text)
        
        # Buttons
        button_layout = QHBoxLayout()
        button_layout.addStretch()
        
        close_button = QPushButton("Close")
        close_button.clicked.connect(self.accept)
        button_layout.addWidget(close_button)
        
        layout.addLayout(button_layout)
        self.setLayout(layout)

    def _compute_statistics(self) -> None:
        """Compute and display statistics."""
        if self.image_data is None or self.image_data.size == 0:
            self.stats_text.setText("No image data available")
            return
        
        # Remove NaN and Inf values for statistics
        valid_data = self.image_data[np.isfinite(self.image_data)]
        
        if valid_data.size == 0:
            self.stats_text.setText("No valid pixel values in image")
            return
        
        # Compute statistics
        stats = {
            "Image Dimensions": f"{self.image_data.shape[1]} x {self.image_data.shape[0]}",
            "Total Pixels": f"{self.image_data.size}",
            "Valid Pixels": f"{valid_data.size}",
            "Invalid Pixels": f"{self.image_data.size - valid_data.size}",
            "": "",
            "Minimum": f"{np.min(valid_data):.6g}",
            "Maximum": f"{np.max(valid_data):.6g}",
            "Mean": f"{np.mean(valid_data):.6g}",
            "Median": f"{np.median(valid_data):.6g}",
            "Std Dev": f"{np.std(valid_data):.6g}",
            " ": "",
            "Sum": f"{np.sum(valid_data):.6g}",
            "25th Percentile": f"{np.percentile(valid_data, 25):.6g}",
            "75th Percentile": f"{np.percentile(valid_data, 75):.6g}",
        }
        
        # Format as text
        text = ""
        for key, value in stats.items():
            if key:
                text += f"{key:20s}: {value}\n"
            else:
                text += "\n"
        
        self.stats_text.setText(text)
