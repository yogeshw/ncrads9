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

"""DS9's crop: the section of the data a frame displays.

A crop is not a zoom. DS9 keeps the pixel grid and its coordinates exactly
as they were and stops displaying what falls outside the crop
(`tksao/frame/basecommand.C:cropCmd`), which is why the scale limits then
come from the cropped section alone -- `FrScale::CROPSEC` -- and why a
cropped frame still reads out the same coordinates under the cursor.

Author: Yogesh Wadadekar
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from numpy.typing import NDArray

#: A crop thinner than this in either direction is not worth having; the
#: pointer's crop drag treats a smaller box as a stray click.
MINIMUM_SIZE = 2.0


@dataclass(frozen=True)
class CropRegion:
    """A rectangle of image pixels, in FITS coordinates counting from one.

    The bounds are inclusive of the pixel centres they name, which is what
    makes a one-pixel crop `x0 == x1` rather than empty.
    """

    x0: float
    y0: float
    x1: float
    y1: float

    def __post_init__(self) -> None:
        """Put the corners in order, so any two opposite ones will do."""
        left, right = sorted((float(self.x0), float(self.x1)))
        bottom, top = sorted((float(self.y0), float(self.y1)))
        object.__setattr__(self, "x0", left)
        object.__setattr__(self, "x1", right)
        object.__setattr__(self, "y0", bottom)
        object.__setattr__(self, "y1", top)

    # -- what it is ------------------------------------------------------------

    @property
    def width(self) -> float:
        """Its width in pixels."""
        return self.x1 - self.x0

    @property
    def height(self) -> float:
        """Its height in pixels."""
        return self.y1 - self.y0

    @property
    def center(self) -> tuple[float, float]:
        """Its centre, which is what DS9's dialog shows."""
        return ((self.x0 + self.x1) / 2.0, (self.y0 + self.y1) / 2.0)

    @property
    def corners(self) -> tuple[tuple[float, float], tuple[float, float]]:
        """Its lower-left and upper-right corners."""
        return ((self.x0, self.y0), (self.x1, self.y1))

    def is_usable(self) -> bool:
        """Whether the rectangle is big enough to be worth cropping to."""
        return self.width >= MINIMUM_SIZE and self.height >= MINIMUM_SIZE

    # -- making one ------------------------------------------------------------

    @classmethod
    def from_center(cls, x: float, y: float, width: float, height: float) -> CropRegion:
        """The crop DS9's dialog describes: a centre and a size."""
        half_w = abs(float(width)) / 2.0
        half_h = abs(float(height)) / 2.0
        return cls(x - half_w, y - half_h, x + half_w, y + half_h)

    @classmethod
    def whole(cls, shape: tuple[int, ...]) -> CropRegion:
        """The crop that hides nothing, which is what Reset returns to."""
        return cls(1.0, 1.0, float(shape[1]), float(shape[0]))

    def clipped_to(self, shape: tuple[int, ...]) -> CropRegion:
        """This crop with nothing outside the image, so it stays meaningful."""
        return CropRegion(
            max(1.0, self.x0),
            max(1.0, self.y0),
            min(float(shape[1]), self.x1),
            min(float(shape[0]), self.y1),
        )

    def covers(self, shape: tuple[int, ...]) -> bool:
        """Whether this crop takes in the whole image, hiding nothing."""
        return self.x0 <= 1.0 and self.y0 <= 1.0 and self.x1 >= float(shape[1]) and self.y1 >= float(shape[0])

    # -- using one ------------------------------------------------------------

    def slices(self, shape: tuple[int, ...]) -> tuple[slice, slice]:
        """Numpy slices for the rows and columns inside the crop.

        A bound names the pixel it falls in -- pixel `i` counting from zero
        covers `[i + 0.5, i + 1.5)` in FITS coordinates -- so a crop drawn
        across part of a pixel keeps that pixel rather than dropping it.
        """
        column0 = max(0, int(np.floor(self.x0 - 0.5)))
        column1 = min(int(shape[1]), int(np.floor(self.x1 - 0.5)) + 1)
        row0 = max(0, int(np.floor(self.y0 - 0.5)))
        row1 = min(int(shape[0]), int(np.floor(self.y1 - 0.5)) + 1)
        return (slice(row0, max(row0, row1)), slice(column0, max(column0, column1)))

    def contains(self, x: float, y: float) -> bool:
        """Whether an image position is inside the crop."""
        return self.x0 <= x <= self.x1 and self.y0 <= y <= self.y1


def blank_outside(
    data: NDArray[np.floating],
    crop: CropRegion | None,
) -> NDArray[np.floating]:
    """The data with everything outside the crop turned blank.

    Blank rather than removed: DS9's crop leaves the pixel grid and its
    coordinates alone, so the array keeps its shape and the hidden pixels
    become NaN. They then fall out of the scale limits by themselves, which
    is DS9's CROPSEC, and the renderer paints them in the blank colour.

    Args:
        data: The image on its way to the screen.
        crop: The crop, or None to leave the data alone.

    Returns:
        The same array when there is nothing to hide, and a copy otherwise.
    """
    if crop is None or data.ndim < 2 or data.size == 0:
        return data
    if crop.covers(data.shape):
        return data

    rows, columns = crop.slices(data.shape)
    hidden = np.full(data.shape, np.nan, dtype=np.result_type(data.dtype, np.float32))
    hidden[rows, columns] = data[rows, columns]
    return hidden


def section(data: NDArray[np.floating], crop: CropRegion | None) -> NDArray[np.floating]:
    """Just the pixels inside the crop, for a measurement that wants them."""
    if crop is None or data.ndim < 2 or data.size == 0:
        return data
    rows, columns = crop.slices(data.shape)
    return data[rows, columns]
