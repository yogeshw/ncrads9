# NCRA DS9 - Astronomical Image Viewer
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
Mathematical utility functions for image processing.

Author: Yogesh Wadadekar
"""

from __future__ import annotations

from typing import Literal

import numpy as np
from numpy.typing import NDArray


def normalize_image(
    data: NDArray[np.floating],
    vmin: float | None = None,
    vmax: float | None = None,
    clip: bool = True,
) -> NDArray[np.float64]:
    """
    Normalize image data to [0, 1] range.

    Args:
        data: Input image array.
        vmin: Minimum value for normalization (default: data min).
        vmax: Maximum value for normalization (default: data max).
        clip: Whether to clip values outside [0, 1].

    Returns:
        Normalized image array.
    """
    data = np.asarray(data, dtype=np.float64)

    if vmin is None:
        vmin = np.nanmin(data)
    if vmax is None:
        vmax = np.nanmax(data)

    if vmax == vmin:
        return np.zeros_like(data)

    normalized = (data - vmin) / (vmax - vmin)

    if clip:
        normalized = np.clip(normalized, 0.0, 1.0)

    return normalized


def compute_histogram(
    data: NDArray[np.floating],
    bins: int = 256,
    range_: tuple[float, float] | None = None,
) -> tuple[NDArray[np.int64], NDArray[np.float64]]:
    """
    Compute histogram of image data.

    Args:
        data: Input image array.
        bins: Number of histogram bins.
        range_: Value range for histogram.

    Returns:
        Tuple of (counts, bin_edges).
    """
    data = np.asarray(data).ravel()
    valid_data = data[np.isfinite(data)]

    if range_ is None:
        range_ = (float(np.min(valid_data)), float(np.max(valid_data)))

    counts, edges = np.histogram(valid_data, bins=bins, range=range_)
    return counts, edges


ScaleType = Literal["linear", "log", "sqrt", "asinh", "square"]


def apply_scaling(
    data: NDArray[np.floating],
    scale: ScaleType = "linear",
    asinh_a: float = 0.1,
) -> NDArray[np.float64]:
    """
    Apply intensity scaling to image data.

    Args:
        data: Input image array (should be normalized to [0, 1]).
        scale: Scaling type.
        asinh_a: Softness parameter for asinh scaling.

    Returns:
        Scaled image array.
    """
    data = np.asarray(data, dtype=np.float64)

    if scale == "linear":
        return data
    elif scale == "log":
        return np.log10(1 + 9 * data) / np.log10(10)
    elif scale == "sqrt":
        return np.sqrt(np.maximum(data, 0))
    elif scale == "asinh":
        if asinh_a <= 0:
            raise ValueError("asinh_a must be positive")
        return np.arcsinh(data / asinh_a) / np.arcsinh(1.0 / asinh_a)
    elif scale == "square":
        return data * data
    else:
        raise ValueError(f"Unknown scale type: {scale}")


def sigma_clip(
    data: NDArray[np.floating],
    sigma: float = 3.0,
    max_iters: int = 5,
) -> tuple[float, float]:
    """
    Compute sigma-clipped statistics.

    Args:
        data: Input array.
        sigma: Number of standard deviations for clipping.
        max_iters: Maximum number of iterations.

    Returns:
        Tuple of (clipped_mean, clipped_std).
    """
    data = np.asarray(data).ravel()
    mask = np.isfinite(data)

    for _ in range(max_iters):
        valid = data[mask]
        if len(valid) == 0:
            return 0.0, 1.0

        mean = np.mean(valid)
        std = np.std(valid)

        if std == 0:
            break

        new_mask = mask & (np.abs(data - mean) <= sigma * std)
        if np.array_equal(new_mask, mask):
            break
        mask = new_mask

    valid = data[mask]
    return float(np.mean(valid)), float(np.std(valid))


def percentile_interval(
    data: NDArray[np.floating],
    percentile: float = 99.5,
) -> tuple[float, float]:
    """
    Compute symmetric percentile interval for scaling.

    Args:
        data: Input array.
        percentile: Upper percentile (lower is 100 - percentile).

    Returns:
        Tuple of (vmin, vmax).
    """
    data = np.asarray(data).ravel()
    valid = data[np.isfinite(data)]

    if len(valid) == 0:
        return 0.0, 1.0

    low = (100 - percentile) / 2
    high = 100 - low

    vmin = float(np.percentile(valid, low))
    vmax = float(np.percentile(valid, high))

    return vmin, vmax
