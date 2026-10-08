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
DS9's coordinate systems, between one frame's image pixels and the rest.

Every XPA point that takes or gives a position -- `crosshair`, `crop`,
`data`, `regions`, `iexam` -- names it the DS9 way: `<x> <y> <coordsys>
[<skyframe>] [<skyformat>]`. This is the one place that turns such a
position into *image* coordinates and back, so the points cannot disagree
about where a pixel is.

Image coordinates here are FITS's: they count from one, at the centre of
the first pixel -- which is what the crosshair, the crop and the regions
store. Astropy's WCS counts from zero, and forgetting the difference puts
every sky position one pixel off; that was the bug this module replaced.

Author: Yogesh Wadadekar
"""

from __future__ import annotations

import math
import re
from typing import Any

from .physical_coords import PhysicalTransform
from .sexagesimal import degrees_to_dms, degrees_to_hms

#: The sky frames DS9 names.
SKY_FRAMES: tuple[str, ...] = ("fk5", "fk4", "icrs", "galactic", "ecliptic")

#: The pixel systems, which need no WCS. DS9's amplifier and detector
#: systems come from the ATM/DTM keywords; frames that carry none -- every
#: frame we load today -- have them equal to image, which is what is used.
PIXEL_SYSTEMS: tuple[str, ...] = ("image", "physical", "amplifier", "detector")

#: The sky frames whose longitude DS9 writes in hours.
HOUR_FRAMES = frozenset({"fk5", "fk4", "icrs"})

#: DS9's default precisions (`ds9/library/ds9.tcl`, `pds9(prec,*)`).
DEFAULT_PRECISION: dict[str, int] = {
    "linear": 8,
    "degrees": 7,
    "hms": 4,
    "dms": 3,
    "len_linear": 8,
    "len_degrees": 7,
    "arcmin": 5,
    "arcsec": 3,
    "angle": 8,
}

#: Length units and what one of each is worth in degrees.
ANGLE_UNITS: dict[str, float] = {"degrees": 1.0, "arcmin": 1.0 / 60.0, "arcsec": 1.0 / 3600.0}


class CoordinateError(ValueError):
    """A position that cannot be converted, for the reason given."""


def is_system(word: str) -> bool:
    """Whether a word names one of DS9's coordinate systems."""
    text = str(word).lower()
    return text in PIXEL_SYSTEMS or text == "wcs" or bool(re.fullmatch(r"wcs[a-z]", text))


def is_sky_system(system: str) -> bool:
    """Whether a system is a WCS one, `wcs` or `wcsa`..`wcsz` or a bare sky frame."""
    text = str(system).lower()
    return text.startswith("wcs") or text in SKY_FRAMES


# -- what a frame carries ----------------------------------------------------------


def header_of(frame) -> Any:
    """A frame's header, or None."""
    if frame is None:
        return None
    header = getattr(frame, "header", None)
    if header is not None:
        return header
    return getattr(getattr(frame, "fits_handler", None), "header", None)


def physical_of(frame) -> PhysicalTransform:
    """A frame's image-to-physical mapping; the identity without LTV/LTM."""
    header = header_of(frame)
    return PhysicalTransform() if header is None else PhysicalTransform.from_header(header)


def wcs_of(frame, system: str = "wcs"):
    """A frame's usable WCS handler for a system, or None.

    `wcs` is the primary description; `wcsa`..`wcsz` the alternates, which
    the frame builds and caches (`Frame.wcs_for`).
    """
    if frame is None:
        return None
    system = str(system or "wcs").lower()
    if system not in ("wcs", "") and len(system) == 4 and system.startswith("wcs") and hasattr(frame, "wcs_for"):
        handler = frame.wcs_for(system)
    else:
        handler = getattr(frame, "wcs_handler", None)
    if handler is None or not getattr(handler, "is_valid", False):
        return None
    return handler


def _wcs_name(system: str) -> str:
    """The WCS a system names: itself for `wcsa`..`wcsz`, else the primary."""
    system = str(system).lower()
    return system if len(system) == 4 and system.startswith("wcs") and system[3].isalpha() else "wcs"


