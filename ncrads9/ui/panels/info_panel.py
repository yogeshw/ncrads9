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
Info panel showing cursor coordinates, pixel values, and WCS info.

Author: Yogesh Wadadekar
"""

from typing import Optional, Any

import numpy as np
from numpy.typing import NDArray
from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QDockWidget,
    QWidget,
    QVBoxLayout,
    QGridLayout,
    QLabel,
    QGroupBox,
)


class InfoPanel(QDockWidget):
    """Dockable panel showing cursor coordinates, pixel values, and WCS info."""

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        """
        Initialize the info panel.

        Args:
            parent: Parent widget.
        """
        super().__init__("Info", parent)
        self.setObjectName("InfoPanel")

        self._wcs: Optional[Any] = None
        self._current_image: Optional[NDArray[np.float64]] = None

        self._setup_ui()

    def _setup_ui(self) -> None:
        """Set up the user interface."""
        container = QWidget()
        layout = QVBoxLayout(container)

        # Pixel coordinates group
        pixel_group = QGroupBox("Pixel Coordinates")
        pixel_layout = QGridLayout(pixel_group)

        pixel_layout.addWidget(QLabel("X:"), 0, 0)
        self._x_label = QLabel("---")
        self._x_label.setAlignment(Qt.AlignmentFlag.AlignRight)
        pixel_layout.addWidget(self._x_label, 0, 1)

        pixel_layout.addWidget(QLabel("Y:"), 1, 0)
        self._y_label = QLabel("---")
        self._y_label.setAlignment(Qt.AlignmentFlag.AlignRight)
        pixel_layout.addWidget(self._y_label, 1, 1)

        layout.addWidget(pixel_group)

        # Pixel value group
        value_group = QGroupBox("Pixel Value")
        value_layout = QGridLayout(value_group)

        value_layout.addWidget(QLabel("Value:"), 0, 0)
        self._value_label = QLabel("---")
        self._value_label.setAlignment(Qt.AlignmentFlag.AlignRight)
        value_layout.addWidget(self._value_label, 0, 1)

        layout.addWidget(value_group)

        # WCS coordinates group
        wcs_group = QGroupBox("WCS Coordinates")
        wcs_layout = QGridLayout(wcs_group)

        wcs_layout.addWidget(QLabel("RA:"), 0, 0)
        self._ra_label = QLabel("---")
        self._ra_label.setAlignment(Qt.AlignmentFlag.AlignRight)
        wcs_layout.addWidget(self._ra_label, 0, 1)

        wcs_layout.addWidget(QLabel("Dec:"), 1, 0)
        self._dec_label = QLabel("---")
        self._dec_label.setAlignment(Qt.AlignmentFlag.AlignRight)
        wcs_layout.addWidget(self._dec_label, 1, 1)

        wcs_layout.addWidget(QLabel("Galactic l:"), 2, 0)
        self._gal_l_label = QLabel("---")
        self._gal_l_label.setAlignment(Qt.AlignmentFlag.AlignRight)
        wcs_layout.addWidget(self._gal_l_label, 2, 1)

        wcs_layout.addWidget(QLabel("Galactic b:"), 3, 0)
        self._gal_b_label = QLabel("---")
        self._gal_b_label.setAlignment(Qt.AlignmentFlag.AlignRight)
        wcs_layout.addWidget(self._gal_b_label, 3, 1)

        layout.addWidget(wcs_group)

        # Image statistics group
        stats_group = QGroupBox("Image Statistics")
        stats_layout = QGridLayout(stats_group)

        stats_layout.addWidget(QLabel("Min:"), 0, 0)
        self._min_label = QLabel("---")
        self._min_label.setAlignment(Qt.AlignmentFlag.AlignRight)
        stats_layout.addWidget(self._min_label, 0, 1)

        stats_layout.addWidget(QLabel("Max:"), 1, 0)
        self._max_label = QLabel("---")
        self._max_label.setAlignment(Qt.AlignmentFlag.AlignRight)
        stats_layout.addWidget(self._max_label, 1, 1)

        stats_layout.addWidget(QLabel("Mean:"), 2, 0)
        self._mean_label = QLabel("---")
        self._mean_label.setAlignment(Qt.AlignmentFlag.AlignRight)
        stats_layout.addWidget(self._mean_label, 2, 1)

        stats_layout.addWidget(QLabel("Std:"), 3, 0)
        self._std_label = QLabel("---")
        self._std_label.setAlignment(Qt.AlignmentFlag.AlignRight)
        stats_layout.addWidget(self._std_label, 3, 1)

        layout.addWidget(stats_group)

        layout.addStretch()
        self.setWidget(container)

    def set_image(self, image: NDArray[np.float64]) -> None:
        """
        Set the image data.

        Args:
            image: 2D numpy array of image data.
        """
        self._current_image = image
        self._update_statistics()

    def set_wcs(self, wcs: Any) -> None:
        """
        Set the WCS object for coordinate conversion.

        Args:
            wcs: Astropy WCS object.
        """
        self._wcs = wcs

    def update_cursor_position(self, x: float, y: float) -> None:
        """
        Update displayed info for cursor position.

        Args:
            x: X coordinate in image pixels.
            y: Y coordinate in image pixels.
        """
        # Update pixel coordinates
        self._x_label.setText(f"{x:.2f}")
        self._y_label.setText(f"{y:.2f}")

        # Update pixel value
        if self._current_image is not None:
            ix, iy = int(x), int(y)
            h, w = self._current_image.shape[:2]
            if 0 <= ix < w and 0 <= iy < h:
                value = self._current_image[iy, ix]
                self._value_label.setText(f"{value:.6g}")
            else:
                self._value_label.setText("---")
        else:
            self._value_label.setText("---")

        # Update WCS coordinates
        self._update_wcs_coordinates(x, y)

    def _update_wcs_coordinates(self, x: float, y: float) -> None:
        """Update WCS coordinate display."""
        if self._wcs is None:
            self._ra_label.setText("---")
            self._dec_label.setText("---")
            self._gal_l_label.setText("---")
            self._gal_b_label.setText("---")
            return

        try:
            # Convert pixel to world coordinates
            from astropy.coordinates import SkyCoord
            import astropy.units as u

            world = self._wcs.pixel_to_world(x, y)
            if hasattr(world, "ra") and hasattr(world, "dec"):
                ra_str = world.ra.to_string(unit=u.hour, sep=":", precision=2)
                dec_str = world.dec.to_string(unit=u.deg, sep=":", precision=2)
                self._ra_label.setText(ra_str)
                self._dec_label.setText(dec_str)

                # Convert to Galactic
                galactic = world.galactic
                self._gal_l_label.setText(f"{galactic.l.deg:.4f}°")
                self._gal_b_label.setText(f"{galactic.b.deg:.4f}°")
            else:
                self._ra_label.setText("---")
                self._dec_label.setText("---")
                self._gal_l_label.setText("---")
                self._gal_b_label.setText("---")
        except Exception:
            self._ra_label.setText("Error")
            self._dec_label.setText("Error")
            self._gal_l_label.setText("Error")
            self._gal_b_label.setText("Error")

    def _update_statistics(self) -> None:
        """Update image statistics display."""
        if self._current_image is None:
            self._min_label.setText("---")
            self._max_label.setText("---")
            self._mean_label.setText("---")
            self._std_label.setText("---")
            return

        self._min_label.setText(f"{np.nanmin(self._current_image):.6g}")
        self._max_label.setText(f"{np.nanmax(self._current_image):.6g}")
        self._mean_label.setText(f"{np.nanmean(self._current_image):.6g}")
        self._std_label.setText(f"{np.nanstd(self._current_image):.6g}")
