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
Working out where a coordinate grid's lines, ticks and numbers go.

This is the geometry only: it produces polylines and label positions in
image pixels, and something else draws them. That separation is what lets it
be tested against a known WCS without a window.

The lines are curves, not a lattice. A line of constant declination is
straight in the sky and bent on the image by whatever projection the file
uses, so each one is sampled along its length and joined up -- which is the
whole difference between a coordinate grid and the pixel grid this replaces.
A line is also broken wherever it leaves the image and rejoined where it
comes back, so a curve that clips a corner does not get a chord drawn across
the frame.

Built on `astropy.wcs`'s own transforms. PLAN.md suggested
`astropy.visualization.wcsaxes`; its transform machinery is bound to a
matplotlib axes object, and the drawing here is QPainter, so the transform
is taken directly from the WCS and the sampling done here. The point of the
suggestion -- do not port AST -- stands either way.

Author: Yogesh Wadadekar
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field

import numpy as np
from numpy.typing import NDArray

from .grid_config import GridConfig
from .grid_labels import Label, LabelPosition, default_format, format_coordinate, nice_spacing

#: How many points each grid line is sampled at. Enough that a curve across
#: a wide field reads as a curve; few enough to redraw on every pan.
SAMPLES_PER_LINE = 120

#: How many points around the image edge are probed to find the sky area it
#: covers. The corners alone are not enough: a projection can put the
#: extreme longitude in the middle of an edge.
EDGE_SAMPLES = 24

#: How long a tick mark is, in screen pixels.
TICK_LENGTH = 6.0

#: How far a label sits from the edge it belongs to, in screen pixels.
LABEL_MARGIN = 4.0

#: A gap in a sampled line longer than this many pixels is taken as the line
#: having left the image and come back, and is not joined up.
BREAK_DISTANCE = 400.0


@dataclass
class GridGeometry:
    """Where everything goes, in image pixels.

    Attributes:
        longitude_lines: One polyline per line of constant longitude.
        latitude_lines: One per line of constant latitude.
        labels: The numbers, with the edge each belongs to.
        ticks: Tick marks, as (x, y, dx, dy) with the direction to draw in.
        border: The image's outline, as one polyline.
        x_title, y_title: The axis titles to draw.
        longitude_spacing, latitude_spacing: The intervals used, in degrees.
    """

    longitude_lines: list[list[tuple[float, float]]] = field(default_factory=list)
    latitude_lines: list[list[tuple[float, float]]] = field(default_factory=list)
    labels: list[Label] = field(default_factory=list)
    ticks: list[tuple[float, float, float, float]] = field(default_factory=list)
    border: list[tuple[float, float]] = field(default_factory=list)
    x_title: str = ""
    y_title: str = ""
    longitude_spacing: float = 0.0
    latitude_spacing: float = 0.0

    @property
    def lines(self) -> list[list[tuple[float, float]]]:
        """Every grid line, both families together."""
        return [*self.longitude_lines, *self.latitude_lines]


