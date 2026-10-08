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
DS9's RGB Align: registering a colour frame's channels to one another.

The three channels of an RGB, HSV or HLS frame usually come from three
files, which need not share a pixel grid. DS9 (`FrameA::updateRGBMatrices`)
maps every channel onto the *key* channel -- the first one loaded -- through
the coordinate system on the RGB dialog's Align menu: WCS (the default),
one of the alternate WCSs, image, physical, amplifier or detector. Image
means pixel for pixel. If a channel lacks the WCS asked for, DS9 falls
back to image alignment, and so does this.

Each channel is resampled onto the key's grid by nearest pixel, as tksao
renders it, so values are never blended. What falls outside a channel is
blank (NaN).

Author: Yogesh Wadadekar
"""

from __future__ import annotations

from typing import Any

import numpy as np
from numpy.typing import NDArray

#: The systems the Align menu offers besides the WCSs.
PIXEL_SYSTEMS: tuple[str, ...] = ("image", "physical", "amplifier", "detector")


def _header(raw: Any):
    from astropy.io import fits

    if raw is None:
        return None
    return raw if isinstance(raw, fits.Header) else fits.Header(raw)


def _wcs(header, system: str):
    """The celestial WCS a system names in a header, or None."""
    if header is None:
        return None
    from astropy.wcs import WCS

    key = "" if system == "wcs" else system[3:].upper()
    if f"CTYPE1{key}" not in header:
        return None
    try:
        described = WCS(header, key=key or " ").celestial
    except Exception:
        return None
    return described if described.has_celestial else None


def _physical(header):
    from ..coordinates.physical_coords import PhysicalTransform

    return PhysicalTransform() if header is None else PhysicalTransform.from_header(header)


def effective_system(system: str, headers: dict[str, Any], channels: dict[str, Any]) -> str:
    """The system actually used: a WCS one only if every channel has it."""
    system = system.lower()
    if system in PIXEL_SYSTEMS:
        return system
    for name, data in channels.items():
        if data is not None and _wcs(_header(headers.get(name)), system) is None:
            return "image"
    return system


def _sample(data: NDArray, rows: NDArray, columns: NDArray) -> NDArray:
    """Nearest-pixel values at fractional positions, NaN off the edge."""
    r = np.rint(rows).astype(np.int64)
    c = np.rint(columns).astype(np.int64)
    inside = (r >= 0) & (r < data.shape[0]) & (c >= 0) & (c < data.shape[1])
    out = np.full(rows.shape, np.nan, dtype=np.float32)
    out[inside] = data[r[inside], c[inside]]
    return out


def align(
    channels: dict[str, NDArray | None],
    headers: dict[str, Any],
    key: str | None,
    system: str = "wcs",
) -> tuple[dict[str, NDArray | None], str]:
    """Every channel on the key channel's pixel grid.

    Args:
        channels: The channels as loaded, by name.
        headers: Each channel's FITS header, by name.
        key: The channel the others are mapped onto; the first loaded.
        system: DS9's Align system.

    Returns:
        The aligned channels, and the system that was used -- "image" if a
        WCS was asked for and a channel lacks it.
    """
    present = {name: data for name, data in channels.items() if data is not None}
    if not present:
        return dict(channels), system
    if key not in present:
        key = next(iter(present))
    used = effective_system(system, headers, present)
    reference = present[key]
    height, width = reference.shape[:2]
    rows, columns = np.indices((height, width), dtype=np.float64)

    aligned: dict[str, NDArray | None] = {}
    for name, data in channels.items():
        if data is None or name == key:
            aligned[name] = data
            continue
        if used == "image":
            if data.shape[:2] == (height, width):
                aligned[name] = data
                continue
            # Pixel for pixel from the bottom-left corner, as FITS counts.
            aligned[name] = _sample(np.asarray(data, dtype=np.float32), rows, columns)
            continue
        if used in PIXEL_SYSTEMS:
            # Physical, amplifier and detector all go through the header's
            # LTM/LTV here; NCRADS9 does not keep the other two apart.
            key_transform = _physical(_header(headers.get(key)))
            own_transform = _physical(_header(headers.get(name)))
            px, py = key_transform.image_to_physical(columns + 1.0, rows + 1.0)
            cx, cy = own_transform.physical_to_image(px, py)
            aligned[name] = _sample(np.asarray(data, dtype=np.float32), np.asarray(cy) - 1.0, np.asarray(cx) - 1.0)
            continue
        key_wcs = _wcs(_header(headers.get(key)), used)
        own_wcs = _wcs(_header(headers.get(name)), used)
        world = key_wcs.pixel_to_world(columns, rows)
        cx, cy = own_wcs.world_to_pixel(world)
        aligned[name] = _sample(np.asarray(data, dtype=np.float32), np.asarray(cy), np.asarray(cx))
    return aligned, used
