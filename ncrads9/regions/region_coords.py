# NCRADS9 - NCRA DS9-like FITS Viewer
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
Regions between the coordinate system a file is written in and the image.

Regions on a frame are held in FITS image coordinates, which is what the
overlay draws and the analysis measures. A region file names its own
system -- `fk5`, `physical`, `image` -- and the numbers in it mean what
that system means; DS9 converts them on the way in and writes them back in
whatever system is asked for on the way out.

Neither direction used to happen: a file in `fk5` was loaded with its
degrees taken as pixels, and `xpaget ds9 regions -system wcs` answered with
pixel numbers under a `wcs` header. This is the conversion, both ways.

Angles are converted too: DS9 measures a region's angle from the image x
axis in image coordinates, and in sky ones from the local west direction
towards north (`ds9_coords.image_angle_to`). For an image with north up
and east left the two agree; for a turned or mirrored one they do not.

A sky frame refers to the WCS description named before it -- `wcsa;fk5;`
is the `a` description in FK5 -- as in DS9's region grammar.

Author: Yogesh Wadadekar
"""

from __future__ import annotations

import re
from collections.abc import Iterator

from ..coordinates import ds9_coords
from .base_region import BaseRegion
from .region_formats import RegionFormat
from .region_writer import RegionWriter
from .shapes.composite import Composite

#: The attribute a parsed region carries saying which system its numbers
#: are in. Set by the parser; absent on regions drawn on screen, which are
#: in image coordinates already.
SYSTEM_ATTRIBUTE = "coord_system"

#: Which of each shape's attributes are lengths, scaled with the system.
LENGTHS: dict[str, tuple[str, ...]] = {
    "Circle": ("radius",),
    "Ellipse": ("semi_major", "semi_minor"),
    "Box": ("width_box", "height_box"),
    "Annulus": ("inner_radius", "outer_radius"),
    "EllipseAnnulus": ("inner_semi_major", "inner_semi_minor", "outer_semi_major", "outer_semi_minor"),
    "BoxAnnulus": ("inner_width", "inner_height", "outer_width", "outer_height"),
    "Panda": ("inner_radius", "outer_radius"),
    "Epanda": ("inner_major", "inner_minor", "outer_major", "outer_minor"),
    "Bpanda": ("inner_major", "inner_minor", "outer_major", "outer_minor"),
    "Vector": ("length",),
    "Compass": ("length",),
    "Projection": ("projection_width",),
}

#: The same, by the position of each length in a written shape's numbers.
#: `ellipse` and `box` carry two lengths, or four as an annulus, which is
#: told apart by how many numbers there are.
_TEXT_LENGTHS: dict[str, tuple[int, ...]] = {
    "circle": (2,),
    "annulus": (2, 3),
    "panda": (5, 6),
    "epanda": (5, 6, 7, 8),
    "bpanda": (5, 6, 7, 8),
    "vector": (2,),
    "compass": (2,),
    "projection": (4,),
}

#: Shapes whose numbers are positions two at a time, start to finish.
_ALL_POSITIONS = frozenset({"polygon", "segment"})
#: Shapes with two positions at the head of their numbers.
_TWO_POSITIONS = frozenset({"line", "ruler", "projection"})

#: A text region's angle, written as a property.
_TEXT_ANGLE = re.compile(r"textangle=([-+0-9.eE]+)")


def _angle_indices(name: str, count: int) -> tuple[int, ...]:
    """Where a written shape's angles are among its numbers."""
    if name in ("ellipse", "box"):
        return (count - 1,) if count >= 5 else ()
    if name == "vector":
        return (3,) if count >= 4 else ()
    if name == "panda":
        return (2, 3)
    if name in ("epanda", "bpanda"):
        return (2, 3, count - 1) if count >= 11 else (2, 3)
    return ()


_SHAPE_LINE = re.compile(r"^(\s*-?)(#\s*)?([A-Za-z]+)\(([^)]*)\)(.*)$")


def _walk(regions: list[BaseRegion]) -> Iterator[BaseRegion]:
    """Every region, and every region inside a composite."""
    for region in regions:
        yield region
        if isinstance(region, Composite):
            yield from _walk(region.regions)


def native_sky(frame, system: str = "wcs") -> str:
    """The sky frame a frame's own WCS is written in, as DS9 names it."""
    handler = ds9_coords.wcs_of(frame, system)
    if handler is None:
        return "fk5"
    return ds9_coords._native_name(handler)


# -- reading: whatever a file said, into image coordinates ------------------------


