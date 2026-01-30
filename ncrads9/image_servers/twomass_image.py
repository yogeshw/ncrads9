# This file is part of ncrads9.
#
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
2MASS image cutout retrieval.

Author: Yogesh Wadadekar
"""

from typing import Optional, Literal
from pathlib import Path


BandType = Literal["j", "h", "k"]


class TwoMassImage:
    """Client for retrieving 2MASS image cutouts."""

    BASE_URL: str = "https://irsa.ipac.caltech.edu/cgi-bin/2MASS/IM/nph-im_sia"

    def __init__(self, band: BandType = "j") -> None:
        """
        Initialize the 2MASS image client.

        Parameters
        ----------
        band : {'j', 'h', 'k'}
            The 2MASS band to retrieve images for.
        """
        self.band = band

    def get_cutout(
        self,
        ra: float,
        dec: float,
        size: float = 5.0,
    ) -> bytes:
        """
        Retrieve a 2MASS image cutout.

        Parameters
        ----------
        ra : float
            Right ascension in degrees.
        dec : float
            Declination in degrees.
        size : float
            Cutout size in arcminutes.

        Returns
        -------
        bytes
            FITS image data.
        """
        raise NotImplementedError("Subclasses must implement get_cutout")

    def save_cutout(
        self,
        ra: float,
        dec: float,
        output_path: Path,
        size: float = 5.0,
    ) -> Path:
        """
        Retrieve and save a 2MASS cutout to disk.

        Parameters
        ----------
        ra : float
            Right ascension in degrees.
        dec : float
            Declination in degrees.
        output_path : Path
            Path where the FITS file will be saved.
        size : float
            Cutout size in arcminutes.

        Returns
        -------
        Path
            Path to the saved FITS file.
        """
        raise NotImplementedError("Subclasses must implement save_cutout")

    def get_available_bands(self) -> list[BandType]:
        """
        Return list of available 2MASS bands.

        Returns
        -------
        list[BandType]
            List of band names.
        """
        return ["j", "h", "k"]

    def set_band(self, band: BandType) -> None:
        """
        Set the band for image retrieval.

        Parameters
        ----------
        band : {'j', 'h', 'k'}
            The 2MASS band to use.
        """
        if band not in self.get_available_bands():
            raise ValueError(f"Invalid band: {band}. Must be one of {self.get_available_bands()}")
        self.band = band
