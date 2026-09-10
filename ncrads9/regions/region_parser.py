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
from typing import Any

from .base_region import BaseRegion
from .shapes.annulus import Annulus
from .shapes.box import Box
from .shapes.box_annulus import BoxAnnulus
from .shapes.bpanda import Bpanda
from .shapes.circle import Circle
from .shapes.compass import Compass
from .shapes.composite import Composite
from .shapes.ellipse import Ellipse
from .shapes.ellipse_annulus import EllipseAnnulus
from .shapes.epanda import Epanda
from .shapes.line import Line
from .shapes.panda import Panda
from .shapes.point import Point
from .shapes.polygon import Polygon
from .shapes.projection import Projection
from .shapes.ruler import Ruler
from .shapes.segment import Segment
from .shapes.text import Text
from .shapes.vector import Vector


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


def _pairs(values: list[float]) -> list[tuple[float, float]]:
    """Turn a flat coordinate list into (x, y) pairs, dropping any odd tail."""
    return [(values[i], values[i + 1]) for i in range(0, len(values) - 1, 2)]


def _flag(value: object, default: bool = True) -> bool:
    """Read a DS9 `0`/`1` property, falling back when it is absent."""
    if value is None or str(value).strip() == "":
        return default
    return str(value).strip().split()[0] not in ("0", "false", "no")


