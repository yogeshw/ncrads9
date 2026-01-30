# NCRADS9 - NCRA DS9 Visualization Tool
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
Ecliptic coordinate transformations.

Author: Yogesh Wadadekar
"""

from typing import Tuple, Optional

from astropy.coordinates import SkyCoord, GeocentricMeanEcliptic, BarycentricMeanEcliptic
import astropy.units as u
from astropy.time import Time


def equatorial_to_ecliptic(
    ra: float,
    dec: float,
    frame: str = "icrs",
    equinox: Optional[float] = None,
    barycentric: bool = False
) -> Tuple[float, float]:
    """
    Convert equatorial coordinates to ecliptic coordinates.
    
    Args:
        ra: Right ascension in degrees.
        dec: Declination in degrees.
        frame: Input equatorial frame (default: 'icrs').
        equinox: Equinox as Julian year (default: J2000.0).
        barycentric: If True, use barycentric ecliptic frame.
        
    Returns:
        Tuple of (lon, lat) ecliptic coordinates in degrees.
    """
    if equinox is None:
        equinox = 2000.0
    
    coord = SkyCoord(ra=ra * u.deg, dec=dec * u.deg, frame=frame)
    
    if barycentric:
        ecliptic_frame = BarycentricMeanEcliptic(equinox=Time(equinox, format="jyear"))
    else:
        ecliptic_frame = GeocentricMeanEcliptic(equinox=Time(equinox, format="jyear"))
    
    ecliptic = coord.transform_to(ecliptic_frame)
    
    return (ecliptic.lon.deg, ecliptic.lat.deg)


def ecliptic_to_equatorial(
    lon: float,
    lat: float,
    frame: str = "icrs",
    equinox: Optional[float] = None,
    barycentric: bool = False
) -> Tuple[float, float]:
    """
    Convert ecliptic coordinates to equatorial coordinates.
    
    Args:
        lon: Ecliptic longitude in degrees.
        lat: Ecliptic latitude in degrees.
        frame: Output equatorial frame (default: 'icrs').
        equinox: Equinox as Julian year (default: J2000.0).
        barycentric: If True, input is in barycentric ecliptic frame.
        
    Returns:
        Tuple of (ra, dec) equatorial coordinates in degrees.
    """
    if equinox is None:
        equinox = 2000.0
    
    if barycentric:
        ecliptic_frame = BarycentricMeanEcliptic(equinox=Time(equinox, format="jyear"))
    else:
        ecliptic_frame = GeocentricMeanEcliptic(equinox=Time(equinox, format="jyear"))
    
    coord = SkyCoord(lon=lon * u.deg, lat=lat * u.deg, frame=ecliptic_frame)
    equatorial = coord.transform_to(frame)
    
    return (equatorial.ra.deg, equatorial.dec.deg)


def ecliptic_to_string(lon: float, lat: float, precision: int = 4) -> str:
    """
    Format ecliptic coordinates as a string.
    
    Args:
        lon: Ecliptic longitude in degrees.
        lat: Ecliptic latitude in degrees.
        precision: Decimal precision.
        
    Returns:
        Formatted string "λ=XXX.XXXX°, β=+YY.YYYY°".
    """
    sign = "+" if lat >= 0 else ""
    return f"λ={lon:.{precision}f}°, β={sign}{lat:.{precision}f}°"
