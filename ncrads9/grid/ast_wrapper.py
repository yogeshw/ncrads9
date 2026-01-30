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

"""Optional AST library interface for complex WCS transformations.

Author: Yogesh Wadadekar

This module provides an interface to the Starlink AST library for handling
complex WCS projections that may not be fully supported by astropy.wcs.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Optional, Tuple, List, Any

if TYPE_CHECKING:
    from astropy.wcs import WCS

# Check for optional starlink-pyast availability
try:
    import starlink.Ast as Ast

    HAS_AST = True
except ImportError:
    HAS_AST = False
    Ast = None


class ASTWrapper:
    """Wrapper for Starlink AST library for complex WCS operations."""

    def __init__(self, wcs: Optional[WCS] = None) -> None:
        """Initialize the AST wrapper.

        Args:
            wcs: Astropy WCS object to wrap.
        """
        self._wcs: Optional[WCS] = wcs
        self._frameset: Optional[Any] = None
        self._available: bool = HAS_AST

    @property
    def available(self) -> bool:
        """Check if AST library is available."""
        return self._available

    @property
    def wcs(self) -> Optional[WCS]:
        """Get the current WCS object."""
        return self._wcs

    @wcs.setter
    def wcs(self, value: WCS) -> None:
        """Set the WCS object and update AST frameset."""
        self._wcs = value
        self._update_frameset()

    def _update_frameset(self) -> None:
        """Update the AST frameset from the current WCS."""
        if not self._available or self._wcs is None:
            self._frameset = None
            return

        # TODO: Convert astropy WCS to AST frameset
        self._frameset = None

    def transform(
        self,
        x: List[float],
        y: List[float],
        forward: bool = True,
    ) -> Tuple[List[float], List[float]]:
        """Transform coordinates using AST.

        Args:
            x: X coordinates (pixel or world).
            y: Y coordinates (pixel or world).
            forward: If True, transform pixel to world; else world to pixel.

        Returns:
            Tuple of transformed (x, y) coordinates.
        """
        if not self._available or self._frameset is None:
            return x, y

        # TODO: Implement AST transformation
        return x, y

    def get_grid_lines(
        self,
        image_width: int,
        image_height: int,
        density: int = 10,
    ) -> List[Tuple[List[float], List[float]]]:
        """Get grid lines using AST plotting.

        Args:
            image_width: Width of the image in pixels.
            image_height: Height of the image in pixels.
            density: Grid density parameter.

        Returns:
            List of grid lines as (x_coords, y_coords) tuples.
        """
        if not self._available or self._frameset is None:
            return []

        # TODO: Implement AST grid line generation
        return []

    def get_boundary(
        self,
        image_width: int,
        image_height: int,
    ) -> Optional[Tuple[float, float, float, float]]:
        """Get the sky boundary for the image.

        Args:
            image_width: Width of the image in pixels.
            image_height: Height of the image in pixels.

        Returns:
            Tuple of (ra_min, ra_max, dec_min, dec_max) in degrees, or None.
        """
        if not self._available or self._frameset is None:
            return None

        # TODO: Implement boundary calculation
        return None
