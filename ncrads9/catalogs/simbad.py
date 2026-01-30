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
SIMBAD catalog query interface.

Author: Yogesh Wadadekar
"""

from typing import Optional, List, Any

from astropy.coordinates import SkyCoord
from astropy.table import Table
import astropy.units as u
from astroquery.simbad import Simbad

from .catalog_base import CatalogBase


class SimbadCatalog(CatalogBase):
    """SIMBAD catalog query class using astroquery.simbad."""

    def __init__(
        self,
        votable_fields: Optional[List[str]] = None,
        row_limit: int = 0,
    ) -> None:
        """
        Initialize SIMBAD catalog query.

        Parameters
        ----------
        votable_fields : list of str, optional
            Additional VOTable fields to retrieve.
        row_limit : int, optional
            Maximum number of rows to return. 0 for unlimited.
        """
        super().__init__(
            name="SIMBAD",
            description="SIMBAD astronomical database",
        )
        self.votable_fields: Optional[List[str]] = votable_fields
        self.row_limit: int = row_limit
        self._simbad: Simbad = self._create_simbad()

    def _create_simbad(self) -> Simbad:
        """Create configured Simbad instance."""
        s = Simbad()
        s.ROW_LIMIT = self.row_limit

        if self.votable_fields:
            for field in self.votable_fields:
                s.add_votable_fields(field)

        return s

    def query_region(
        self,
        coord: SkyCoord,
        radius: u.Quantity,
        **kwargs: Any,
    ) -> Optional[Table]:
        """
        Query SIMBAD for objects within a region.

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
        try:
            result = self._simbad.query_region(
                coord,
                radius=radius,
                **kwargs,
            )

            self._last_result = result
            return result

        except Exception as e:
            print(f"SIMBAD query error: {e}")
            self._last_result = None
            return None

    def query_object(
        self,
        name: str,
        **kwargs: Any,
    ) -> Optional[Table]:
        """
        Query SIMBAD by object name.

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
        try:
            result = self._simbad.query_object(name, **kwargs)
            self._last_result = result
            return result

        except Exception as e:
            print(f"SIMBAD query error: {e}")
            self._last_result = None
            return None

    def query_objectids(self, name: str) -> Optional[Table]:
        """
        Query all identifiers for an object.

        Parameters
        ----------
        name : str
            Object name to query.

        Returns
        -------
        Table or None
            Table of identifiers or None.
        """
        try:
            return self._simbad.query_objectids(name)
        except Exception as e:
            print(f"SIMBAD objectids query error: {e}")
            return None

    def query_bibcode(
        self,
        bibcode: str,
        **kwargs: Any,
    ) -> Optional[Table]:
        """
        Query objects associated with a bibcode.

        Parameters
        ----------
        bibcode : str
            ADS bibcode to query.
        **kwargs : Any
            Additional query parameters.

        Returns
        -------
        Table or None
            Result table or None if no results.
        """
        try:
            result = self._simbad.query_bibcode(bibcode, **kwargs)
            self._last_result = result
            return result

        except Exception as e:
            print(f"SIMBAD bibcode query error: {e}")
            self._last_result = None
            return None

    def query_criteria(
        self,
        criteria: str,
        **kwargs: Any,
    ) -> Optional[Table]:
        """
        Query SIMBAD using criteria string.

        Parameters
        ----------
        criteria : str
            SIMBAD criteria query string.
        **kwargs : Any
            Additional query parameters.

        Returns
        -------
        Table or None
            Result table or None if no results.
        """
        try:
            result = self._simbad.query_criteria(criteria, **kwargs)
            self._last_result = result
            return result

        except Exception as e:
            print(f"SIMBAD criteria query error: {e}")
            self._last_result = None
            return None

    def add_votable_fields(self, *fields: str) -> None:
        """Add VOTable fields to retrieve."""
        for field in fields:
            self._simbad.add_votable_fields(field)
            if self.votable_fields is None:
                self.votable_fields = []
            self.votable_fields.append(field)

    def reset_votable_fields(self) -> None:
        """Reset VOTable fields to defaults."""
        self._simbad.reset_votable_fields()
        self.votable_fields = None

    def set_row_limit(self, limit: int) -> None:
        """Set the maximum number of rows to return."""
        self.row_limit = limit
        self._simbad.ROW_LIMIT = limit
