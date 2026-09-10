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
What a region says about the pixels under it.

DS9 puts an Analysis menu on every region's dialog: Statistics, Histogram,
Radial Profile for the shapes with annuli, Plot 2D along a projection and
Plot 3D through a cube. All of them start from the same question -- which
pixels are inside this region -- and this module answers it once.

The statistics are DS9's, field for field, from `Base::markerAnalysisStats`
in `tksao/frame/frblt.C`: sum, error as the root of its absolute value, area,
surface brightness and its error in the first table; sum, npix, mean, median,
min, max, variance, standard deviation and rms in the second. The variance is
DS9's population form, `|sum2/n - (sum/n)^2|`, not the sample one, so the
numbers match what DS9 prints for the same region.

A shape with annuli reports one row per annulus, numbered from one, again as
DS9 does -- an annulus whose rings all reported together would say nothing a
plain circle does not.

Author: Yogesh Wadadekar
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from itertools import pairwise

import numpy as np
from numpy.typing import NDArray

from ..analysis.histogram import Histogram
from ..analysis.statistics import image_stats
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
from .shapes.vector import Vector

#: How wide a shape with no extent of its own is taken to be, in pixels.
POINT_EXTENT = 5.0

#: Shapes made of concentric rings, which report one row per ring.
ANNULAR_SHAPES = (Annulus, EllipseAnnulus, BoxAnnulus, Panda, Epanda, Bpanda)

#: The shapes a cut along a line can be taken from.
LINEAR_SHAPES = (Line, Ruler, Projection, Vector, Segment)

#: How many samples a cut along a line takes per pixel of its length.
CUT_SAMPLES_PER_PIXEL = 1.0

#: The default number of bins in a region's histogram, as DS9 uses.
DEFAULT_BINS = 100


class AnalysisError(ValueError):
    """A region that cannot be analysed, for the reason given."""


@dataclass(frozen=True)
class Statistics:
    """One region's -- or one annulus's -- pixel statistics.

    The names are DS9's, from the two tables its Statistics window prints.

    Attributes:
        npix: How many pixels fell inside.
        total: Their sum. Called `sum` in DS9's table; `sum` is a builtin.
        error: `sqrt(|sum|)`, the counting error DS9 reports.
        area: The area, in pixels or in arcsec squared if a scale is given.
        surface_brightness: Sum per unit area.
        surface_error: Error per unit area.
        mean: The mean.
        median: The median.
        minimum: The smallest value.
        maximum: The largest.
        variance: DS9's population variance, `|sum2/n - (sum/n)^2|`.
        stddev: Its square root.
        rms: `sqrt(sum2/n)`.
    """

    npix: int
    total: float
    error: float
    area: float
    surface_brightness: float
    surface_error: float
    mean: float
    median: float
    minimum: float
    maximum: float
    variance: float
    stddev: float
    rms: float

    @classmethod
    def of(cls, values: NDArray[np.floating], pixel_area: float = 1.0) -> Statistics:
        """Measure a set of pixel values.

        Args:
            values: The pixels inside the region, already flattened. Any
                non-finite value has been dropped by the caller.
            pixel_area: The area of one pixel, in whatever unit the caller
                wants the area reported in. One, for pixels.
        """
        count = int(values.size)
        if count == 0:
            return cls(0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0)

        # mean, median, min, max and the count come from `analysis.statistics`,
        # which already has them; the rest are DS9's own fields.
        summary = image_stats(values)
        total = float(values.sum())
        squares = float(np.square(values, dtype=np.float64).sum())
        area = count * pixel_area
        error = math.sqrt(abs(total))
        # DS9's population variance, and its absolute value: the two terms
        # are close for a flat region and rounding can make the difference
        # slightly negative.
        variance = abs(squares / count - summary["mean"] ** 2)

        return cls(
            npix=int(summary["npixels"]),
            total=total,
            error=error,
            area=area,
            surface_brightness=total / area if area else 0.0,
            surface_error=error / area if area else 0.0,
            mean=summary["mean"],
            median=summary["median"],
            minimum=summary["min"],
            maximum=summary["max"],
            variance=variance,
            stddev=math.sqrt(variance),
            rms=math.sqrt(squares / count),
        )


# -- which pixels are inside ---------------------------------------------------


