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
Region writer for DS9 format files.

Author: Yogesh Wadadekar
"""

from pathlib import Path
from typing import Optional

from .base_region import BaseRegion


class RegionWriter:
    """Writer for DS9 region files."""

    # DS9 file header
    DS9_HEADER = "# Region file format: DS9 version 4.1"

    def __init__(
        self,
        coordinate_system: str = "image",
        global_properties: Optional[dict[str, str]] = None,
    ) -> None:
        """
        Initialize the region writer.

        Args:
            coordinate_system: The coordinate system to use (image, fk5, etc.).
            global_properties: Optional global properties for regions.
        """
        self._coordinate_system = coordinate_system
        self._global_properties = global_properties or {}

    @property
    def coordinate_system(self) -> str:
        """Get the coordinate system."""
        return self._coordinate_system

    @coordinate_system.setter
    def coordinate_system(self, value: str) -> None:
        """Set the coordinate system."""
        self._coordinate_system = value

    def write_file(
        self,
        regions: list[BaseRegion],
        filepath: str | Path,
        include_header: bool = True,
    ) -> None:
        """
        Write regions to a DS9 format file.

        Args:
            regions: List of regions to write.
            filepath: Path to the output file.
            include_header: Whether to include the DS9 header.
        """
        content = self.to_string(regions, include_header)
        filepath = Path(filepath)

        with open(filepath, "w", encoding="utf-8") as f:
            f.write(content)

    def to_string(
        self,
        regions: list[BaseRegion],
        include_header: bool = True,
    ) -> str:
        """
        Convert regions to a DS9 format string.

        Args:
            regions: List of regions to convert.
            include_header: Whether to include the DS9 header.

        Returns:
            The regions as a DS9 format string.
        """
        lines: list[str] = []

        if include_header:
            lines.append(self.DS9_HEADER)

        # Add global properties if present
        if self._global_properties:
            global_line = self._format_global_properties()
            lines.append(global_line)

        # Add coordinate system
        lines.append(self._coordinate_system)

        # Add each region
        for region in regions:
            region_str = self._format_region(region)
            lines.append(region_str)

        return "\n".join(lines)

    def _format_global_properties(self) -> str:
        """Format global properties as a DS9 global line."""
        props: list[str] = []
        for key, value in self._global_properties.items():
            if " " in value or '"' in value:
                props.append(f'{key}="{value}"')
            else:
                props.append(f"{key}={value}")
        return "global " + " ".join(props)

    def _format_region(self, region: BaseRegion) -> str:
        """
        Format a single region as a DS9 string.

        Args:
            region: The region to format.

        Returns:
            The region as a DS9 format string.
        """
        # Get the basic region string from the region object
        region_str = region.to_ds9_string()

        # Add properties as a comment
        properties = self._format_region_properties(region)
        if properties:
            region_str = f"{region_str} # {properties}"

        return region_str

    def _format_region_properties(self, region: BaseRegion) -> str:
        """
        Format region properties as a DS9 comment string.

        Args:
            region: The region whose properties to format.

        Returns:
            The properties as a string.
        """
        props: list[str] = []

        # Add color if not default
        if region.color != "green":
            props.append(f"color={region.color}")

        # Add width if not default
        if region.width != 1:
            props.append(f"width={region.width}")

        # Add text if present
        if region.text:
            props.append(f'text="{region.text}"')

        # Add font if not default
        if region.font != "helvetica 10 normal roman":
            props.append(f'font="{region.font}"')

        # Add tags if present
        if region.tags:
            for tag in region.tags:
                props.append(f"tag={{{tag}}}")

        return " ".join(props)

    def set_global_property(self, key: str, value: str) -> None:
        """
        Set a global property.

        Args:
            key: The property key.
            value: The property value.
        """
        self._global_properties[key] = value

    def clear_global_properties(self) -> None:
        """Clear all global properties."""
        self._global_properties.clear()
