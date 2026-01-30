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
Galactic coordinate transformations.

Author: Yogesh Wadadekar
"""

from typing import Tuple

from astropy.coordinates import SkyCoord, Galactic
import astropy.units as u


def equatorial_to_galactic(
    ra: float,
    dec: float,
    frame: str = "icrs"
) -> Tuple[float, float]:
    """
    Convert equatorial coordinates to Galactic coordinates.
    
    Args:
        ra: Right ascension in degrees.
        dec: Declination in degrees.
        frame: Input equatorial frame (default: 'icrs').
        
    Returns:
        Tuple of (l, b) Galactic coordinates in degrees.
    """
    coord = SkyCoord(ra=ra * u.deg, dec=dec * u.deg, frame=frame)
    galactic = coord.galactic
    
    return (galactic.l.deg, galactic.b.deg)


def galactic_to_equatorial(
    l: float,
    b: float,
    frame: str = "icrs"
) -> Tuple[float, float]:
    """
    Convert Galactic coordinates to equatorial coordinates.
    
    Args:
        l: Galactic longitude in degrees.
        b: Galactic latitude in degrees.
        frame: Output equatorial frame (default: 'icrs').
        
    Returns:
        Tuple of (ra, dec) equatorial coordinates in degrees.
    """
    coord = SkyCoord(l=l * u.deg, b=b * u.deg, frame="galactic")
    equatorial = coord.transform_to(frame)
    
    return (equatorial.ra.deg, equatorial.dec.deg)


def galactic_to_string(l: float, b: float, precision: int = 4) -> str:
    """
    Format Galactic coordinates as a string.
    
    Args:
        l: Galactic longitude in degrees.
        b: Galactic latitude in degrees.
        precision: Decimal precision.
        
    Returns:
        Formatted string "l=XXX.XXXX, b=+YY.YYYY".
    """
    sign = "+" if b >= 0 else ""
    return f"l={l:.{precision}f}, b={sign}{b:.{precision}f}"
