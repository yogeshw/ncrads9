# NCRADS9 - NCRA DS9 Visualization Tool
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
FITS file reader for NCRADS9.

Author: Yogesh Wadadekar
"""

from pathlib import Path
from typing import Any, Optional, Union

import numpy as np
from astropy.io import fits
from numpy.typing import NDArray


class FITSReader:
    """Reader for FITS (Flexible Image Transport System) files."""

    def __init__(self, filepath: Union[str, Path]) -> None:
        """
        Initialize FITS reader.

        Args:
            filepath: Path to the FITS file.
        """
        self.filepath = Path(filepath)
        self._hdu_list: Optional[fits.HDUList] = None

    def open(self) -> None:
        """Open the FITS file."""
        self._hdu_list = fits.open(self.filepath)

    def close(self) -> None:
        """Close the FITS file."""
        if self._hdu_list is not None:
            self._hdu_list.close()
            self._hdu_list = None

    def read_data(self, extension: int = 0) -> NDArray[Any]:
        """
        Read image data from the specified extension.

        Args:
            extension: HDU extension number.

        Returns:
            Image data as numpy array.
        """
        if self._hdu_list is None:
            self.open()
        assert self._hdu_list is not None
        return np.array(self._hdu_list[extension].data)

    def read_header(self, extension: int = 0) -> fits.Header:
        """
        Read header from the specified extension.

        Args:
            extension: HDU extension number.

        Returns:
            FITS header object.
        """
        if self._hdu_list is None:
            self.open()
        assert self._hdu_list is not None
        return self._hdu_list[extension].header

    def get_extensions(self) -> list[str]:
        """
        Get list of extension names.

        Returns:
            List of extension names.
        """
        if self._hdu_list is None:
            self.open()
        assert self._hdu_list is not None
        return [hdu.name for hdu in self._hdu_list]

    def __enter__(self) -> "FITSReader":
        """Context manager entry."""
        self.open()
        return self

    def __exit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        """Context manager exit."""
        self.close()
