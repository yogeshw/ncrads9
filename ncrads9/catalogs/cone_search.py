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
Virtual Observatory cone search implementation.

Author: Yogesh Wadadekar
"""

from typing import Optional, List, Any
from urllib.parse import urlencode
import requests

from astropy.coordinates import SkyCoord
from astropy.table import Table
from astropy.io.votable import parse_single_table
import astropy.units as u

from .catalog_base import CatalogBase


class ConeSearch(CatalogBase):
    """VO cone search implementation for querying catalog services."""

    # Well-known cone search services
    KNOWN_SERVICES: dict = {
        "vizier": "https://vizier.cds.unistra.fr/viz-bin/conesearch",
        "heasarc": "https://heasarc.gsfc.nasa.gov/cgi-bin/vo/cone/coneGet.pl",
        "mast": "https://archive.stsci.edu/vo/cone_search",
        "ned": "https://ned.ipac.caltech.edu/cgi-bin/NEDobjsearch",
    }

    def __init__(
        self,
        url: Optional[str] = None,
        service_name: Optional[str] = None,
        timeout: int = 60,
    ) -> None:
        """
        Initialize cone search.

        Parameters
        ----------
        url : str, optional
            URL of the cone search service.
        service_name : str, optional
            Name of a known service (vizier, heasarc, mast, ned).
        timeout : int, optional
            Request timeout in seconds. Default is 60.
        """
        super().__init__(
            name="ConeSearch",
            description="VO Cone Search service",
        )

        if service_name and service_name.lower() in self.KNOWN_SERVICES:
            self.url: str = self.KNOWN_SERVICES[service_name.lower()]
        elif url:
            self.url = url
        else:
            self.url = self.KNOWN_SERVICES["vizier"]

        self.timeout: int = timeout
        self._session: requests.Session = requests.Session()

    def query_region(
        self,
        coord: SkyCoord,
        radius: u.Quantity,
        catalog: Optional[str] = None,
        **kwargs: Any,
    ) -> Optional[Table]:
        """
        Perform a cone search query.

        Parameters
        ----------
        coord : SkyCoord
            Center coordinate for the query.
        radius : Quantity
            Search radius with angular units.
        catalog : str, optional
            Catalog identifier (service-specific).
        **kwargs : Any
            Additional query parameters.

        Returns
        -------
        Table or None
            Result table or None if no results.
        """
        try:
            ra = coord.ra.deg
            dec = coord.dec.deg
            sr = radius.to(u.deg).value

            params: dict = {
                "RA": ra,
                "DEC": dec,
                "SR": sr,
            }

            if catalog:
                params["catalog"] = catalog

            params.update(kwargs)

            response = self._session.get(
                self.url,
                params=params,
                timeout=self.timeout,
            )
            response.raise_for_status()

            table = self._parse_votable(response.content)
            self._last_result = table
            return table

        except requests.RequestException as e:
            print(f"Cone search request error: {e}")
            self._last_result = None
            return None
        except Exception as e:
            print(f"Cone search error: {e}")
            self._last_result = None
            return None

    def query_object(
        self,
        name: str,
        radius: u.Quantity = 1 * u.arcmin,
        **kwargs: Any,
    ) -> Optional[Table]:
        """
        Query by object name.

        Parameters
        ----------
        name : str
            Object name to resolve.
        radius : Quantity, optional
            Search radius. Default is 1 arcmin.
        **kwargs : Any
            Additional query parameters.

        Returns
        -------
        Table or None
            Result table or None if no results.
        """
        try:
            coord = SkyCoord.from_name(name)
            return self.query_region(coord, radius=radius, **kwargs)
        except Exception as e:
            print(f"Object name resolution error: {e}")
            self._last_result = None
            return None

    def _parse_votable(self, content: bytes) -> Optional[Table]:
        """
        Parse VOTable from response content.

        Parameters
        ----------
        content : bytes
            Response content.

        Returns
        -------
        Table or None
            Parsed table or None.
        """
        from io import BytesIO

        try:
            votable = parse_single_table(BytesIO(content))
            return votable.to_table()
        except Exception as e:
            print(f"VOTable parse error: {e}")
            return None

    def search_multiple(
        self,
        coords: List[SkyCoord],
        radius: u.Quantity,
        **kwargs: Any,
    ) -> List[Optional[Table]]:
        """
        Perform cone search for multiple positions.

        Parameters
        ----------
        coords : list of SkyCoord
            List of coordinates to search.
        radius : Quantity
            Search radius for all searches.
        **kwargs : Any
            Additional query parameters.

        Returns
        -------
        list of Table or None
            Results for each coordinate.
        """
        results: List[Optional[Table]] = []
        for coord in coords:
            result = self.query_region(coord, radius=radius, **kwargs)
            results.append(result)
        return results

    def set_url(self, url: str) -> None:
        """Set the cone search service URL."""
        self.url = url

    def set_service(self, service_name: str) -> bool:
        """
        Set a known service by name.

        Parameters
        ----------
        service_name : str
            Name of the service.

        Returns
        -------
        bool
            True if service was found and set.
        """
        if service_name.lower() in self.KNOWN_SERVICES:
            self.url = self.KNOWN_SERVICES[service_name.lower()]
            return True
        print(f"Unknown service: {service_name}")
        print(f"Known services: {list(self.KNOWN_SERVICES.keys())}")
        return False

    def set_timeout(self, timeout: int) -> None:
        """Set request timeout in seconds."""
        self.timeout = timeout

    @staticmethod
    def list_known_services() -> List[str]:
        """Return list of known service names."""
        return list(ConeSearch.KNOWN_SERVICES.keys())

    def validate_service(self) -> bool:
        """
        Validate that the service URL is accessible.

        Returns
        -------
        bool
            True if service responds.
        """
        try:
            response = self._session.head(self.url, timeout=10)
            return response.status_code < 400
        except Exception:
            return False
