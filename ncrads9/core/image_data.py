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
Image data container module.

Provides a class for storing and managing image data along with
metadata, WCS information, and statistics.

Author: Yogesh Wadadekar
"""

from dataclasses import dataclass, field
from typing import Optional, Dict, Any, Tuple

import numpy as np
from astropy.io import fits
from astropy.wcs import WCS
from numpy.typing import NDArray


@dataclass
class ImageStatistics:
    """Container for image statistics.

    Attributes:
        min: Minimum pixel value.
        max: Maximum pixel value.
        mean: Mean pixel value.
        std: Standard deviation.
        median: Median pixel value.
    """

    min: float = 0.0
    max: float = 0.0
    mean: float = 0.0
    std: float = 0.0
    median: float = 0.0


class ImageData:
    """Container class for image data and metadata.

    This class stores image data along with its header, WCS information,
    and computed statistics.

    Attributes:
        data: The image data array.
        header: The FITS header.
        wcs: The WCS object for coordinate transformations.
        statistics: Computed image statistics.
    """

    def __init__(
        self,
        data: Optional[NDArray[np.floating]] = None,
        header: Optional[fits.Header] = None,
        wcs: Optional[WCS] = None,
    ) -> None:
        """Initialize ImageData.

        Args:
            data: The image data array.
            header: The FITS header.
            wcs: The WCS object.
        """
        self._data: Optional[NDArray[np.floating]] = data
        self._header: Optional[fits.Header] = header
        self._wcs: Optional[WCS] = wcs
        self._statistics: Optional[ImageStatistics] = None

        if wcs is None and header is not None:
            try:
                self._wcs = WCS(header)
            except Exception:
                self._wcs = None

    @property
    def data(self) -> Optional[NDArray[np.floating]]:
        """Get the image data array."""
        return self._data

    @data.setter
    def data(self, value: NDArray[np.floating]) -> None:
        """Set the image data array and invalidate statistics."""
        self._data = value
        self._statistics = None

    @property
    def header(self) -> Optional[fits.Header]:
        """Get the FITS header."""
        return self._header

    @header.setter
    def header(self, value: fits.Header) -> None:
        """Set the FITS header."""
        self._header = value

    @property
    def wcs(self) -> Optional[WCS]:
        """Get the WCS object."""
        return self._wcs

    @wcs.setter
    def wcs(self, value: WCS) -> None:
        """Set the WCS object."""
        self._wcs = value

    @property
    def shape(self) -> Optional[Tuple[int, ...]]:
        """Get the shape of the data array."""
        if self._data is not None:
            return self._data.shape
        return None

    @property
    def statistics(self) -> Optional[ImageStatistics]:
        """Get computed image statistics."""
        if self._statistics is None and self._data is not None:
            self._compute_statistics()
        return self._statistics

    def _compute_statistics(self) -> None:
        """Compute image statistics."""
        if self._data is None:
            return

        valid_data = self._data[np.isfinite(self._data)]
        if len(valid_data) == 0:
            return

        self._statistics = ImageStatistics(
            min=float(np.min(valid_data)),
            max=float(np.max(valid_data)),
            mean=float(np.mean(valid_data)),
            std=float(np.std(valid_data)),
            median=float(np.median(valid_data)),
        )

    def get_cutout(
        self, center: Tuple[int, int], size: Tuple[int, int]
    ) -> Optional[NDArray[np.floating]]:
        """Extract a cutout from the image.

        Args:
            center: Center pixel coordinates (x, y).
            size: Size of the cutout (width, height).

        Returns:
            The cutout array, or None if data is not available.
        """
        if self._data is None:
            return None

        x, y = center
        w, h = size
        x0 = max(0, x - w // 2)
        x1 = min(self._data.shape[1], x + w // 2)
        y0 = max(0, y - h // 2)
        y1 = min(self._data.shape[0], y + h // 2)

        return self._data[y0:y1, x0:x1]

    def to_dict(self) -> Dict[str, Any]:
        """Convert image data to dictionary representation.

        Returns:
            Dictionary containing image metadata.
        """
        result: Dict[str, Any] = {
            "shape": self.shape,
            "has_wcs": self._wcs is not None,
            "has_header": self._header is not None,
        }
        if self._statistics is not None:
            result["statistics"] = {
                "min": self._statistics.min,
                "max": self._statistics.max,
                "mean": self._statistics.mean,
                "std": self._statistics.std,
                "median": self._statistics.median,
            }
        return result
