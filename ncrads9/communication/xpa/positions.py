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
Positions as DS9's access points write them: `<x> <y> <coordsys> [<skyframe>]`.

`pan to 13:29:55 47:11:50 wcs fk5`, `pan 200 200 image`, `xpaget ds9 pan
wcs fk4 sexagesimal` -- one grammar, read and written here, so that every
point taking a position agrees on what it means. Image coordinates count
from one with a pixel's centre on the whole number, as FITS and DS9 do.

Author: Yogesh Wadadekar
"""

from __future__ import annotations

from typing import Any

#: DS9's coordinate systems, in the order its grammar lists them.
SYSTEMS: tuple[str, ...] = ("image", "physical", "amplifier", "detector", "wcs")

#: DS9's sky frames.
SKY_FRAMES: tuple[str, ...] = ("fk4", "fk5", "icrs", "galactic", "ecliptic")

#: DS9's sky formats.
SKY_FORMATS: tuple[str, ...] = ("degrees", "sexagesimal")


def is_system(word: str) -> bool:
    """Whether a word names a coordinate system, `wcsa`..`wcsz` included."""
    lowered = word.lower()
    return lowered in SYSTEMS or (len(lowered) == 4 and lowered.startswith("wcs") and lowered[3].isalpha())


def split_spec(words: list[str]) -> tuple[list[str], str, str, str]:
    """Separate the values from a trailing `<system> [<sky>] [<format>]`.

    Returns:
        The leading words that are not part of the specification, the
        system (default image), the sky frame (default fk5) and the sky
        format (default degrees).
    """
    values: list[str] = []
    system, sky, sky_format = "image", "fk5", "degrees"
    for word in words:
        lowered = word.lower()
        if is_system(lowered):
            system = lowered
        elif lowered in SKY_FRAMES:
            sky = lowered
        elif lowered in SKY_FORMATS:
            sky_format = lowered
        else:
            values.append(word)
    return values, system, sky, sky_format


def wcs_handler(frame: Any, system: str):
    """The WCS a system names on a frame: the primary, or `wcsa`..`wcsz`."""
    if frame is None:
        return None
    if system in ("wcs", ""):
        return getattr(frame, "wcs_handler", None)
    # A real frame caches its alternates; building an astropy WCS on every
    # call is far too slow for a dialog that follows the crosshair.
    cached = getattr(frame, "wcs_for", None)
    if callable(cached):
        handler = cached(system)
        return handler if getattr(handler, "is_valid", False) else None
    from ...core.wcs_handler import WCSHandler

    header = getattr(frame, "header", None)
    if header is None:
        return None
    key = system[3:].upper()
    try:
        from astropy.io import fits

        handler = WCSHandler(header if isinstance(header, fits.Header) else fits.Header(header), key=key)
    except Exception:
        return None
    return handler if getattr(handler, "is_valid", False) else None


def _physical(frame: Any):
    from ...coordinates.physical_coords import PhysicalTransform

    header = getattr(frame, "header", None)
    return PhysicalTransform() if header is None else PhysicalTransform.from_header(header)


def _sky_coord(first: str, second: str, sky: str):
    """A SkyCoord from two words in degrees or sexagesimal."""
    from astropy import units as u
    from astropy.coordinates import SkyCoord

    sexagesimal = ":" in first or ":" in second or any(c in first.lower() for c in "hms")
    if sexagesimal:
        # Equatorial longitudes in sexagesimal are hours; DS9 writes the
        # galactic and ecliptic ones in degrees.
        lon_unit = u.hourangle if sky in ("fk4", "fk5", "icrs") else u.deg
        return SkyCoord(first, second, unit=(lon_unit, u.deg), frame=sky)
    return SkyCoord(float(first) * u.deg, float(second) * u.deg, frame=sky)


def to_image(frame: Any, first: str, second: str, system: str, sky: str = "fk5") -> tuple[float, float]:
    """One position in any of DS9's systems, as image coordinates from one.

    Raises:
        ValueError: If the position cannot be read, or the frame has no
            WCS to read it with.
    """
    system = system.lower()
    if system == "image":
        return float(first), float(second)
    if system in ("physical", "amplifier", "detector"):
        # Amplifier and detector are not modelled apart from physical,
        # which is what DS9 falls back to when a file lacks them.
        return _physical(frame).physical_to_image(float(first), float(second))
    handler = wcs_handler(frame, system)
    if handler is None:
        raise ValueError(f"the frame has no {system} coordinates")
    coordinate = _sky_coord(first, second, sky)
    x, y = handler.wcs.world_to_pixel(coordinate)
    # astropy counts pixels from zero.
    return float(x) + 1.0, float(y) + 1.0


def from_image(
    frame: Any,
    x: float,
    y: float,
    system: str,
    sky: str = "fk5",
    sky_format: str = "degrees",
    digits: int = 8,
) -> str:
    """Write an image position (from one) in any of DS9's systems.

    Args:
        digits: Significant digits of a number; the dialogs ask for DS9's
            ten for degrees, so a value read back lands on the same pixel.
    """
    system = system.lower()
    if system == "image":
        return f"{x:.{digits}g} {y:.{digits}g}"
    if system in ("physical", "amplifier", "detector"):
        px, py = _physical(frame).image_to_physical(x, y)
        return f"{px:.{digits}g} {py:.{digits}g}"
    handler = wcs_handler(frame, system)
    if handler is None:
        return f"{x:.{digits}g} {y:.{digits}g}"
    world = handler.wcs.pixel_to_world(x - 1.0, y - 1.0)
    if not hasattr(world, "transform_to"):
        return f"{x:.{digits}g} {y:.{digits}g}"
    world = world.transform_to(sky)
    spherical = world.spherical
    if sky_format == "sexagesimal":
        if sky in ("fk4", "fk5", "icrs"):
            lon = spherical.lon.to_string(unit="hourangle", sep=":", precision=4, pad=True)
        else:
            lon = spherical.lon.to_string(unit="deg", sep=":", precision=3, pad=True)
        lat = spherical.lat.to_string(unit="deg", sep=":", precision=3, alwayssign=True, pad=True)
        return f"{lon} {lat}"
    return f"{spherical.lon.deg:.{digits}g} {spherical.lat.deg:.{digits}g}"


#: The units DS9 writes a WCS distance in, as degrees per unit.
DISTANCE_FORMATS: dict[str, float] = {"degrees": 1.0, "arcmin": 1.0 / 60.0, "arcsec": 1.0 / 3600.0}


def has_system(frame: Any, system: str) -> bool:
    """Whether a frame can express positions in a system.

    The pixel systems always can; a WCS only when the frame carries it.
    """
    system = system.lower()
    if system in ("image", "physical", "amplifier", "detector"):
        return True
    return wcs_handler(frame, system) is not None


def _pixel_scales(frame: Any, system: str) -> tuple[float, float]:
    """Degrees per image pixel along x and y in a WCS.

    Raises:
        ValueError: If the frame has no such WCS.
    """
    handler = wcs_handler(frame, system)
    if handler is None:
        raise ValueError(f"the frame has no {system} coordinates")
    import numpy as np

    scales = handler.wcs.proj_plane_pixel_scales()
    values = [abs(float(getattr(scale, "value", scale))) for scale in scales]
    if len(values) < 2 or not all(np.isfinite(values)) or 0.0 in values:
        raise ValueError(f"the {system} coordinates have no pixel scale")
    return values[0], values[1]


def distance_to_image(
    frame: Any, width: float, height: float, system: str, distance_format: str = "degrees"
) -> tuple[float, float]:
    """A width and height in any of DS9's systems, as image pixels.

    DS9's `DistMenuButton`: image and physical are pixels, a WCS is an angle
    in degrees, arcminutes or arcseconds.

    Raises:
        ValueError: If the frame has no WCS to measure the angle with.
    """
    system = system.lower()
    if system == "image":
        return float(width), float(height)
    if system in ("physical", "amplifier", "detector"):
        transform = _physical(frame)
        return abs(float(width) * transform.ltm1), abs(float(height) * transform.ltm2)
    per_unit = DISTANCE_FORMATS.get(distance_format, 1.0)
    scale_x, scale_y = _pixel_scales(frame, system)
    return float(width) * per_unit / scale_x, float(height) * per_unit / scale_y


def distance_from_image(
    frame: Any, width: float, height: float, system: str, distance_format: str = "degrees"
) -> tuple[float, float]:
    """An image-pixel width and height in any of DS9's systems.

    Falls back to pixels when the frame has no such WCS, as `from_image`
    falls back for a position.
    """
    system = system.lower()
    if system == "image":
        return float(width), float(height)
    if system in ("physical", "amplifier", "detector"):
        transform = _physical(frame)
        return abs(float(width) / transform.ltm1), abs(float(height) / transform.ltm2)
    try:
        scale_x, scale_y = _pixel_scales(frame, system)
    except ValueError:
        return float(width), float(height)
    per_unit = DISTANCE_FORMATS.get(distance_format, 1.0)
    return float(width) * scale_x / per_unit, float(height) * scale_y / per_unit