class GridRenderer:
    """Computes a coordinate grid for one image and WCS.

    Args:
        wcs: The image's WCS handler, or anything with `pixel_to_world`,
            `world_to_pixel` and `is_valid`.
        config: How the grid should look.
    """

    def __init__(self, wcs=None, config: GridConfig | None = None) -> None:
        self._wcs = wcs
        self._config = config or GridConfig()

    @property
    def wcs(self):
        """The WCS the grid is computed through."""
        return self._wcs

    @wcs.setter
    def wcs(self, value) -> None:
        self._wcs = value

    @property
    def config(self) -> GridConfig:
        """How the grid looks."""
        return self._config

    @config.setter
    def config(self, value: GridConfig) -> None:
        self._config = value

    @property
    def usable(self) -> bool:
        """Whether there is a WCS to compute a sky grid from."""
        return bool(self._wcs is not None and getattr(self._wcs, "is_valid", False))

    # -- the sky area the image covers ---------------------------------------

    def sky_bounds(self, width: int, height: int) -> tuple[float, float, float, float] | None:
        """The longitude and latitude range the image covers.

        Returns:
            (lon0, lon1, lat0, lat1) in degrees, or None if the WCS cannot
            say. The longitude range may exceed 360 where the field crosses
            the meridian, which is what lets the caller step across it.
        """
        if not self.usable or width <= 0 or height <= 0:
            return None

        x, y = _edge_points(width, height)
        try:
            longitude, latitude = self._wcs.pixel_to_world(x, y)
        except Exception:
            return None

        longitude = np.asarray(longitude, dtype=float)
        latitude = np.asarray(latitude, dtype=float)
        good = np.isfinite(longitude) & np.isfinite(latitude)
        if not good.any():
            return None
        longitude, latitude = longitude[good], latitude[good]

        # A field spanning 0h reports longitudes near 0 and near 360, whose
        # plain min and max say "the whole sky". Unwrapping puts them next
        # to each other, and the caller steps through a range that may run
        # past 360.
        unwrapped = np.degrees(np.unwrap(np.radians(longitude)))
        return (
            float(unwrapped.min()),
            float(unwrapped.max()),
            float(latitude.min()),
            float(latitude.max()),
        )

    def spacings(self, width: int, height: int) -> tuple[float, float]:
        """The intervals to use, chosen from the image unless set by hand."""
        config = self._config
        sexagesimal = config.sky_format == "sexagesimal"

        if not config.auto_spacing and config.x_spacing and config.y_spacing:
            return (float(config.x_spacing), float(config.y_spacing))

        bounds = self.sky_bounds(width, height)
        if bounds is None:
            return (1.0, 1.0)
        lon0, lon1, lat0, lat1 = bounds

        # A longitude interval covers less sky the further from the equator
        # it is, so a field at high declination needs a wider one to look
        # evenly spaced. cos(dec) is that correction.
        middle = math.radians((lat0 + lat1) / 2.0)
        squeeze = max(math.cos(middle), 1e-6)
        return (
            nice_spacing((lon1 - lon0) * squeeze, config.target_lines, sexagesimal) / squeeze,
            nice_spacing(lat1 - lat0, config.target_lines, sexagesimal),
        )

    # -- the grid ---------------------------------------------------------------

    def compute(self, width: int, height: int) -> GridGeometry:
        """Work out the whole grid for an image of this size.

        Returns:
            The geometry. Empty when there is no usable WCS, which the
            caller shows as "no grid" rather than as a wrong one.
        """
        geometry = GridGeometry(border=_border(width, height))
        bounds = self.sky_bounds(width, height)
        if bounds is None:
            return geometry

        lon0, lon1, lat0, lat1 = bounds
        longitude_step, latitude_step = self.spacings(width, height)
        geometry.longitude_spacing = longitude_step
        geometry.latitude_spacing = latitude_step

        # Latitudes are clamped: a grid line at 95 degrees is not a place.
        low_latitude = max(-90.0, lat0)
        high_latitude = min(90.0, lat1)

        for longitude in _steps(lon0, lon1, longitude_step):
            latitudes = np.linspace(low_latitude, high_latitude, SAMPLES_PER_LINE)
            points = self._project(np.full_like(latitudes, longitude), latitudes, width, height)
            geometry.longitude_lines.extend(points)

        for latitude in _steps(low_latitude, high_latitude, latitude_step):
            longitudes = np.linspace(lon0, lon1, SAMPLES_PER_LINE)
            points = self._project(longitudes, np.full_like(longitudes, latitude), width, height)
            geometry.latitude_lines.extend(points)

        geometry.labels, geometry.ticks = self._edges(
            width, height, lon0, lon1, low_latitude, high_latitude, longitude_step, latitude_step
        )
        geometry.x_title = self._config.x_title or self._axis_title(latitude=False)
        geometry.y_title = self._config.y_title or self._axis_title(latitude=True)
        return geometry

    def _project(
        self,
        longitude: NDArray[np.floating],
        latitude: NDArray[np.floating],
        width: int,
        height: int,
    ) -> list[list[tuple[float, float]]]:
        """Turn one sky curve into the pieces of it that are on the image."""
        try:
            x, y = self._wcs.world_to_pixel(longitude, latitude)
        except Exception:
            return []

        x = np.atleast_1d(np.asarray(x, dtype=float))
        y = np.atleast_1d(np.asarray(y, dtype=float))
        return _split(x, y, width, height)

    def _edges(
        self,
        width: int,
        height: int,
        lon0: float,
        lon1: float,
        lat0: float,
        lat1: float,
        longitude_step: float,
        latitude_step: float,
    ) -> tuple[list[Label], list[tuple[float, float, float, float]]]:
        """Where each grid line meets the border, and what to write there.

        The label goes where the line actually crosses the edge, not at a
        position computed from the value: on a rotated or skewed WCS those
        are different places, and a number that does not sit on its own
        line is worse than no number.
        """
        labels: list[Label] = []
        ticks: list[tuple[float, float, float, float]] = []

        longitude_format = default_format(
            self._config.x_format, latitude=False, sky_format=self._config.sky_format
        )
        latitude_format = default_format(
            self._config.y_format, latitude=True, sky_format=self._config.sky_format
        )

        for longitude in _steps(lon0, lon1, longitude_step):
            latitudes = np.linspace(lat0, lat1, SAMPLES_PER_LINE)
            crossing = self._crossing(np.full_like(latitudes, longitude), latitudes, width, height)
            if crossing is None:
                continue
            x, y, position = crossing
            labels.append(Label(format_coordinate(longitude % 360.0, longitude_format), x, y, position))
            ticks.append((x, y, *_tick_direction(position)))

        for latitude in _steps(lat0, lat1, latitude_step):
            longitudes = np.linspace(lon0, lon1, SAMPLES_PER_LINE)
            crossing = self._crossing(
                longitudes, np.full_like(longitudes, latitude), width, height, prefer_side=True
            )
            if crossing is None:
                continue
            x, y, position = crossing
            labels.append(Label(format_coordinate(latitude, latitude_format), x, y, position))
            ticks.append((x, y, *_tick_direction(position)))

        return (labels, ticks)

    def _crossing(
        self,
        longitude: NDArray[np.floating],
        latitude: NDArray[np.floating],
        width: int,
        height: int,
        prefer_side: bool = False,
    ) -> tuple[float, float, LabelPosition] | None:
        """Where one sky curve first meets the image's edge.

        Args:
            prefer_side: Label on the left or right edge when the curve
                touches both a side and the bottom -- which is what a line
                of latitude wants, and a line of longitude does not.
        """
        try:
            x, y = self._wcs.world_to_pixel(longitude, latitude)
        except Exception:
            return None

        x = np.atleast_1d(np.asarray(x, dtype=float))
        y = np.atleast_1d(np.asarray(y, dtype=float))
        inside = _inside(x, y, width, height)
        if not inside.any():
            return None

        indices = np.nonzero(inside)[0]
        candidates = [indices[0], indices[-1]]
        best: tuple[float, float, LabelPosition] | None = None
        best_score = -1.0

        for index in candidates:
            px, py = float(x[index]), float(y[index])
            position = _nearest_edge(px, py, width, height)
            score = 1.0 if (position in (LabelPosition.LEFT, LabelPosition.RIGHT)) == prefer_side else 0.0
            if score > best_score:
                best_score = score
                best = (px, py, position)
        return best

    def _axis_title(self, latitude: bool) -> str:
        """The title an axis gets when the user has not set one."""
        if self._config.system != "wcs":
            return "Y" if latitude else "X"
        names = {
            "galactic": ("Galactic Longitude", "Galactic Latitude"),
            "ecliptic": ("Ecliptic Longitude", "Ecliptic Latitude"),
        }
        pair = names.get(self._config.sky, ("Right Ascension", "Declination"))
        return pair[1] if latitude else pair[0]


