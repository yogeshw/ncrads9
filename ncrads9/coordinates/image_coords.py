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
Image (pixel) coordinate system.

Author: Yogesh Wadadekar
"""

from typing import Tuple, Optional

from .coord_system import CoordSystem, CoordSystemType


class ImageCoords(CoordSystem):
    """Coordinate system for image pixel coordinates."""
    
    def __init__(self, x: float = 0.0, y: float = 0.0) -> None:
        """
        Initialize image coordinates.
        
        Args:
            x: The x pixel coordinate (1-based).
            y: The y pixel coordinate (1-based).
        """
        super().__init__(CoordSystemType.IMAGE)
        self._x = x
        self._y = y
    
    @property
    def x(self) -> float:
        """Return the x pixel coordinate."""
        return self._x
    
    @x.setter
    def x(self, value: float) -> None:
        """Set the x pixel coordinate."""
        self._x = value
    
    @property
    def y(self) -> float:
        """Return the y pixel coordinate."""
        return self._y
    
    @y.setter
    def y(self, value: float) -> None:
        """Set the y pixel coordinate."""
        self._y = value
    
    def get_coordinates(self) -> Tuple[float, float]:
        """
        Get the pixel coordinates as a tuple.
        
        Returns:
            A tuple of (x, y) pixel coordinates.
        """
        return (self._x, self._y)
    
    def set_coordinates(self, x: float, y: float) -> None:
        """
        Set the pixel coordinates.
        
        Args:
            x: The x pixel coordinate.
            y: The y pixel coordinate.
        """
        self._x = x
        self._y = y
    
    def to_string(self, precision: Optional[int] = None) -> str:
        """
        Convert pixel coordinates to a string representation.
        
        Args:
            precision: Optional decimal precision for formatting.
            
        Returns:
            String representation of the pixel coordinates.
        """
        if precision is not None:
            return f"{self._x:.{precision}f}, {self._y:.{precision}f}"
        return f"{self._x}, {self._y}"
    
    def to_zero_based(self) -> Tuple[float, float]:
        """
        Convert to zero-based pixel coordinates.
        
        Returns:
            A tuple of zero-based (x, y) coordinates.
        """
        return (self._x - 1.0, self._y - 1.0)
    
    @classmethod
    def from_zero_based(cls, x: float, y: float) -> "ImageCoords":
        """
        Create ImageCoords from zero-based coordinates.
        
        Args:
            x: Zero-based x coordinate.
            y: Zero-based y coordinate.
            
        Returns:
            ImageCoords instance with 1-based coordinates.
        """
        return cls(x + 1.0, y + 1.0)