def _astropy_frame(name: str):
    """One of DS9's sky frame names, as an astropy frame."""
    from astropy.coordinates import FK4, FK5, ICRS, BarycentricMeanEcliptic, Galactic

    return {
        "fk5": FK5(equinox="J2000"),
        "fk4": FK4(equinox="B1950"),
        "icrs": ICRS(),
        "galactic": Galactic(),
        "ecliptic": BarycentricMeanEcliptic(equinox="J2000"),
    }[name]


def _native_name(handler) -> str:
    """Which of DS9's sky frames a WCS is written in, as near as it names one."""
    try:
        from astropy.wcs.utils import wcs_to_celestial_frame

        native = wcs_to_celestial_frame(handler.wcs)
    except Exception:
        return "fk5"
    name = native.name.lower()
    if name == "fk4":
        return "fk4"
    if name == "galactic":
        return "galactic"
    if "ecliptic" in name:
        return "ecliptic"
    # ICRS and FK5 J2000 differ by tens of milliarcseconds, which DS9's own
    # display cannot show; treating them as one keeps a round trip exact.
    return "fk5"


def _same(native: str, sky: str) -> bool:
    """Whether two sky frames are the same for our purposes."""
    equatorial = {"fk5", "icrs"}
    return native == sky or (native in equatorial and sky in equatorial)


def _convert_sky(longitude: float, latitude: float, source: str, target: str) -> tuple[float, float]:
    """One position from one sky frame to another, in degrees."""
    if _same(source, target):
        return (float(longitude), float(latitude))
    import astropy.units as u
    from astropy.coordinates import SkyCoord

    coordinate = SkyCoord(longitude * u.deg, latitude * u.deg, frame=_astropy_frame(source))
    moved = coordinate.transform_to(_astropy_frame(target)).spherical
    return (float(moved.lon.deg) % 360.0, float(moved.lat.deg))


# -- positions ---------------------------------------------------------------------


def to_image(frame, a: float, b: float, system: str = "image", sky: str = "fk5") -> tuple[float, float]:
    """A position in some system, as FITS image coordinates on a frame.

    Args:
        frame: The frame whose image the position is on.
        a, b: The position: pixels, or degrees in `sky` for a WCS system.
        system: DS9's coordinate system -- image, physical, wcs, or a bare
            sky frame, which DS9 accepts as shorthand for `wcs <frame>`.
        sky: The sky frame, for a WCS system.

    Raises:
        CoordinateError: For a WCS system on a frame with no WCS.
    """
    system = str(system).lower()
    if system in SKY_FRAMES:
        system, sky = "wcs", system
    if system == "physical":
        return physical_of(frame).physical_to_image(float(a), float(b))
    if system in PIXEL_SYSTEMS:
        return (float(a), float(b))
    handler = wcs_of(frame, _wcs_name(system))
    if handler is None:
        raise CoordinateError(f"the frame has no {_wcs_name(system)}")
    longitude, latitude = _convert_sky(float(a), float(b), str(sky).lower(), _native_name(handler))
    x, y = handler.world_to_pixel(longitude, latitude)
    return (float(x) + 1.0, float(y) + 1.0)


def from_image(frame, x: float, y: float, system: str = "image", sky: str = "fk5") -> tuple[float, float]:
    """FITS image coordinates on a frame, in some other system.

    The inverse of `to_image`; WCS answers come back in degrees, in `sky`.

    Raises:
        CoordinateError: For a WCS system on a frame with no WCS.
    """
    system = str(system).lower()
    if system in SKY_FRAMES:
        system, sky = "wcs", system
    if system == "physical":
        return physical_of(frame).image_to_physical(float(x), float(y))
    if system in PIXEL_SYSTEMS:
        return (float(x), float(y))
    handler = wcs_of(frame, _wcs_name(system))
    if handler is None:
        raise CoordinateError(f"the frame has no {_wcs_name(system)}")
    longitude, latitude = handler.pixel_to_world(float(x) - 1.0, float(y) - 1.0)
    return _convert_sky(float(longitude), float(latitude), _native_name(handler), str(sky).lower())


