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
Data cube handler module.

Provides functionality for handling 3D data cubes (e.g., spectral cubes).

Author: Yogesh Wadadekar
"""

from typing import Optional, Union, Tuple, List

import numpy as np
from astropy.io import fits
from astropy.wcs import WCS
from numpy.typing import NDArray


class CubeHandler:
    """Handler class for 3D data cube operations.

    This class provides methods for working with 3D FITS data cubes,
    including slice extraction, moment maps, and spectral operations.

    Attributes:
        data: The 3D data cube array.
        header: The FITS header.
        wcs: The WCS object for the cube.
    """

    def __init__(
        self,
        data: Optional[NDArray[np.floating]] = None,
        header: Optional[fits.Header] = None,
    ) -> None:
        """Initialize CubeHandler.

        Args:
            data: The 3D data cube array.
            header: The FITS header.
        """
        self._data: Optional[NDArray[np.floating]] = data
        self._header: Optional[fits.Header] = header
        self._wcs: Optional[WCS] = None

        if header is not None:
            try:
                self._wcs = WCS(header)
            except Exception:
                pass

        self._validate_cube()

    def _validate_cube(self) -> None:
        """Validate that data is a 3D cube."""
        if self._data is not None and self._data.ndim != 3:
            raise ValueError(f"Expected 3D cube, got {self._data.ndim}D array")

    @property
    def data(self) -> Optional[NDArray[np.floating]]:
        """Get the data cube array."""
        return self._data

    @property
    def header(self) -> Optional[fits.Header]:
        """Get the FITS header."""
        return self._header

    @property
    def wcs(self) -> Optional[WCS]:
        """Get the WCS object."""
        return self._wcs

    @property
    def shape(self) -> Optional[Tuple[int, int, int]]:
        """Get the shape of the cube (nz, ny, nx)."""
        if self._data is not None:
            return self._data.shape
        return None

    @property
    def n_channels(self) -> Optional[int]:
        """Get the number of spectral channels."""
        if self._data is not None:
            return self._data.shape[0]
        return None

    def get_slice(self, channel: int) -> Optional[NDArray[np.floating]]:
        """Get a 2D slice at a specific channel.

        Args:
            channel: The channel index.

        Returns:
            The 2D slice at the given channel.
        """
        if self._data is None:
            return None
        if channel < 0 or channel >= self._data.shape[0]:
            raise IndexError(f"Channel {channel} out of range")
        return self._data[channel, :, :]

    def get_spectrum(self, x: int, y: int) -> Optional[NDArray[np.floating]]:
        """Get the spectrum at a specific pixel position.

        Args:
            x: X pixel coordinate.
            y: Y pixel coordinate.

        Returns:
            The spectrum at the given position.
        """
        if self._data is None:
            return None
        return self._data[:, y, x]

    def moment0(self) -> Optional[NDArray[np.floating]]:
        """Compute the zeroth moment (integrated intensity) map.

        Returns:
            The moment-0 map.
        """
        if self._data is None:
            return None
        return np.nansum(self._data, axis=0)

    def moment1(self) -> Optional[NDArray[np.floating]]:
        """Compute the first moment (velocity field) map.

        Returns:
            The moment-1 map.
        """
        if self._data is None:
            return None

        channels = np.arange(self._data.shape[0])
        weights = self._data.copy()
        weights[weights < 0] = 0

        total = np.nansum(weights, axis=0)
        with np.errstate(invalid="ignore", divide="ignore"):
            m1 = np.nansum(weights * channels[:, np.newaxis, np.newaxis], axis=0) / total
        return m1

    def moment2(self) -> Optional[NDArray[np.floating]]:
        """Compute the second moment (velocity dispersion) map.

        Returns:
            The moment-2 map.
        """
        if self._data is None:
            return None

        m1 = self.moment1()
        if m1 is None:
            return None

        channels = np.arange(self._data.shape[0])
        weights = self._data.copy()
        weights[weights < 0] = 0

        total = np.nansum(weights, axis=0)
        diff_sq = (channels[:, np.newaxis, np.newaxis] - m1) ** 2

        with np.errstate(invalid="ignore", divide="ignore"):
            m2 = np.sqrt(np.nansum(weights * diff_sq, axis=0) / total)
        return m2

    def collapse(
        self,
        start_channel: Optional[int] = None,
        end_channel: Optional[int] = None,
        method: str = "sum",
    ) -> Optional[NDArray[np.floating]]:
        """Collapse the cube along the spectral axis.

        Args:
            start_channel: Starting channel (inclusive).
            end_channel: Ending channel (exclusive).
            method: Collapse method ('sum', 'mean', 'max', 'min').

        Returns:
            The collapsed 2D image.
        """
        if self._data is None:
            return None

        subcube = self._data[start_channel:end_channel, :, :]

        if method == "sum":
            return np.nansum(subcube, axis=0)
        elif method == "mean":
            return np.nanmean(subcube, axis=0)
        elif method == "max":
            return np.nanmax(subcube, axis=0)
        elif method == "min":
            return np.nanmin(subcube, axis=0)
        else:
            raise ValueError(f"Unknown collapse method: {method}")

    def get_channel_wcs(self, channel: int) -> Optional[WCS]:
        """Get a 2D WCS for a specific channel slice.

        Args:
            channel: The channel index.

        Returns:
            A 2D WCS object for the slice.
        """
        if self._wcs is None:
            return None
        try:
            return self._wcs.celestial
        except Exception:
            return None
