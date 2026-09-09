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
Mosaics: many detector images assembled into one.

DS9 supports three forms, set out in `ds9/doc/ref/file.html`:

* **IRAF** -- each image carries `DETSEC`, the rectangle of the detector it
  covers, and `DETSIZE`, the whole detector's extent. Placement is exact
  integer pixel copying, no resampling; this is NOAO's Mosaic Data Structures
  convention.
* **WCS** -- each image carries its own valid WCS and nothing else ties them
  together, so they are resampled onto a common grid.
* **HST WFPC2** -- a four-plane cube plus an ASCII table holding a WCS per
  plane.

Each form comes in a whole-file variant and a *segment* variant: DS9's menu
offers `Mosaic WCS` and `Mosaic WCS Segment`, the second adding one more file
into a mosaic already on screen ("A FITS mosaic may be loaded all at one time,
or by the segment").

The resampling is nearest-neighbour. That is what makes a mosaic a display
aid rather than a science product, and it is worth being explicit about: no
flux is conserved, and a pixel is either present or it is not. DS9's own
mosaic display resamples too. Anyone wanting a photometrically correct mosaic
should use `reproject` or SWarp and load the result.

Author: Yogesh Wadadekar
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from enum import Enum

import numpy as np
from astropy.io import fits
from astropy.wcs import WCS
from numpy.typing import NDArray

from .image_data import ImageData

#: `DETSEC` and `DETSIZE` are written as `[x0:x1,y0:y1]`.
_SECTION = re.compile(r"\[\s*(-?\d+)\s*:\s*(-?\d+)\s*,\s*(-?\d+)\s*:\s*(-?\d+)\s*\]")

#: The value an unfilled mosaic pixel takes. DS9 leaves gaps blank, and NaN
#: is what the scale algorithms already treat as absent.
BLANK = np.nan

#: A mosaic bigger than this many pixels is refused rather than attempted,
#: since a bad `DETSIZE` or a wild WCS can otherwise ask for terabytes.
MAX_MOSAIC_PIXELS = 400_000_000

#: How many planes an HST WFPC2 cube has.
WFPC2_PLANES = 4


class MosaicError(ValueError):
    """A mosaic that cannot be assembled, for the reason given."""


class MosaicKind(Enum):
    """Which of DS9's three mosaic conventions to use."""

    WCS = "wcs"
    IRAF = "iraf"
    WFPC2 = "wfpc2"


@dataclass(frozen=True)
class Placement:
    """Where one image sits in the mosaic, in output pixels.

    Bounds are zero-based and half-open, ready to slice with.
    """

    x0: int
    y0: int
    x1: int
    y1: int

    @property
    def width(self) -> int:
        """Columns covered."""
        return self.x1 - self.x0

    @property
    def height(self) -> int:
        """Rows covered."""
        return self.y1 - self.y0


def parse_section(value: object) -> Placement | None:
    """Read an IRAF `[x0:x1,y0:y1]` section into a zero-based `Placement`.

    Args:
        value: The card's value, or anything that is not a section.

    Returns:
        The placement, or None if the value is not a section.
    """
    match = _SECTION.search(str(value or ""))
    if match is None:
        return None
    x0, x1, y0, y1 = (int(group) for group in match.groups())
    return Placement(
        x0=min(x0, x1) - 1,
        y0=min(y0, y1) - 1,
        x1=max(x0, x1),
        y1=max(y0, y1),
    )


def _check_size(width: int, height: int) -> None:
    """Refuse a mosaic too large to allocate."""
    if width < 1 or height < 1:
        raise MosaicError(f"mosaic would be {width}x{height} pixels")
    if width * height > MAX_MOSAIC_PIXELS:
        raise MosaicError(
            f"mosaic would be {width}x{height} = {width * height:,} pixels, "
            f"over the {MAX_MOSAIC_PIXELS:,} limit"
        )


# -- IRAF ---------------------------------------------------------------------


def build_iraf_mosaic(images: list[ImageData]) -> ImageData:
    """Assemble images that carry `DETSEC` and `DETSIZE`.

    No resampling: each image is copied into the rectangle its own header
    names, which is exact as long as the sections do not overlap.

    Args:
        images: The extensions to assemble, in any order.

    Returns:
        The mosaic, with the first image's header carried over and its
        `CRPIX` shifted to the mosaic's own origin.

    Raises:
        MosaicError: If no image carries a usable `DETSEC`.
    """
    placements: list[tuple[ImageData, Placement]] = []
    for image in images:
        if image.data is None or image.header is None:
            continue
        placement = parse_section(image.header.get("DETSEC"))
        if placement is not None:
            placements.append((image, placement))

    if not placements:
        raise MosaicError(
            "no extension carries a DETSEC keyword; an IRAF mosaic needs "
            "DETSEC and DETSIZE (try Mosaic WCS instead)"
        )

    extent = _iraf_extent(placements)
    _check_size(extent.width, extent.height)
    canvas = np.full((extent.height, extent.width), BLANK, dtype=np.float32)

    for image, placement in placements:
        data = np.asarray(image.data, dtype=np.float32)
        while data.ndim > 2:
            data = data[0]
        # Trim to the smaller of what the section claims and what is there.
        height = min(placement.height, data.shape[0])
        width = min(placement.width, data.shape[1])
        row = placement.y0 - extent.y0
        column = placement.x0 - extent.x0
        canvas[row : row + height, column : column + width] = data[:height, :width]

    header = _mosaic_header(placements[0][0], placements[0][1], extent)
    return ImageData(data=canvas, header=header)


def _iraf_extent(placements: list[tuple[ImageData, Placement]]) -> Placement:
    """The mosaic's bounds: `DETSIZE` if given, else the union of sections."""
    for image, _placement in placements:
        if image.header is None:
            continue
        detsize = parse_section(image.header.get("DETSIZE"))
        if detsize is not None:
            return detsize
    return Placement(
        x0=min(p.x0 for _i, p in placements),
        y0=min(p.y0 for _i, p in placements),
        x1=max(p.x1 for _i, p in placements),
        y1=max(p.y1 for _i, p in placements),
    )


def _mosaic_header(
    reference: ImageData,
    placement: Placement,
    extent: Placement,
) -> fits.Header:
    """The first image's header, with `CRPIX` moved to the mosaic origin."""
    header = fits.Header() if reference.header is None else reference.header.copy()
    for key, shift in (
        ("CRPIX1", extent.x0 - placement.x0),
        ("CRPIX2", extent.y0 - placement.y0),
    ):
        if key in header and shift:
            header[key] = header[key] - shift
    # The mosaic is one image; the pieces' own placement cards no longer
    # describe it.
    for key in ("DETSEC", "DATASEC", "CCDSEC", "AMPSEC"):
        header.pop(key, None)
    return header


# -- WCS ----------------------------------------------------------------------


def build_wcs_mosaic(
    images: list[ImageData],
    existing: ImageData | None = None,
) -> ImageData:
    """Resample images with their own WCS onto one grid.

    The output grid keeps the first image's projection and pixel scale, sized
    to cover every image's footprint. Sampling is nearest-neighbour.

    Args:
        images: The extensions to assemble.
        existing: A mosaic already on screen, for DS9's segment variant --
            the new images are resampled onto *its* grid and merged into it,
            so the frame's coordinates do not shift as segments arrive.

    Returns:
        The mosaic.

    Raises:
        MosaicError: If fewer than one image carries a usable WCS.
    """
    usable = [
        (image, WCS(image.header))
        for image in images
        if image.data is not None and image.header is not None and _has_wcs(image.header)
    ]
    if not usable:
        raise MosaicError(
            "no extension carries a usable WCS; a WCS mosaic needs one per "
            "image (try Mosaic IRAF if the headers have DETSEC instead)"
        )

    if existing is not None and existing.header is not None and _has_wcs(existing.header):
        canvas = np.array(existing.data, dtype=np.float32, copy=True)
        header = existing.header.copy()
        output_wcs = WCS(header).celestial
    else:
        canvas, header, output_wcs = _empty_canvas(usable)

    for image, image_wcs in usable:
        _paint(canvas, output_wcs, image, image_wcs)

    return ImageData(data=canvas, header=header)


def _has_wcs(header: fits.Header) -> bool:
    """Whether a header declares a celestial WCS."""
    try:
        return bool(WCS(header).has_celestial)
    except Exception:
        return False


def _empty_canvas(
    usable: list[tuple[ImageData, WCS]],
) -> tuple[NDArray[np.float32], fits.Header, WCS]:
    """A blank grid in the first image's projection covering every footprint."""
    reference_image, reference_wcs = usable[0]
    celestial = reference_wcs.celestial

    corners_x: list[float] = []
    corners_y: list[float] = []
    for image, image_wcs in usable:
        height, width = _plane_shape(image)
        # The four corners are enough: a tangent projection maps a rectangle
        # to a convex quadrilateral, so nothing lies outside their bounds.
        # They are the outer *edges* of the corner pixels, not their centres,
        # or the canvas comes out a pixel short on each axis and the last row
        # and column of an input get clipped away.
        pixel_x = [-0.5, width - 0.5, -0.5, width - 0.5]
        pixel_y = [-0.5, -0.5, height - 0.5, height - 0.5]
        sky = image_wcs.celestial.pixel_to_world(pixel_x, pixel_y)
        out_x, out_y = celestial.world_to_pixel(sky)
        corners_x.extend(np.atleast_1d(out_x).tolist())
        corners_y.extend(np.atleast_1d(out_y).tolist())

    finite_x = [value for value in corners_x if np.isfinite(value)]
    finite_y = [value for value in corners_y if np.isfinite(value)]
    if not finite_x or not finite_y:
        raise MosaicError("the images' WCS footprints do not overlap a common projection")

    x0, x1 = int(np.floor(min(finite_x))), int(np.ceil(max(finite_x)))
    y0, y1 = int(np.floor(min(finite_y))), int(np.ceil(max(finite_y)))
    width, height = x1 - x0 + 1, y1 - y0 + 1
    _check_size(width, height)

    header = fits.Header() if reference_image.header is None else reference_image.header.copy()
    for key, shift in (("CRPIX1", x0), ("CRPIX2", y0)):
        if key in header:
            header[key] = header[key] - shift
    for key in ("NAXIS3", "NAXIS4", "DETSEC", "DATASEC"):
        header.pop(key, None)

    canvas = np.full((height, width), BLANK, dtype=np.float32)
    return canvas, header, WCS(header).celestial


def _plane_shape(image: ImageData) -> tuple[int, int]:
    """One image's 2D shape, taking the first plane of a cube.

    Raises:
        MosaicError: If the image holds no data.
    """
    if image.data is None:
        raise MosaicError("an image in the mosaic holds no data")
    shape = image.data.shape
    return int(shape[-2]), int(shape[-1])


def _paint(
    canvas: NDArray[np.float32],
    output_wcs: WCS,
    image: ImageData,
    image_wcs: WCS,
) -> None:
    """Sample one image into the canvas, nearest neighbour.

    Walks the *output* pixels that the image's footprint covers and pulls a
    value for each, rather than pushing input pixels out -- pushing leaves
    holes wherever the output grid is finer than the input.
    """
    data = np.asarray(image.data, dtype=np.float32)
    while data.ndim > 2:
        data = data[0]
    height, width = data.shape

    celestial = image_wcs.celestial
    corner_sky = celestial.pixel_to_world([0, width - 1, 0, width - 1], [0, 0, height - 1, height - 1])
    corner_x, corner_y = output_wcs.world_to_pixel(corner_sky)
    corner_x = np.atleast_1d(corner_x)
    corner_y = np.atleast_1d(corner_y)
    if not (np.all(np.isfinite(corner_x)) and np.all(np.isfinite(corner_y))):
        return

    out_x0 = max(0, int(np.floor(corner_x.min())))
    out_x1 = min(canvas.shape[1] - 1, int(np.ceil(corner_x.max())))
    out_y0 = max(0, int(np.floor(corner_y.min())))
    out_y1 = min(canvas.shape[0] - 1, int(np.ceil(corner_y.max())))
    if out_x1 < out_x0 or out_y1 < out_y0:
        return

    grid_y, grid_x = np.mgrid[out_y0 : out_y1 + 1, out_x0 : out_x1 + 1]
    sky = output_wcs.pixel_to_world(grid_x.ravel(), grid_y.ravel())
    source_x, source_y = celestial.world_to_pixel(sky)

    source_x = np.rint(np.asarray(source_x, dtype=np.float64))
    source_y = np.rint(np.asarray(source_y, dtype=np.float64))
    inside = (
        np.isfinite(source_x)
        & np.isfinite(source_y)
        & (source_x >= 0)
        & (source_x <= width - 1)
        & (source_y >= 0)
        & (source_y <= height - 1)
    )
    if not inside.any():
        return

    values = data[source_y[inside].astype(np.intp), source_x[inside].astype(np.intp)]
    target = canvas[out_y0 : out_y1 + 1, out_x0 : out_x1 + 1].ravel()

    # Write wherever this image has a real value, so a later image wins an
    # overlap and an earlier one survives wherever the later has nothing.
    # That makes a segment load additive: what is already on screen is kept
    # except where the new segment actually covers it.
    keep = np.isfinite(values)
    writable = inside.copy()
    writable[inside] = keep
    target[writable] = values[keep]
    canvas[out_y0 : out_y1 + 1, out_x0 : out_x1 + 1] = target.reshape(grid_x.shape)


# -- HST WFPC2 ----------------------------------------------------------------


def build_wfpc2_mosaic(images: list[ImageData]) -> ImageData:
    """Assemble an HST WFPC2 mosaic.

    WFPC2 data is a four-plane cube, one plane per CCD, with the per-plane
    WCS in a companion ASCII table rather than in the cube's own header. When
    the table is present each plane is given its WCS from it; when it is not,
    the planes are treated as a WCS mosaic on whatever WCS they carry, which
    is what DS9 falls back to as well.

    Args:
        images: The file's extensions. The cube is found among them.

    Returns:
        The mosaic.

    Raises:
        MosaicError: If no four-plane cube is present.
    """
    cube = next((image for image in images if image.data is not None and image.data.ndim >= 3), None)
    cube_data = None if cube is None else cube.data
    if cube is None or cube_data is None or cube_data.shape[-3] != WFPC2_PLANES:
        raise MosaicError(f"no {WFPC2_PLANES}-plane cube in this file; a WFPC2 mosaic needs one")

    table = next(
        (
            image
            for image in images
            if image.header is not None and _has_wcs(image.header) and image is not cube
        ),
        None,
    )
    planes = [
        ImageData(
            data=cube_data[index],
            header=_plane_header(cube, table, index),
        )
        for index in range(WFPC2_PLANES)
    ]
    return build_wcs_mosaic(planes)


def _plane_header(
    cube: ImageData,
    table: ImageData | None,
    index: int,
) -> fits.Header:
    """The WCS header for one WFPC2 plane."""
    header = fits.Header() if cube.header is None else cube.header.copy()
    for key in ("NAXIS3", "NAXIS4"):
        header.pop(key, None)
    if table is not None and table.header is not None:
        # The companion table's cards are per-plane, suffixed with the plane
        # number in the files that carry them.
        for card in ("CRVAL1", "CRVAL2", "CRPIX1", "CRPIX2", "CD1_1", "CD1_2", "CD2_1", "CD2_2"):
            value = table.header.get(f"{card}{index + 1}", table.header.get(card))
            if value is not None:
                header[card] = value
    return header


def build_mosaic(
    images: list[ImageData],
    kind: MosaicKind = MosaicKind.WCS,
    existing: ImageData | None = None,
) -> ImageData:
    """Assemble a mosaic in one of DS9's three conventions.

    Args:
        images: The extensions to assemble.
        kind: Which convention to use.
        existing: For a segment load, the mosaic already on screen. Only the
            WCS convention uses it; an IRAF mosaic is placed by absolute
            detector coordinates, so its segments land in the same place
            whether they arrive together or one at a time.

    Returns:
        The mosaic.

    Raises:
        MosaicError: If the images do not carry what the convention needs.
    """
    if not images:
        raise MosaicError("no images to assemble")
    if kind is MosaicKind.IRAF:
        if existing is not None:
            return _merge_blanks(build_iraf_mosaic(images), existing)
        return build_iraf_mosaic(images)
    if kind is MosaicKind.WFPC2:
        return build_wfpc2_mosaic(images)
    return build_wcs_mosaic(images, existing=existing)


def _merge_blanks(new: ImageData, existing: ImageData) -> ImageData:
    """Fill `existing`'s blank pixels from `new`, where the two line up.

    Used for an IRAF segment load: both mosaics are laid out in absolute
    detector coordinates, so identical shapes mean identical grids.
    """
    if existing.data is None or new.data is None or existing.data.shape != new.data.shape:
        return new
    merged = np.array(existing.data, dtype=np.float32, copy=True)
    blank = np.isnan(merged)
    merged[blank] = np.asarray(new.data, dtype=np.float32)[blank]
    return ImageData(data=merged, header=existing.header)
