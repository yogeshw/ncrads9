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
Abstract base class for catalog queries.

Author: Yogesh Wadadekar
"""

from abc import ABC, abstractmethod
from typing import Optional, Tuple, List, Any

from astropy.coordinates import SkyCoord
from astropy.table import Table
import astropy.units as u


class CatalogBase(ABC):
    """Abstract base class for astronomical catalog queries."""

    def __init__(self, name: str, description: str = "") -> None:
        """
        Initialize catalog base.

        Parameters
        ----------
        name : str
            Name of the catalog.
        description : str, optional
            Description of the catalog.
        """
        self.name: str = name
        self.description: str = description
        self._last_result: Optional[Table] = None

    @abstractmethod
    def query_region(
        self,
        coord: SkyCoord,
        radius: u.Quantity,
        **kwargs: Any,
    ) -> Optional[Table]:
        """
        Query catalog for objects within a region.

        Parameters
        ----------
        coord : SkyCoord
            Center coordinate for the query.
        radius : Quantity
            Search radius with angular units.
        **kwargs : Any
            Additional query parameters.

        Returns
        -------
        Table or None
            Result table or None if no results.
        """
        pass

    @abstractmethod
    def query_object(
        self,
        name: str,
        **kwargs: Any,
    ) -> Optional[Table]:
        """
        Query catalog by object name.

        Parameters
        ----------
        name : str
            Object name to query.
        **kwargs : Any
            Additional query parameters.

        Returns
        -------
        Table or None
            Result table or None if no results.
        """
        pass

    def get_coordinates(self, table: Table) -> Optional[List[SkyCoord]]:
        """
        Extract coordinates from result table.

        Parameters
        ----------
        table : Table
            Result table from query.

        Returns
        -------
        list of SkyCoord or None
            List of coordinates or None if extraction fails.
        """
        ra_col: Optional[str] = None
        dec_col: Optional[str] = None

        for col in table.colnames:
            col_lower = col.lower()
            if col_lower in ("ra", "_ra", "raj2000", "ra_icrs"):
                ra_col = col
            elif col_lower in ("dec", "_dec", "dej2000", "de", "dec_icrs"):
                dec_col = col

        if ra_col is None or dec_col is None:
            return None

        coords: List[SkyCoord] = []
        for row in table:
            try:
                coord = SkyCoord(
                    ra=row[ra_col],
                    dec=row[dec_col],
                    unit=(u.deg, u.deg),
                    frame="icrs",
                )
                coords.append(coord)
            except Exception:
                continue

        return coords if coords else None

    @property
    def last_result(self) -> Optional[Table]:
        """Return the last query result."""
        return self._last_result

    def clear_cache(self) -> None:
        """Clear cached results."""
        self._last_result = None
