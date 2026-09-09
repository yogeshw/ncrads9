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


from PyQt6.QtWidgets import QLabel, QStatusBar, QWidget


class StatusBar(QStatusBar):
    """Status bar showing coordinates, pixel values, and image info."""

    def __init__(self, parent: QWidget | None = None) -> None:
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
        self.addWidget(self.pixel_coord_label)

        # WCS coordinates
        self.wcs_coord_label = QLabel("RA: --- Dec: ---")
        self.wcs_coord_label.setMinimumWidth(200)
        self.addWidget(self.wcs_coord_label)

        # Pixel value
        self.pixel_value_label = QLabel("Value: ---")
        self.pixel_value_label.setMinimumWidth(120)
        self.addWidget(self.pixel_value_label)

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

    def update_wcs_coords(self, text: str | None = None) -> None:
        """Show a pre-formatted coordinate string.

        Formatting belongs to `coordinates.CoordinateContext`, not here: this
        method used to do its own frame-dependent sexagesimal conversion while
        `MainWindow._update_wcs_display` did the frame transform, so the two
        halves of one calculation lived in different layers and neither could
        be reused by the info panel or by XPA.

        Args:
            text: Formatted coordinates, or None to blank the field.
        """
        self.wcs_coord_label.setText(text if text else "RA: --- Dec: ---")

    def update_pixel_value(self, value: float | None = None) -> None:
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
        width: int | None = None,
        height: int | None = None,
        bitpix: int | None = None,
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
        pixel_coords: tuple[int, int] | None = None,
        wcs_text: str | None = None,
        value: float | None = None,
    ) -> None:
        """
        Update all coordinate displays at once.

        Args:
            pixel_coords: Tuple of (x, y) pixel coordinates.
            wcs_text: Coordinates already formatted by a CoordinateContext.
            value: Pixel value.
        """
        if pixel_coords is not None:
            self.update_pixel_coords(*pixel_coords)
        if wcs_text is not None:
            self.update_wcs_coords(wcs_text)
        if value is not None:
            self.update_pixel_value(value)