def place(regions: list[BaseRegion], frame) -> list[BaseRegion]:
    """Turn parsed regions' numbers into image coordinates on a frame.

    Each region says which system it was written in (`coord_system`, set by
    the parser); one in `image` -- or that says nothing -- is left alone.

    Raises:
        ds9_coords.CoordinateError: A sky region on a frame with no WCS.
    """
    for region in _walk(regions):
        system = str(getattr(region, SYSTEM_ATTRIBUTE, "image") or "image").lower()
        if system in ("image", "amplifier", "detector") or isinstance(region, Composite):
            setattr(region, SYSTEM_ATTRIBUTE, "image")
            continue
        # The WCS description the file named last: `wcs`, or `wcsa`..`wcsz`.
        described = str(getattr(region, "wcs_system", "wcs") or "wcs").lower()
        sky = system
        if system.startswith("wcs"):
            system = system if system != "wcs" else described
            sky = native_sky(frame, system)
        elif system in ds9_coords.SKY_FRAMES:
            system = described

        def to_image(point, system=system, sky=sky):
            return ds9_coords.to_image(frame, point[0], point[1], system, sky)

        for name in ("center", "start", "end"):
            if hasattr(region, name) and name in _settable(region):
                setattr(region, name, to_image(getattr(region, name)))
        for name in ("vertices", "points"):
            if hasattr(region, name):
                setattr(region, name, [to_image(point) for point in getattr(region, name)])
        if isinstance(getattr(region, "radii", None), list):
            # An annulus of any number of rings: every radius, not only the
            # two ends `inner_radius` and `outer_radius` name.
            region.radii = [
                ds9_coords.length_to_image(frame, radius, system, "degrees") for radius in region.radii
            ]
        else:
            for name in LENGTHS.get(type(region).__name__, ()):
                value = ds9_coords.length_to_image(frame, getattr(region, name), system, "degrees")
                setattr(region, name, value)
        _angles_to_image(region, frame, system, sky)
        setattr(region, SYSTEM_ATTRIBUTE, "image")

    for region in regions:
        if isinstance(region, Composite):
            region.recompute_center()
    return regions


#: The angle properties a shape may have, in the order DS9 writes them.
_ANGLES = ("angle", "start_angle", "stop_angle")


def _angles_to_image(region: BaseRegion, frame, system: str, sky: str) -> None:
    """A placed region's angles, from the file's system to the image's."""
    if not ds9_coords.is_sky_system(system):
        return
    center = getattr(region, "center", None)
    if center is None:
        return
    x, y = center
    present = [name for name in _ANGLES if _has_angle(region, name)]
    for name in present:
        setattr(region, name, ds9_coords.angle_to_image(frame, getattr(region, name), x, y, system, sky))
    if "start_angle" in present and not ds9_coords.sky_is_usual(frame, x, y, system, sky):
        # Mirrored, an arc running anticlockwise from start to stop on the
        # sky runs the other way on the image: the ends change places.
        region.start_angle, region.stop_angle = region.stop_angle, region.start_angle


def _has_angle(region: BaseRegion, name: str) -> bool:
    for klass in type(region).__mro__:
        attribute = vars(klass).get(name)
        if isinstance(attribute, property):
            return attribute.fset is not None
    return False


def _settable(region: BaseRegion) -> set[str]:
    """Which of a region's position attributes can be assigned."""
    found = set()
    for name in ("center", "start", "end"):
        for klass in type(region).__mro__:
            attribute = vars(klass).get(name)
            if isinstance(attribute, property):
                if attribute.fset is not None:
                    found.add(name)
                break
    return found


# -- writing: image coordinates, out in whatever system is asked for ----------------


