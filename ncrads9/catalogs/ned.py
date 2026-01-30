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
NED (NASA/IPAC Extragalactic Database) query interface.

Author: Yogesh Wadadekar
"""

from typing import Optional, Any

from astropy.coordinates import SkyCoord
from astropy.table import Table
import astropy.units as u
from astroquery.ned import Ned

from .catalog_base import CatalogBase


class NEDCatalog(CatalogBase):
    """NED catalog query class using astroquery.ned."""

    def __init__(self) -> None:
        """Initialize NED catalog query."""
        super().__init__(
            name="NED",
            description="NASA/IPAC Extragalactic Database",
        )

    def query_region(
        self,
        coord: SkyCoord,
        radius: u.Quantity,
        equinox: str = "J2000.0",
        **kwargs: Any,
    ) -> Optional[Table]:
        """
        Query NED for objects within a region.

        Parameters
        ----------
        coord : SkyCoord
            Center coordinate for the query.
        radius : Quantity
            Search radius with angular units.
        equinox : str, optional
            Coordinate equinox. Default is "J2000.0".
        **kwargs : Any
            Additional query parameters.

        Returns
        -------
        Table or None
            Result table or None if no results.
        """
        try:
            result = Ned.query_region(
                coord,
                radius=radius,
                equinox=equinox,
                **kwargs,
            )

            self._last_result = result
            return result

        except Exception as e:
            print(f"NED query error: {e}")
            self._last_result = None
            return None

    def query_object(
        self,
        name: str,
        **kwargs: Any,
    ) -> Optional[Table]:
        """
        Query NED by object name.

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
            result = Ned.query_object(name, **kwargs)
            self._last_result = result
            return result

        except Exception as e:
            print(f"NED query error: {e}")
            self._last_result = None
            return None

    def query_refcode(
        self,
        refcode: str,
        **kwargs: Any,
    ) -> Optional[Table]:
        """
        Query NED by reference code.

        Parameters
        ----------
        refcode : str
            NED reference code (e.g., "1997AJ....113....22G").
        **kwargs : Any
            Additional query parameters.

        Returns
        -------
        Table or None
            Result table or None if no results.
        """
        try:
            result = Ned.query_refcode(refcode, **kwargs)
            self._last_result = result
            return result

        except Exception as e:
            print(f"NED refcode query error: {e}")
            self._last_result = None
            return None

    def get_images(
        self,
        name: str,
        **kwargs: Any,
    ) -> Optional[Table]:
        """
        Get image metadata for an object.

        Parameters
        ----------
        name : str
            Object name to query.
        **kwargs : Any
            Additional query parameters.

        Returns
        -------
        Table or None
            Table of image metadata or None.
        """
        try:
            return Ned.get_images(name, **kwargs)
        except Exception as e:
            print(f"NED get_images error: {e}")
            return None

    def get_spectra(
        self,
        name: str,
        **kwargs: Any,
    ) -> Optional[Table]:
        """
        Get spectra metadata for an object.

        Parameters
        ----------
        name : str
            Object name to query.
        **kwargs : Any
            Additional query parameters.

        Returns
        -------
        Table or None
            Table of spectra metadata or None.
        """
        try:
            return Ned.get_spectra(name, **kwargs)
        except Exception as e:
            print(f"NED get_spectra error: {e}")
            return None

    def get_photometry(
        self,
        name: str,
        **kwargs: Any,
    ) -> Optional[Table]:
        """
        Get photometry data for an object.

        Parameters
        ----------
        name : str
            Object name to query.
        **kwargs : Any
            Additional query parameters.

        Returns
        -------
        Table or None
            Table of photometry data or None.
        """
        try:
            return Ned.get_table(name, table="photometry", **kwargs)
        except Exception as e:
            print(f"NED get_photometry error: {e}")
            return None

    def get_redshifts(
        self,
        name: str,
        **kwargs: Any,
    ) -> Optional[Table]:
        """
        Get redshift measurements for an object.

        Parameters
        ----------
        name : str
            Object name to query.
        **kwargs : Any
            Additional query parameters.

        Returns
        -------
        Table or None
            Table of redshift data or None.
        """
        try:
            return Ned.get_table(name, table="redshifts", **kwargs)
        except Exception as e:
            print(f"NED get_redshifts error: {e}")
            return None
