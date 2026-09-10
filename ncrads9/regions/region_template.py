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
Template regions, and DS9's bundled instrument fields of view.

DS9's own words (`ds9/doc/ref/region.html`, Template Region): "A Template
Region is a special form of a region which is saved in a special wcs
coordinate system WCS0. WCS0 indicates that the ra and dec values are
relative to the current WCS location, not absolute. A template region can be
loaded at any location into any fits image which contains a valid wcs."

So a template is a region file whose positions are offsets in degrees from a
reference point. Loading one means choosing where the reference point goes --
the centre of the image, unless a caller says otherwise -- and turning every
offset into a pixel position through that image's WCS. Saving one is the
same in reverse.

The offsets are in RA and Dec directly, not projected: DS9 writes a template
by subtracting the reference RA and Dec, and reads it by adding them back.
Doing anything cleverer here would put the regions somewhere DS9 does not.

The twenty-three files under `templates/` are DS9's own, the instrument
fields of view its Instrument FOV cascade offers -- Chandra ACIS and HRC,
XMM's three EPIC cameras, Suzaku, and the MMT's instruments.

Author: Yogesh Wadadekar
"""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path
from typing import TYPE_CHECKING

from .base_region import BaseRegion
from .region_parser import RegionParser
from .region_writer import RegionWriter
from .shapes.composite import Composite

if TYPE_CHECKING:  # pragma: no cover - import cycle at runtime, types only
    from ..core.wcs_handler import WCSHandler

#: Where the bundled instrument templates live.
TEMPLATE_ROOT = Path(__file__).parent / "templates"

#: The line that makes a region file a template.
TEMPLATE_SYSTEM = "wcs0;fk5"

#: The header DS9 writes on one.
TEMPLATE_HEADER = "# Region file format: DS9 version 4.1"

#: The file extension DS9 gives them.
TEMPLATE_SUFFIX = ".tpl"


class TemplateError(ValueError):
    """A template that cannot be placed, for the reason given."""


def bundled_templates() -> dict[str, Path]:
    """DS9's instrument templates, keyed by the path its menu shows.

    The key is the file's path under `templates/` without its extension --
    `chandra/acis/acis-i` -- which is exactly the cascade DS9 builds from
    the same tree (`CreateFOVMenu` in `ds9/library/template.tcl`).
    """
    if not TEMPLATE_ROOT.is_dir():
        return {}
    found = sorted(TEMPLATE_ROOT.rglob(f"*{TEMPLATE_SUFFIX}"))
    return {path.relative_to(TEMPLATE_ROOT).with_suffix("").as_posix(): path for path in found}


def _positions(region: BaseRegion) -> list[str]:
    """Which of a region's attributes hold a position."""
    return [name for name in ("center", "start", "end") if hasattr(region, name)]


def _paths(region: BaseRegion) -> list[str]:
    """Which of a region's attributes hold a list of positions."""
    return [name for name in ("vertices", "points") if hasattr(region, name)]


def _walk(regions: list[BaseRegion]) -> Iterator[BaseRegion]:
    """Every region, and every region inside a composite."""
    for region in regions:
        yield region
        if isinstance(region, Composite):
            yield from _walk(region.regions)


def place(
    regions: list[BaseRegion],
    wcs_handler: WCSHandler | None,
    reference: tuple[float, float] | None = None,
) -> list[BaseRegion]:
    """Turn a template's offsets into pixel positions on one image.

    Args:
        regions: The template's regions, positions in degrees relative to
            its reference point.
        wcs_handler: The frame's WCS, which the offsets are placed through.
        reference: Where the template's origin goes, as (RA, Dec) in
            degrees. Defaults to the image's own centre, which is where DS9
            drops a template that is not told otherwise.

    Returns:
        The same region objects, moved. They are moved in place rather than
        copied, because they were parsed for this and nothing else holds
        them.

    Raises:
        TemplateError: If the image has no WCS to place the template on --
            a template is offsets from a sky position, so without one there
            is nowhere to put it.
    """
    if wcs_handler is None or not getattr(wcs_handler, "is_valid", False):
        raise TemplateError("a template needs an image with a WCS")

    if reference is None:
        reference = wcs_handler.get_center_coord()
    if reference is None:
        raise TemplateError("the image's WCS has no centre to place the template on")

    origin_ra, origin_dec = reference

    def to_pixel(lon: float, lat: float) -> tuple[float, float]:
        x, y = wcs_handler.world_to_pixel(origin_ra + lon, origin_dec + lat)
        return (float(x), float(y))

    for region in _walk(regions):
        if isinstance(region, Composite):
            # Its centre is the mean of its members, not a position of its
            # own; converting it would place the composite by a number that
            # is about to change anyway.
            continue
        for name in _positions(region):
            setattr(region, name, to_pixel(*getattr(region, name)))
        for name in _paths(region):
            setattr(region, name, [to_pixel(*point) for point in getattr(region, name)])

    for region in _walk(regions):
        if isinstance(region, Composite):
            region.recompute_center()
    return regions


def load(
    path: str | Path,
    wcs_handler: WCSHandler | None,
    reference: tuple[float, float] | None = None,
) -> list[BaseRegion]:
    """Read a template file and place it on an image.

    Raises:
        TemplateError: If the file is not a template, or the image has no
            WCS to place it on.
        OSError: If the file cannot be read.
    """
    parser = RegionParser()
    regions = parser.parse_file(path)
    if not parser.relative:
        raise TemplateError(f"{Path(path).name} is a region file, not a template (no wcs0)")
    return place(regions, wcs_handler, reference)


def save(
    path: str | Path,
    regions: list[BaseRegion],
    wcs_handler: WCSHandler | None,
    reference: tuple[float, float] | None = None,
) -> None:
    """Write regions out as a template, relative to a reference point.

    The regions themselves are not moved: they are converted to offsets on
    the way out, which is what makes this safe to call on what is on screen.

    Raises:
        TemplateError: If the image has no WCS to measure the offsets
            against.
        OSError: If the file cannot be written.
    """
    if wcs_handler is None or not getattr(wcs_handler, "is_valid", False):
        raise TemplateError("saving a template needs an image with a WCS")
    if reference is None:
        reference = wcs_handler.get_center_coord()
    if reference is None:
        raise TemplateError("the image's WCS has no centre to measure the template against")

    origin_ra, origin_dec = reference

    def to_offset(x: float, y: float) -> tuple[float, float]:
        lon, lat = wcs_handler.pixel_to_world(x, y)
        return (float(lon) - origin_ra, float(lat) - origin_dec)

    lines = [TEMPLATE_HEADER, TEMPLATE_SYSTEM]
    writer = RegionWriter()
    for region in _walk(regions):
        if isinstance(region, Composite):
            lines.append(writer._format_region(region))
            continue
        # Convert, write, and put the region back exactly as it was: the
        # caller's regions are the ones on screen.
        saved = {name: getattr(region, name) for name in _positions(region)}
        saved_paths = {name: list(getattr(region, name)) for name in _paths(region)}
        try:
            for name, value in saved.items():
                setattr(region, name, to_offset(*value))
            for name, value in saved_paths.items():
                setattr(region, name, [to_offset(*point) for point in value])
            lines.append(writer._format_region(region))
        finally:
            for name, value in saved.items():
                setattr(region, name, value)
            for name, value in saved_paths.items():
                setattr(region, name, value)

    Path(path).write_text("\n".join(lines) + "\n")
