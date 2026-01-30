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
Simple Image Access (SIA) protocol client for Virtual Observatory services.

Author: Yogesh Wadadekar
"""

from typing import Optional, Any
from pathlib import Path


class SIAClient:
    """Client for Virtual Observatory Simple Image Access (SIA) protocol."""

    def __init__(self, service_url: str) -> None:
        """
        Initialize the SIA client.

        Parameters
        ----------
        service_url : str
            The URL of the SIA service endpoint.
        """
        self.service_url = service_url.rstrip("/")

    def query(
        self,
        ra: float,
        dec: float,
        size: float = 0.1,
        format: Optional[str] = None,
    ) -> list[dict[str, Any]]:
        """
        Query the SIA service for images.

        Parameters
        ----------
        ra : float
            Right ascension in degrees.
        dec : float
            Declination in degrees.
        size : float
            Search radius in degrees.
        format : str, optional
            Desired image format (e.g., 'image/fits', 'image/jpeg').

        Returns
        -------
        list[dict[str, Any]]
            List of matching image records.
        """
        raise NotImplementedError("Subclasses must implement query")

    def query_region(
        self,
        ra: float,
        dec: float,
        width: float,
        height: Optional[float] = None,
        format: Optional[str] = None,
    ) -> list[dict[str, Any]]:
        """
        Query the SIA service for images in a rectangular region.

        Parameters
        ----------
        ra : float
            Right ascension of center in degrees.
        dec : float
            Declination of center in degrees.
        width : float
            Region width in degrees.
        height : float, optional
            Region height in degrees. Defaults to width if not specified.
        format : str, optional
            Desired image format.

        Returns
        -------
        list[dict[str, Any]]
            List of matching image records.
        """
        raise NotImplementedError("Subclasses must implement query_region")

    def get_image(self, access_url: str) -> bytes:
        """
        Download an image from an access URL.

        Parameters
        ----------
        access_url : str
            The URL to retrieve the image from.

        Returns
        -------
        bytes
            Image data.
        """
        raise NotImplementedError("Subclasses must implement get_image")

    def save_image(self, access_url: str, output_path: Path) -> Path:
        """
        Download and save an image to disk.

        Parameters
        ----------
        access_url : str
            The URL to retrieve the image from.
        output_path : Path
            Path where the image file will be saved.

        Returns
        -------
        Path
            Path to the saved image file.
        """
        raise NotImplementedError("Subclasses must implement save_image")

    def get_service_capabilities(self) -> dict[str, Any]:
        """
        Retrieve the capabilities of the SIA service.

        Returns
        -------
        dict[str, Any]
            Service capabilities metadata.
        """
        raise NotImplementedError("Subclasses must implement get_service_capabilities")

    def is_available(self) -> bool:
        """
        Check if the SIA service is available.

        Returns
        -------
        bool
            True if the service responds correctly.
        """
        raise NotImplementedError("Subclasses must implement is_available")

    @staticmethod
    def get_known_services() -> dict[str, str]:
        """
        Return dictionary of well-known SIA services.

        Returns
        -------
        dict[str, str]
            Dictionary mapping service names to URLs.
        """
        return {
            "2MASS": "https://irsa.ipac.caltech.edu/cgi-bin/2MASS/IM/nph-im_sia",
            "WISE": "https://irsa.ipac.caltech.edu/cgi-bin/WISE/IM/nph-im_sia",
            "SDSS": "https://skyserver.sdss.org/SkyserverWS/dr18/SIAP/getSIAP",
            "HST": "https://mast.stsci.edu/portal_vo/Mashup/VoQuery.asmx/SiaV1",
            "ESO": "https://archive.eso.org/ssap/ssap",
            "CADC": "https://www.cadc-ccda.hia-iha.nrc-cnrc.gc.ca/sia/query",
        }
