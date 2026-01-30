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
Base coordinate system classes and types.

Author: Yogesh Wadadekar
"""

from abc import ABC, abstractmethod
from enum import Enum, auto
from typing import Tuple, Optional


class CoordSystemType(Enum):
    """Enumeration of coordinate system types."""
    
    IMAGE = auto()
    PHYSICAL = auto()
    WCS = auto()


class CoordSystem(ABC):
    """Abstract base class for coordinate systems."""
    
    def __init__(self, coord_type: CoordSystemType) -> None:
        """
        Initialize the coordinate system.
        
        Args:
            coord_type: The type of coordinate system.
        """
        self._coord_type = coord_type
    
    @property
    def coord_type(self) -> CoordSystemType:
        """Return the coordinate system type."""
        return self._coord_type
    
    @abstractmethod
    def get_coordinates(self) -> Tuple[float, float]:
        """
        Get the coordinates as a tuple.
        
        Returns:
            A tuple of (x, y) or (ra, dec) coordinates.
        """
        pass
    
    @abstractmethod
    def set_coordinates(self, x: float, y: float) -> None:
        """
        Set the coordinates.
        
        Args:
            x: The x or RA coordinate.
            y: The y or Dec coordinate.
        """
        pass
    
    @abstractmethod
    def to_string(self, precision: Optional[int] = None) -> str:
        """
        Convert coordinates to a string representation.
        
        Args:
            precision: Optional decimal precision for formatting.
            
        Returns:
            String representation of the coordinates.
        """
        pass
    
    def __repr__(self) -> str:
        """Return string representation of the coordinate system."""
        return f"{self.__class__.__name__}({self.to_string()})"
