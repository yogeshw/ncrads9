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
World Coordinate System (WCS) coordinate handling.

Author: Yogesh Wadadekar
"""

from typing import Tuple, Optional, Union

from astropy.coordinates import SkyCoord
import astropy.units as u

from .coord_system import CoordSystem, CoordSystemType
from .sexagesimal import degrees_to_hms, degrees_to_dms


class WCSCoords(CoordSystem):
    """Coordinate system for World Coordinate System (WCS) coordinates."""
    
    def __init__(
        self,
        ra: float = 0.0,
        dec: float = 0.0,
        frame: str = "icrs",
        unit: str = "deg"
    ) -> None:
        """
        Initialize WCS coordinates.
        
        Args:
            ra: Right ascension in specified units.
            dec: Declination in specified units.
            frame: Coordinate frame (e.g., 'icrs', 'fk5', 'fk4', 'galactic').
            unit: Unit of input coordinates ('deg' or 'rad').
        """
        super().__init__(CoordSystemType.WCS)
        self._frame = frame
        
        if unit == "rad":
            ra = ra * 180.0 / 3.141592653589793
            dec = dec * 180.0 / 3.141592653589793
        
        self._skycoord = SkyCoord(ra=ra * u.deg, dec=dec * u.deg, frame=frame)
    
    @property
    def ra(self) -> float:
        """Return the right ascension in degrees."""
        return self._skycoord.ra.deg
    
    @property
    def dec(self) -> float:
        """Return the declination in degrees."""
        return self._skycoord.dec.deg
    
    @property
    def frame(self) -> str:
        """Return the coordinate frame."""
        return self._frame
    
    @property
    def skycoord(self) -> SkyCoord:
        """Return the underlying astropy SkyCoord object."""
        return self._skycoord
    
    def get_coordinates(self) -> Tuple[float, float]:
        """
        Get the WCS coordinates as a tuple.
        
        Returns:
            A tuple of (ra, dec) in degrees.
        """
        return (self.ra, self.dec)
    
    def set_coordinates(self, ra: float, dec: float) -> None:
        """
        Set the WCS coordinates.
        
        Args:
            ra: Right ascension in degrees.
            dec: Declination in degrees.
        """
        self._skycoord = SkyCoord(ra=ra * u.deg, dec=dec * u.deg, frame=self._frame)
    
    def to_string(self, precision: Optional[int] = None) -> str:
        """
        Convert WCS coordinates to a string representation in degrees.
        
        Args:
            precision: Optional decimal precision for formatting.
            
        Returns:
            String representation of the WCS coordinates.
        """
        if precision is not None:
            return f"{self.ra:.{precision}f}, {self.dec:.{precision}f}"
        return f"{self.ra}, {self.dec}"
    
    def to_sexagesimal(self, precision: int = 2) -> str:
        """
        Convert WCS coordinates to sexagesimal string.
        
        Args:
            precision: Decimal precision for seconds.
            
        Returns:
            String in format "HH:MM:SS.ss, +DD:MM:SS.ss".
        """
        ra_str = degrees_to_hms(self.ra, precision)
        dec_str = degrees_to_dms(self.dec, precision)
        return f"{ra_str}, {dec_str}"
    
    def transform_to(self, frame: str) -> "WCSCoords":
        """
        Transform coordinates to a different frame.
        
        Args:
            frame: Target coordinate frame.
            
        Returns:
            New WCSCoords instance in the target frame.
        """
        transformed = self._skycoord.transform_to(frame)
        return WCSCoords(
            ra=transformed.ra.deg,
            dec=transformed.dec.deg,
            frame=frame
        )
    
    def separation(self, other: "WCSCoords") -> float:
        """
        Calculate angular separation from another coordinate.
        
        Args:
            other: Another WCSCoords instance.
            
        Returns:
            Angular separation in degrees.
        """
        return self._skycoord.separation(other.skycoord).deg
    
    @classmethod
    def from_skycoord(cls, skycoord: SkyCoord) -> "WCSCoords":
        """
        Create WCSCoords from an astropy SkyCoord.
        
        Args:
            skycoord: An astropy SkyCoord object.
            
        Returns:
            WCSCoords instance.
        """
        frame = skycoord.frame.name
        return cls(ra=skycoord.ra.deg, dec=skycoord.dec.deg, frame=frame)
