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
FITS file writer for NCRADS9.

Author: Yogesh Wadadekar
"""

from pathlib import Path
from typing import Any, Optional, Union

import numpy as np
from astropy.io import fits
from numpy.typing import NDArray


class FITSWriter:
    """Writer for FITS (Flexible Image Transport System) files."""

    def __init__(self, filepath: Union[str, Path]) -> None:
        """
        Initialize FITS writer.

        Args:
            filepath: Path for the output FITS file.
        """
        self.filepath = Path(filepath)
        self._hdu_list: fits.HDUList = fits.HDUList()

    def add_image(
        self,
        data: NDArray[Any],
        header: Optional[fits.Header] = None,
        name: str = "",
    ) -> None:
        """
        Add an image extension.

        Args:
            data: Image data as numpy array.
            header: Optional FITS header.
            name: Extension name.
        """
        if len(self._hdu_list) == 0:
            hdu = fits.PrimaryHDU(data=data, header=header)
        else:
            hdu = fits.ImageHDU(data=data, header=header, name=name)
        self._hdu_list.append(hdu)

    def add_table(
        self,
        columns: list[fits.Column],
        header: Optional[fits.Header] = None,
        name: str = "",
    ) -> None:
        """
        Add a binary table extension.

        Args:
            columns: List of FITS column definitions.
            header: Optional FITS header.
            name: Extension name.
        """
        hdu = fits.BinTableHDU.from_columns(columns, header=header, name=name)
        if len(self._hdu_list) == 0:
            self._hdu_list.append(fits.PrimaryHDU())
        self._hdu_list.append(hdu)

    def write(self, overwrite: bool = False) -> None:
        """
        Write the FITS file to disk.

        Args:
            overwrite: Whether to overwrite existing file.
        """
        self._hdu_list.writeto(self.filepath, overwrite=overwrite)

    def close(self) -> None:
        """Close and cleanup resources."""
        self._hdu_list.close()

    def __enter__(self) -> "FITSWriter":
        """Context manager entry."""
        return self

    def __exit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        """Context manager exit."""
        self.close()
