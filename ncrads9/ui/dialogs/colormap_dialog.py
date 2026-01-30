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
Colormap selection dialog.

Author: Yogesh Wadadekar
"""

from typing import Optional, List

from PyQt6.QtCore import pyqtSignal, Qt
from PyQt6.QtWidgets import (
    QDialog,
    QVBoxLayout,
    QHBoxLayout,
    QPushButton,
    QGroupBox,
    QFormLayout,
    QComboBox,
    QCheckBox,
    QListWidget,
    QListWidgetItem,
    QLabel,
    QSlider,
)
from PyQt6.QtGui import QPixmap, QImage, QPainter, QLinearGradient, QColor


class ColormapDialog(QDialog):
    """Dialog for selecting and configuring colormaps."""

    colormap_changed = pyqtSignal(dict)

    # Standard astronomical colormaps
    COLORMAPS: List[str] = [
        "gray",
        "heat",
        "cool",
        "rainbow",
        "viridis",
        "plasma",
        "inferno",
        "magma",
        "cividis",
        "jet",
        "hot",
        "copper",
        "bone",
        "cubehelix",
        "gist_heat",
        "gist_stern",
        "afmhot",
        "gnuplot",
        "gnuplot2",
        "CMRmap",
        "ocean",
        "terrain",
        "gist_earth",
        "gist_ncar",
        "spectral",
        "RdYlBu",
        "RdBu",
        "coolwarm",
        "seismic",
    ]

    def __init__(self, parent: Optional[QDialog] = None) -> None:
        """Initialize the colormap dialog.

        Args:
            parent: Parent widget.
        """
        super().__init__(parent)
        self.setWindowTitle("Colormap Selection")
        self.setMinimumSize(500, 600)
        self._current_colormap = "gray"
        self._setup_ui()

    def _setup_ui(self) -> None:
        """Set up the dialog UI."""
        layout = QVBoxLayout(self)

        # Colormap list
        cmap_group = QGroupBox("Colormaps")
        cmap_layout = QVBoxLayout(cmap_group)

        self._cmap_list = QListWidget()
        for cmap_name in self.COLORMAPS:
            item = QListWidgetItem(cmap_name)
            self._cmap_list.addItem(item)
        self._cmap_list.currentItemChanged.connect(self._on_colormap_selected)
        cmap_layout.addWidget(self._cmap_list)

        layout.addWidget(cmap_group)

        # Preview
        preview_group = QGroupBox("Preview")
        preview_layout = QVBoxLayout(preview_group)

        self._preview_label = QLabel()
        self._preview_label.setMinimumHeight(50)
        self._preview_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._update_preview()
        preview_layout.addWidget(self._preview_label)

        layout.addWidget(preview_group)

        # Options
        options_group = QGroupBox("Options")
        options_layout = QFormLayout(options_group)

        self._invert_check = QCheckBox("Invert colormap")
        self._invert_check.stateChanged.connect(self._on_option_changed)
        options_layout.addRow("", self._invert_check)

        self._gamma_slider = QSlider(Qt.Orientation.Horizontal)
        self._gamma_slider.setRange(10, 300)
        self._gamma_slider.setValue(100)
        self._gamma_slider.valueChanged.connect(self._on_option_changed)
        options_layout.addRow("Gamma:", self._gamma_slider)

        self._gamma_label = QLabel("1.00")
        options_layout.addRow("", self._gamma_label)

        self._stretch_combo = QComboBox()
        self._stretch_combo.addItems(["Linear", "Log", "Power", "Sqrt", "Asinh"])
        options_layout.addRow("Stretch:", self._stretch_combo)

        layout.addWidget(options_group)

        # Button row
        button_layout = QHBoxLayout()
        button_layout.addStretch()

        apply_btn = QPushButton("Apply")
        apply_btn.clicked.connect(self._apply)
        button_layout.addWidget(apply_btn)

        ok_btn = QPushButton("OK")
        ok_btn.clicked.connect(self._ok)
        button_layout.addWidget(ok_btn)

        cancel_btn = QPushButton("Cancel")
        cancel_btn.clicked.connect(self.reject)
        button_layout.addWidget(cancel_btn)

        layout.addLayout(button_layout)

    def _on_colormap_selected(self, current: QListWidgetItem, previous: QListWidgetItem) -> None:
        """Handle colormap selection.

        Args:
            current: Currently selected item.
            previous: Previously selected item.
        """
        if current:
            self._current_colormap = current.text()
            self._update_preview()

    def _on_option_changed(self) -> None:
        """Handle option change."""
        gamma = self._gamma_slider.value() / 100.0
        self._gamma_label.setText(f"{gamma:.2f}")
        self._update_preview()

    def _update_preview(self) -> None:
        """Update the colormap preview."""
        width = 400
        height = 40
        image = QImage(width, height, QImage.Format.Format_RGB32)

        # Create a simple gradient preview
        for x in range(width):
            value = int(255 * x / width)
            if self._invert_check.isChecked():
                value = 255 - value
            # Apply gamma
            gamma = self._gamma_slider.value() / 100.0
            value = int(255 * ((value / 255.0) ** gamma))

            # Simple grayscale for now - actual colormap would use matplotlib
            for y in range(height):
                image.setPixelColor(x, y, QColor(value, value, value))

        pixmap = QPixmap.fromImage(image)
        self._preview_label.setPixmap(pixmap)

    def _get_settings(self) -> dict:
        """Get current colormap settings.

        Returns:
            Dictionary of colormap settings.
        """
        return {
            "colormap": self._current_colormap,
            "invert": self._invert_check.isChecked(),
            "gamma": self._gamma_slider.value() / 100.0,
            "stretch": self._stretch_combo.currentText(),
        }

    def _apply(self) -> None:
        """Apply current settings."""
        self.colormap_changed.emit(self._get_settings())

    def _ok(self) -> None:
        """Apply settings and close dialog."""
        self._apply()
        self.accept()

    def get_colormap(self) -> str:
        """Get the selected colormap name.

        Returns:
            Selected colormap name.
        """
        return self._current_colormap
