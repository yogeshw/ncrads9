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
SkyBot (Sky Body Tracker) query interface for solar system objects.

Author: Yogesh Wadadekar
"""

from typing import Optional, Any
from datetime import datetime

from astropy.coordinates import SkyCoord
from astropy.table import Table
from astropy.time import Time
import astropy.units as u
from astroquery.imcce import Skybot

from .catalog_base import CatalogBase


class SkybotCatalog(CatalogBase):
    """SkyBot catalog query class for solar system objects."""

    def __init__(
        self,
        location: str = "500",
        object_type: str = "all",
    ) -> None:
        """
        Initialize SkyBot catalog query.

        Parameters
        ----------
        location : str, optional
            Observatory code. Default is "500" (geocentric).
        object_type : str, optional
            Type of objects to query: "all", "asteroid", "comet", "planet".
            Default is "all".
        """
        super().__init__(
            name="SkyBot",
            description="IMCCE SkyBot solar system object service",
        )
        self.location: str = location
        self.object_type: str = object_type

    def query_region(
        self,
        coord: SkyCoord,
        radius: u.Quantity,
        epoch: Optional[Time] = None,
        **kwargs: Any,
    ) -> Optional[Table]:
        """
        Query SkyBot for solar system objects within a region.

        Parameters
        ----------
        coord : SkyCoord
            Center coordinate for the query.
        radius : Quantity
            Search radius with angular units.
        epoch : Time, optional
            Observation epoch. Default is current time.
        **kwargs : Any
            Additional query parameters.

        Returns
        -------
        Table or None
            Result table or None if no results.
        """
        try:
            if epoch is None:
                epoch = Time(datetime.utcnow())

            result = Skybot.cone_search(
                coord,
                radius,
                epoch,
                location=self.location,
                **kwargs,
            )

            if result is None or len(result) == 0:
                self._last_result = None
                return None

            if self.object_type != "all":
                mask = self._filter_by_type(result)
                result = result[mask]
                if len(result) == 0:
                    self._last_result = None
                    return None

            self._last_result = result
            return result

        except Exception as e:
            print(f"SkyBot query error: {e}")
            self._last_result = None
            return None

    def query_object(
        self,
        name: str,
        **kwargs: Any,
    ) -> Optional[Table]:
        """
        Query SkyBot by object name.

        Note: SkyBot does not support direct object name queries.
        This method is provided for interface compatibility.

        Parameters
        ----------
        name : str
            Object name to query.
        **kwargs : Any
            Additional query parameters.

        Returns
        -------
        None
            Always returns None (not supported).
        """
        print("SkyBot does not support object name queries.")
        print("Use query_region with an epoch instead.")
        return None

    def _filter_by_type(self, table: Table) -> list:
        """
        Filter results by object type.

        Parameters
        ----------
        table : Table
            Result table from SkyBot.

        Returns
        -------
        list
            Boolean mask for filtering.
        """
        if "Type" not in table.colnames:
            return [True] * len(table)

        type_map = {
            "asteroid": ["Asteroid", "NEA"],
            "comet": ["Comet"],
            "planet": ["Planet", "Satellite"],
        }

        valid_types = type_map.get(self.object_type.lower(), [])
        if not valid_types:
            return [True] * len(table)

        return [t in valid_types for t in table["Type"]]

    def set_location(self, location: str) -> None:
        """
        Set the observatory location code.

        Parameters
        ----------
        location : str
            Observatory code (e.g., "500" for geocentric).
        """
        self.location = location

    def set_object_type(self, object_type: str) -> None:
        """
        Set the object type filter.

        Parameters
        ----------
        object_type : str
            Type of objects: "all", "asteroid", "comet", "planet".
        """
        if object_type.lower() in ("all", "asteroid", "comet", "planet"):
            self.object_type = object_type.lower()
        else:
            print(f"Unknown object type: {object_type}")
            print("Valid types: all, asteroid, comet, planet")

    @staticmethod
    def get_observatory_codes() -> dict:
        """
        Return common observatory codes.

        Returns
        -------
        dict
            Dictionary of observatory codes and names.
        """
        return {
            "500": "Geocentric",
            "309": "Cerro Paranal",
            "568": "Mauna Kea",
            "675": "Palomar Mountain",
            "950": "La Palma",
            "I11": "Gemini South",
            "W84": "Cerro Tololo",
        }
