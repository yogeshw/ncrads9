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
from io import BytesIO

import requests
from astropy.io.votable import parse_single_table
from astropy.table import Table


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
        size: Any = 0.1,
        format: Optional[str] = None,
    ) -> Optional[Table]:
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
        Table or None
            VOTable results parsed into an Astropy table.
        """
        params: dict[str, Any] = {"POS": f"{ra},{dec}", "SIZE": size}
        if format:
            params["FORMAT"] = format
        try:
            response = requests.get(self.service_url, params=params, timeout=60)
            response.raise_for_status()
            return self._parse_votable(response.content)
        except requests.RequestException:
            return None

    def query_region(
        self,
        ra: float,
        dec: float,
        width: float,
        height: Optional[float] = None,
        format: Optional[str] = None,
    ) -> Optional[Table]:
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
        Table or None
            VOTable results parsed into an Astropy table.
        """
        size = width if height is None else f"{width},{height}"
        return self.query(ra, dec, size=size, format=format)

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
        response = requests.get(access_url, timeout=60)
        response.raise_for_status()
        return response.content

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
        image_data = self.get_image(access_url)
        output_path.write_bytes(image_data)
        return output_path

    def get_service_capabilities(self) -> dict[str, Any]:
        """
        Retrieve the capabilities of the SIA service.

        Returns
        -------
        dict[str, Any]
            Service capabilities metadata.
        """
        return {"url": self.service_url}

    def is_available(self) -> bool:
        """
        Check if the SIA service is available.

        Returns
        -------
        bool
            True if the service responds correctly.
        """
        try:
            response = requests.get(self.service_url, timeout=10)
            return response.status_code == 200
        except requests.RequestException:
            return False

    def _parse_votable(self, content: bytes) -> Optional[Table]:
        """Parse a VOTable response into a Table."""
        try:
            table = parse_single_table(BytesIO(content)).to_table()
            return table
        except Exception:
            return None

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
