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
Physical coordinate system.

Author: Yogesh Wadadekar
"""

from typing import Tuple, Optional

from .coord_system import CoordSystem, CoordSystemType


class PhysicalCoords(CoordSystem):
    """Coordinate system for physical coordinates (detector coordinates)."""
    
    def __init__(self, x: float = 0.0, y: float = 0.0) -> None:
        """
        Initialize physical coordinates.
        
        Args:
            x: The x physical coordinate.
            y: The y physical coordinate.
        """
        super().__init__(CoordSystemType.PHYSICAL)
        self._x = x
        self._y = y
    
    @property
    def x(self) -> float:
        """Return the x physical coordinate."""
        return self._x
    
    @x.setter
    def x(self, value: float) -> None:
        """Set the x physical coordinate."""
        self._x = value
    
    @property
    def y(self) -> float:
        """Return the y physical coordinate."""
        return self._y
    
    @y.setter
    def y(self, value: float) -> None:
        """Set the y physical coordinate."""
        self._y = value
    
    def get_coordinates(self) -> Tuple[float, float]:
        """
        Get the physical coordinates as a tuple.
        
        Returns:
            A tuple of (x, y) physical coordinates.
        """
        return (self._x, self._y)
    
    def set_coordinates(self, x: float, y: float) -> None:
        """
        Set the physical coordinates.
        
        Args:
            x: The x physical coordinate.
            y: The y physical coordinate.
        """
        self._x = x
        self._y = y
    
    def to_string(self, precision: Optional[int] = None) -> str:
        """
        Convert physical coordinates to a string representation.
        
        Args:
            precision: Optional decimal precision for formatting.
            
        Returns:
            String representation of the physical coordinates.
        """
        if precision is not None:
            return f"{self._x:.{precision}f}, {self._y:.{precision}f}"
        return f"{self._x}, {self._y}"
