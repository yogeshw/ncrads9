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
Sexagesimal formatting and parsing functions.

Author: Yogesh Wadadekar
"""

import re
from typing import Tuple, Optional


def degrees_to_hms(degrees: float, precision: int = 2) -> str:
    """
    Convert degrees to hours:minutes:seconds format.
    
    Args:
        degrees: Angle in degrees (typically RA, 0-360).
        precision: Decimal places for seconds.
        
    Returns:
        String in format "HH:MM:SS.ss".
    """
    # Normalize to 0-360 range
    degrees = degrees % 360.0
    
    # Convert to hours (24 hours = 360 degrees)
    hours_decimal = degrees / 15.0
    
    hours = int(hours_decimal)
    minutes_decimal = (hours_decimal - hours) * 60.0
    minutes = int(minutes_decimal)
    seconds = (minutes_decimal - minutes) * 60.0
    
    # Handle rounding edge cases
    if round(seconds, precision) >= 60.0:
        seconds = 0.0
        minutes += 1
    if minutes >= 60:
        minutes = 0
        hours += 1
    if hours >= 24:
        hours = 0
    
    return f"{hours:02d}:{minutes:02d}:{seconds:0{precision + 3}.{precision}f}"


def degrees_to_dms(degrees: float, precision: int = 2) -> str:
    """
    Convert degrees to degrees:arcminutes:arcseconds format.
    
    Args:
        degrees: Angle in degrees (typically Dec, -90 to +90).
        precision: Decimal places for arcseconds.
        
    Returns:
        String in format "+DD:MM:SS.ss" or "-DD:MM:SS.ss".
    """
    sign = "+" if degrees >= 0 else "-"
    degrees = abs(degrees)
    
    deg = int(degrees)
    minutes_decimal = (degrees - deg) * 60.0
    minutes = int(minutes_decimal)
    seconds = (minutes_decimal - minutes) * 60.0
    
    # Handle rounding edge cases
    if round(seconds, precision) >= 60.0:
        seconds = 0.0
        minutes += 1
    if minutes >= 60:
        minutes = 0
        deg += 1
    
    return f"{sign}{deg:02d}:{minutes:02d}:{seconds:0{precision + 3}.{precision}f}"


def parse_sexagesimal(value: str) -> Tuple[float, str]:
    """
    Parse a sexagesimal coordinate string.
    
    Supports formats:
    - HH:MM:SS.ss or HH MM SS.ss (hours)
    - +DD:MM:SS.ss or DD MM SS.ss (degrees)
    - Decimal degrees
    
    Args:
        value: String to parse.
        
    Returns:
        Tuple of (value_in_degrees, format_type) where format_type
        is 'hms', 'dms', or 'degrees'.
        
    Raises:
        ValueError: If the string cannot be parsed.
    """
    value = value.strip()
    
    # Try decimal degrees first
    try:
        return (float(value), "degrees")
    except ValueError:
        pass
    
    # Patterns for sexagesimal
    # HMS pattern: optional sign, hours, minutes, seconds
    hms_pattern = r"^([+-]?)(\d{1,2})[:hHdD\s]+(\d{1,2})[:mM'\s]+(\d{1,2}(?:\.\d*)?)[:sS\"\s]*$"
    
    # DMS pattern with explicit sign
    dms_pattern = r"^([+-])(\d{1,2})[:°dD\s]+(\d{1,2})[:'\s]+(\d{1,2}(?:\.\d*)?)[:\"″\s]*$"
    
    # Try DMS (with sign)
    match = re.match(dms_pattern, value)
    if match:
        sign = -1 if match.group(1) == "-" else 1
        deg = float(match.group(2))
        minutes = float(match.group(3))
        seconds = float(match.group(4))
        
        result = sign * (deg + minutes / 60.0 + seconds / 3600.0)
        return (result, "dms")
    
    # Try HMS
    match = re.match(hms_pattern, value)
    if match:
        sign = -1 if match.group(1) == "-" else 1
        hours = float(match.group(2))
        minutes = float(match.group(3))
        seconds = float(match.group(4))
        
        # Convert hours to degrees (1 hour = 15 degrees)
        result = sign * (hours + minutes / 60.0 + seconds / 3600.0) * 15.0
        return (result, "hms")
    
    # Try simple three-part format without sign (assume positive degrees)
    simple_pattern = r"^(\d{1,3})[:°dD\s]+(\d{1,2})[:'\s]+(\d{1,2}(?:\.\d*)?)[:\"″\s]*$"
    match = re.match(simple_pattern, value)
    if match:
        deg = float(match.group(1))
        minutes = float(match.group(2))
        seconds = float(match.group(3))
        
        result = deg + minutes / 60.0 + seconds / 3600.0
        return (result, "dms")
    
    raise ValueError(f"Cannot parse sexagesimal value: {value}")


def hms_to_degrees(hours: int, minutes: int, seconds: float) -> float:
    """
    Convert hours, minutes, seconds to degrees.
    
    Args:
        hours: Hours (0-23).
        minutes: Minutes (0-59).
        seconds: Seconds (0-60).
        
    Returns:
        Angle in degrees.
    """
    return (hours + minutes / 60.0 + seconds / 3600.0) * 15.0


def dms_to_degrees(
    degrees: int,
    arcminutes: int,
    arcseconds: float,
    negative: bool = False
) -> float:
    """
    Convert degrees, arcminutes, arcseconds to decimal degrees.
    
    Args:
        degrees: Degrees.
        arcminutes: Arcminutes (0-59).
        arcseconds: Arcseconds (0-60).
        negative: If True, result is negative.
        
    Returns:
        Angle in decimal degrees.
    """
    result = abs(degrees) + arcminutes / 60.0 + arcseconds / 3600.0
    return -result if negative else result
