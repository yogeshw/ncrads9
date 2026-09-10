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
Region writer: DS9's own format, and the four others it exports.

`region_formats.py` holds what each format can and cannot express; this
writes it. Only DS9's own format carries properties, so everything else is
the shape line alone, with an exclude written as a leading `-` and any shape
the format has no equivalent for dropped -- silently, as DS9 drops it, with
`region_formats.dropped_shapes` there for a caller that wants to say so.

Author: Yogesh Wadadekar
"""

from pathlib import Path

from .base_region import BaseRegion
from .region_formats import (
    FORMAT_HEADERS,
    FORMATS_WITH_PROPERTIES,
    RegionFormat,
    is_writable,
    shape_keyword,
    translate,
)


class RegionWriter:
    """Writer for DS9 region files."""

    # DS9 file header
    DS9_HEADER = "# Region file format: DS9 version 4.1"

    def __init__(
        self,
        coordinate_system: str = "image",
        global_properties: dict[str, str] | None = None,
        region_format: RegionFormat | str = RegionFormat.DS9,
    ) -> None:
        """
        Initialize the region writer.

        Args:
            coordinate_system: The coordinate system to use (image, fk5, etc.).
            global_properties: Optional global properties for regions.
            region_format: Which format to write. A string is accepted, so
                the Region menu and the XPA `regions` access point can pass
                DS9's own spelling straight through.

        Raises:
            ValueError: If `region_format` names no known format.
        """
        self._coordinate_system = coordinate_system
        self._global_properties = global_properties or {}
        self._format = (
            region_format
            if isinstance(region_format, RegionFormat)
            else RegionFormat(str(region_format).strip().lower())
        )

    @property
    def region_format(self) -> RegionFormat:
        """The format being written."""
        return self._format

    @region_format.setter
    def region_format(self, value: RegionFormat | str) -> None:
        """Set the format.

        Raises:
            ValueError: If the value names no known format.
        """
        self._format = value if isinstance(value, RegionFormat) else RegionFormat(str(value).strip().lower())

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
        if self._format is RegionFormat.XY:
            return self._to_xy(regions)

        lines: list[str] = []

        if include_header:
            header = FORMAT_HEADERS.get(self._format, self.DS9_HEADER)
            if header:
                lines.append(header)

        # Global properties are a DS9 idea; no other format has them.
        if self._global_properties and self._format in FORMATS_WITH_PROPERTIES:
            lines.append(self._format_global_properties())

        # Add coordinate system
        lines.append(self._coordinate_system)

        for region in regions:
            if not is_writable(region, self._format):
                # DS9 drops what a format cannot express, without comment.
                continue
            lines.append(self._format_region(region))

        return "\n".join(lines)

    def _to_xy(self, regions: list[BaseRegion]) -> str:
        """One `x y` per line, which is all the X Y format holds."""
        return "\n".join(f"{x:g} {y:g}" for x, y in (region.center for region in regions))

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
        # The shape line itself, e.g. `circle(10,20,5)`. Some shapes (point,
        # text, ruler) already carry a `# ...` tail of their own, so the
        # property tokens have to merge into that comment rather than start a
        # second one -- two `#` on a line would make the second unparseable.
        shape = region.to_ds9_string()
        if self._format not in FORMATS_WITH_PROPERTIES:
            # Everything but DS9's own format is the shape alone: no
            # properties, no trailing comment, and a shape renamed if the
            # format calls it something else.
            shape = shape.split("#", 1)[0].strip()
            keyword = shape_keyword(region)
            renamed = translate(keyword, self._format)
            if renamed != keyword:
                shape = renamed + shape[len(keyword) :]
            return region.prefix + shape

        region_str = region.prefix + shape

        properties = self._format_region_properties(region)
        if not properties:
            return region_str
        if "#" in region_str:
            return f"{region_str} {properties}"
        return f"{region_str} # {properties}"

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

        # Add text if present. DS9's own advice: "Strings may be quoted with
        # " or ' or {}. For best results, use {}." -- braces survive a text
        # containing either quote character.
        if region.text:
            props.append(f"text={{{region.text}}}")

        # Add font if not default
        if region.font != "helvetica 10 normal roman":
            props.append(f'font="{region.font}"')

        # Add tags if present
        if region.tags:
            props.extend(f"tag={{{tag}}}" for tag in region.tags)

        # DS9 property flags: fixed, edit, move, rotate, delete, dash, fill,
        # and source/background. Only non-default values are written.
        props.extend(region.ds9_properties())

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