def bounds(region: BaseRegion) -> tuple[float, float, float, float]:
    """A box that certainly contains a region, as (x0, x1, y0, y1).

    Deliberately generous for a rotated shape -- the half-extent is taken as
    if it were turned to its worst angle -- because `contains` does the real
    test and a box that is too small silently loses pixels.
    """
    cx, cy = region.center

    if isinstance(region, Composite):
        boxes = [bounds(child) for child in region.regions]
        if not boxes:
            return (cx - POINT_EXTENT, cx + POINT_EXTENT, cy - POINT_EXTENT, cy + POINT_EXTENT)
        return (
            min(box[0] for box in boxes),
            max(box[1] for box in boxes),
            min(box[2] for box in boxes),
            max(box[3] for box in boxes),
        )

    if isinstance(region, (Polygon, Segment)):
        points = region.vertices if isinstance(region, Polygon) else region.points
        xs = [x for x, _y in points]
        ys = [y for _x, y in points]
        return (min(xs), max(xs), min(ys), max(ys))

    if isinstance(region, (Line, Ruler, Projection)):
        (x1, y1), (x2, y2) = region.start, region.end
        pad = getattr(region, "projection_width", 0.0) or 0.0
        return (min(x1, x2) - pad, max(x1, x2) + pad, min(y1, y2) - pad, max(y1, y2) + pad)

    reach = _reach(region)
    return (cx - reach, cx + reach, cy - reach, cy + reach)


def _reach(region: BaseRegion) -> float:
    """How far a shape extends from its centre, at worst."""
    if isinstance(region, Circle):
        return float(region.radius)
    if isinstance(region, Annulus):
        return float(region.outer_radius)
    if isinstance(region, Panda):
        return float(region.outer_radius)
    if isinstance(region, (Epanda, Bpanda)):
        return math.hypot(region.outer_major, region.outer_minor)
    if isinstance(region, EllipseAnnulus):
        return math.hypot(region.outer_semi_major, region.outer_semi_minor)
    if isinstance(region, Ellipse):
        return math.hypot(region.semi_major, region.semi_minor)
    if isinstance(region, BoxAnnulus):
        return math.hypot(region.outer_width, region.outer_height) / 2.0
    if isinstance(region, Box):
        return math.hypot(region.width_box, region.height_box) / 2.0
    if isinstance(region, Vector):
        return float(region.length)
    if isinstance(region, Compass):
        return float(region.length)
    if isinstance(region, Point):
        return float(getattr(region, "size", POINT_EXTENT)) / 2.0
    return POINT_EXTENT


def mask_for(region: BaseRegion, shape: tuple[int, int]) -> NDArray[np.bool_]:
    """Which pixels of an image of `shape` fall inside a region.

    Args:
        region: The region.
        shape: The image's (height, width).

    Returns:
        A boolean array of that shape. Pixel centres are tested, and image
        coordinates count from one, so array element [j, i] is the pixel
        centred on (i + 1, j + 1).
    """
    height, width = shape
    inside = np.zeros((height, width), dtype=bool)

    x0, x1, y0, y1 = bounds(region)
    first_column = max(0, int(math.floor(x0)) - 1)
    last_column = min(width, int(math.ceil(x1)) + 1)
    first_row = max(0, int(math.floor(y0)) - 1)
    last_row = min(height, int(math.ceil(y1)) + 1)
    if first_column >= last_column or first_row >= last_row:
        return inside

    columns = np.arange(first_column, last_column) + 1.0
    rows = np.arange(first_row, last_row) + 1.0
    grid_x, grid_y = np.meshgrid(columns, rows)

    patch = _contains(region, grid_x, grid_y)
    inside[first_row:last_row, first_column:last_column] = patch
    return inside


def _contains(region: BaseRegion, x: NDArray, y: NDArray) -> NDArray[np.bool_]:
    """Test a grid of positions against a region.

    Circles, ellipses and boxes are tested with arithmetic rather than
    through `contains`, because a per-pixel Python call over a few hundred
    pixels square is a hundred thousand of them and takes about a second.
    Everything else falls back to the shape's own test, which is right by
    construction and only slow.
    """
    cx, cy = region.center

    if isinstance(region, Circle):
        return (x - cx) ** 2 + (y - cy) ** 2 <= region.radius**2

    if isinstance(region, Annulus):
        distance = (x - cx) ** 2 + (y - cy) ** 2
        return (distance >= region.inner_radius**2) & (distance <= region.outer_radius**2)

    if isinstance(region, Ellipse) and not isinstance(region, EllipseAnnulus):
        local_x, local_y = _rotate(x - cx, y - cy, -math.radians(region.angle))
        return (local_x / region.semi_major) ** 2 + (local_y / region.semi_minor) ** 2 <= 1.0

    if isinstance(region, Box) and not isinstance(region, BoxAnnulus):
        # Half-open on the upper edge. A ten-pixel box centred on a pixel
        # centre reaches exactly the centres five away on both sides, and
        # counting both gives eleven columns for a ten-pixel box -- a 28%
        # overstatement of the area every statistic is then divided by.
        # `contains` stays inclusive: that is hit-testing, not area.
        local_x, local_y = _rotate(x - cx, y - cy, -math.radians(region.angle))
        half_width, half_height = region.width_box / 2.0, region.height_box / 2.0
        return (
            (local_x >= -half_width)
            & (local_x < half_width)
            & (local_y >= -half_height)
            & (local_y < half_height)
        )

    tester = np.vectorize(region.contains, otypes=[bool])
    return tester(x, y)


