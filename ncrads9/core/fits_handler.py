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
FITS file handler module.

Provides functionality for loading and managing FITS files using astropy.

Author: Yogesh Wadadekar
"""

from typing import Optional, Union, List, Tuple
from pathlib import Path

import numpy as np
from astropy.io import fits
from numpy.typing import NDArray


class FITSHandler:
    """Handler class for FITS file operations.

    This class provides methods for loading FITS files, accessing
    extensions, and extracting data arrays.

    Attributes:
        filepath: Path to the FITS file.
        hdu_list: The HDU list from the opened FITS file.
    """

    def __init__(self, filepath: Optional[Union[str, Path]] = None) -> None:
        """Initialize FITSHandler.

        Args:
            filepath: Optional path to a FITS file to load.
        """
        self.filepath: Optional[Path] = Path(filepath) if filepath else None
        self.hdu_list: Optional[fits.HDUList] = None

        if self.filepath is not None:
            self.load(self.filepath)

    def load(self, filepath: Union[str, Path]) -> fits.HDUList:
        """Load a FITS file.

        Args:
            filepath: Path to the FITS file.

        Returns:
            The HDU list from the FITS file.

        Raises:
            FileNotFoundError: If the file does not exist.
            IOError: If the file cannot be read.
        """
        self.filepath = Path(filepath)
        self.hdu_list = fits.open(self.filepath)
        return self.hdu_list

    def get_extension(self, ext: Union[int, str] = 0) -> fits.hdu.base.ExtensionHDU:
        """Get a specific extension from the FITS file.

        Args:
            ext: Extension index or name.

        Returns:
            The requested HDU extension.

        Raises:
            ValueError: If no file is loaded.
        """
        if self.hdu_list is None:
            raise ValueError("No FITS file loaded")
        return self.hdu_list[ext]

    def get_data(self, ext: Union[int, str] = 0) -> NDArray[np.floating]:
        """Get data array from a specific extension.

        Args:
            ext: Extension index or name.

        Returns:
            The data array from the extension.
        """
        if self.hdu_list is None:
            raise ValueError("No FITS file loaded")
        return self.hdu_list[ext].data

    def get_header(self, ext: Union[int, str] = 0) -> fits.Header:
        """Get header from a specific extension.

        Args:
            ext: Extension index or name.

        Returns:
            The header from the extension.
        """
        if self.hdu_list is None:
            raise ValueError("No FITS file loaded")
        return self.hdu_list[ext].header

    def list_extensions(self) -> List[Tuple[int, str, str]]:
        """List all extensions in the FITS file.

        Returns:
            List of tuples containing (index, name, type) for each extension.
        """
        if self.hdu_list is None:
            raise ValueError("No FITS file loaded")
        extensions = []
        for i, hdu in enumerate(self.hdu_list):
            extensions.append((i, hdu.name, type(hdu).__name__))
        return extensions

    def close(self) -> None:
        """Close the FITS file."""
        if self.hdu_list is not None:
            self.hdu_list.close()
            self.hdu_list = None

    def __enter__(self) -> "FITSHandler":
        """Context manager entry."""
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        """Context manager exit."""
        self.close()