# -- geometry helpers ----------------------------------------------------------


def _edge_points(width: int, height: int) -> tuple[NDArray[np.floating], NDArray[np.floating]]:
    """Points around the image's edge, plus its middle.

    The corners alone miss the extreme longitude of a projection that bulges
    along an edge, and the middle catches a pole inside the field.
    """
    steps = np.linspace(1.0, float(max(width, height)), EDGE_SAMPLES)
    columns = np.clip(steps, 1.0, float(width))
    rows = np.clip(steps, 1.0, float(height))
    ones_x = np.ones_like(rows)
    ones_y = np.ones_like(columns)

    x = np.concatenate([columns, columns, ones_x, ones_x * width, [width / 2.0]])
    y = np.concatenate([ones_y, ones_y * height, rows, rows, [height / 2.0]])
    return (x, y)


def _border(width: int, height: int) -> list[tuple[float, float]]:
    """The image's outline, as a closed polyline in image pixels."""
    return [
        (0.5, 0.5),
        (width + 0.5, 0.5),
        (width + 0.5, height + 0.5),
        (0.5, height + 0.5),
        (0.5, 0.5),
    ]


def _steps(low: float, high: float, step: float) -> list[float]:
    """Every multiple of `step` from `low` to `high`, inclusive.

    Anchored on multiples of the step rather than on `low`, so the lines
    fall on round values -- which is the point of choosing a round step.
    """
    if step <= 0 or not math.isfinite(low) or not math.isfinite(high) or high < low:
        return []
    first = math.ceil(low / step) * step
    count = int((high - first) / step) + 1
    if count <= 0:
        return []
    # A pathological step and range could ask for millions of lines.
    count = min(count, 512)
    return [first + index * step for index in range(count)]


