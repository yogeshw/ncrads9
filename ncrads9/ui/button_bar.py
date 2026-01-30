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
DS9-style button bar for NCRADS9 application.

Author: Yogesh Wadadekar
"""

from typing import Optional

from PyQt6.QtCore import pyqtSignal
from PyQt6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QGroupBox,
    QPushButton,
    QButtonGroup,
)


class ButtonBar(QWidget):
    """DS9-style vertical button bar."""

    # Signals
    zoom_changed: pyqtSignal = pyqtSignal(str)
    scale_changed: pyqtSignal = pyqtSignal(str)
    colormap_changed: pyqtSignal = pyqtSignal(str)
    region_mode_changed: pyqtSignal = pyqtSignal(str)

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        """
        Initialize the button bar.

        Args:
            parent: Optional parent widget.
        """
        super().__init__(parent)

        self.main_layout = QVBoxLayout(self)
        self.main_layout.setContentsMargins(4, 4, 4, 4)
        self.main_layout.setSpacing(8)

        self._setup_zoom_buttons()
        self._setup_scale_buttons()
        self._setup_color_buttons()
        self._setup_region_buttons()

        self.main_layout.addStretch()

    def _setup_zoom_buttons(self) -> None:
        """Set up zoom buttons."""
        zoom_group = QGroupBox("Zoom")
        zoom_layout = QVBoxLayout(zoom_group)

        self.zoom_button_group = QButtonGroup(self)
        self.zoom_button_group.setExclusive(True)

        zoom_levels: list[str] = ["Fit", "1/4", "1/2", "1", "2", "4", "8"]
        self.zoom_buttons: dict[str, QPushButton] = {}

        for level in zoom_levels:
            btn = QPushButton(level)
            btn.setCheckable(True)
            self.zoom_buttons[level] = btn
            self.zoom_button_group.addButton(btn)
            zoom_layout.addWidget(btn)

        self.zoom_buttons["1"].setChecked(True)
        self.zoom_button_group.buttonClicked.connect(self._on_zoom_clicked)

        self.main_layout.addWidget(zoom_group)

    def _setup_scale_buttons(self) -> None:
        """Set up scale buttons."""
        scale_group = QGroupBox("Scale")
        scale_layout = QVBoxLayout(scale_group)

        self.scale_button_group = QButtonGroup(self)
        self.scale_button_group.setExclusive(True)

        scales: list[str] = ["Linear", "Log", "Sqrt", "Squared", "Asinh", "HistEq"]
        self.scale_buttons: dict[str, QPushButton] = {}

        for scale in scales:
            btn = QPushButton(scale)
            btn.setCheckable(True)
            self.scale_buttons[scale] = btn
            self.scale_button_group.addButton(btn)
            scale_layout.addWidget(btn)

        self.scale_buttons["Linear"].setChecked(True)
        self.scale_button_group.buttonClicked.connect(self._on_scale_clicked)

        self.main_layout.addWidget(scale_group)

    def _setup_color_buttons(self) -> None:
        """Set up colormap buttons."""
        color_group = QGroupBox("Color")
        color_layout = QVBoxLayout(color_group)

        self.color_button_group = QButtonGroup(self)
        self.color_button_group.setExclusive(True)

        colormaps: list[str] = ["Gray", "Heat", "Cool", "Rainbow"]
        self.color_buttons: dict[str, QPushButton] = {}

        for cmap in colormaps:
            btn = QPushButton(cmap)
            btn.setCheckable(True)
            self.color_buttons[cmap] = btn
            self.color_button_group.addButton(btn)
            color_layout.addWidget(btn)

        self.color_buttons["Gray"].setChecked(True)
        self.color_button_group.buttonClicked.connect(self._on_color_clicked)

        self.main_layout.addWidget(color_group)

    def _setup_region_buttons(self) -> None:
        """Set up region buttons."""
        region_group = QGroupBox("Region")
        region_layout = QVBoxLayout(region_group)

        self.region_button_group = QButtonGroup(self)
        self.region_button_group.setExclusive(True)

        regions: list[str] = ["None", "Circle", "Ellipse", "Box", "Polygon", "Line"]
        self.region_buttons: dict[str, QPushButton] = {}

        for region in regions:
            btn = QPushButton(region)
            btn.setCheckable(True)
            self.region_buttons[region] = btn
            self.region_button_group.addButton(btn)
            region_layout.addWidget(btn)

        self.region_buttons["None"].setChecked(True)
        self.region_button_group.buttonClicked.connect(self._on_region_clicked)

        self.main_layout.addWidget(region_group)

    def _on_zoom_clicked(self, button: QPushButton) -> None:
        """Handle zoom button click."""
        self.zoom_changed.emit(button.text())

    def _on_scale_clicked(self, button: QPushButton) -> None:
        """Handle scale button click."""
        self.scale_changed.emit(button.text())

    def _on_color_clicked(self, button: QPushButton) -> None:
        """Handle colormap button click."""
        self.colormap_changed.emit(button.text())

    def _on_region_clicked(self, button: QPushButton) -> None:
        """Handle region button click."""
        self.region_mode_changed.emit(button.text())

    def set_zoom(self, level: str) -> None:
        """
        Set the current zoom level.

        Args:
            level: Zoom level string.
        """
        if level in self.zoom_buttons:
            self.zoom_buttons[level].setChecked(True)

    def set_scale(self, scale: str) -> None:
        """
        Set the current scale.

        Args:
            scale: Scale name.
        """
        if scale in self.scale_buttons:
            self.scale_buttons[scale].setChecked(True)

    def set_colormap(self, colormap: str) -> None:
        """
        Set the current colormap.

        Args:
            colormap: Colormap name.
        """
        if colormap in self.color_buttons:
            self.color_buttons[colormap].setChecked(True)

    def set_region_mode(self, mode: str) -> None:
        """
        Set the current region mode.

        Args:
            mode: Region mode name.
        """
        if mode in self.region_buttons:
            self.region_buttons[mode].setChecked(True)
