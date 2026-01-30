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

"""PrintEngine class for print rendering.

Author: Yogesh Wadadekar
"""

from __future__ import annotations

from enum import Enum
from pathlib import Path
from typing import TYPE_CHECKING, Optional, List, Callable

if TYPE_CHECKING:
    from numpy.typing import NDArray
    from .page_setup import PageSetup


class OutputFormat(Enum):
    """Supported output formats for printing."""

    POSTSCRIPT = "ps"
    PDF = "pdf"
    PNG = "png"
    JPEG = "jpeg"
    TIFF = "tiff"


class PrintEngine:
    """Engine for rendering images to print output."""

    def __init__(
        self,
        page_setup: Optional[PageSetup] = None,
    ) -> None:
        """Initialize the print engine.

        Args:
            page_setup: Page setup configuration.
        """
        self._page_setup: Optional[PageSetup] = page_setup
        self._dpi: int = 300
        self._output_format: OutputFormat = OutputFormat.PDF
        self._progress_callback: Optional[Callable[[float], None]] = None

    @property
    def page_setup(self) -> Optional[PageSetup]:
        """Get the current page setup."""
        return self._page_setup

    @page_setup.setter
    def page_setup(self, value: PageSetup) -> None:
        """Set the page setup."""
        self._page_setup = value

    @property
    def dpi(self) -> int:
        """Get the output DPI."""
        return self._dpi

    @dpi.setter
    def dpi(self, value: int) -> None:
        """Set the output DPI."""
        self._dpi = max(72, min(1200, value))

    @property
    def output_format(self) -> OutputFormat:
        """Get the output format."""
        return self._output_format

    @output_format.setter
    def output_format(self, value: OutputFormat) -> None:
        """Set the output format."""
        self._output_format = value

    def set_progress_callback(
        self,
        callback: Optional[Callable[[float], None]],
    ) -> None:
        """Set a callback for progress updates.

        Args:
            callback: Function called with progress (0.0 to 1.0).
        """
        self._progress_callback = callback

    def render_image(
        self,
        image: NDArray,
        output_path: str | Path,
        title: Optional[str] = None,
    ) -> bool:
        """Render an image to file.

        Args:
            image: Image data to render.
            output_path: Path for output file.
            title: Optional title for the print.

        Returns:
            True if rendering was successful.
        """
        output_path = Path(output_path)

        if self._progress_callback:
            self._progress_callback(0.0)

        # TODO: Implement image rendering
        if self._progress_callback:
            self._progress_callback(1.0)

        return False

    def render_to_printer(
        self,
        image: NDArray,
        printer_name: Optional[str] = None,
    ) -> bool:
        """Send image directly to a printer.

        Args:
            image: Image data to print.
            printer_name: Name of printer, or None for default.

        Returns:
            True if printing was successful.
        """
        # TODO: Implement direct printing
        return False

    def get_available_printers(self) -> List[str]:
        """Get list of available printers.

        Returns:
            List of printer names.
        """
        # TODO: Implement printer enumeration
        return []

    def calculate_output_size(self) -> tuple[int, int]:
        """Calculate output size in pixels based on page setup and DPI.

        Returns:
            Tuple of (width, height) in pixels.
        """
        if self._page_setup is None:
            return (self._dpi * 8, self._dpi * 10)  # Default 8x10 inches

        width_inches = self._page_setup.printable_width
        height_inches = self._page_setup.printable_height

        return (int(width_inches * self._dpi), int(height_inches * self._dpi))
