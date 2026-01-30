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
SkyView Virtual Observatory service for multi-wavelength image retrieval.

Author: Yogesh Wadadekar
"""

from typing import Optional
from pathlib import Path


class SkyViewServer:
    """Client for accessing NASA's SkyView Virtual Observatory."""

    BASE_URL: str = "https://skyview.gsfc.nasa.gov/cgi-bin/images"

    def __init__(self, survey: str = "DSS2 Red") -> None:
        """
        Initialize the SkyView server client.

        Parameters
        ----------
        survey : str
            The survey to retrieve images from.
        """
        self.survey = survey

    def get_image(
        self,
        ra: float,
        dec: float,
        size: float = 10.0,
        pixels: int = 500,
    ) -> bytes:
        """
        Retrieve an image from SkyView.

        Parameters
        ----------
        ra : float
            Right ascension in degrees.
        dec : float
            Declination in degrees.
        size : float
            Image size in arcminutes.
        pixels : int
            Number of pixels along each axis.

        Returns
        -------
        bytes
            FITS image data.
        """
        raise NotImplementedError("Subclasses must implement get_image")

    def save_image(
        self,
        ra: float,
        dec: float,
        output_path: Path,
        size: float = 10.0,
        pixels: int = 500,
    ) -> Path:
        """
        Retrieve and save a SkyView image to disk.

        Parameters
        ----------
        ra : float
            Right ascension in degrees.
        dec : float
            Declination in degrees.
        output_path : Path
            Path where the FITS file will be saved.
        size : float
            Image size in arcminutes.
        pixels : int
            Number of pixels along each axis.

        Returns
        -------
        Path
            Path to the saved FITS file.
        """
        raise NotImplementedError("Subclasses must implement save_image")

    def get_available_surveys(self) -> dict[str, list[str]]:
        """
        Return dictionary of available surveys by wavelength category.

        Returns
        -------
        dict[str, list[str]]
            Dictionary mapping categories to lists of survey names.
        """
        return {
            "Optical": [
                "DSS",
                "DSS1 Blue",
                "DSS1 Red",
                "DSS2 Blue",
                "DSS2 Red",
                "DSS2 IR",
                "SDSS",
            ],
            "Infrared": [
                "2MASS-J",
                "2MASS-H",
                "2MASS-K",
                "WISE 3.4",
                "WISE 4.6",
                "WISE 12",
                "WISE 22",
            ],
            "Radio": [
                "NVSS",
                "FIRST",
                "SUMSS",
                "GLEAM",
                "TGSS ADR1",
            ],
            "X-ray": [
                "RASS-Cnt Broad",
                "RASS-Cnt Hard",
                "RASS-Cnt Soft",
                "Chandra ACIS",
            ],
            "Gamma-ray": [
                "Fermi 1",
                "Fermi 2",
                "Fermi 3",
                "Fermi 4",
                "Fermi 5",
            ],
        }

    def set_survey(self, survey: str) -> None:
        """
        Set the survey for image retrieval.

        Parameters
        ----------
        survey : str
            The survey name to use.
        """
        self.survey = survey

    def get_multi_survey_images(
        self,
        ra: float,
        dec: float,
        surveys: list[str],
        size: float = 10.0,
        pixels: int = 500,
    ) -> dict[str, bytes]:
        """
        Retrieve images from multiple surveys.

        Parameters
        ----------
        ra : float
            Right ascension in degrees.
        dec : float
            Declination in degrees.
        surveys : list[str]
            List of survey names.
        size : float
            Image size in arcminutes.
        pixels : int
            Number of pixels along each axis.

        Returns
        -------
        dict[str, bytes]
            Dictionary mapping survey names to FITS image data.
        """
        raise NotImplementedError("Subclasses must implement get_multi_survey_images")
