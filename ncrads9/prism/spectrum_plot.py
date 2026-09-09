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

"""SpectrumPlot widget for spectrum visualization.

Author: Yogesh Wadadekar
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from numpy.typing import NDArray


class PlotStyle(Enum):
    """Style for spectrum plotting."""

    LINE = "line"
    STEP = "step"
    HISTOGRAM = "histogram"
    SCATTER = "scatter"


@dataclass
class PlotConfig:
    """Configuration for spectrum plot appearance."""

    line_color: tuple[int, int, int] = (255, 255, 255)
    line_width: float = 1.0
    error_color: tuple[int, int, int] = (128, 128, 128)
    show_error: bool = True
    style: PlotStyle = PlotStyle.LINE
    background_color: tuple[int, int, int] = (0, 0, 0)
    grid_visible: bool = True


class SpectrumPlot:
    """Widget for spectrum visualization and interaction."""

    def __init__(
        self,
        parent: object | None = None,
        config: PlotConfig | None = None,
    ) -> None:
        """Initialize the spectrum plot widget.

        Args:
            parent: Parent widget.
            config: Plot configuration.
        """
        self._parent: object | None = parent
        self._config: PlotConfig = config or PlotConfig()
        self._wavelength: NDArray | None = None
        self._flux: NDArray | None = None
        self._error: NDArray | None = None
        self._x_range: tuple[float, float] | None = None
        self._y_range: tuple[float, float] | None = None
        self._markers: list[tuple[float, str]] = []

    @property
    def config(self) -> PlotConfig:
        """Get the plot configuration."""
        return self._config

    @config.setter
    def config(self, value: PlotConfig) -> None:
        """Set the plot configuration."""
        self._config = value
        self.refresh()

    @property
    def x_range(self) -> tuple[float, float] | None:
        """Get the current X axis range."""
        return self._x_range

    @property
    def y_range(self) -> tuple[float, float] | None:
        """Get the current Y axis range."""
        return self._y_range

    def set_data(
        self,
        wavelength: NDArray,
        flux: NDArray,
        error: NDArray | None = None,
    ) -> None:
        """Set the spectrum data to display.

        Args:
            wavelength: Wavelength array.
            flux: Flux array.
            error: Optional error array.
        """
        self._wavelength = wavelength
        self._flux = flux
        self._error = error
        self._auto_range()
        self.refresh()

    def clear(self) -> None:
        """Clear all data from the plot."""
        self._wavelength = None
        self._flux = None
        self._error = None
        self._markers = []
        self.refresh()

    def set_x_range(self, min_val: float, max_val: float) -> None:
        """Set the X axis range.

        Args:
            min_val: Minimum X value.
            max_val: Maximum X value.
        """
        self._x_range = (min_val, max_val)
        self.refresh()

    def set_y_range(self, min_val: float, max_val: float) -> None:
        """Set the Y axis range.

        Args:
            min_val: Minimum Y value.
            max_val: Maximum Y value.
        """
        self._y_range = (min_val, max_val)
        self.refresh()

    def auto_scale(self) -> None:
        """Automatically scale axes to fit data."""
        self._auto_range()
        self.refresh()

    def _auto_range(self) -> None:
        """Calculate automatic axis ranges from data."""
        if self._wavelength is None or self._flux is None:
            self._x_range = None
            self._y_range = None
            return

        # TODO: Implement auto-range calculation

    def add_marker(
        self,
        wavelength: float,
        label: str = "",
    ) -> None:
        """Add a vertical marker at a wavelength.

        Args:
            wavelength: Wavelength position for marker.
            label: Optional label for the marker.
        """
        self._markers.append((wavelength, label))
        self.refresh()

    def clear_markers(self) -> None:
        """Remove all markers from the plot."""
        self._markers = []
        self.refresh()

    def refresh(self) -> None:
        """Refresh the plot display."""
        # TODO: Implement plot rendering

    def get_wavelength_at_x(self, x: int) -> float | None:
        """Get wavelength at a given x pixel position.

        Args:
            x: X coordinate in pixels.

        Returns:
            Wavelength at that position, or None.
        """
        # TODO: Implement coordinate conversion
        return None

    def get_flux_at_wavelength(self, wavelength: float) -> float | None:
        """Get interpolated flux at a given wavelength.

        Args:
            wavelength: Wavelength to query.

        Returns:
            Interpolated flux value, or None.
        """
        # TODO: Implement flux interpolation
        return None
