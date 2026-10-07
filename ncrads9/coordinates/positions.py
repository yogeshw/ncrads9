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

It began in the XPA package, but the dialogs read and write the same
positions -- the Pan Zoom Rotate dialog's Pan row is `pan to` typed by
hand -- so it lives with the other coordinate code, where both can reach
it without the dialogs importing the XPA server.

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
    from ..core.wcs_handler import WCSHandler

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


def has_system(frame: Any, system: str) -> bool:
    """Whether a frame can express positions in a system.

    Image, physical, amplifier and detector always can -- the last three
    fall back to image when a header says nothing. A WCS system needs a
    celestial WCS under that key, which is DS9's `has wcs <system>`.
    """
    system = system.lower()
    if system in ("image", "physical", "amplifier", "detector"):
        return True
    handler = wcs_handler(frame, system)
    return handler is not None and bool(getattr(handler, "is_valid", True))


def _physical(frame: Any):
    from .physical_coords import PhysicalTransform

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


def from_image(frame: Any, x: float, y: float, system: str, sky: str = "fk5", sky_format: str = "degrees") -> str:
    """Write an image position (from one) in any of DS9's systems."""
    system = system.lower()
    if system == "image":
        return f"{x:.8g} {y:.8g}"
    if system in ("physical", "amplifier", "detector"):
        px, py = _physical(frame).image_to_physical(x, y)
        return f"{px:.8g} {py:.8g}"
    handler = wcs_handler(frame, system)
    if handler is None:
        return f"{x:.8g} {y:.8g}"
    world = handler.wcs.pixel_to_world(x - 1.0, y - 1.0)
    if not hasattr(world, "transform_to"):
        return f"{x:.8g} {y:.8g}"
    world = world.transform_to(sky)
    spherical = world.spherical
    if sky_format == "sexagesimal":
        if sky in ("fk4", "fk5", "icrs"):
            lon = spherical.lon.to_string(unit="hourangle", sep=":", precision=4, pad=True)
        else:
            lon = spherical.lon.to_string(unit="deg", sep=":", precision=3, pad=True)
        lat = spherical.lat.to_string(unit="deg", sep=":", precision=3, alwayssign=True, pad=True)
        return f"{lon} {lat}"
    return f"{spherical.lon.deg:.8g} {spherical.lat.deg:.8g}"
