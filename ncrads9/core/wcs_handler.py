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
WCS handler module.

Provides a wrapper class for astropy.wcs for coordinate transformations.

Author: Yogesh Wadadekar
"""

from typing import Optional, Union, Tuple, List

import numpy as np
from astropy.io import fits
from astropy.wcs import WCS
from astropy.coordinates import SkyCoord
import astropy.units as u
from numpy.typing import NDArray


class WCSHandler:
    """Handler class for WCS coordinate transformations.

    This class wraps astropy.wcs to provide convenient methods for
    coordinate transformations between pixel and world coordinates.

    Attributes:
        wcs: The underlying WCS object.
    """

    def __init__(
        self,
        header: Optional[fits.Header] = None,
        wcs: Optional[WCS] = None,
    ) -> None:
        """Initialize WCSHandler.

        Args:
            header: FITS header to extract WCS from.
            wcs: Existing WCS object to wrap.
        """
        self._wcs: Optional[WCS] = None

        if wcs is not None:
            self._wcs = wcs
        elif header is not None:
            self._wcs = WCS(header)

    @property
    def wcs(self) -> Optional[WCS]:
        """Get the underlying WCS object."""
        return self._wcs

    @property
    def is_valid(self) -> bool:
        """Check if WCS is valid and usable."""
        return self._wcs is not None and self._wcs.has_celestial

    def pixel_to_world(
        self, x: Union[float, NDArray], y: Union[float, NDArray]
    ) -> Tuple[Union[float, NDArray], Union[float, NDArray]]:
        """Convert pixel coordinates to world coordinates.

        Args:
            x: X pixel coordinate(s).
            y: Y pixel coordinate(s).

        Returns:
            Tuple of (RA, Dec) in degrees.

        Raises:
            ValueError: If WCS is not initialized.
        """
        if self._wcs is None:
            raise ValueError("WCS not initialized")

        world = self._wcs.pixel_to_world(x, y)
        if isinstance(world, SkyCoord):
            return world.ra.deg, world.dec.deg
        return world

    def world_to_pixel(
        self, ra: Union[float, NDArray], dec: Union[float, NDArray]
    ) -> Tuple[Union[float, NDArray], Union[float, NDArray]]:
        """Convert world coordinates to pixel coordinates.

        Args:
            ra: Right Ascension in degrees.
            dec: Declination in degrees.

        Returns:
            Tuple of (x, y) pixel coordinates.

        Raises:
            ValueError: If WCS is not initialized.
        """
        if self._wcs is None:
            raise ValueError("WCS not initialized")

        coord = SkyCoord(ra=ra * u.deg, dec=dec * u.deg)
        x, y = self._wcs.world_to_pixel(coord)
        return x, y

    def get_pixel_scale(self) -> Optional[float]:
        """Get the pixel scale in arcseconds per pixel.

        Returns:
            Pixel scale in arcsec/pixel, or None if unavailable.
        """
        if self._wcs is None:
            return None

        try:
            scales = self._wcs.proj_plane_pixel_scales()
            return float(np.mean(scales) * 3600.0)  # Convert to arcsec
        except Exception:
            return None

    def get_center_coord(self) -> Optional[Tuple[float, float]]:
        """Get the center coordinates of the image.

        Returns:
            Tuple of (RA, Dec) at image center, or None.
        """
        if self._wcs is None:
            return None

        try:
            naxis1 = self._wcs.pixel_shape[0] if self._wcs.pixel_shape else 1
            naxis2 = self._wcs.pixel_shape[1] if self._wcs.pixel_shape else 1
            return self.pixel_to_world(naxis1 / 2, naxis2 / 2)
        except Exception:
            return None

    def get_footprint(self) -> Optional[NDArray]:
        """Get the WCS footprint (corner coordinates).

        Returns:
            Array of corner coordinates, or None.
        """
        if self._wcs is None:
            return None

        try:
            return self._wcs.calc_footprint()
        except Exception:
            return None

    def separation(
        self, ra1: float, dec1: float, ra2: float, dec2: float
    ) -> float:
        """Calculate angular separation between two points.

        Args:
            ra1: RA of first point in degrees.
            dec1: Dec of first point in degrees.
            ra2: RA of second point in degrees.
            dec2: Dec of second point in degrees.

        Returns:
            Angular separation in arcseconds.
        """
        coord1 = SkyCoord(ra=ra1 * u.deg, dec=dec1 * u.deg)
        coord2 = SkyCoord(ra=ra2 * u.deg, dec=dec2 * u.deg)
        return coord1.separation(coord2).arcsec
