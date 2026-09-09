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
DS9's Block: reduce an image for display without changing it.

Block averages every `factor` by `factor` square of pixels into one, purely
so that a large image can be drawn quickly and seen whole. DS9 treats it as a
display transform -- the data behind it is untouched, coordinates stay in the
original pixels, and turning Block off restores the full-resolution view
exactly.

NCRADS9 conflated this with binning until M5 and applied it destructively,
overwriting `frame.image_data`. PLAN.md §3.4 records what that cost: a region
drawn at pixel 100 read back at pixel 25 under a block of four, the WCS was
never rescaled to match, and `Save` wrote the reduced array as though it were
the data.

Author: Yogesh Wadadekar
"""

from __future__ import annotations

import warnings

import numpy as np
from numpy.typing import NDArray


def block_image(
    data: NDArray[np.floating] | None,
    factor: int = 1,
) -> NDArray[np.floating] | None:
    """Average `factor` by `factor` squares of pixels into one.

    Args:
        data: The image. A cube is blocked in its two image axes only, the
            others being left alone.
        factor: Image pixels per output pixel along each axis. One, or
            anything smaller, returns the input unchanged and uncopied.

    Returns:
        The reduced image, or the input itself when there is nothing to do.
        Any partial square at the top or right edge is dropped rather than
        averaged over fewer pixels, which is what DS9 does; a factor larger
        than the image therefore returns the input rather than nothing.

    The average ignores NaN, so a blocked pixel overlapping blank data takes
    the mean of the real pixels rather than becoming blank itself.
    """
    factor = int(factor)
    if data is None or factor <= 1 or data.ndim < 2:
        return data

    height, width = data.shape[-2], data.shape[-1]
    rows, columns = height // factor, width // factor
    if rows < 1 or columns < 1:
        return data

    trimmed = data[..., : rows * factor, : columns * factor]
    reshaped = trimmed.reshape(*trimmed.shape[:-2], rows, factor, columns, factor)
    with warnings.catch_warnings():
        # A square that is entirely blank averages to NaN, which is the right
        # answer; numpy warns about it, and the warning is not news.
        warnings.filterwarnings("ignore", "Mean of empty slice", RuntimeWarning)
        blocked = np.nanmean(reshaped, axis=(-3, -1))
    return np.asarray(blocked, dtype=np.float32)