def _rotate(x: NDArray, y: NDArray, angle: float) -> tuple[NDArray, NDArray]:
    """Turn a grid of offsets by `angle` radians."""
    cosine, sine = math.cos(angle), math.sin(angle)
    return (x * cosine - y * sine, x * sine + y * cosine)


def values_in(region: BaseRegion, data: NDArray[np.floating]) -> NDArray[np.floating]:
    """The finite pixel values inside a region.

    Raises:
        AnalysisError: If there is no two-dimensional image to measure.
    """
    if data is None or np.ndim(data) != 2:
        raise AnalysisError("no image to measure")
    values = np.asarray(data, dtype=np.float64)[mask_for(region, values_shape(data))]
    return values[np.isfinite(values)]


def values_shape(data: NDArray) -> tuple[int, int]:
    """An image's (height, width)."""
    return (int(data.shape[0]), int(data.shape[1]))


# -- annuli --------------------------------------------------------------------


def annuli(region: BaseRegion) -> list[BaseRegion]:
    """A region broken into the rings it reports separately.

    A plain shape is one ring: itself. An annulus, or one of the panda
    family, becomes one `Annulus` per gap between its radii -- reporting
    every ring together would say nothing a plain circle does not.
    """
    if isinstance(region, Annulus):
        radii = [region.inner_radius, region.outer_radius]
    elif isinstance(region, Panda):
        radii = _steps(region.inner_radius, region.outer_radius, region.num_radii)
    elif isinstance(region, EllipseAnnulus):
        radii = [region.inner_semi_major, region.outer_semi_major]
    elif isinstance(region, (Epanda, Bpanda)):
        radii = _steps(region.inner_major, region.outer_major, region.num_radii)
    elif isinstance(region, BoxAnnulus):
        radii = [region.inner_width / 2.0, region.outer_width / 2.0]
    else:
        return [region]

    return [
        Annulus(center=region.center, inner_radius=inner, outer_radius=outer)
        for inner, outer in pairwise(radii)
    ]


def _steps(inner: float, outer: float, count: int) -> list[float]:
    """`count` rings between two radii, as a list of `count + 1` edges."""
    steps = max(1, int(count))
    span = (outer - inner) / steps
    return [inner + span * index for index in range(steps + 1)]


def statistics(
    region: BaseRegion,
    data: NDArray[np.floating],
    pixel_area: float = 1.0,
) -> list[Statistics]:
    """Measure a region, one entry per annulus.

    Raises:
        AnalysisError: If there is no image to measure.
    """
    return [Statistics.of(values_in(ring, data), pixel_area) for ring in annuli(region)]


# -- the profiles DS9 plots -------------------------------------------------------


def radial_profile(
    region: BaseRegion,
    data: NDArray[np.floating],
) -> tuple[list[float], list[float], list[float]]:
    """Surface brightness against radius, for a shape with annuli.

    Returns:
        The mid-radius of each ring, its surface brightness, and the error
        on that -- which is what DS9 plots and what its error bars show.

    Raises:
        AnalysisError: If the shape has no annuli to profile.
    """
    if not isinstance(region, ANNULAR_SHAPES):
        raise AnalysisError(
            f"a radial profile needs a shape with annuli, not a {type(region).__name__.lower()}"
        )

    radii: list[float] = []
    brightness: list[float] = []
    errors: list[float] = []
    for ring in annuli(region):
        if not isinstance(ring, Annulus):
            continue
        measured = Statistics.of(values_in(ring, data))
        radii.append((ring.inner_radius + ring.outer_radius) / 2.0)
        brightness.append(measured.surface_brightness)
        errors.append(measured.surface_error)
    return (radii, brightness, errors)


def cut(region: BaseRegion, data: NDArray[np.floating]) -> tuple[list[float], list[float]]:
    """The pixel values along a line, DS9's Plot 2D.

    Returns:
        Distance from the start in pixels, and the value there. Values are
        read at the nearest pixel rather than interpolated, which is what
        DS9 does and keeps a cut across sharp edges honest.

    Raises:
        AnalysisError: If the region is not a line of some kind.
    """
    if not isinstance(region, LINEAR_SHAPES):
        raise AnalysisError(f"a cut needs a line, not a {type(region).__name__.lower()}")
    if data is None or np.ndim(data) != 2:
        raise AnalysisError("no image to measure")

    start, end = _ends(region)
    length = math.hypot(end[0] - start[0], end[1] - start[1])
    steps = max(2, int(length * CUT_SAMPLES_PER_PIXEL) + 1)

    height, width = values_shape(data)
    distances: list[float] = []
    values: list[float] = []
    for step in range(steps):
        fraction = step / (steps - 1)
        x = start[0] + (end[0] - start[0]) * fraction
        y = start[1] + (end[1] - start[1]) * fraction
        column, row = int(round(x)) - 1, int(round(y)) - 1
        if 0 <= column < width and 0 <= row < height:
            distances.append(length * fraction)
            values.append(float(data[row, column]))
    return (distances, values)