def parse_angle(text: str, hours: bool = False) -> float:
    """One coordinate as DS9 takes it: degrees, or sexagesimal.

    Args:
        text: `202.48`, `13:29:52.8`, `+47:11:42`, `13h29m52.8s` or
            `47d11m42s`.
        hours: Whether a sexagesimal value is in hours, as an equatorial
            longitude is.

    Raises:
        ValueError: If it is neither.
    """
    word = str(text).strip()
    try:
        return float(word)
    except ValueError:
        pass
    if word.endswith("d"):
        try:
            return float(word[:-1])
        except ValueError:
            pass
    unit_hours = "h" in word.lower()
    parts = [part for part in re.split(r"[:hHdDmMsS'\"\s]+", word) if part]
    if not 1 <= len(parts) <= 3:
        raise ValueError(f"{text} is not a coordinate")
    negative = parts[0].startswith("-")
    values = [abs(float(part)) for part in parts] + [0.0, 0.0]
    value = values[0] + values[1] / 60.0 + values[2] / 3600.0
    if hours or unit_hours:
        value *= 15.0
    return -value if negative else value


def parse_position(a: str, b: str, system: str = "image", sky: str = "fk5") -> tuple[float, float]:
    """Two words of a position, as numbers in their own system.

    Sexagesimal is read in hours for an equatorial longitude and degrees
    otherwise, as DS9 reads it.
    """
    system = str(system).lower()
    if system in SKY_FRAMES:
        system, sky = "wcs", system
    if not is_sky_system(system):
        return (float(a), float(b))
    return (parse_angle(a, hours=str(sky).lower() in HOUR_FRAMES), parse_angle(b))


def split_system(words: list[str]) -> tuple[list[str], str, str, str, str | None]:
    """Pull DS9's trailing system words off an argument list.

    `100 100 wcs fk5 degrees arcsec` comes back as the values, then
    `wcs`, `fk5`, `degrees` and the length unit `arcsec`. A bare sky frame
    (`fk5`) implies `wcs`. Missing words take DS9's defaults: physical for
    the system (which is image for a frame without LTV/LTM), fk5 and
    degrees.

    Returns:
        (values, system, sky, skyformat, unit) -- `unit` is None when no
        length unit was given.
    """
    values: list[str] = []
    system = ""
    sky = "fk5"
    sky_format = "degrees"
    unit: str | None = None
    for word in words:
        text = str(word).lower()
        if is_system(text):
            system = text
        elif text in SKY_FRAMES:
            sky = text
            system = system or "wcs"
        elif text in ("degrees", "sexagesimal"):
            # DS9 uses `degrees` for both the sky format and a length unit;
            # it is the same word with the same meaning either way.
            sky_format = text
            if text == "degrees":
                unit = text
        elif text in ("arcmin", "arcsec"):
            unit = text
        else:
            values.append(str(word))
    return (values, system or "physical", sky, sky_format, unit)


def format_position(
    a: float,
    b: float,
    system: str = "image",
    sky: str = "fk5",
    sky_format: str = "degrees",
    precision: dict[str, int] | None = None,
) -> str:
    """A position as DS9 writes it, `a b`."""
    digits = {**DEFAULT_PRECISION, **(precision or {})}
    system = str(system).lower()
    if not is_sky_system(system):
        return f"{_linear(a, digits['linear'])} {_linear(b, digits['linear'])}"
    if str(sky_format).lower().startswith("sex"):
        if str(sky).lower() in HOUR_FRAMES:
            longitude = degrees_to_hms(a, digits["hms"])
        else:
            longitude = degrees_to_dms(a % 360.0, digits["dms"]).lstrip("+")
        return f"{longitude} {degrees_to_dms(b, digits['dms'])}"
    return f"{a:.{digits['degrees']}f} {b:.{digits['degrees']}f}"


def _linear(value: float, significant: int) -> str:
    """A pixel coordinate, to DS9's linear precision without trailing zeros."""
    return f"{float(value):.{significant}g}"


# -- lengths -------------------------------------------------------------------------


