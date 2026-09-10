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
DS9's 3D frame: a data cube seen from an angle, by ray tracing.

"For each pixel on the screen, a ray is projected back into the view
volume, based on the current viewing parameters, returning a data value if
the ray intersects the FITS data cube" (`ds9/doc/ref/3d.html`). Two
reductions along the ray: MIP takes the largest value it met, AIP the
average of them. Then the ordinary scale, clip and colormap follow, which
is why this returns data rather than a picture.

The rotation is DS9's own composition, azimuth about the screen's vertical
axis and elevation about its horizontal one (`RotateY3d(az) *
RotateX3d(el)`, `frame3dbase.C:394`).

DS9 spreads its ray trace over POSIX threads because it walks the rays one
at a time. Ours walks every ray's Nth sample at once, in numpy, so the work
is already in one C loop per step and threads would only add copies. That
is the one deliberate difference in the engine, and it is why there is no
thread count to set.

Author: Yogesh Wadadekar
"""

from __future__ import annotations

import math
from dataclasses import dataclass

import numpy as np
from numpy.typing import NDArray

#: The two reductions along a ray (`3d.tcl:19`).
METHODS: tuple[str, ...] = ("mip", "aip")

#: What the background behind the cube is shaded by (`3d.tcl:20`).
BACKGROUNDS: tuple[str, ...] = ("none", "azimuth", "elevation")

#: How far apart the samples along a ray are, in data pixels. One means a
#: sample per pixel of depth, which is what makes the trace exact for an
#: unrotated cube.
SAMPLE_STEP = 1.0

#: How many samples are taken at once. A cube seen corner-on needs three
#: times its depth in samples, and doing them all at once would need an
#: array that size; this is the chunk the accumulation is done in.
CHUNK = 32

#: The largest output either way, so a badly scaled z axis cannot ask for
#: an image nothing can hold.
MAX_EXTENT = 4096


@dataclass(frozen=True)
class View3D:
    """Where the cube is seen from.

    Attributes:
        azimuth: Degrees about the screen's vertical axis, -180 to 180.
        elevation: Degrees about its horizontal axis, -90 to 90.
        scale: How much to stretch the cube's third axis. A cube of 20
            slices and 500 pixels a side is a sheet until this is raised.
    """

    azimuth: float = 0.0
    elevation: float = 0.0
    scale: float = 1.0

    @property
    def matrix(self) -> NDArray[np.float64]:
        """The rotation taking data axes to screen axes.

        DS9's composition: azimuth first, about y, then elevation, about x.
        """
        az = math.radians(self.azimuth)
        el = math.radians(self.elevation)
        about_y = np.array(
            [
                [math.cos(az), 0.0, math.sin(az)],
                [0.0, 1.0, 0.0],
                [-math.sin(az), 0.0, math.cos(az)],
            ]
        )
        about_x = np.array(
            [
                [1.0, 0.0, 0.0],
                [0.0, math.cos(el), -math.sin(el)],
                [0.0, math.sin(el), math.cos(el)],
            ]
        )
        return about_y @ about_x

    def is_face_on(self) -> bool:
        """Whether the cube is being seen straight down its third axis.

        Which is the case a slice view already covers, and where the ray
        trace has nothing to add.
        """
        return abs(self.azimuth) < 1e-9 and abs(self.elevation) < 1e-9


def corners(shape: tuple[int, ...], view: View3D) -> NDArray[np.float64]:
    """The cube's eight corners in screen coordinates.

    Args:
        shape: The cube's shape, (depth, height, width).
        view: Where it is seen from.

    Returns:
        (8, 3) of screen coordinates about the cube's centre, x and y
        across the screen and z into it.
    """
    depth, height, width = shape[0], shape[1], shape[2]
    half = np.array([width / 2.0, height / 2.0, depth * view.scale / 2.0])
    signs = np.array([[sx, sy, sz] for sx in (-1.0, 1.0) for sy in (-1.0, 1.0) for sz in (-1.0, 1.0)])
    return (signs * half) @ view.matrix.T


def extent(shape: tuple[int, ...], view: View3D) -> tuple[int, int]:
    """How large the rendered image has to be to hold the whole cube.

    Args:
        shape: The cube's shape.
        view: Where it is seen from.

    Returns:
        (height, width) in pixels.
    """
    projected = corners(shape, view)
    width = int(math.ceil(projected[:, 0].max() - projected[:, 0].min()))
    height = int(math.ceil(projected[:, 1].max() - projected[:, 1].min()))
    return (
        max(1, min(MAX_EXTENT, height)),
        max(1, min(MAX_EXTENT, width)),
    )


def render(
    cube: NDArray[np.floating],
    view: View3D | None = None,
    method: str = "mip",
) -> NDArray[np.float32]:
    """Ray-trace a cube into one image.

    Args:
        cube: The data, (depth, height, width).
        view: Where to see it from. Face-on by default.
        method: `mip` for the largest value along each ray, `aip` for the
            average of the values along it.

    Returns:
        The rendered image, with NaN where a ray missed the cube entirely.
        Data, not a picture: the scale, the clip and the colormap come
        after, exactly as they do for a slice.

    Raises:
        ValueError: If the data is not a cube, or the method is not one of
            DS9's two.
    """
    data = np.asarray(cube, dtype=np.float32)
    if data.ndim != 3:
        raise ValueError("a 3D frame needs a data cube")
    if method not in METHODS:
        raise ValueError(f"{method} is not a rendering method DS9 has")

    chosen = view or View3D()
    depth, height, width = data.shape

    # Face-on with no z stretch is the slice view: every ray runs straight
    # down the third axis, so the reduction is the whole cube's.
    if chosen.is_face_on():
        if method == "mip":
            return np.nanmax(data, axis=0).astype(np.float32)
        return np.nanmean(data, axis=0).astype(np.float32)

    out_height, out_width = extent(data.shape, chosen)
    rotation = chosen.matrix

    # Screen coordinates about the centre.
    ys, xs = np.mgrid[0:out_height, 0:out_width]
    screen_x = xs - (out_width - 1) / 2.0
    screen_y = ys - (out_height - 1) / 2.0

    # How far along the ray to go: the cube's longest diagonal, which is as
    # far as any ray can stay inside it.
    reach = math.sqrt(width**2 + height**2 + (depth * chosen.scale) ** 2) / 2.0
    steps = max(1, int(math.ceil(2 * reach / SAMPLE_STEP)))
    offsets = np.linspace(-reach, reach, steps, dtype=np.float32)

    centre = np.array([(width - 1) / 2.0, (height - 1) / 2.0, (depth - 1) / 2.0])
    # A screen direction back into the data: the rotation's transpose.
    inverse = rotation.T

    largest = np.full((out_height, out_width), -np.inf, dtype=np.float32)
    total = np.zeros((out_height, out_width), dtype=np.float64)
    hits = np.zeros((out_height, out_width), dtype=np.int32)

    for start in range(0, steps, CHUNK):
        chunk = offsets[start : start + CHUNK]
        # (chunk, out_height, out_width) data coordinates.
        sx = screen_x[None, :, :]
        sy = screen_y[None, :, :]
        sz = chunk[:, None, None]

        data_x = inverse[0, 0] * sx + inverse[0, 1] * sy + inverse[0, 2] * sz + centre[0]
        data_y = inverse[1, 0] * sx + inverse[1, 1] * sy + inverse[1, 2] * sz + centre[1]
        # The third axis is stretched on the way out, so it is compressed
        # on the way back in.
        data_z = (inverse[2, 0] * sx + inverse[2, 1] * sy + inverse[2, 2] * sz) / max(
            chosen.scale, 1e-6
        ) + centre[2]

        column = np.rint(data_x).astype(np.int32)
        row = np.rint(data_y).astype(np.int32)
        plane = np.rint(data_z).astype(np.int32)

        inside = (
            (column >= 0) & (column < width) & (row >= 0) & (row < height) & (plane >= 0) & (plane < depth)
        )
        if not inside.any():
            continue

        sampled = data[
            np.clip(plane, 0, depth - 1),
            np.clip(row, 0, height - 1),
            np.clip(column, 0, width - 1),
        ]
        # A blank pixel is not a value, in the cube or out of it.
        valid = inside & np.isfinite(sampled)
        values = np.where(valid, sampled, 0.0)

        if method == "mip":
            largest = np.maximum(largest, np.where(valid, sampled, -np.inf).max(axis=0))
        else:
            total += values.sum(axis=0)
        hits += valid.sum(axis=0, dtype=np.int32)

    missed = hits == 0
    if method == "mip":
        image = largest
    else:
        image = np.divide(total, np.maximum(hits, 1), out=np.zeros_like(total), where=~missed).astype(
            np.float32
        )
    image = np.asarray(image, dtype=np.float32)
    image[missed] = np.nan
    return image


def background(shape: tuple[int, int], view: View3D, kind: str = "none") -> NDArray[np.float32] | None:
    """The gradient DS9 shades the space around the cube with.

    Args:
        shape: The rendered image's (height, width).
        view: Where the cube is seen from.
        kind: `none`, `azimuth` or `elevation`.

    Returns:
        A (height, width) array from 0 to 1, or None for `none`.

    Raises:
        ValueError: If the kind is not one of DS9's three.
    """
    if kind not in BACKGROUNDS:
        raise ValueError(f"{kind} is not a 3D background DS9 has")
    if kind == "none":
        return None

    height, width = shape
    if kind == "azimuth":
        ramp = np.linspace(0.0, 1.0, max(1, width), dtype=np.float32)[None, :]
        gradient = np.repeat(ramp, height, axis=0)
    else:
        ramp = np.linspace(0.0, 1.0, max(1, height), dtype=np.float32)[:, None]
        gradient = np.repeat(ramp, width, axis=1)

    # Turned with the view, so the shading says which way round the cube is
    # rather than sitting still behind it.
    turn = view.azimuth if kind == "azimuth" else view.elevation
    return np.clip(gradient * math.cos(math.radians(turn)) + 0.5, 0.0, 1.0)


def edges() -> tuple[tuple[int, int], ...]:
    """Which of the eight corners the cube's twelve edges join.

    The corner order is `corners`': x slowest, then y, then z.
    """
    return (
        (0, 1),
        (1, 3),
        (3, 2),
        (2, 0),
        (4, 5),
        (5, 7),
        (7, 6),
        (6, 4),
        (0, 4),
        (1, 5),
        (2, 6),
        (3, 7),
    )


def slice_outline(
    shape: tuple[int, ...],
    view: View3D,
    index: int,
) -> NDArray[np.float64]:
    """The four corners of one slice, in screen coordinates.

    DS9 highlights the current slice, because that is the one the regions,
    the crosshair and the contours are on.

    Args:
        shape: The cube's shape.
        view: Where it is seen from.
        index: Which slice, counting from zero.

    Returns:
        (4, 3) of screen coordinates about the cube's centre.
    """
    depth, height, width = shape[0], shape[1], shape[2]
    wanted = max(0, min(int(index), depth - 1))
    # The slice's own z, measured from the cube's centre and stretched.
    z = (wanted - (depth - 1) / 2.0) * view.scale
    half_w, half_h = width / 2.0, height / 2.0
    box = np.array(
        [
            [-half_w, -half_h, z],
            [half_w, -half_h, z],
            [half_w, half_h, z],
            [-half_w, half_h, z],
        ]
    )
    return box @ view.matrix.T
