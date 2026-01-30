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

"""PrismWindow class for spectral analysis window.

Author: Yogesh Wadadekar
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Optional, List, Callable
from pathlib import Path

if TYPE_CHECKING:
    import numpy as np
    from numpy.typing import NDArray


class PrismWindow:
    """Main window for spectral analysis and visualization."""

    def __init__(self, parent: Optional[object] = None) -> None:
        """Initialize the Prism spectral analysis window.

        Args:
            parent: Parent widget or window.
        """
        self._parent: Optional[object] = parent
        self._wavelength: Optional[NDArray] = None
        self._flux: Optional[NDArray] = None
        self._error: Optional[NDArray] = None
        self._filename: Optional[Path] = None
        self._title: str = "Prism - Spectral Analysis"
        self._callbacks: List[Callable[[], None]] = []

    @property
    def title(self) -> str:
        """Get the window title."""
        return self._title

    @title.setter
    def title(self, value: str) -> None:
        """Set the window title."""
        self._title = value

    @property
    def wavelength(self) -> Optional[NDArray]:
        """Get the wavelength array."""
        return self._wavelength

    @property
    def flux(self) -> Optional[NDArray]:
        """Get the flux array."""
        return self._flux

    @property
    def error(self) -> Optional[NDArray]:
        """Get the error array."""
        return self._error

    def load_spectrum(
        self,
        filename: str | Path,
        format: Optional[str] = None,
    ) -> bool:
        """Load a spectrum from file.

        Args:
            filename: Path to the spectrum file.
            format: Optional format specification (fits, ascii, etc.).

        Returns:
            True if loading was successful.
        """
        self._filename = Path(filename)
        # TODO: Implement spectrum loading
        return False

    def set_spectrum(
        self,
        wavelength: NDArray,
        flux: NDArray,
        error: Optional[NDArray] = None,
    ) -> None:
        """Set spectrum data directly.

        Args:
            wavelength: Wavelength array.
            flux: Flux array.
            error: Optional error array.
        """
        self._wavelength = wavelength
        self._flux = flux
        self._error = error
        self._notify_callbacks()

    def clear(self) -> None:
        """Clear the current spectrum data."""
        self._wavelength = None
        self._flux = None
        self._error = None
        self._filename = None
        self._notify_callbacks()

    def show(self) -> None:
        """Show the window."""
        # TODO: Implement window display
        pass

    def hide(self) -> None:
        """Hide the window."""
        # TODO: Implement window hiding
        pass

    def add_callback(self, callback: Callable[[], None]) -> None:
        """Add a callback for spectrum changes.

        Args:
            callback: Function to call when spectrum changes.
        """
        self._callbacks.append(callback)

    def remove_callback(self, callback: Callable[[], None]) -> None:
        """Remove a callback.

        Args:
            callback: Callback function to remove.
        """
        if callback in self._callbacks:
            self._callbacks.remove(callback)

    def _notify_callbacks(self) -> None:
        """Notify all registered callbacks of changes."""
        for callback in self._callbacks:
            callback()

    def zoom_to_range(
        self,
        wavelength_min: float,
        wavelength_max: float,
    ) -> None:
        """Zoom to a specific wavelength range.

        Args:
            wavelength_min: Minimum wavelength.
            wavelength_max: Maximum wavelength.
        """
        # TODO: Implement zoom functionality
        pass

    def reset_zoom(self) -> None:
        """Reset zoom to show full spectrum."""
        # TODO: Implement zoom reset
        pass
