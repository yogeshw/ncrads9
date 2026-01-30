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
Digital Sky Survey (DSS) image retrieval.

Author: Yogesh Wadadekar
"""

from typing import Optional, Tuple
from pathlib import Path


class DSSServer:
    """Client for retrieving images from the Digital Sky Survey."""

    BASE_URL: str = "https://archive.stsci.edu/cgi-bin/dss_search"

    def __init__(self, survey: str = "poss2ukstu_red") -> None:
        """
        Initialize the DSS server client.

        Parameters
        ----------
        survey : str
            The DSS survey to use. Options include 'poss2ukstu_red',
            'poss2ukstu_blue', 'poss1_red', 'poss1_blue', etc.
        """
        self.survey = survey

    def get_image(
        self,
        ra: float,
        dec: float,
        width: float = 10.0,
        height: Optional[float] = None,
    ) -> bytes:
        """
        Retrieve a DSS image cutout.

        Parameters
        ----------
        ra : float
            Right ascension in degrees.
        dec : float
            Declination in degrees.
        width : float
            Image width in arcminutes.
        height : float, optional
            Image height in arcminutes. Defaults to width if not specified.

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
        width: float = 10.0,
        height: Optional[float] = None,
    ) -> Path:
        """
        Retrieve and save a DSS image to disk.

        Parameters
        ----------
        ra : float
            Right ascension in degrees.
        dec : float
            Declination in degrees.
        output_path : Path
            Path where the FITS file will be saved.
        width : float
            Image width in arcminutes.
        height : float, optional
            Image height in arcminutes.

        Returns
        -------
        Path
            Path to the saved FITS file.
        """
        raise NotImplementedError("Subclasses must implement save_image")

    def get_available_surveys(self) -> list[str]:
        """
        Return list of available DSS surveys.

        Returns
        -------
        list[str]
            List of survey names.
        """
        return [
            "poss2ukstu_red",
            "poss2ukstu_blue",
            "poss2ukstu_ir",
            "poss1_red",
            "poss1_blue",
            "quickv",
            "phase2_gsc2",
            "phase2_gsc1",
        ]