def pixel_scale(frame, system: str = "wcs") -> float:
    """How many degrees one image pixel spans, on average over both axes.

    Raises:
        CoordinateError: If the frame has no WCS.
    """
    handler = wcs_of(frame, _wcs_name(system))
    if handler is None:
        raise CoordinateError("the frame has no WCS")
    from astropy.wcs.utils import proj_plane_pixel_scales

    scales = proj_plane_pixel_scales(handler.wcs.celestial)
    return float(math.sqrt(abs(scales[0] * scales[1])))


def length_to_image(frame, value: float, system: str = "image", unit: str | None = None) -> float:
    """A length in some system, in image pixels.

    Args:
        value: The length.
        system: The system it is in; a WCS one takes `unit`.
        unit: degrees, arcmin or arcsec for a WCS system; ignored otherwise.
    """
    system = str(system).lower()
    if is_sky_system(system):
        degrees = float(value) * ANGLE_UNITS.get(unit or "degrees", 1.0)
        return degrees / pixel_scale(frame, system)
    if system == "physical":
        transform = physical_of(frame)
        return float(value) * abs(transform.ltm1)
    return float(value)


def image_length_to(frame, value: float, system: str = "image", unit: str | None = None) -> float:
    """A length in image pixels, in some other system: the inverse of the above."""
    system = str(system).lower()
    if is_sky_system(system):
        degrees = float(value) * pixel_scale(frame, system)
        return degrees / ANGLE_UNITS.get(unit or "degrees", 1.0)
    if system == "physical":
        transform = physical_of(frame)
        return float(value) / abs(transform.ltm1)
    return float(value)


# -- angles ------------------------------------------------------------------------


def _sky_axes(frame, x: float, y: float, system: str, sky: str) -> tuple[float, bool]:
    """Where west points in the image at a position, and the sky's handedness.

    Returns:
        The image angle of the local west direction in the sky frame, in
        degrees, and whether the sky is seen the usual way round -- east
        to the left of north, as on a normal astronomical image.
    """
    step = 1.0 / 3600.0
    lon, lat = from_image(frame, x, y, system, sky)
    scale = max(math.cos(math.radians(lat)), 1e-6)
    north = to_image(frame, lon, min(lat + step, 90.0), system, sky)
    west = to_image(frame, lon - step / scale, lat, system, sky)
    wx, wy = west[0] - x, west[1] - y
    nx, ny = north[0] - x, north[1] - y
    return math.degrees(math.atan2(wy, wx)), (wx * ny - wy * nx) > 0


def sky_is_usual(frame, x: float, y: float, system: str, sky: str) -> bool:
    """Whether east is to the left of north at a position, as on a normal image."""
    try:
        return _sky_axes(frame, x, y, system, sky)[1]
    except CoordinateError:
        return True


def image_angle_to(frame, angle: float, x: float, y: float, system: str = "image", sky: str = "fk5") -> float:
    """A region's angle on the image, as DS9 writes it in a system.

    In image and physical coordinates the angle is measured from the x
    axis, as on the image. In a sky system DS9 measures it from the local
    west direction towards north (`Base::mapAngleFromRef`), which for an
    image with north up and east left is the same thing; for a turned image
    the turn is taken out, and for one with east to the right the sense is
    reversed.

    Args:
        angle: Degrees, on the image.
        x, y: Where the region is, in image coordinates: the sky turns
            across a wide field.
    """
    if not is_sky_system(system) and system not in SKY_FRAMES:
        return float(angle) % 360.0
    try:
        west, usual = _sky_axes(frame, x, y, system, sky)
    except CoordinateError:
        return float(angle) % 360.0
    turned = float(angle) - west
    return (turned if usual else -turned) % 360.0


def angle_to_image(frame, angle: float, x: float, y: float, system: str = "image", sky: str = "fk5") -> float:
    """The inverse of `image_angle_to`: an angle written in a system, on the image."""
    if not is_sky_system(system) and system not in SKY_FRAMES:
        return float(angle) % 360.0
    try:
        west, usual = _sky_axes(frame, x, y, system, sky)
    except CoordinateError:
        return float(angle) % 360.0
    return ((float(angle) if usual else -float(angle)) + west) % 360.0
