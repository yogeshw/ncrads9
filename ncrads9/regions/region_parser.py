# NCRADS9 - NCRA DS9 Viewer
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
Region parser for DS9 region files.

Supports multiple region file formats:
- ds9: Standard DS9 format
- ciao: CIAO format
- saotng: SAOtng format
- funtools: Funtools format
- xy: Simple x,y coordinate format

Author: Yogesh Wadadekar
"""

import re
from enum import Enum
from pathlib import Path
from typing import Optional

from .base_region import BaseRegion


class RegionFormat(Enum):
    """Supported region file formats."""

    DS9 = "ds9"
    CIAO = "ciao"
    SAOTNG = "saotng"
    FUNTOOLS = "funtools"
    XY = "xy"


class CoordinateSystem(Enum):
    """Supported coordinate systems."""

    IMAGE = "image"
    PHYSICAL = "physical"
    FK4 = "fk4"
    FK5 = "fk5"
    GALACTIC = "galactic"
    ECLIPTIC = "ecliptic"
    ICRS = "icrs"
    WCS = "wcs"


class RegionParser:
    """Parser for DS9 region files in multiple formats."""

    # Pattern for parsing DS9 region properties
    PROPERTY_PATTERN = re.compile(
        r'(\w+)\s*=\s*(?:"([^"]*)"|\'([^\']*)\'|(\S+))'
    )

    # Pattern for parsing region shapes
    SHAPE_PATTERN = re.compile(
        r"^([+-]?)(\w+)\s*\((.*?)\)\s*(#.*)?$", re.IGNORECASE
    )

    # Pattern for global properties
    GLOBAL_PATTERN = re.compile(r"^global\s+(.*)$", re.IGNORECASE)

    def __init__(self) -> None:
        """Initialize the region parser."""
        self._format: RegionFormat = RegionFormat.DS9
        self._coordinate_system: CoordinateSystem = CoordinateSystem.IMAGE
        self._global_properties: dict[str, str] = {}

    @property
    def format(self) -> RegionFormat:
        """Get the current region format."""
        return self._format

    @property
    def coordinate_system(self) -> CoordinateSystem:
        """Get the current coordinate system."""
        return self._coordinate_system

    def parse_file(self, filepath: str | Path) -> list[BaseRegion]:
        """
        Parse a region file and return a list of regions.

        Args:
            filepath: Path to the region file.

        Returns:
            List of parsed BaseRegion objects.

        Raises:
            FileNotFoundError: If the file does not exist.
            ValueError: If the file format is invalid.
        """
        filepath = Path(filepath)
        if not filepath.exists():
            raise FileNotFoundError(f"Region file not found: {filepath}")

        with open(filepath, "r", encoding="utf-8") as f:
            content = f.read()

        return self.parse_string(content)

    def parse_string(self, content: str) -> list[BaseRegion]:
        """
        Parse a region string and return a list of regions.

        Args:
            content: The region file content as a string.

        Returns:
            List of parsed BaseRegion objects.
        """
        regions: list[BaseRegion] = []
        lines = content.strip().split("\n")

        for line in lines:
            line = line.strip()
            if not line or line.startswith("#"):
                continue

            # Detect format from header
            if self._is_format_header(line):
                self._parse_format_header(line)
                continue

            # Parse global properties
            if self._is_global_line(line):
                self._parse_global_properties(line)
                continue

            # Parse coordinate system
            if self._is_coordinate_system(line):
                self._parse_coordinate_system(line)
                continue

            # Parse region shape
            region = self._parse_region_line(line)
            if region is not None:
                regions.append(region)

        return regions

    def detect_format(self, content: str) -> RegionFormat:
        """
        Detect the format of a region file from its content.

        Args:
            content: The region file content.

        Returns:
            The detected RegionFormat.
        """
        first_line = content.strip().split("\n")[0].lower()

        if "ds9" in first_line:
            return RegionFormat.DS9
        elif "ciao" in first_line:
            return RegionFormat.CIAO
        elif "saotng" in first_line:
            return RegionFormat.SAOTNG
        elif "funtools" in first_line:
            return RegionFormat.FUNTOOLS
        else:
            # Check for XY format (simple coordinate pairs)
            if self._is_xy_format(content):
                return RegionFormat.XY
            return RegionFormat.DS9

    def _is_format_header(self, line: str) -> bool:
        """Check if a line is a format header."""
        lower_line = line.lower()
        return any(
            fmt in lower_line
            for fmt in ["ds9", "ciao", "saotng", "funtools", "# region"]
        )

    def _parse_format_header(self, line: str) -> None:
        """Parse the format header line."""
        lower_line = line.lower()
        if "ciao" in lower_line:
            self._format = RegionFormat.CIAO
        elif "saotng" in lower_line:
            self._format = RegionFormat.SAOTNG
        elif "funtools" in lower_line:
            self._format = RegionFormat.FUNTOOLS
        else:
            self._format = RegionFormat.DS9

    def _is_global_line(self, line: str) -> bool:
        """Check if a line contains global properties."""
        return line.lower().startswith("global")

    def _parse_global_properties(self, line: str) -> None:
        """Parse global properties from a line."""
        match = self.GLOBAL_PATTERN.match(line)
        if match:
            props_str = match.group(1)
            for prop_match in self.PROPERTY_PATTERN.finditer(props_str):
                key = prop_match.group(1)
                value = (
                    prop_match.group(2)
                    or prop_match.group(3)
                    or prop_match.group(4)
                )
                self._global_properties[key] = value

    def _is_coordinate_system(self, line: str) -> bool:
        """Check if a line specifies a coordinate system."""
        coord_systems = [cs.value for cs in CoordinateSystem]
        return line.lower().strip() in coord_systems

    def _parse_coordinate_system(self, line: str) -> None:
        """Parse the coordinate system from a line."""
        try:
            self._coordinate_system = CoordinateSystem(line.lower().strip())
        except ValueError:
            pass

    def _parse_region_line(self, line: str) -> Optional[BaseRegion]:
        """
        Parse a single region line.

        Args:
            line: The line containing region definition.

        Returns:
            A BaseRegion object or None if parsing fails.
        """
        match = self.SHAPE_PATTERN.match(line)
        if not match:
            return None

        include = match.group(1) != "-"
        shape_type = match.group(2).lower()
        params_str = match.group(3)
        comment = match.group(4)

        # Parse parameters
        params = self._parse_parameters(params_str)

        # Parse properties from comment
        properties = self._parse_comment_properties(comment)

        # Create region based on shape type
        return self._create_region(shape_type, params, properties, include)

    def _parse_parameters(self, params_str: str) -> list[str]:
        """Parse comma-separated parameters."""
        params: list[str] = []
        current = ""
        paren_depth = 0

        for char in params_str:
            if char == "(":
                paren_depth += 1
                current += char
            elif char == ")":
                paren_depth -= 1
                current += char
            elif char == "," and paren_depth == 0:
                params.append(current.strip())
                current = ""
            else:
                current += char

        if current.strip():
            params.append(current.strip())

        return params

    def _parse_comment_properties(
        self, comment: Optional[str]
    ) -> dict[str, str]:
        """Parse properties from a comment string."""
        properties: dict[str, str] = {}
        if not comment:
            return properties

        # Remove leading #
        comment = comment.lstrip("#").strip()

        for match in self.PROPERTY_PATTERN.finditer(comment):
            key = match.group(1)
            value = match.group(2) or match.group(3) or match.group(4)
            properties[key] = value

        return properties

    def _create_region(
        self,
        shape_type: str,
        params: list[str],
        properties: dict[str, str],
        include: bool,
    ) -> Optional[BaseRegion]:
        """
        Create a region object from parsed data.

        Args:
            shape_type: The type of shape (circle, box, etc.).
            params: The shape parameters.
            properties: The shape properties.
            include: Whether this is an include or exclude region.

        Returns:
            A BaseRegion subclass instance or None.
        """
        # This is a placeholder - actual implementation would create
        # specific shape instances based on shape_type
        # For now, return None as we don't have concrete shape classes yet
        return None

    def _is_xy_format(self, content: str) -> bool:
        """Check if content is in simple XY format."""
        lines = content.strip().split("\n")
        for line in lines:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            # XY format should have just two numbers per line
            parts = line.split()
            if len(parts) == 2:
                try:
                    float(parts[0])
                    float(parts[1])
                    return True
                except ValueError:
                    return False
        return False

    def get_global_properties(self) -> dict[str, str]:
        """Get the parsed global properties."""
        return self._global_properties.copy()
