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
SDSS (Sloan Digital Sky Survey) catalog query interface.

Author: Yogesh Wadadekar
"""

from typing import Any

import astropy.units as u
from astropy.coordinates import SkyCoord
from astropy.table import Table
from astroquery.sdss import SDSS

from .catalog_base import CatalogBase


class SDSSCatalog(CatalogBase):
    """SDSS catalog query class using astroquery.sdss."""

    # Default photometric columns
    DEFAULT_PHOTO_FIELDS: list[str] = [
        "ra",
        "dec",
        "objid",
        "type",
        "u",
        "g",
        "r",
        "i",
        "z",
        "err_u",
        "err_g",
        "err_r",
        "err_i",
        "err_z",
    ]

    # Default spectroscopic columns
    DEFAULT_SPEC_FIELDS: list[str] = [
        "ra",
        "dec",
        "objid",
        "specobjid",
        "class",
        "subclass",
        "z",
        "zerr",
        "zwarning",
    ]

    def __init__(
        self,
        data_release: int = 18,
        photoobj_fields: list[str] | None = None,
        specobj_fields: list[str] | None = None,
    ) -> None:
        """
        Initialize SDSS catalog query.

        Parameters
        ----------
        data_release : int, optional
            SDSS data release number. Default is 18.
        photoobj_fields : list of str, optional
            Photometric fields to retrieve.
        specobj_fields : list of str, optional
            Spectroscopic fields to retrieve.
        """
        super().__init__(
            name="SDSS",
            description="Sloan Digital Sky Survey",
        )
        self.data_release: int = data_release
        self.photoobj_fields: list[str] = photoobj_fields or self.DEFAULT_PHOTO_FIELDS
        self.specobj_fields: list[str] = specobj_fields or self.DEFAULT_SPEC_FIELDS

    def query_region(
        self,
        coord: SkyCoord,
        radius: u.Quantity,
        spectro: bool = False,
        **kwargs: Any,
    ) -> Table | None:
        """
        Query SDSS for objects within a region.

        Parameters
        ----------
        coord : SkyCoord
            Center coordinate for the query.
        radius : Quantity
            Search radius with angular units.
        spectro : bool, optional
            If True, query spectroscopic catalog. Default is False.
        **kwargs : Any
            Additional query parameters.

        Returns
        -------
        Table or None
            Result table or None if no results.
        """
        try:
            result = SDSS.query_region(
                coord,
                radius=radius,
                spectro=spectro,
                photoobj_fields=self.photoobj_fields,
                specobj_fields=self.specobj_fields if spectro else None,
                data_release=self.data_release,
                **kwargs,
            )

            self._last_result = result
            return result

        except Exception as e:
            print(f"SDSS query error: {e}")
            self._last_result = None
            return None

    def query_object(
        self,
        name: str,
        **kwargs: Any,
    ) -> Table | None:
        """
        Query SDSS by object name.

        Parameters
        ----------
        name : str
            Object name to query (resolved via Sesame).
        **kwargs : Any
            Additional query parameters.

        Returns
        -------
        Table or None
            Result table or None if no results.
        """
        try:
            coord = SkyCoord.from_name(name)
            radius = kwargs.pop("radius", 1 * u.arcmin)
            return self.query_region(coord, radius=radius, **kwargs)

        except Exception as e:
            print(f"SDSS object query error: {e}")
            self._last_result = None
            return None

    def query_sql(
        self,
        sql: str,
        **kwargs: Any,
    ) -> Table | None:
        """
        Execute SQL query on SDSS database.

        Parameters
        ----------
        sql : str
            SQL query string.
        **kwargs : Any
            Additional query parameters.

        Returns
        -------
        Table or None
            Result table or None if query fails.
        """
        try:
            result = SDSS.query_sql(
                sql,
                data_release=self.data_release,
                **kwargs,
            )
            self._last_result = result
            return result

        except Exception as e:
            print(f"SDSS SQL query error: {e}")
            self._last_result = None
            return None

    def query_crossid(
        self,
        coords: SkyCoord,
        radius: u.Quantity = 2 * u.arcsec,
        spectro: bool = False,
        **kwargs: Any,
    ) -> Table | None:
        """
        Cross-match coordinates with SDSS.

        Parameters
        ----------
        coords : SkyCoord
            Coordinates to cross-match.
        radius : Quantity, optional
            Match radius. Default is 2 arcsec.
        spectro : bool, optional
            If True, query spectroscopic catalog.
        **kwargs : Any
            Additional query parameters.

        Returns
        -------
        Table or None
            Result table or None if no matches.
        """
        try:
            result = SDSS.query_crossid(
                coords,
                radius=radius,
                spectro=spectro,
                photoobj_fields=self.photoobj_fields,
                specobj_fields=self.specobj_fields if spectro else None,
                data_release=self.data_release,
                **kwargs,
            )
            self._last_result = result
            return result

        except Exception as e:
            print(f"SDSS crossid query error: {e}")
            self._last_result = None
            return None

    def get_spectra(
        self,
        matches: Table,
        **kwargs: Any,
    ) -> list[Any] | None:
        """
        Download spectra for matched objects.

        Parameters
        ----------
        matches : Table
            Result table from a spectroscopic query.
        **kwargs : Any
            Additional parameters.

        Returns
        -------
        list or None
            List of spectra HDU objects or None.
        """
        try:
            return SDSS.get_spectra(
                matches,
                data_release=self.data_release,
                **kwargs,
            )
        except Exception as e:
            print(f"SDSS get_spectra error: {e}")
            return None

    def get_images(
        self,
        matches: Table,
        band: str = "r",
        **kwargs: Any,
    ) -> list[Any] | None:
        """
        Download images for matched objects.

        Parameters
        ----------
        matches : Table
            Result table from a photometric query.
        band : str, optional
            SDSS band to download. Default is "r".
        **kwargs : Any
            Additional parameters.

        Returns
        -------
        list or None
            List of image HDU objects or None.
        """
        try:
            return SDSS.get_images(
                matches,
                band=band,
                data_release=self.data_release,
                **kwargs,
            )
        except Exception as e:
            print(f"SDSS get_images error: {e}")
            return None

    def set_data_release(self, release: int) -> None:
        """Set the SDSS data release number."""
        self.data_release = release
