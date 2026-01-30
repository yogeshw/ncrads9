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
SDSS (Sloan Digital Sky Survey) image cutout retrieval.

Author: Yogesh Wadadekar
"""

from typing import Optional, Literal
from pathlib import Path


SDSSBand = Literal["u", "g", "r", "i", "z"]


class SDSSImage:
    """Client for retrieving SDSS image cutouts."""

    BASE_URL: str = "https://skyserver.sdss.org/dr18/SkyServerWS/ImgCutout"

    def __init__(self, data_release: str = "DR18") -> None:
        """
        Initialize the SDSS image client.

        Parameters
        ----------
        data_release : str
            The SDSS data release to use (e.g., 'DR18', 'DR17').
        """
        self.data_release = data_release

    def get_cutout(
        self,
        ra: float,
        dec: float,
        scale: float = 0.4,
        width: int = 512,
        height: Optional[int] = None,
        band: Optional[SDSSBand] = None,
    ) -> bytes:
        """
        Retrieve an SDSS image cutout.

        Parameters
        ----------
        ra : float
            Right ascension in degrees.
        dec : float
            Declination in degrees.
        scale : float
            Pixel scale in arcsec/pixel.
        width : int
            Image width in pixels.
        height : int, optional
            Image height in pixels. Defaults to width if not specified.
        band : {'u', 'g', 'r', 'i', 'z'}, optional
            Single band for FITS cutout. If None, returns color JPEG.

        Returns
        -------
        bytes
            Image data (FITS for single band, JPEG for color).
        """
        raise NotImplementedError("Subclasses must implement get_cutout")

    def save_cutout(
        self,
        ra: float,
        dec: float,
        output_path: Path,
        scale: float = 0.4,
        width: int = 512,
        height: Optional[int] = None,
        band: Optional[SDSSBand] = None,
    ) -> Path:
        """
        Retrieve and save an SDSS cutout to disk.

        Parameters
        ----------
        ra : float
            Right ascension in degrees.
        dec : float
            Declination in degrees.
        output_path : Path
            Path where the image file will be saved.
        scale : float
            Pixel scale in arcsec/pixel.
        width : int
            Image width in pixels.
        height : int, optional
            Image height in pixels.
        band : {'u', 'g', 'r', 'i', 'z'}, optional
            Single band for FITS cutout.

        Returns
        -------
        Path
            Path to the saved image file.
        """
        raise NotImplementedError("Subclasses must implement save_cutout")

    def get_available_bands(self) -> list[SDSSBand]:
        """
        Return list of available SDSS bands.

        Returns
        -------
        list[SDSSBand]
            List of band names.
        """
        return ["u", "g", "r", "i", "z"]

    def get_jpeg_cutout(
        self,
        ra: float,
        dec: float,
        scale: float = 0.4,
        width: int = 512,
        height: Optional[int] = None,
    ) -> bytes:
        """
        Retrieve a color JPEG cutout from SDSS.

        Parameters
        ----------
        ra : float
            Right ascension in degrees.
        dec : float
            Declination in degrees.
        scale : float
            Pixel scale in arcsec/pixel.
        width : int
            Image width in pixels.
        height : int, optional
            Image height in pixels.

        Returns
        -------
        bytes
            JPEG image data.
        """
        raise NotImplementedError("Subclasses must implement get_jpeg_cutout")

    def check_coverage(self, ra: float, dec: float) -> bool:
        """
        Check if coordinates are within SDSS coverage.

        Parameters
        ----------
        ra : float
            Right ascension in degrees.
        dec : float
            Declination in degrees.

        Returns
        -------
        bool
            True if coordinates are within SDSS coverage.
        """
        raise NotImplementedError("Subclasses must implement check_coverage")
