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
Regions carried inside a FITS file, in a `REGION` binary table.

DS9 opens one on every file it loads: "now, load fits[REGION] if present"
(`ds9/library/fits.tcl:29`), controlled by the Autoload FITS Regions
preference, which DS9 has on by default.

The table is the FITS region convention that CIAO and funtools write: one
row per region, with `X` and `Y` holding the position (or every vertex, for
a polygon), `SHAPE` naming the shape, `R` its radii, `ROTANG` its angle, and
`COMPONENT` grouping rows. A shape name beginning with `!` or `-` is an
exclusion, and `ROT` prefixed to a shape means it carries an angle -- a
`rotbox` is a box that does.

Sizes in the table are radii, not diameters, for the box-like shapes too,
which is the one place this differs from DS9's own text format and the one
place it is easy to get wrong.

Author: Yogesh Wadadekar
"""

from __future__ import annotations

from typing import Any

import numpy as np

from .base_region import BaseRegion
from .shapes.annulus import Annulus
from .shapes.box import Box
from .shapes.circle import Circle
from .shapes.ellipse import Ellipse
from .shapes.point import Point
from .shapes.polygon import Polygon

#: The extension name DS9 looks for.
REGION_EXTENSION = "REGION"

#: The columns the convention defines. Only X, Y and SHAPE are required.
SHAPE_COLUMN = "SHAPE"
X_COLUMN = "X"
Y_COLUMN = "Y"
RADIUS_COLUMN = "R"
ANGLE_COLUMN = "ROTANG"

#: The markers that make a row an exclusion.
EXCLUSION_MARKS = ("!", "-")


def has_region_extension(hdu_list: Any) -> bool:
    """Whether a FITS file carries a `REGION` table."""
    if hdu_list is None:
        return False
    for hdu in hdu_list:
        name = str(getattr(hdu, "name", "") or "").strip().upper()
        if name == REGION_EXTENSION and getattr(hdu, "data", None) is not None:
            return True
    return False


def region_hdu(hdu_list: Any) -> Any:
    """The file's `REGION` table, or None."""
    if hdu_list is None:
        return None
    for hdu in hdu_list:
        if str(getattr(hdu, "name", "") or "").strip().upper() == REGION_EXTENSION:
            return hdu
    return None


def _values(row: Any, column: str) -> list[float]:
    """One column of one row, always as a list of numbers.

    A column may hold a scalar or a vector -- `X` is one number for a circle
    and every vertex for a polygon -- and this flattens both to a list so
    the shape builders need not care which they were given.
    """
    try:
        value = row[column]
    except (KeyError, IndexError, TypeError):
        return []
    if value is None:
        return []
    array = np.atleast_1d(np.asarray(value, dtype=float)).ravel()
    return [float(number) for number in array if np.isfinite(number)]


def _first(values: list[float], index: int = 0, default: float = 0.0) -> float:
    """One number out of a column, or a default if it is not there."""
    return values[index] if len(values) > index else default


def _build(
    shape: str,
    x: list[float],
    y: list[float],
    r: list[float],
    angle: float,
) -> BaseRegion | None:
    """Build the region one row describes, or None for a shape we skip."""
    cx, cy = _first(x), _first(y)

    if shape in ("circle",):
        return Circle(center=(cx, cy), radius=_first(r))
    if shape in ("annulus",):
        return Annulus(center=(cx, cy), inner_radius=_first(r), outer_radius=_first(r, 1))
    if shape in ("ellipse", "elliptannulus"):
        # An elliptical annulus in the convention carries four radii; only
        # the outer pair describes an ellipse, which is what DS9 draws when
        # it cannot draw the annulus.
        return Ellipse(center=(cx, cy), semi_major=_first(r), semi_minor=_first(r, 1), angle=angle)
    if shape in ("box", "rotbox", "rectangle", "rotrectangle"):
        # The convention gives radii, not widths, for these too.
        return Box(
            center=(cx, cy),
            width_box=_first(r) * 2.0,
            height_box=_first(r, 1) * 2.0,
            angle=angle,
        )
    if shape in ("polygon",):
        vertices = list(zip(x, y, strict=False))
        return Polygon(vertices=vertices) if len(vertices) >= 3 else None
    if shape in ("point",):
        return Point(center=(cx, cy))
    return None


def read_regions(hdu: Any) -> list[BaseRegion]:
    """Read every region out of a `REGION` table.

    Args:
        hdu: The table HDU, as astropy returns it.

    Returns:
        The regions. A row naming a shape with no equivalent here is
        skipped rather than being an error -- the convention has shapes
        (sector, pie, diamond) DS9 itself does not always draw, and one
        unreadable row must not lose the rest of the table.
    """
    data = getattr(hdu, "data", None)
    if data is None or len(data) == 0:
        return []

    columns = {name.strip().upper() for name in getattr(data, "names", ()) or ()}
    if SHAPE_COLUMN not in columns:
        return []

    regions: list[BaseRegion] = []
    for row in data:
        raw = str(row[SHAPE_COLUMN]).strip()
        include = not raw.startswith(EXCLUSION_MARKS)
        shape = raw.lstrip("".join(EXCLUSION_MARKS)).strip().lower()

        region = _build(
            shape,
            _values(row, X_COLUMN),
            _values(row, Y_COLUMN),
            _values(row, RADIUS_COLUMN),
            _first(_values(row, ANGLE_COLUMN)),
        )
        if region is None:
            continue
        region.include = include
        regions.append(region)
    return regions


def load_from_file(hdu_list: Any) -> list[BaseRegion]:
    """Read a file's `REGION` table, if it has one."""
    hdu = region_hdu(hdu_list)
    return read_regions(hdu) if hdu is not None else []
