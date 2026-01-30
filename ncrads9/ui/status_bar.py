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
Status bar for NCRADS9 application.

Author: Yogesh Wadadekar
"""

from typing import Optional, Tuple

from PyQt6.QtWidgets import QStatusBar, QLabel, QWidget


class StatusBar(QStatusBar):
    """Status bar showing coordinates, pixel values, and image info."""

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        """
        Initialize the status bar.

        Args:
            parent: Optional parent widget.
        """
        super().__init__(parent)

        self._setup_widgets()

    def _setup_widgets(self) -> None:
        """Set up status bar widgets."""
        # Image coordinates (pixel)
        self.pixel_coord_label = QLabel("X: --- Y: ---")
        self.pixel_coord_label.setMinimumWidth(120)
        self.addPermanentWidget(self.pixel_coord_label)

        # WCS coordinates
        self.wcs_coord_label = QLabel("RA: --- Dec: ---")
        self.wcs_coord_label.setMinimumWidth(200)
        self.addPermanentWidget(self.wcs_coord_label)

        # Pixel value
        self.pixel_value_label = QLabel("Value: ---")
        self.pixel_value_label.setMinimumWidth(120)
        self.addPermanentWidget(self.pixel_value_label)

        # Image info (permanent widget on the right)
        self.image_info_label = QLabel("No image loaded")
        self.image_info_label.setMinimumWidth(200)
        self.addPermanentWidget(self.image_info_label)

        # Zoom level
        self.zoom_label = QLabel("Zoom: 1x")
        self.zoom_label.setMinimumWidth(80)
        self.addPermanentWidget(self.zoom_label)

    def update_pixel_coords(self, x: int, y: int) -> None:
        """
        Update pixel coordinates display.

        Args:
            x: X pixel coordinate.
            y: Y pixel coordinate.
        """
        self.pixel_coord_label.setText(f"X: {x:d} Y: {y:d}")

    def update_wcs_coords(
        self,
        ra: Optional[float] = None,
        dec: Optional[float] = None,
        format_type: str = "sexagesimal",
        labels: Tuple[str, str] = ("RA", "Dec"),
    ) -> None:
        """
        Update WCS coordinates display.

        Args:
            ra: Right ascension in degrees, or None if unavailable.
            dec: Declination in degrees, or None if unavailable.
        """
        if ra is not None and dec is not None:
            label_x, label_y = labels

            if format_type == "degrees":
                self.wcs_coord_label.setText(
                    f"{label_x}: {ra:.5f} deg {label_y}: {dec:.5f} deg"
                )
                return

            use_hours = label_x.lower() == "ra"
            if use_hours:
                ra_h = ra / 15.0
                ra_hours = int(ra_h)
                ra_min = int((ra_h - ra_hours) * 60)
                ra_sec = ((ra_h - ra_hours) * 60 - ra_min) * 60

                dec_sign = "+" if dec >= 0 else "-"
                dec_abs = abs(dec)
                dec_deg = int(dec_abs)
                dec_min = int((dec_abs - dec_deg) * 60)
                dec_sec = ((dec_abs - dec_deg) * 60 - dec_min) * 60

                self.wcs_coord_label.setText(
                    f"{label_x}: {ra_hours:02d}:{ra_min:02d}:{ra_sec:05.2f} "
                    f"{label_y}: {dec_sign}{dec_deg:02d}:{dec_min:02d}:{dec_sec:04.1f}"
                )
                return

            ra_sign = "+" if ra >= 0 else "-"
            ra_abs = abs(ra)
            ra_deg = int(ra_abs)
            ra_min = int((ra_abs - ra_deg) * 60)
            ra_sec = ((ra_abs - ra_deg) * 60 - ra_min) * 60

            dec_sign = "+" if dec >= 0 else "-"
            dec_abs = abs(dec)
            dec_deg = int(dec_abs)
            dec_min = int((dec_abs - dec_deg) * 60)
            dec_sec = ((dec_abs - dec_deg) * 60 - dec_min) * 60

            self.wcs_coord_label.setText(
                f"{label_x}: {ra_sign}{ra_deg:02d}:{ra_min:02d}:{ra_sec:05.2f} "
                f"{label_y}: {dec_sign}{dec_deg:02d}:{dec_min:02d}:{dec_sec:04.1f}"
            )
        else:
            self.wcs_coord_label.setText("RA: --- Dec: ---")

    def update_pixel_value(self, value: Optional[float] = None) -> None:
        """
        Update pixel value display.

        Args:
            value: Pixel value, or None if unavailable.
        """
        if value is not None:
            self.pixel_value_label.setText(f"Value: {value:.4g}")
        else:
            self.pixel_value_label.setText("Value: ---")

    def update_image_info(
        self,
        width: Optional[int] = None,
        height: Optional[int] = None,
        bitpix: Optional[int] = None,
    ) -> None:
        """
        Update image info display.

        Args:
            width: Image width in pixels.
            height: Image height in pixels.
            bitpix: FITS BITPIX value.
        """
        if width is not None and height is not None:
            info = f"{width}x{height}"
            if bitpix is not None:
                info += f" BITPIX={bitpix}"
            self.image_info_label.setText(info)
        else:
            self.image_info_label.setText("No image loaded")

    def update_zoom(self, zoom: float) -> None:
        """
        Update zoom level display.

        Args:
            zoom: Zoom factor.
        """
        if zoom >= 1:
            self.zoom_label.setText(f"Zoom: {zoom:.0f}x")
        else:
            self.zoom_label.setText(f"Zoom: 1/{1/zoom:.0f}x")

    def show_message(self, message: str, timeout: int = 5000) -> None:
        """
        Show a temporary message in the status bar.

        Args:
            message: Message to display.
            timeout: Timeout in milliseconds.
        """
        self.showMessage(message, timeout)

    def clear_coords(self) -> None:
        """Clear all coordinate displays."""
        self.pixel_coord_label.setText("X: --- Y: ---")
        self.wcs_coord_label.setText("RA: --- Dec: ---")
        self.pixel_value_label.setText("Value: ---")

    def update_all(
        self,
        pixel_coords: Optional[Tuple[int, int]] = None,
        wcs_coords: Optional[Tuple[float, float]] = None,
        value: Optional[float] = None,
        wcs_format: str = "sexagesimal",
        wcs_labels: Tuple[str, str] = ("RA", "Dec"),
    ) -> None:
        """
        Update all coordinate displays at once.

        Args:
            pixel_coords: Tuple of (x, y) pixel coordinates.
            wcs_coords: Tuple of (ra, dec) in degrees.
            value: Pixel value.
        """
        if pixel_coords is not None:
            self.update_pixel_coords(*pixel_coords)
        if wcs_coords is not None:
            self.update_wcs_coords(*wcs_coords, format_type=wcs_format, labels=wcs_labels)
        if value is not None:
            self.update_pixel_value(value)
