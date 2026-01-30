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

"""GridRenderer class for WCS grid line rendering.

Author: Yogesh Wadadekar
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Optional, Tuple, List

if TYPE_CHECKING:
    from astropy.wcs import WCS
    from .grid_config import GridConfig


class GridRenderer:
    """Renders WCS coordinate grid lines on astronomical images."""

    def __init__(
        self,
        wcs: Optional[WCS] = None,
        config: Optional[GridConfig] = None,
    ) -> None:
        """Initialize the grid renderer.

        Args:
            wcs: World Coordinate System object for coordinate transformations.
            config: Grid configuration settings.
        """
        self._wcs: Optional[WCS] = wcs
        self._config: Optional[GridConfig] = config
        self._grid_lines: List[Tuple[List[float], List[float]]] = []

    @property
    def wcs(self) -> Optional[WCS]:
        """Get the current WCS object."""
        return self._wcs

    @wcs.setter
    def wcs(self, value: WCS) -> None:
        """Set the WCS object."""
        self._wcs = value

    @property
    def config(self) -> Optional[GridConfig]:
        """Get the current grid configuration."""
        return self._config

    @config.setter
    def config(self, value: GridConfig) -> None:
        """Set the grid configuration."""
        self._config = value

    def compute_grid_lines(
        self,
        image_width: int,
        image_height: int,
    ) -> List[Tuple[List[float], List[float]]]:
        """Compute grid lines for the given image dimensions.

        Args:
            image_width: Width of the image in pixels.
            image_height: Height of the image in pixels.

        Returns:
            List of grid lines, each as a tuple of (x_coords, y_coords).
        """
        self._grid_lines = []
        if self._wcs is None:
            return self._grid_lines

        # TODO: Implement grid line computation using WCS
        return self._grid_lines

    def render(
        self,
        canvas: object,
        offset_x: float = 0.0,
        offset_y: float = 0.0,
        scale: float = 1.0,
    ) -> None:
        """Render grid lines on the given canvas.

        Args:
            canvas: Canvas object to render on.
            offset_x: X offset for rendering.
            offset_y: Y offset for rendering.
            scale: Scale factor for rendering.
        """
        # TODO: Implement rendering logic
        pass

    def clear(self) -> None:
        """Clear all computed grid lines."""
        self._grid_lines = []
