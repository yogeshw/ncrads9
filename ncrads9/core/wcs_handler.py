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


import astropy.units as u
import numpy as np
from astropy.coordinates import SkyCoord
from astropy.io import fits
from astropy.wcs import WCS
from numpy.typing import NDArray

#: The letters FITS allows for an alternate WCS description.
ALTERNATE_KEYS: tuple[str, ...] = tuple("ABCDEFGHIJKLMNOPQRSTUVWXYZ")


def available_alternates(header: fits.Header | None) -> tuple[str, ...]:
    """Which alternate WCS descriptions a header actually carries.

    A header declares an alternate by suffixing its keywords with a letter,
    so `CTYPE1A` marks description "A" as present. Returns the letters in
    order, lowercased to match the `wcs_a`..`wcs_z` field names the
    information panel and the View menu use.

    Args:
        header: A FITS header, or None.

    Returns:
        The suffixes present, e.g. ("a", "d").
    """
    if header is None:
        return ()
    return tuple(key.lower() for key in ALTERNATE_KEYS if f"CTYPE1{key}" in header)


class WCSHandler:
    """Handler class for WCS coordinate transformations.

    This class wraps astropy.wcs to provide convenient methods for
    coordinate transformations between pixel and world coordinates.

    Attributes:
        wcs: The underlying WCS object.
    """

    def __init__(
        self,
        header: fits.Header | None = None,
        wcs: WCS | None = None,
        key: str = "",
    ) -> None:
        """Initialize WCSHandler.

        Args:
            header: FITS header to extract WCS from.
            wcs: Existing WCS object to wrap.
            key: Which WCS description to read, "" for the primary or a
                single letter "A".."Z" for one of the alternates FITS allows
                (`CTYPE1A`, `CRVAL1A` and so on). DS9 offers all twenty-six
                on its `View -> Multiple WCS` submenu.
        """
        self._wcs: WCS | None = None
        self._key = key.upper()

        if wcs is not None:
            self._wcs = wcs
        elif header is not None:
            # astropy spells the primary description as a space, not "".
            self._wcs = WCS(header, key=self._key or " ")

    @property
    def key(self) -> str:
        """The WCS description this handler reads: "" or "A".."Z"."""
        return self._key

    @property
    def wcs(self) -> WCS | None:
        """Get the underlying WCS object."""
        return self._wcs

    @property
    def is_valid(self) -> bool:
        """Check if WCS is valid and usable."""
        return self._wcs is not None and self._wcs.has_celestial

    def pixel_to_world(
        self, x: float | NDArray, y: float | NDArray
    ) -> tuple[float | NDArray, float | NDArray]:
        """Convert pixel coordinates to world coordinates.

        Args:
            x: X pixel coordinate(s).
            y: Y pixel coordinate(s).

        Returns:
            Tuple of (longitude, latitude) in degrees, in whatever frame the
            WCS declares -- (RA, Dec) for an equatorial one.

        Raises:
            ValueError: If WCS is not initialized.
        """
        if self._wcs is None:
            raise ValueError("WCS not initialized")

        world = self._wcs.pixel_to_world(x, y)
        if isinstance(world, SkyCoord):
            # `.ra`/`.dec` exist only on equatorial frames, and an alternate
            # WCS description is often galactic or ecliptic; the spherical
            # representation names its axes the same way for every frame.
            spherical = world.spherical
            return spherical.lon.deg, spherical.lat.deg
        return world

    def world_to_pixel(
        self, ra: float | NDArray, dec: float | NDArray
    ) -> tuple[float | NDArray, float | NDArray]:
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

    def get_pixel_scale(self) -> float | None:
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

    def get_center_coord(self) -> tuple[float, float] | None:
        """Get the center coordinates of the image.

        Returns:
            Tuple of (RA, Dec) at image center, or None.
        """
        if self._wcs is None:
            return None

        try:
            naxis1 = self._wcs.pixel_shape[0] if self._wcs.pixel_shape else 1
            naxis2 = self._wcs.pixel_shape[1] if self._wcs.pixel_shape else 1
            ra, dec = self.pixel_to_world(naxis1 / 2, naxis2 / 2)
            return float(ra), float(dec)
        except Exception:
            return None

    def get_footprint(self) -> NDArray | None:
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

    def separation(self, ra1: float, dec1: float, ra2: float, dec2: float) -> float:
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
