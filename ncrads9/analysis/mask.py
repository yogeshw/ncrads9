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
Mask files: a second image laid over the first in a flat colour.

DS9's Mask menu loads a FITS file, decides which of its pixels count -- the
zero ones, the non-zero ones, the NaNs, the non-NaNs, or a range -- and
paints those over the displayed image in one colour, blended one of four
ways (`ds9/library/mask.tcl:116`).

The point is that the mask is a *file*, not a threshold on the data being
displayed: a bad-pixel map, a segmentation image, an exposure map. What
existed before was a threshold on the displayed data, which cannot show any
of those.

The blend modes are the usual four, and they are worth naming because their
effect on a greyscale image is not obvious: Source replaces, Screen
lightens towards white, Darken keeps whichever is darker, Lighten keeps
whichever is lighter.

Author: Yogesh Wadadekar

"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from pathlib import Path

import numpy as np
from numpy.typing import NDArray


class MaskError(ValueError):
    """A mask that cannot be used, for the reason given."""


class MaskMode(Enum):
    """Which of a mask file's pixels count, as DS9's menu offers them."""

    ZERO = "zero"
    NON_ZERO = "nonzero"
    NAN = "nan"
    NON_NAN = "nonnan"
    RANGE = "range"


class BlendMode(Enum):
    """How the mask's colour is combined with the image beneath it."""

    SOURCE = "source"
    SCREEN = "screen"
    DARKEN = "darken"
    LIGHTEN = "lighten"


#: The colours DS9's Mask colour cascade offers.
MASK_COLORS: tuple[str, ...] = (
    "black",
    "white",
    "red",
    "green",
    "blue",
    "cyan",
    "magenta",
    "yellow",
)

#: What a new mask takes.
DEFAULT_COLOR = "red"
DEFAULT_TRANSPARENCY = 50.0


@dataclass
class MaskSettings:
    """One mask layer.

    Attributes:
        mode: Which pixels of the mask file count.
        low, high: The range, for `MaskMode.RANGE`.
        color: The colour to paint them.
        transparency: 0 for opaque, 100 for invisible -- DS9's scale.
        blend: How the colour is combined with the image.
    """

    mode: MaskMode = MaskMode.NON_ZERO
    low: float = 0.0
    high: float = 1.0
    color: str = DEFAULT_COLOR
    transparency: float = DEFAULT_TRANSPARENCY
    blend: BlendMode = BlendMode.SOURCE

    @property
    def alpha(self) -> float:
        """How strongly the mask shows, from 0 to 1."""
        return max(0.0, min(1.0, 1.0 - float(self.transparency) / 100.0))


def load(path: str | Path, extension: int | str | None = None) -> NDArray[np.floating]:
    """Read a mask image out of a FITS file.

    Args:
        path: The file.
        extension: Which HDU to take. By default the first one holding a
            two-dimensional image, which is what DS9 does and what makes a
            file whose primary HDU is empty still work.

    Returns:
        The mask image.

    Raises:
        MaskError: If the file holds no two-dimensional image.
        OSError: If it cannot be read.
    """
    from astropy.io import fits

    with fits.open(path) as opened:
        if extension is not None:
            data = opened[extension].data
            if data is None or np.ndim(data) != 2:
                raise MaskError(f"extension {extension} of {Path(path).name} is not an image")
            return np.asarray(data, dtype=np.float64)

        for hdu in opened:
            data = getattr(hdu, "data", None)
            if data is not None and np.ndim(data) == 2:
                return np.asarray(data, dtype=np.float64)

    raise MaskError(f"{Path(path).name} holds no two-dimensional image")


def selected(mask: NDArray[np.floating], settings: MaskSettings) -> NDArray[np.bool_]:
    """Which pixels of a mask image count, per the settings.

    Args:
        mask: The mask image.
        settings: Which pixels to take.

    Returns:
        A boolean array of the mask's shape.
    """
    values = np.asarray(mask, dtype=np.float64)
    finite = np.isfinite(values)

    if settings.mode is MaskMode.ZERO:
        return finite & (values == 0.0)
    if settings.mode is MaskMode.NON_ZERO:
        return finite & (values != 0.0)
    if settings.mode is MaskMode.NAN:
        return ~finite
    if settings.mode is MaskMode.NON_NAN:
        return finite

    low, high = sorted((float(settings.low), float(settings.high)))
    return finite & (values >= low) & (values <= high)


def align(mask: NDArray[np.floating], shape: tuple[int, int]) -> NDArray[np.floating]:
    """Fit a mask to an image's shape by cropping or padding.

    A mask a few rows short of the image it belongs to is common enough --
    a trimmed exposure map, a segmentation image from a slightly different
    cutout -- that refusing it is less useful than lining up what does
    overlap. The uncovered part is left as NaN, which no mode selects
    except NAN.

    Args:
        mask: The mask image.
        shape: The image's (height, width).

    Returns:
        A mask of exactly that shape.
    """
    height, width = shape
    if mask.shape == (height, width):
        return mask

    fitted = np.full((height, width), np.nan, dtype=np.float64)
    rows = min(height, mask.shape[0])
    columns = min(width, mask.shape[1])
    fitted[:rows, :columns] = mask[:rows, :columns]
    return fitted


def blend(
    image: NDArray[np.floating],
    mask: NDArray[np.bool_],
    color: tuple[float, float, float],
    alpha: float,
    mode: BlendMode = BlendMode.SOURCE,
) -> NDArray[np.floating]:
    """Paint a mask's colour over an RGB image.

    Args:
        image: The displayed image as (height, width, 3), values 0 to 1.
        mask: Which pixels to paint.
        color: The colour, as (r, g, b) in 0 to 1.
        alpha: How strongly, from 0 to 1.
        mode: How the colour combines with what is there.

    Returns:
        A new image. The input is left alone -- it is the displayed frame,
        and masking must not be destructive.
    """
    painted = np.array(image, dtype=np.float64, copy=True)
    if not mask.any() or alpha <= 0.0:
        return painted

    tint = np.asarray(color, dtype=np.float64).reshape(1, 3)
    beneath = painted[mask]

    if mode is BlendMode.SCREEN:
        combined = 1.0 - (1.0 - beneath) * (1.0 - tint)
    elif mode is BlendMode.DARKEN:
        combined = np.minimum(beneath, tint)
    elif mode is BlendMode.LIGHTEN:
        combined = np.maximum(beneath, tint)
    else:
        combined = np.broadcast_to(tint, beneath.shape)

    painted[mask] = beneath * (1.0 - alpha) + combined * alpha
    return np.clip(painted, 0.0, 1.0)


def rgb(name: str) -> tuple[float, float, float]:
    """One of DS9's colour names as RGB in 0 to 1."""
    table = {
        "black": (0.0, 0.0, 0.0),
        "white": (1.0, 1.0, 1.0),
        "red": (1.0, 0.0, 0.0),
        "green": (0.0, 1.0, 0.0),
        "blue": (0.0, 0.0, 1.0),
        "cyan": (0.0, 1.0, 1.0),
        "magenta": (1.0, 0.0, 1.0),
        "yellow": (1.0, 1.0, 0.0),
    }
    return table.get(str(name).strip().lower(), table["red"])