def _ends(
    region: Line | Ruler | Projection | Vector | Segment,
) -> tuple[tuple[float, float], tuple[float, float]]:
    """A linear region's two ends."""
    if isinstance(region, Vector):
        angle = math.radians(region.angle)
        x, y = region.start
        return ((x, y), (x + region.length * math.cos(angle), y + region.length * math.sin(angle)))
    if isinstance(region, Segment):
        return (region.points[0], region.points[-1])
    return (region.start, region.end)


def depth_profile(region: BaseRegion, cube: NDArray[np.floating]) -> tuple[list[int], list[float]]:
    """The sum inside a region on each slice of a cube, DS9's Plot 3D.

    Returns:
        The slice numbers, counting from one as DS9's Cube dialog does, and
        the sum inside the region on each.

    Raises:
        AnalysisError: If the data is not a cube.
    """
    if cube is None or np.ndim(cube) != 3:
        raise AnalysisError("a 3D plot needs a data cube")

    inside = mask_for(region, values_shape(cube[0]))
    if not inside.any():
        raise AnalysisError("the region covers no pixels")

    slices: list[int] = []
    totals: list[float] = []
    for index in range(cube.shape[0]):
        plane = np.asarray(cube[index], dtype=np.float64)[inside]
        plane = plane[np.isfinite(plane)]
        slices.append(index + 1)
        totals.append(float(plane.sum()))
    return (slices, totals)


def histogram(
    region: BaseRegion,
    data: NDArray[np.floating],
    bins: int = DEFAULT_BINS,
) -> tuple[NDArray[np.floating], NDArray[np.floating]]:
    """The distribution of the pixel values inside a region.

    Returns:
        The bin centres and the counts.

    Raises:
        AnalysisError: If there is no image, or the region covers nothing.
    """
    if data is None or np.ndim(data) != 2:
        raise AnalysisError("no image to measure")
    inside = mask_for(region, values_shape(data))
    if not inside.any():
        raise AnalysisError("the region covers no pixels")

    # `analysis.histogram.Histogram` takes a mask, which is exactly what a
    # region is: the pixels inside it.
    binned = Histogram(np.asarray(data, dtype=np.float64), bins=max(1, int(bins)), mask=inside)
    return (np.asarray(binned.bin_centers, dtype=float), np.asarray(binned.counts, dtype=float))


# -- DS9's statistics text ----------------------------------------------------------


def describe(
    region: BaseRegion,
    data: NDArray[np.floating],
    pixel_area: float = 1.0,
    area_unit: str = "pix**2",
) -> str:
    """DS9's two statistics tables for one region, as text.

    The layout is `Base::markerAnalysisStats1..4` in `tksao/frame/frblt.C`:
    the centre and coordinate system, then a table of sum, error, area and
    surface brightness, then a table of the distribution.
    """
    measured = statistics(region, data, pixel_area)
    cx, cy = region.center

    lines = [f"center={cx:.8g} {cy:.8g}", "image", ""]
    lines.append("reg\tsum\t\terror\tarea\t\tsurf_bri\t\tsurf_err")
    lines.append(f"\t\t\t({area_unit})\t\t(sum/{area_unit})\t\t(sum/{area_unit})")
    lines.append("---\t---\t\t-----\t--------\t\t------------\t\t------------")
    for number, entry in enumerate(measured, start=1):
        lines.append(
            f"{number}\t{entry.total:.8g}\t\t{entry.error:.6g}\t{entry.area:.6g}\t\t"
            f"{entry.surface_brightness:.6g}\t\t{entry.surface_error:.6g}"
        )

    lines.append("")
    lines.append("reg\tsum\tnpix\tmean\tmedian\tmin\tmax\tvar\tstddev\trms")
    lines.append("---\t---\t----\t----\t------\t---\t---\t---\t------\t---")
    for number, entry in enumerate(measured, start=1):
        lines.append(
            f"{number}\t{entry.total:.8g}\t{entry.npix}\t{entry.mean:.6g}\t"
            f"{entry.median:.6g}\t{entry.minimum:.6g}\t{entry.maximum:.6g}\t"
            f"{entry.variance:.6g}\t{entry.stddev:.6g}\t{entry.rms:.6g}"
        )
    return "\n".join(lines)