class RegionParser:
    """Parser for DS9 region files in multiple formats."""

    # Pattern for parsing DS9 region properties
    # DS9 property values may be brace-delimited ({Hello World}), quoted, or
    # bare. Braces and quotes are delimiters and are stripped from the value.
    PROPERTY_PATTERN = re.compile(r'(\w+)\s*=\s*(?:\{([^}]*)\}|"([^"]*)"|\'([^\']*)\'|(\S+))')

    # Pattern for parsing region shapes
    SHAPE_PATTERN = re.compile(r"^([+-]?)(\w+)\s*\((.*?)\)\s*(#.*)?$", re.IGNORECASE)

    # Pattern for global properties
    GLOBAL_PATTERN = re.compile(r"^global\s+(.*)$", re.IGNORECASE)

    #: DS9 properties written as a bare word rather than `key=value`.
    #: Properties whose value runs past a space: DS9 writes `point=diamond 15`
    #: and `line=0 1`, which the key=value pattern would cut at the space.
    #: DS9 writes a composite as `# composite(x,y,angle)`, the only shape
    #: whose line begins with a `#`.
    _COMPOSITE_LINE = re.compile(r"^#\s*composite\b", re.IGNORECASE)

    SPACED_PROPERTIES: tuple[str, ...] = ("point", "line", "ruler", "compass", "vector")

    BARE_PROPERTIES: tuple[str, ...] = ("background", "source")

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

        with open(filepath, encoding="utf-8") as f:
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

        for raw in lines:
            line = raw.strip()
            if not line:
                continue
            if line.startswith("#"):
                # Almost every `#` line is a comment -- but DS9 writes a
                # composite region as `# composite(x,y,angle)`, so a
                # composite would be thrown away with the comments.
                if self._COMPOSITE_LINE.match(line):
                    line = line.lstrip("# ").strip()
                else:
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
        return any(fmt in lower_line for fmt in ["ds9", "ciao", "saotng", "funtools", "# region"])

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
                self._global_properties[prop_match.group(1)] = self._property_value(prop_match)

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

    def _parse_region_line(self, line: str) -> BaseRegion | None:
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

    def _parse_comment_properties(self, comment: str | None) -> dict[str, str]:
        """Parse properties from a comment string."""
        properties: dict[str, str] = {}
        if not comment:
            return properties

        # Remove leading #
        comment = comment.lstrip("#").strip()

        tags: list[str] = []
        for match in self.PROPERTY_PATTERN.finditer(comment):
            key, value = match.group(1), self._property_value(match)
            properties[key] = value
            if key == "tag" and value:
                # A region may carry several tags; the dictionary would keep
                # only the last, so they are gathered separately.
                tags.append(value)
        if tags:
            properties["tags"] = tags  # type: ignore[assignment]

        # `point=diamond 15` and `line=0 1` put a value *after* the one the
        # key=value pattern captures, separated by a space, so the pattern
        # stops at the glyph and the size is lost. Re-read those two whole.
        for keyword in self.SPACED_PROPERTIES:
            spaced = re.search(rf"{keyword}\s*=\s*([^#\n]*)", comment)
            if spaced:
                properties[keyword] = spaced.group(1).strip()

        # DS9 writes source/background as bare words, not key=value pairs, so
        # the key=value pattern above never sees them. Record them with an
        # empty value; _parse_property_flags only tests for their presence.
        for bare in self.BARE_PROPERTIES:
            if re.search(rf"(?<![\w=]){bare}(?![\w=])", comment):
                properties.setdefault(bare, "")

        return properties

    #: DS9 property keyword -> BaseRegion keyword argument.
    _FLAG_KEYWORDS: dict[str, str] = {
        "fixed": "fixed",
        "edit": "can_edit",
        "move": "can_move",
        "rotate": "can_rotate",
        "delete": "can_delete",
        "dash": "dash",
        "fill": "fill",
    }

    def _parse_property_flags(self, properties: dict[str, str], include: bool) -> dict[str, bool]:
        """Turn DS9 property tokens into BaseRegion keyword arguments.

        Falls back to the `global` line for any flag the shape does not set
        itself, which is how DS9 applies global properties.
        """
        flags: dict[str, bool] = {"include": include}

        for keyword, argument in self._FLAG_KEYWORDS.items():
            raw = properties.get(keyword, self._global_properties.get(keyword))
            if raw is not None:
                flags[argument] = raw.strip() not in ("0", "false", "False")

        # `source` and `background` are written as bare words, so the property
        # parser records them with an empty value; either may also appear as
        # `source=1` / `background=1`.
        if "background" in properties or "background" in self._global_properties:
            flags["source"] = False
        if "source" in properties:
            flags["source"] = properties["source"].strip() not in ("0", "false", "False")

        return flags

    @staticmethod
    def _parse_tags(properties: dict[str, str]) -> list[str]:
        """Return the region's tags.

        DS9 allows `tag={...}` more than once on a region, which is how a
        region belongs to several groups. `_parse_comment_properties`
        gathers them under `tags`; the singular `tag` key is the last one
        seen and is only a fallback for a caller that built the dictionary
        itself.
        """
        gathered = properties.get("tags")
        if isinstance(gathered, list):
            return list(gathered)
        tag = properties.get("tag")
        return [tag] if tag else []

    @staticmethod
    def _property_value(match: re.Match[str]) -> str:
        """Return the matched property value from whichever delimiter was used.

        An empty brace or quote pair is a legitimate empty value, so the groups
        are checked for ``None`` rather than for truthiness.
        """
        for group in (2, 3, 4, 5):
            value = match.group(group)
            if value is not None:
                return value
        return ""

    def _create_region(
        self,
        shape_type: str,
        params: list[str],
        properties: dict[str, str],
        include: bool,
    ) -> BaseRegion | None:
        """
        Create a region object from parsed data.

        Args:
            shape_type: The type of shape (circle, box, etc.).
            params: The shape parameters.
            properties: The shape properties.
            include: Whether this is an include or exclude region.

        Returns:
            A BaseRegion subclass instance, or None when the shape is
            unknown or its parameters cannot be read. A malformed region is
            skipped rather than aborting the file, which is what DS9 does.
        """
        color = properties.get("color", self._global_properties.get("color", "green"))
        width = int(properties.get("width", self._global_properties.get("width", "1")))
        text = properties.get("text", "")
        font = properties.get("font", self._global_properties.get("font", "helvetica 10 normal roman"))
        common: dict[str, Any] = {
            "color": color,
            "width": width,
            "text": text,
            "font": font,
            "tags": self._parse_tags(properties),
            **self._parse_property_flags(properties, include),
        }

        builder = self._BUILDERS.get(shape_type.strip().lower().lstrip("# "))
        if builder is None:
            return None

        try:
            return builder(self, [float(value) for value in params], properties, common)
        except (IndexError, ValueError, TypeError):
            # A shape whose numbers cannot be read is skipped, not fatal.
            return None

    # -- one builder per shape -----------------------------------------------
    #
    # DS9 overloads three of its keywords by parameter count: `ellipse` with
    # four numbers is an ellipse and with six or more an ellipse annulus,
    # `box` likewise, and `annulus` takes either an inner and outer radius or
    # a whole list of them. The builders below make that explicit rather than
    # leaving it in a chain of conditions.

    def _build_circle(
        self,
        values: list[float],
        properties: dict[str, Any],
        common: dict[str, Any],
    ) -> BaseRegion:
        return Circle(center=(values[0], values[1]), radius=values[2], **common)

    def _build_ellipse(
        self,
        values: list[float],
        properties: dict[str, Any],
        common: dict[str, Any],
    ) -> BaseRegion:
        centre = (values[0], values[1])
        radii = values[2:]
        if len(radii) < 4:
            # `ellipse x y a b [angle]`
            angle = radii[2] if len(radii) > 2 else 0.0
            return Ellipse(center=centre, semi_major=radii[0], semi_minor=radii[1], angle=angle, **common)

        # `ellipse x y r11 r12 r21 r22 ... [angle]` -- an ellipse annulus.
        angle = radii[-1] if len(radii) % 2 else 0.0
        pairs = radii[: len(radii) - (len(radii) % 2)]
        return EllipseAnnulus(
            center=centre,
            inner_semi_major=pairs[0],
            inner_semi_minor=pairs[1],
            outer_semi_major=pairs[-2],
            outer_semi_minor=pairs[-1],
            angle=angle,
            **common,
        )

    def _build_box(
        self,
        values: list[float],
        properties: dict[str, Any],
        common: dict[str, Any],
    ) -> BaseRegion:
        centre = (values[0], values[1])
        sizes = values[2:]
        if len(sizes) < 4:
            # `box x y w h [angle]`
            angle = sizes[2] if len(sizes) > 2 else 0.0
            return Box(center=centre, width_box=sizes[0], height_box=sizes[1], angle=angle, **common)

        # `box x y w1 h1 w2 h2 ... [angle]` -- a box annulus.
        angle = sizes[-1] if len(sizes) % 2 else 0.0
        pairs = sizes[: len(sizes) - (len(sizes) % 2)]
        return BoxAnnulus(
            center=centre,
            inner_width=pairs[0],
            inner_height=pairs[1],
            outer_width=pairs[-2],
            outer_height=pairs[-1],
            angle=angle,
            **common,
        )

    def _build_point(
        self,
        values: list[float],
        properties: dict[str, Any],
        common: dict[str, Any],
    ) -> BaseRegion:
        # DS9 writes the glyph as `point=diamond 11`, and also accepts it as
        # a prefix: `diamond point x y`.
        glyph, size = self._point_glyph(properties)
        return Point(center=(values[0], values[1]), shape=glyph, size=size, **common)

    def _build_line(
        self,
        values: list[float],
        properties: dict[str, Any],
        common: dict[str, Any],
    ) -> BaseRegion:
        return Line(start=(values[0], values[1]), end=(values[2], values[3]), **common)

    def _build_polygon(
        self,
        values: list[float],
        properties: dict[str, Any],
        common: dict[str, Any],
    ) -> BaseRegion:
        return Polygon(vertices=_pairs(values), **common)

    def _build_segment(
        self,
        values: list[float],
        properties: dict[str, Any],
        common: dict[str, Any],
    ) -> BaseRegion:
        return Segment(points=_pairs(values), **common)

    def _build_annulus(
        self,
        values: list[float],
        properties: dict[str, Any],
        common: dict[str, Any],
    ) -> BaseRegion:
        centre = (values[0], values[1])
        radii = values[2:]
        # `annulus x y inner outer n=#` divides the span into n rings; the
        # region's own extent is the same either way, so the count is kept
        # only so the writer can put it back.
        return Annulus(center=centre, inner_radius=radii[0], outer_radius=radii[-1], **common)

    def _build_panda(
        self,
        values: list[float],
        properties: dict[str, Any],
        common: dict[str, Any],
    ) -> BaseRegion:
        return Panda(
            center=(values[0], values[1]),
            start_angle=values[2],
            stop_angle=values[3],
            num_angles=int(values[4]),
            inner_radius=values[5],
            outer_radius=values[6],
            num_radii=int(values[7]),
            **common,
        )

    def _build_epanda(
        self,
        values: list[float],
        properties: dict[str, Any],
        common: dict[str, Any],
    ) -> BaseRegion:
        return Epanda(**self._panda_arguments(values), **common)

    def _build_bpanda(
        self,
        values: list[float],
        properties: dict[str, Any],
        common: dict[str, Any],
    ) -> BaseRegion:
        return Bpanda(**self._panda_arguments(values), **common)

    @staticmethod
    def _panda_arguments(values: list[float]) -> dict[str, Any]:
        """The arguments epanda and bpanda share, which is all of them."""
        return {
            "center": (values[0], values[1]),
            "start_angle": values[2],
            "stop_angle": values[3],
            "num_angles": int(values[4]),
            "inner_major": values[5],
            "inner_minor": values[6],
            "outer_major": values[7],
            "outer_minor": values[8],
            "num_radii": int(values[9]),
            "angle": values[10] if len(values) > 10 else 0.0,
        }

    def _build_vector(
        self,
        values: list[float],
        properties: dict[str, Any],
        common: dict[str, Any],
    ) -> BaseRegion:
        arrow = _flag(properties.get("vector"), default=True)
        return Vector(
            start=(values[0], values[1]),
            length=values[2],
            angle=values[3],
            arrow=arrow,
            **common,
        )

    def _build_ruler(
        self,
        values: list[float],
        properties: dict[str, Any],
        common: dict[str, Any],
    ) -> BaseRegion:
        return Ruler(start=(values[0], values[1]), end=(values[2], values[3]), **common)

    def _build_compass(
        self,
        values: list[float],
        properties: dict[str, Any],
        common: dict[str, Any],
    ) -> BaseRegion:
        return Compass(center=(values[0], values[1]), length=values[2], **common)

    def _build_projection(
        self,
        values: list[float],
        properties: dict[str, Any],
        common: dict[str, Any],
    ) -> BaseRegion:
        return Projection(
            start=(values[0], values[1]),
            end=(values[2], values[3]),
            projection_width=values[4],
            **common,
        )

    def _build_text(
        self,
        values: list[float],
        properties: dict[str, Any],
        common: dict[str, Any],
    ) -> BaseRegion:
        label = common.pop("text", "")
        return Text(center=(values[0], values[1]), label=label, **common)

    def _build_composite(
        self,
        values: list[float],
        properties: dict[str, Any],
        common: dict[str, Any],
    ) -> BaseRegion:
        # A composite's children follow it in the file, each tagged with the
        # composite's own tag; DS9 writes `# composite x y angle`. Assembling
        # them is the manager's job, so this is the empty container.
        return Composite(**common)

    #: Shape keyword -> the method that builds it.
    _BUILDERS: dict[str, Any] = {
        "circle": _build_circle,
        "ellipse": _build_ellipse,
        "box": _build_box,
        "point": _build_point,
        "line": _build_line,
        "polygon": _build_polygon,
        "segment": _build_segment,
        "annulus": _build_annulus,
        "panda": _build_panda,
        "epanda": _build_epanda,
        "bpanda": _build_bpanda,
        "vector": _build_vector,
        "ruler": _build_ruler,
        "compass": _build_compass,
        "projection": _build_projection,
        "text": _build_text,
        "composite": _build_composite,
    }

    #: The glyphs DS9's `point=` property offers, and its default size.
    POINT_GLYPHS: tuple[str, ...] = (
        "circle",
        "box",
        "diamond",
        "cross",
        "x",
        "arrow",
        "boxcircle",
    )
    DEFAULT_POINT_SIZE = 11

    def _point_glyph(self, properties: dict[str, str]) -> tuple[str, int]:
        """The glyph and size a point's `point=` property asks for.

        DS9 writes `point=diamond 11`: the glyph, optionally followed by a
        size. An unknown glyph falls back to circle, as DS9's own default.
        """
        value = str(properties.get("point", "")).strip()
        if not value:
            return "circle", self.DEFAULT_POINT_SIZE

        parts = value.split()
        glyph = parts[0].lower()
        if glyph not in self.POINT_GLYPHS:
            glyph = "circle"
        size = self.DEFAULT_POINT_SIZE
        if len(parts) > 1:
            try:
                size = int(float(parts[1]))
            except ValueError:
                size = self.DEFAULT_POINT_SIZE
        return glyph, size

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
