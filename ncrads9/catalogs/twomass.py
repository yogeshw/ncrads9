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
2MASS (Two Micron All Sky Survey) catalog query interface.

Author: Yogesh Wadadekar
"""

from typing import Optional, List, Any

from astropy.coordinates import SkyCoord
from astropy.table import Table
import astropy.units as u
from astroquery.vizier import Vizier

from .catalog_base import CatalogBase


class TwoMASSCatalog(CatalogBase):
    """2MASS catalog query class using VizieR."""

    # 2MASS Point Source Catalog
    CATALOG_PSC: str = "II/246/out"

    # 2MASS Extended Source Catalog
    CATALOG_XSC: str = "VII/233/xsc"

    # Default columns for PSC
    DEFAULT_PSC_COLUMNS: List[str] = [
        "RAJ2000",
        "DEJ2000",
        "2MASS",
        "Jmag",
        "e_Jmag",
        "Hmag",
        "e_Hmag",
        "Kmag",
        "e_Kmag",
        "Qflg",
    ]

    # Default columns for XSC
    DEFAULT_XSC_COLUMNS: List[str] = [
        "RAJ2000",
        "DEJ2000",
        "2MASX",
        "Jmag",
        "e_Jmag",
        "Hmag",
        "e_Hmag",
        "Kmag",
        "e_Kmag",
        "r.ext",
    ]

    def __init__(
        self,
        catalog_type: str = "psc",
        columns: Optional[List[str]] = None,
        row_limit: int = -1,
    ) -> None:
        """
        Initialize 2MASS catalog query.

        Parameters
        ----------
        catalog_type : str, optional
            Catalog type: "psc" (point source) or "xsc" (extended source).
            Default is "psc".
        columns : list of str, optional
            Columns to retrieve. Default depends on catalog type.
        row_limit : int, optional
            Maximum number of rows to return. -1 for unlimited.
        """
        super().__init__(
            name="2MASS",
            description="Two Micron All Sky Survey",
        )
        self.catalog_type: str = catalog_type.lower()
        self.row_limit: int = row_limit

        if self.catalog_type == "xsc":
            self._catalog: str = self.CATALOG_XSC
            self._default_columns: List[str] = self.DEFAULT_XSC_COLUMNS
        else:
            self._catalog = self.CATALOG_PSC
            self._default_columns = self.DEFAULT_PSC_COLUMNS

        self.columns: List[str] = columns or self._default_columns
        self._vizier: Vizier = self._create_vizier()

    def _create_vizier(self) -> Vizier:
        """Create configured Vizier instance."""
        return Vizier(
            columns=self.columns,
            row_limit=self.row_limit,
            catalog=self._catalog,
        )

    def query_region(
        self,
        coord: SkyCoord,
        radius: u.Quantity,
        **kwargs: Any,
    ) -> Optional[Table]:
        """
        Query 2MASS for objects within a region.

        Parameters
        ----------
        coord : SkyCoord
            Center coordinate for the query.
        radius : Quantity
            Search radius with angular units.
        **kwargs : Any
            Additional query parameters passed to Vizier.

        Returns
        -------
        Table or None
            Result table or None if no results.
        """
        try:
            result = self._vizier.query_region(
                coord,
                radius=radius,
                **kwargs,
            )

            if result is None or len(result) == 0:
                self._last_result = None
                return None

            self._last_result = result[0]
            return self._last_result

        except Exception as e:
            print(f"2MASS query error: {e}")
            self._last_result = None
            return None

    def query_object(
        self,
        name: str,
        radius: u.Quantity = 1 * u.arcmin,
        **kwargs: Any,
    ) -> Optional[Table]:
        """
        Query 2MASS by object name.

        Parameters
        ----------
        name : str
            Object name to query.
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
            print(f"2MASS object query error: {e}")
            self._last_result = None
            return None

    def query_constraints(
        self,
        **constraints: Any,
    ) -> Optional[Table]:
        """
        Query 2MASS with magnitude or other constraints.

        Parameters
        ----------
        **constraints : Any
            Constraint parameters (e.g., Jmag="<10", Hmag=">12").

        Returns
        -------
        Table or None
            Result table or None if no results.
        """
        try:
            result = self._vizier.query_constraints(**constraints)

            if result is None or len(result) == 0:
                self._last_result = None
                return None

            self._last_result = result[0]
            return self._last_result

        except Exception as e:
            print(f"2MASS constraints query error: {e}")
            self._last_result = None
            return None

    def set_catalog_type(self, catalog_type: str) -> None:
        """
        Set the catalog type.

        Parameters
        ----------
        catalog_type : str
            Catalog type: "psc" (point source) or "xsc" (extended source).
        """
        self.catalog_type = catalog_type.lower()

        if self.catalog_type == "xsc":
            self._catalog = self.CATALOG_XSC
            self._default_columns = self.DEFAULT_XSC_COLUMNS
        else:
            self._catalog = self.CATALOG_PSC
            self._default_columns = self.DEFAULT_PSC_COLUMNS

        self.columns = self._default_columns
        self._vizier = self._create_vizier()

    def set_columns(self, columns: List[str]) -> None:
        """Set the columns to retrieve."""
        self.columns = columns
        self._vizier = self._create_vizier()

    def set_row_limit(self, limit: int) -> None:
        """Set the maximum number of rows to return."""
        self.row_limit = limit
        self._vizier = self._create_vizier()

    def get_jh_color(self, table: Table) -> Optional[List[float]]:
        """
        Calculate J-H color from table.

        Parameters
        ----------
        table : Table
            Result table with Jmag and Hmag columns.

        Returns
        -------
        list of float or None
            J-H color values or None.
        """
        if "Jmag" not in table.colnames or "Hmag" not in table.colnames:
            return None

        return [
            float(row["Jmag"] - row["Hmag"])
            for row in table
            if row["Jmag"] is not None and row["Hmag"] is not None
        ]

    def get_hk_color(self, table: Table) -> Optional[List[float]]:
        """
        Calculate H-K color from table.

        Parameters
        ----------
        table : Table
            Result table with Hmag and Kmag columns.

        Returns
        -------
        list of float or None
            H-K color values or None.
        """
        if "Hmag" not in table.colnames or "Kmag" not in table.colnames:
            return None

        return [
            float(row["Hmag"] - row["Kmag"])
            for row in table
            if row["Hmag"] is not None and row["Kmag"] is not None
        ]
