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
VizieR catalog query interface.

Author: Yogesh Wadadekar
"""

from typing import Optional, List, Any

from astropy.coordinates import SkyCoord
from astropy.table import Table, vstack
import astropy.units as u
from astroquery.vizier import Vizier

from .catalog_base import CatalogBase


class VizierCatalog(CatalogBase):
    """VizieR catalog query class using astroquery.vizier."""

    def __init__(
        self,
        catalog: Optional[str] = None,
        columns: Optional[List[str]] = None,
        row_limit: int = -1,
    ) -> None:
        """
        Initialize VizieR catalog query.

        Parameters
        ----------
        catalog : str, optional
            VizieR catalog identifier (e.g., "II/246" for 2MASS).
        columns : list of str, optional
            Columns to retrieve. Default is all columns.
        row_limit : int, optional
            Maximum number of rows to return. -1 for unlimited.
        """
        super().__init__(name="VizieR", description="VizieR catalog service")
        self.catalog: Optional[str] = catalog
        self.columns: Optional[List[str]] = columns
        self.row_limit: int = row_limit
        self._vizier: Vizier = self._create_vizier()

    def _create_vizier(self) -> Vizier:
        """Create configured Vizier instance."""
        v = Vizier(
            columns=self.columns if self.columns else ["*"],
            row_limit=self.row_limit,
        )
        if self.catalog:
            v.catalog = self.catalog
        return v

    def query_region(
        self,
        coord: SkyCoord,
        radius: u.Quantity,
        catalog: Optional[str] = None,
        **kwargs: Any,
    ) -> Optional[Table]:
        """
        Query VizieR for objects within a region.

        Parameters
        ----------
        coord : SkyCoord
            Center coordinate for the query.
        radius : Quantity
            Search radius with angular units.
        catalog : str, optional
            Override catalog identifier for this query.
        **kwargs : Any
            Additional query parameters passed to Vizier.

        Returns
        -------
        Table or None
            Result table or None if no results.
        """
        try:
            cat = catalog or self.catalog
            if cat:
                result = self._vizier.query_region(
                    coord,
                    radius=radius,
                    catalog=cat,
                    **kwargs,
                )
            else:
                result = self._vizier.query_region(
                    coord,
                    radius=radius,
                    **kwargs,
                )

            if result is None or len(result) == 0:
                self._last_result = None
                return None

            if len(result) == 1:
                self._last_result = result[0]
            else:
                self._last_result = vstack(result)

            return self._last_result

        except Exception as e:
            print(f"VizieR query error: {e}")
            self._last_result = None
            return None

    def query_object(
        self,
        name: str,
        catalog: Optional[str] = None,
        **kwargs: Any,
    ) -> Optional[Table]:
        """
        Query VizieR by object name.

        Parameters
        ----------
        name : str
            Object name to query.
        catalog : str, optional
            Override catalog identifier for this query.
        **kwargs : Any
            Additional query parameters.

        Returns
        -------
        Table or None
            Result table or None if no results.
        """
        try:
            cat = catalog or self.catalog
            if cat:
                result = self._vizier.query_object(
                    name,
                    catalog=cat,
                    **kwargs,
                )
            else:
                result = self._vizier.query_object(name, **kwargs)

            if result is None or len(result) == 0:
                self._last_result = None
                return None

            if len(result) == 1:
                self._last_result = result[0]
            else:
                self._last_result = vstack(result)

            return self._last_result

        except Exception as e:
            print(f"VizieR query error: {e}")
            self._last_result = None
            return None

    def find_catalogs(self, keywords: str) -> Optional[Table]:
        """
        Find VizieR catalogs matching keywords.

        Parameters
        ----------
        keywords : str
            Keywords to search for.

        Returns
        -------
        Table or None
            Table of matching catalogs.
        """
        try:
            result = Vizier.find_catalogs(keywords)
            if result:
                return Table(
                    rows=[(k, v.description) for k, v in result.items()],
                    names=["catalog", "description"],
                )
            return None
        except Exception as e:
            print(f"VizieR catalog search error: {e}")
            return None

    def set_catalog(self, catalog: str) -> None:
        """Set the default catalog identifier."""
        self.catalog = catalog
        self._vizier = self._create_vizier()

    def set_columns(self, columns: List[str]) -> None:
        """Set the columns to retrieve."""
        self.columns = columns
        self._vizier = self._create_vizier()

    def set_row_limit(self, limit: int) -> None:
        """Set the maximum number of rows to return."""
        self.row_limit = limit
        self._vizier = self._create_vizier()
