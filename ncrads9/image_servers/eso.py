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
ESO Archive access for astronomical data retrieval.

Author: Yogesh Wadadekar
"""

from typing import Optional, Any
from pathlib import Path


class ESOArchive:
    """Client for accessing the ESO Science Archive."""

    BASE_URL: str = "https://archive.eso.org"

    def __init__(self, username: Optional[str] = None, password: Optional[str] = None) -> None:
        """
        Initialize the ESO Archive client.

        Parameters
        ----------
        username : str, optional
            ESO archive username for authenticated access.
        password : str, optional
            ESO archive password.
        """
        self.username = username
        self.password = password
        self._authenticated = False

    def authenticate(self) -> bool:
        """
        Authenticate with the ESO archive.

        Returns
        -------
        bool
            True if authentication was successful.
        """
        raise NotImplementedError("Subclasses must implement authenticate")

    def query_region(
        self,
        ra: float,
        dec: float,
        radius: float = 5.0,
        instrument: Optional[str] = None,
    ) -> list[dict[str, Any]]:
        """
        Query the ESO archive for observations in a region.

        Parameters
        ----------
        ra : float
            Right ascension in degrees.
        dec : float
            Declination in degrees.
        radius : float
            Search radius in arcminutes.
        instrument : str, optional
            Filter by instrument name.

        Returns
        -------
        list[dict[str, Any]]
            List of matching observations.
        """
        raise NotImplementedError("Subclasses must implement query_region")

    def download_data(
        self,
        dataset_id: str,
        output_dir: Path,
    ) -> Path:
        """
        Download a dataset from the ESO archive.

        Parameters
        ----------
        dataset_id : str
            The ESO dataset identifier.
        output_dir : Path
            Directory where files will be saved.

        Returns
        -------
        Path
            Path to the downloaded file or directory.
        """
        raise NotImplementedError("Subclasses must implement download_data")

    def get_available_instruments(self) -> list[str]:
        """
        Return list of available ESO instruments.

        Returns
        -------
        list[str]
            List of instrument names.
        """
        return [
            "FORS1",
            "FORS2",
            "VIMOS",
            "XSHOOTER",
            "MUSE",
            "HAWK-I",
            "KMOS",
            "SPHERE",
            "GRAVITY",
            "ERIS",
        ]

    def get_cutout(
        self,
        ra: float,
        dec: float,
        size: float = 1.0,
        survey: str = "DSS2",
    ) -> bytes:
        """
        Retrieve an image cutout from ESO surveys.

        Parameters
        ----------
        ra : float
            Right ascension in degrees.
        dec : float
            Declination in degrees.
        size : float
            Cutout size in arcminutes.
        survey : str
            Survey name (e.g., 'DSS2', 'VISTA').

        Returns
        -------
        bytes
            FITS image data.
        """
        raise NotImplementedError("Subclasses must implement get_cutout")
