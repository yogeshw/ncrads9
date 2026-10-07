# NCRADS9 - NCRA DS9-like FITS Viewer
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
A sky position as DS9's dialogs type it, and a radius with its unit.

DS9's catalog and name-resolution dialogs show a position as two entries
under a coordinate menu -- the sky frame (fk4, fk5, icrs, galactic,
ecliptic) and the format (degrees or sexagesimal) -- and a radius with an
`ARRFormat` unit menu (degrees, arcmin, arcsec). This turns those strings
into a `SkyCoord` and a `Quantity` and back, so the dialogs hold text the
way DS9's do and the queries get astropy objects.

Author: Yogesh Wadadekar
"""

from __future__ import annotations

import astropy.units as u
from astropy.coordinates import SkyCoord

#: DS9's sky frames, in its menu's order.
SKY_FRAMES: tuple[str, ...] = ("fk4", "fk5", "icrs", "galactic", "ecliptic")

#: DS9's two sky formats.
SKY_FORMATS: tuple[str, ...] = ("degrees", "sexagesimal")

#: DS9's radius units (`ARRFormat`), in its menu's order.
RADIUS_UNITS: tuple[str, ...] = ("degrees", "arcmin", "arcsec")

#: Each radius unit as an astropy unit.
_UNITS = {"degrees": u.deg, "arcmin": u.arcmin, "arcsec": u.arcsec}


class PositionError(ValueError):
    """A position or radius that cannot be read, for the reason given."""


def _astropy_frame(sky: str) -> dict:
    """The keyword arguments that make a SkyCoord in one of DS9's frames."""
    sky = str(sky).lower()
    if sky == "fk4":
        return {"frame": "fk4", "equinox": "B1950"}
    if sky == "fk5":
        return {"frame": "fk5", "equinox": "J2000"}
    if sky == "galactic":
        return {"frame": "galactic"}
    if sky == "ecliptic":
        return {"frame": "geocentricmeanecliptic"}
    return {"frame": "icrs"}


def _is_equatorial(sky: str) -> bool:
    return str(sky).lower() in ("fk4", "fk5", "icrs")


def format_position(coord: SkyCoord, sky: str = "fk5", skyformat: str = "degrees") -> tuple[str, str]:
    """Two strings for a position, in a DS9 sky frame and format.

    Args:
        coord: The position, in any frame.
        sky: One of `SKY_FRAMES`.
        skyformat: `degrees` or `sexagesimal`.
    """
    converted = coord.transform_to(SkyCoord(0 * u.deg, 0 * u.deg, **_astropy_frame(sky)).frame)
    spherical = converted.spherical
    longitude, latitude = spherical.lon, spherical.lat
    if skyformat == "sexagesimal":
        if _is_equatorial(sky):
            x = longitude.to_string(unit=u.hourangle, sep=":", precision=3, pad=True)
        else:
            x = longitude.to_string(unit=u.deg, sep=":", precision=3, pad=True)
        y = latitude.to_string(unit=u.deg, sep=":", precision=2, alwayssign=True, pad=True)
        return (x, y)
    return (f"{longitude.deg:.7f}", f"{latitude.deg:.7f}")


def parse_position(x: str, y: str, sky: str = "fk5") -> SkyCoord:
    """Read two typed strings as a position in a DS9 sky frame.

    Sexagesimal is recognised by its colons or letters, as DS9's parser does,
    so the format menu need not agree with what was typed.

    Returns:
        The position, in ICRS.

    Raises:
        PositionError: If either string is empty or not a coordinate.
    """
    x, y = str(x).strip(), str(y).strip()
    if not x or not y:
        raise PositionError("a position needs two coordinates")
    sexagesimal = any(mark in x for mark in ":hms ")
    if sexagesimal and _is_equatorial(sky):
        unit = (u.hourangle, u.deg)
    else:
        unit = (u.deg, u.deg)
    try:
        coord = SkyCoord(x, y, unit=unit, **_astropy_frame(sky))
    except Exception as exc:
        raise PositionError(f"{x} {y} is not a position: {exc}") from exc
    return coord.icrs


def radius_quantity(value: str | float, unit: str = "arcmin") -> u.Quantity:
    """A typed radius as an angle.

    Raises:
        PositionError: If it is not a positive number.
    """
    try:
        number = float(str(value).strip())
    except ValueError as exc:
        raise PositionError(f"{value!r} is not a radius") from exc
    if number <= 0:
        raise PositionError("the radius must be greater than zero")
    return number * _UNITS.get(str(unit).lower(), u.arcmin)


def radius_in(angle: u.Quantity, unit: str = "arcmin") -> float:
    """An angle in one of DS9's radius units."""
    return float(angle.to_value(_UNITS.get(str(unit).lower(), u.arcmin)))