def write(
    regions: list[BaseRegion],
    frame,
    region_format: RegionFormat | str = RegionFormat.DS9,
    system: str = "image",
    sky: str = "fk5",
    sky_format: str = "degrees",
    strip: bool = False,
    precision: dict[str, int] | None = None,
) -> str:
    """Regions as a region file, in the system, sky frame and format asked.

    A WCS system on a frame with no WCS falls back to physical, as DS9's
    `AdjustCoordSystem` does.
    """
    region_format = (
        region_format if isinstance(region_format, RegionFormat) else RegionFormat(str(region_format).lower())
    )
    system = str(system).lower()
    sky = str(sky).lower()
    if system in ds9_coords.SKY_FRAMES:
        system, sky = "wcs", system
    if ds9_coords.is_sky_system(system):
        # `wcsa`..`wcsz` stay themselves; any other sky system is `wcs`.
        system = ds9_coords._wcs_name(system)
        if ds9_coords.wcs_of(frame, system) is None:
            system = "physical"
    digits = {**ds9_coords.DEFAULT_PRECISION, **(precision or {})}
    if system == "wcs":
        heading = sky
    elif ds9_coords.is_sky_system(system):
        # DS9's grammar: the description, then the sky frame of its numbers.
        heading = f"{system};{sky}"
    else:
        heading = system

    text = RegionWriter(coordinate_system=heading, region_format=region_format).to_string(regions)
    convert = _Converter(frame, system, sky, sky_format, digits)
    lines = []
    for line in text.split("\n"):
        if region_format is RegionFormat.XY:
            lines.append(convert.xy(line))
        else:
            lines.append(convert.line(line))
    if strip:
        lines = [line for line in lines if line and not line.lstrip().startswith("#")]
        return ";".join(lines)
    return "\n".join(lines)


class _Converter:
    """Rewrites the numbers of written region lines into another system."""

    def __init__(self, frame, system: str, sky: str, sky_format: str, digits: dict[str, int]) -> None:
        self.frame = frame
        self.system = system
        self.sky = sky
        self.sky_format = sky_format
        self.digits = digits

    def position(self, x: float, y: float) -> tuple[str, str]:
        a, b = ds9_coords.from_image(self.frame, x, y, self.system, self.sky)
        if not self.sky_system:
            return (self._linear(a), self._linear(b))
        text = ds9_coords.format_position(a, b, "wcs", self.sky, self.sky_format, self.digits)
        first, second = text.split()
        return (first, second)

    @property
    def sky_system(self) -> bool:
        return ds9_coords.is_sky_system(self.system)

    def angle(self, value: float, x: float, y: float) -> str:
        converted = ds9_coords.image_angle_to(self.frame, value, x, y, self.system, self.sky)
        return f"{converted:.{self.digits.get('angle', 8)}g}"

    def length(self, value: float) -> str:
        if not self.sky_system:
            return self._linear(ds9_coords.image_length_to(self.frame, value, self.system))
        arcsec = ds9_coords.image_length_to(self.frame, value, self.system, "arcsec")
        digits = self.digits["arcsec"]
        return f"{arcsec:.{digits}f}" + '"'

    def _linear(self, value: float) -> str:
        return f"{float(value):.{self.digits['linear']}g}"

    def xy(self, line: str) -> str:
        words = line.split()
        if len(words) < 2:
            return line
        try:
            x, y = float(words[0]), float(words[1])
        except ValueError:
            return line
        return " ".join(self.position(x, y))

    def line(self, line: str) -> str:
        match = _SHAPE_LINE.match(line)
        if match is None:
            return line
        prefix, comment, shape, body, tail = match.groups()
        values = [value.strip() for value in body.split(",")]
        try:
            numbers = [float(value) for value in values]
        except ValueError:
            return line
        name = shape.lower()
        written = list(values)

        if name in _ALL_POSITIONS:
            pairs = range(0, len(numbers) - 1, 2)
        elif name in _TWO_POSITIONS:
            pairs = range(0, 4, 2)
        else:
            pairs = range(0, 2, 2)
        for index in pairs:
            if index + 1 < len(numbers):
                written[index], written[index + 1] = self.position(numbers[index], numbers[index + 1])

        if name in ("ellipse", "box"):
            lengths = tuple(range(2, len(numbers) - 1)) if len(numbers) > 5 else (2, 3)
        elif name == "annulus":
            # Every radius after the centre, however many rings there are.
            lengths = tuple(range(2, len(numbers)))
        else:
            lengths = _TEXT_LENGTHS.get(name, ())
        for index in lengths:
            if index < len(numbers):
                written[index] = self.length(numbers[index])

        if self.sky_system and len(numbers) >= 2:
            x, y = numbers[0], numbers[1]
            for index in _angle_indices(name, len(numbers)):
                written[index] = self.angle(numbers[index], x, y)
            if name in ("panda", "epanda", "bpanda") and not ds9_coords.sky_is_usual(
                self.frame, x, y, self.system, self.sky
            ):
                written[2], written[3] = written[3], written[2]
            tail = _TEXT_ANGLE.sub(lambda m: f"textangle={self.angle(float(m.group(1)), x, y)}", tail)
        return f"{prefix}{comment or ''}{shape}({','.join(written)}){tail}"
