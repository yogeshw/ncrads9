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
FK4/FK5 coordinate frame transformations.

Author: Yogesh Wadadekar
"""

from typing import Tuple, Optional

from astropy.coordinates import SkyCoord, FK4, FK5
import astropy.units as u
from astropy.time import Time


def convert_fk4_to_fk5(
    ra: float,
    dec: float,
    equinox: Optional[float] = None,
    epoch: Optional[float] = None
) -> Tuple[float, float]:
    """
    Convert FK4 coordinates to FK5.
    
    Args:
        ra: Right ascension in degrees (FK4).
        dec: Declination in degrees (FK4).
        equinox: FK4 equinox as Besselian year (default: B1950.0).
        epoch: Observation epoch as Besselian year (default: same as equinox).
        
    Returns:
        Tuple of (ra, dec) in degrees (FK5 J2000.0).
    """
    if equinox is None:
        equinox = 1950.0
    
    if epoch is None:
        epoch = equinox
    
    fk4_frame = FK4(
        equinox=Time(equinox, format="byear"),
        obstime=Time(epoch, format="byear")
    )
    
    coord = SkyCoord(ra=ra * u.deg, dec=dec * u.deg, frame=fk4_frame)
    fk5_coord = coord.transform_to(FK5(equinox=Time(2000.0, format="jyear")))
    
    return (fk5_coord.ra.deg, fk5_coord.dec.deg)


def convert_fk5_to_fk4(
    ra: float,
    dec: float,
    equinox: Optional[float] = None,
    epoch: Optional[float] = None
) -> Tuple[float, float]:
    """
    Convert FK5 coordinates to FK4.
    
    Args:
        ra: Right ascension in degrees (FK5).
        dec: Declination in degrees (FK5).
        equinox: FK5 equinox as Julian year (default: J2000.0).
        epoch: Target FK4 observation epoch as Besselian year (default: B1950.0).
        
    Returns:
        Tuple of (ra, dec) in degrees (FK4 B1950.0).
    """
    if equinox is None:
        equinox = 2000.0
    
    if epoch is None:
        epoch = 1950.0
    
    fk5_frame = FK5(equinox=Time(equinox, format="jyear"))
    
    coord = SkyCoord(ra=ra * u.deg, dec=dec * u.deg, frame=fk5_frame)
    fk4_coord = coord.transform_to(
        FK4(
            equinox=Time(1950.0, format="byear"),
            obstime=Time(epoch, format="byear")
        )
    )
    
    return (fk4_coord.ra.deg, fk4_coord.dec.deg)


def precess_fk5(
    ra: float,
    dec: float,
    from_equinox: float,
    to_equinox: float
) -> Tuple[float, float]:
    """
    Precess FK5 coordinates between equinoxes.
    
    Args:
        ra: Right ascension in degrees.
        dec: Declination in degrees.
        from_equinox: Source equinox as Julian year.
        to_equinox: Target equinox as Julian year.
        
    Returns:
        Tuple of (ra, dec) in degrees at the target equinox.
    """
    from_frame = FK5(equinox=Time(from_equinox, format="jyear"))
    to_frame = FK5(equinox=Time(to_equinox, format="jyear"))
    
    coord = SkyCoord(ra=ra * u.deg, dec=dec * u.deg, frame=from_frame)
    precessed = coord.transform_to(to_frame)
    
    return (precessed.ra.deg, precessed.dec.deg)


def precess_fk4(
    ra: float,
    dec: float,
    from_equinox: float,
    to_equinox: float
) -> Tuple[float, float]:
    """
    Precess FK4 coordinates between equinoxes.
    
    Args:
        ra: Right ascension in degrees.
        dec: Declination in degrees.
        from_equinox: Source equinox as Besselian year.
        to_equinox: Target equinox as Besselian year.
        
    Returns:
        Tuple of (ra, dec) in degrees at the target equinox.
    """
    from_frame = FK4(
        equinox=Time(from_equinox, format="byear"),
        obstime=Time(from_equinox, format="byear")
    )
    to_frame = FK4(
        equinox=Time(to_equinox, format="byear"),
        obstime=Time(to_equinox, format="byear")
    )
    
    coord = SkyCoord(ra=ra * u.deg, dec=dec * u.deg, frame=from_frame)
    precessed = coord.transform_to(to_frame)
    
    return (precessed.ra.deg, precessed.dec.deg)