def _inside(x: NDArray[np.floating], y: NDArray[np.floating], width: int, height: int) -> NDArray[np.bool_]:
    """Which sampled points fall on the image."""
    return (
        np.isfinite(x) & np.isfinite(y) & (x >= 0.5) & (x <= width + 0.5) & (y >= 0.5) & (y <= height + 0.5)
    )


def _split(
    x: NDArray[np.floating], y: NDArray[np.floating], width: int, height: int
) -> list[list[tuple[float, float]]]:
    """Break a sampled curve into the runs of it that are on the image.

    A curve that leaves the frame and comes back must not be joined across
    the gap, or a line of declination near a pole draws a chord straight
    through the picture.
    """
    inside = _inside(x, y, width, height)
    pieces: list[list[tuple[float, float]]] = []
    current: list[tuple[float, float]] = []

    for index, keep in enumerate(inside):
        if not keep:
            if len(current) > 1:
                pieces.append(current)
            current = []
            continue
        point = (float(x[index]), float(y[index]))
        if current and math.dist(current[-1], point) > BREAK_DISTANCE:
            if len(current) > 1:
                pieces.append(current)
            current = []
        current.append(point)

    if len(current) > 1:
        pieces.append(current)
    return pieces


def _nearest_edge(x: float, y: float, width: int, height: int) -> LabelPosition:
    """Which edge a point is closest to."""
    distances = {
        LabelPosition.LEFT: x - 0.5,
        LabelPosition.RIGHT: width + 0.5 - x,
        LabelPosition.BOTTOM: y - 0.5,
        LabelPosition.TOP: height + 0.5 - y,
    }
    return min(distances, key=lambda edge: distances[edge])


def _tick_direction(position: LabelPosition) -> tuple[float, float]:
    """Which way a tick on one edge points, in image pixels."""
    return {
        LabelPosition.LEFT: (TICK_LENGTH, 0.0),
        LabelPosition.RIGHT: (-TICK_LENGTH, 0.0),
        LabelPosition.BOTTOM: (0.0, TICK_LENGTH),
        LabelPosition.TOP: (0.0, -TICK_LENGTH),
    }[position]
