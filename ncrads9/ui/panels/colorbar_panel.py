# This file is part of ncrads9.
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
Colorbar panel showing color scale with value labels.

Author: Yogesh Wadadekar
"""

from typing import Optional

import numpy as np
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QImage, QPixmap, QPainter, QFont, QColor, QLinearGradient
from PyQt6.QtWidgets import (
    QDockWidget,
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QComboBox,
)


class ColorbarPanel(QDockWidget):
    """Dockable panel showing colorbar with scale."""

    COLORMAPS: list[str] = [
        "grayscale",
        "viridis",
        "plasma",
        "inferno",
        "magma",
        "hot",
        "cool",
        "jet",
        "rainbow",
    ]

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        """
        Initialize the colorbar panel.

        Args:
            parent: Parent widget.
        """
        super().__init__("Colorbar", parent)
        self.setObjectName("ColorbarPanel")

        self._vmin: float = 0.0
        self._vmax: float = 1.0
        self._colormap: str = "grayscale"
        self._orientation: Qt.Orientation = Qt.Orientation.Vertical

        self._setup_ui()

    def _setup_ui(self) -> None:
        """Set up the user interface."""
        container = QWidget()
        layout = QVBoxLayout(container)

        # Colormap selector
        cmap_layout = QHBoxLayout()
        cmap_label = QLabel("Colormap:")
        self._cmap_combo = QComboBox()
        self._cmap_combo.addItems(self.COLORMAPS)
        self._cmap_combo.currentTextChanged.connect(self._on_colormap_changed)
        cmap_layout.addWidget(cmap_label)
        cmap_layout.addWidget(self._cmap_combo)
        layout.addLayout(cmap_layout)

        # Value labels
        self._max_label = QLabel("1.0")
        self._max_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self._max_label)

        # Colorbar display
        self._colorbar_label = QLabel()
        self._colorbar_label.setMinimumSize(50, 200)
        self._colorbar_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self._colorbar_label)

        self._min_label = QLabel("0.0")
        self._min_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self._min_label)

        layout.addStretch()
        self.setWidget(container)

        self._update_colorbar()

    def _on_colormap_changed(self, colormap: str) -> None:
        """Handle colormap selection change."""
        self._colormap = colormap
        self._update_colorbar()

    def set_range(self, vmin: float, vmax: float) -> None:
        """
        Set the value range for the colorbar.

        Args:
            vmin: Minimum value.
            vmax: Maximum value.
        """
        self._vmin = vmin
        self._vmax = vmax
        self._min_label.setText(f"{vmin:.4g}")
        self._max_label.setText(f"{vmax:.4g}")
        self._update_colorbar()

    def set_colormap(self, colormap: str) -> None:
        """
        Set the colormap.

        Args:
            colormap: Name of the colormap.
        """
        if colormap in self.COLORMAPS:
            self._colormap = colormap
            self._cmap_combo.setCurrentText(colormap)
            self._update_colorbar()

    def get_colormap(self) -> str:
        """
        Get the current colormap name.

        Returns:
            Current colormap name.
        """
        return self._colormap

    def _get_colormap_colors(self) -> list[tuple[int, int, int]]:
        """Get color list for current colormap."""
        colormaps: dict[str, list[tuple[int, int, int]]] = {
            "grayscale": [(0, 0, 0), (255, 255, 255)],
            "viridis": [(68, 1, 84), (59, 82, 139), (33, 145, 140), (94, 201, 98), (253, 231, 37)],
            "plasma": [(13, 8, 135), (126, 3, 168), (204, 71, 120), (248, 149, 64), (240, 249, 33)],
            "inferno": [(0, 0, 4), (87, 16, 110), (188, 55, 84), (249, 142, 9), (252, 255, 164)],
            "magma": [(0, 0, 4), (81, 18, 124), (183, 55, 121), (254, 159, 109), (252, 253, 191)],
            "hot": [(0, 0, 0), (128, 0, 0), (255, 128, 0), (255, 255, 0), (255, 255, 255)],
            "cool": [(0, 255, 255), (255, 0, 255)],
            "jet": [(0, 0, 128), (0, 0, 255), (0, 255, 255), (255, 255, 0), (255, 0, 0), (128, 0, 0)],
            "rainbow": [(128, 0, 255), (0, 0, 255), (0, 255, 255), (0, 255, 0), (255, 255, 0), (255, 0, 0)],
        }
        return colormaps.get(self._colormap, colormaps["grayscale"])

    def _update_colorbar(self) -> None:
        """Update the colorbar display."""
        width = 40
        height = 180

        # Create gradient image
        pixmap = QPixmap(width, height)
        painter = QPainter(pixmap)

        gradient = QLinearGradient(0, height, 0, 0)
        colors = self._get_colormap_colors()
        n_colors = len(colors)

        for i, (r, g, b) in enumerate(colors):
            pos = i / (n_colors - 1) if n_colors > 1 else 0.5
            gradient.setColorAt(pos, QColor(r, g, b))

        painter.fillRect(0, 0, width, height, gradient)
        painter.end()

        self._colorbar_label.setPixmap(pixmap)

    def apply_colormap(self, data: np.ndarray) -> np.ndarray:
        """
        Apply the current colormap to normalized data.

        Args:
            data: Normalized data array (0-1 range).

        Returns:
            RGB array with colormap applied.
        """
        colors = self._get_colormap_colors()
        n_colors = len(colors)

        # Create lookup table
        lut = np.zeros((256, 3), dtype=np.uint8)
        for i in range(256):
            t = i / 255.0
            idx = t * (n_colors - 1)
            idx_low = int(idx)
            idx_high = min(idx_low + 1, n_colors - 1)
            frac = idx - idx_low

            for c in range(3):
                lut[i, c] = int(
                    colors[idx_low][c] * (1 - frac) + colors[idx_high][c] * frac
                )

        # Apply LUT
        indices = (np.clip(data, 0, 1) * 255).astype(np.uint8)
        return lut[indices]
