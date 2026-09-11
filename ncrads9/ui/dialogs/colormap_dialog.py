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


import numpy as np
from numpy.typing import NDArray
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QColor, QImage, QPixmap
from PyQt6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QSlider,
    QVBoxLayout,
)

from ...colormaps.builtin_maps import get_builtin_colormap, list_builtin_colormaps


class ColormapDialog(QDialog):
    """Dialog for selecting and configuring colormaps."""

    colormap_changed = pyqtSignal(dict)

    # Standard astronomical colormaps
    COLORMAPS: list[str] = list(
        dict.fromkeys("gray" if cmap == "grey" else cmap for cmap in list_builtin_colormaps())
    )

    def __init__(self, parent: QDialog | None = None) -> None:
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
        # Selected *before* the signal is connected, and the preview drawn
        # once at the end of this method. Connecting first made
        # `setCurrentRow` fire `_on_colormap_selected` -> `_update_preview`
        # before `_invert_check` existed, so constructing this dialog
        # raised `AttributeError` and Color -> Colormap Parameters could
        # never be opened at all.
        if self.COLORMAPS:
            self._cmap_list.setCurrentRow(0)
            self._current_colormap = self._cmap_list.currentItem().text()
        self._cmap_list.currentItemChanged.connect(self._on_colormap_selected)
        cmap_layout.addWidget(self._cmap_list)

        layout.addWidget(cmap_group)

        # Preview
        preview_group = QGroupBox("Preview")
        preview_layout = QVBoxLayout(preview_group)

        self._preview_label = QLabel()
        self._preview_label.setMinimumHeight(50)
        self._preview_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
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

        # Everything the preview reads now exists.
        self._update_preview()

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
        """Draw a ramp through the chosen colormap, inverted and gammaed.

        It used to draw the same grey ramp whatever was selected, with a
        comment saying the real colormap "would use matplotlib" -- which
        `colormaps/` has done since M5. A preview that shows grey for
        `heat` is worse than no preview.
        """
        width, height = 400, 40
        ramp = np.linspace(0.0, 1.0, width, dtype=np.float64)
        if self._invert_check.isChecked():
            ramp = 1.0 - ramp
        gamma = max(0.1, self._gamma_slider.value() / 100.0)
        ramp = np.clip(ramp, 0.0, 1.0) ** gamma

        colours = self._ramp_colours(ramp)
        image = QImage(width, height, QImage.Format.Format_RGB32)
        for x in range(width):
            red, green, blue = (int(component) for component in colours[x])
            colour = QColor(red, green, blue)
            for y in range(height):
                image.setPixelColor(x, y, colour)

        self._preview_label.setPixmap(QPixmap.fromImage(image))

    def _ramp_colours(self, ramp: NDArray[np.floating]) -> NDArray[np.uint8]:
        """The ramp through the selected colormap, as RGB rows.

        Falls back to grey when the name is not one we hold, which is what
        a preview of an unknown colormap honestly is.
        """
        colormap = get_builtin_colormap(self._current_colormap)
        if colormap is None:
            grey = np.clip(ramp * 255.0, 0, 255).astype(np.uint8)
            return np.stack([grey, grey, grey], axis=-1)
        return colormap.apply_normalized(ramp)

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
