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
What goes into DS9's horizontal and vertical cut graphs.

DS9's `graph` access point sets five things (`ds9/doc/ref/xpa.html`): a
grid, a log vertical axis, whether a thick cut is summed or averaged, how
thick it is, and how big the panel is. The first two are drawing and the
last is layout; the middle two are arithmetic, and this is the
arithmetic, apart from Qt so it can be tested directly.

Before this the two panels each read a single row or column and drew it
with no settings at all, which is why `xpaset ds9 graph thickness 10` had
nothing to set.

Author: Yogesh Wadadekar
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

import numpy as np
from numpy.typing import NDArray

#: What a thick cut does with the rows it covers. DS9's `graph method`.
Method = Literal["average", "sum"]

#: DS9's default panel size, in pixels, and the range its dialog allows.
DEFAULT_SIZE = 150
MINIMUM_SIZE = 20
MAXIMUM_SIZE = 1000

#: The thickest cut DS9 offers. One is a single row or column.
MAXIMUM_THICKNESS = 100


@dataclass
class GraphSettings:
    """DS9's Graph menu and its `graph` access point, as one object.

    Attributes:
        grid: Whether grid lines are drawn behind the curve.
        log: Whether the value axis is logarithmic.
        method: Whether a thick cut is averaged or summed.
        thickness: How many rows or columns the cut covers.
        size: How tall the horizontal panel is, and how wide the vertical
            one -- the across-the-cut dimension in both cases.
    """

    grid: bool = False
    log: bool = False
    method: Method = "average"
    thickness: int = 1
    size: int = DEFAULT_SIZE

    def with_thickness(self, thickness: int) -> GraphSettings:
        """A copy at a different thickness, clamped to what is allowed."""
        self.thickness = max(1, min(MAXIMUM_THICKNESS, int(thickness)))
        return self

    def with_size(self, size: int) -> GraphSettings:
        """A copy at a different panel size, clamped to what is allowed."""
        self.size = max(MINIMUM_SIZE, min(MAXIMUM_SIZE, int(size)))
        return self


def cut(
    image: NDArray[np.floating],
    axis: str,
    index: int,
    settings: GraphSettings | None = None,
) -> NDArray[np.float64] | None:
    """The values along one cut through an image.

    Args:
        image: The image, indexed `[row, column]`.
        axis: `horizontal` for a cut along a row, `vertical` along a
            column.
        index: Which row or column the cut is centred on, counting from
            zero.
        settings: The thickness and the method. Defaults to one row,
            which is what a graph with no settings drew.

    Returns:
        The values, or None if the index is off the image. A cut thicker
        than one is reduced across its width by the method, ignoring
        blanks so a NaN does not wipe out the whole band.
    """
    if image is None or image.ndim < 2:
        return None
    settings = settings or GraphSettings()
    height, width = image.shape[:2]
    extent = height if axis == "horizontal" else width
    if not 0 <= index < extent:
        return None

    half = (settings.thickness - 1) // 2
    low = max(0, index - half)
    high = min(extent, low + settings.thickness)
    low = max(0, high - settings.thickness)

    band = image[low:high, :] if axis == "horizontal" else image[:, low:high]
    values = np.asarray(band, dtype=np.float64)
    if values.shape[0 if axis == "horizontal" else 1] == 1:
        return values.reshape(-1)

    across = 0 if axis == "horizontal" else 1
    # A band of all-blank pixels averages to NaN rather than to zero, and
    # numpy warns about it; the warning is not news, so it is silenced and
    # the NaN kept -- a gap in the curve is the honest drawing.
    with np.errstate(invalid="ignore"):
        import warnings

        with warnings.catch_warnings():
            warnings.simplefilter("ignore", RuntimeWarning)
            if settings.method == "sum":
                return np.asarray(np.nansum(values, axis=across), dtype=np.float64)
            reduced = np.nanmean(values, axis=across)
    return np.asarray(reduced, dtype=np.float64)


def limits(values: NDArray[np.floating], log: bool = False) -> tuple[float, float]:
    """The value range a cut is drawn against.

    Args:
        values: The cut.
        log: Whether the axis is logarithmic, in which case the range is
            of the logarithms and only positive values count.

    Returns:
        A (low, high) pair, never equal: a flat cut still needs a range
        to be divided by.
    """
    finite = np.asarray(values, dtype=np.float64)
    finite = finite[np.isfinite(finite)]
    if log:
        finite = finite[finite > 0.0]
        finite = np.log10(finite) if finite.size else finite
    if finite.size == 0:
        return (0.0, 1.0)
    low, high = float(np.min(finite)), float(np.max(finite))
    return (low, high) if high > low else (low, low + 1.0)


def scaled(values: NDArray[np.floating], log: bool = False) -> NDArray[np.float64]:
    """A cut mapped to 0..1 against its own range, for drawing.

    A value the axis cannot show -- a blank, or a non-positive value on a
    log axis -- comes back NaN, which the painter draws as a gap.
    """
    low, high = limits(values, log)
    numbers = np.asarray(values, dtype=np.float64)
    if log:
        with np.errstate(divide="ignore", invalid="ignore"):
            numbers = np.where(numbers > 0.0, np.log10(np.where(numbers > 0.0, numbers, 1.0)), np.nan)
    return (numbers - low) / (high - low)
