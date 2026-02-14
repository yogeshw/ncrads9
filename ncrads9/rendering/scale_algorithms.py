# NCRADS9 - Image Scaling Algorithms
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
#
# Author: Yogesh Wadadekar

"""
Image scaling algorithms for astronomical data visualization.

Provides various scaling functions commonly used in astronomy to enhance
the visibility of faint features while preserving bright source detail.
"""

from enum import Enum, auto
from typing import Optional, Tuple

import numpy as np
from numpy.typing import NDArray


class ScaleAlgorithm(Enum):
    """Enumeration of available scaling algorithms."""

    LINEAR = auto()
    LOG = auto()
    SQRT = auto()
    POWER = auto()
    SINH = auto()
    ASINH = auto()
    HISTOGRAM_EQUALIZATION = auto()
    ZSCALE = auto()


def apply_scale(
    data: NDArray[np.float32],
    algorithm: ScaleAlgorithm,
    vmin: Optional[float] = None,
    vmax: Optional[float] = None,
    **kwargs,
) -> NDArray[np.float32]:
    """
    Apply a scaling algorithm to image data.

    Args:
        data: Input image data.
        algorithm: Scaling algorithm to apply.
        vmin: Minimum value for scaling (auto-computed if None).
        vmax: Maximum value for scaling (auto-computed if None).
        **kwargs: Algorithm-specific parameters.

    Returns:
        Scaled data normalized to [0, 1] range.
    """
    if vmin is None:
        vmin = float(np.nanmin(data))
    if vmax is None:
        vmax = float(np.nanmax(data))

    scale_funcs = {
        ScaleAlgorithm.LINEAR: scale_linear,
        ScaleAlgorithm.LOG: scale_log,
        ScaleAlgorithm.SQRT: scale_sqrt,
        ScaleAlgorithm.POWER: scale_power,
        ScaleAlgorithm.SINH: scale_sinh,
        ScaleAlgorithm.ASINH: scale_asinh,
        ScaleAlgorithm.HISTOGRAM_EQUALIZATION: scale_histogram_equalization,
        ScaleAlgorithm.ZSCALE: scale_zscale,
    }

    func = scale_funcs.get(algorithm, scale_linear)
    return func(data, vmin, vmax, **kwargs)


def scale_linear(
    data: NDArray[np.float32],
    vmin: float,
    vmax: float,
    **kwargs,
) -> NDArray[np.float32]:
    """
    Apply linear scaling.

    Args:
        data: Input data.
        vmin: Minimum value.
        vmax: Maximum value.

    Returns:
        Linearly scaled data in [0, 1].
    """
    if vmax == vmin:
        return np.zeros_like(data)
    result = (data - vmin) / (vmax - vmin)
    return np.clip(result, 0.0, 1.0).astype(np.float32)


def scale_log(
    data: NDArray[np.float32],
    vmin: float,
    vmax: float,
    a: float = 1000.0,
    **kwargs,
) -> NDArray[np.float32]:
    """
    Apply logarithmic scaling.

    Args:
        data: Input data.
        vmin: Minimum value.
        vmax: Maximum value.
        a: Scaling parameter (default 1000).

    Returns:
        Log-scaled data in [0, 1].
    """
    normalized = scale_linear(data, vmin, vmax)
    result = np.log10(a * normalized + 1) / np.log10(a + 1)
    return np.clip(result, 0.0, 1.0).astype(np.float32)


def scale_sqrt(
    data: NDArray[np.float32],
    vmin: float,
    vmax: float,
    **kwargs,
) -> NDArray[np.float32]:
    """
    Apply square root scaling.

    Args:
        data: Input data.
        vmin: Minimum value.
        vmax: Maximum value.

    Returns:
        Sqrt-scaled data in [0, 1].
    """
    normalized = scale_linear(data, vmin, vmax)
    result = np.sqrt(normalized)
    return np.clip(result, 0.0, 1.0).astype(np.float32)


def scale_power(
    data: NDArray[np.float32],
    vmin: float,
    vmax: float,
    exponent: float = 2.0,
    **kwargs,
) -> NDArray[np.float32]:
    """
    Apply power law scaling.

    Args:
        data: Input data.
        vmin: Minimum value.
        vmax: Maximum value.
        exponent: Power law exponent (default 2.0).

    Returns:
        Power-scaled data in [0, 1].
    """
    normalized = scale_linear(data, vmin, vmax)
    result = np.power(normalized, exponent)
    return np.clip(result, 0.0, 1.0).astype(np.float32)


def scale_sinh(
    data: NDArray[np.float32],
    vmin: float,
    vmax: float,
    a: float = 1.0,
    **kwargs,
) -> NDArray[np.float32]:
    """
    Apply hyperbolic sine scaling.

    Args:
        data: Input data.
        vmin: Minimum value.
        vmax: Maximum value.
        a: Scaling parameter.

    Returns:
        Sinh-scaled data in [0, 1].
    """
    normalized = scale_linear(data, vmin, vmax)
    result = np.sinh(a * normalized) / np.sinh(a)
    return np.clip(result, 0.0, 1.0).astype(np.float32)


def scale_asinh(
    data: NDArray[np.float32],
    vmin: float,
    vmax: float,
    a: float = 0.1,
    **kwargs,
) -> NDArray[np.float32]:
    """
    Apply inverse hyperbolic sine (arcsinh) scaling.

    This is particularly useful for astronomical images with large
    dynamic range, as it behaves like log for large values but
    remains linear near zero.

    Args:
        data: Input data.
        vmin: Minimum value.
        vmax: Maximum value.
        a: Softening parameter (default 0.1).

    Returns:
        Asinh-scaled data in [0, 1].
    """
    if a <= 0:
        raise ValueError("Parameter 'a' must be positive")
    normalized = scale_linear(data, vmin, vmax)
    result = np.arcsinh(normalized / a) / np.arcsinh(1.0 / a)
    return np.clip(result, 0.0, 1.0).astype(np.float32)


def scale_histogram_equalization(
    data: NDArray[np.float32],
    vmin: float,
    vmax: float,
    num_bins: int = 65536,
    **kwargs,
) -> NDArray[np.float32]:
    """
    Apply histogram equalization scaling.

    Args:
        data: Input data.
        vmin: Minimum value.
        vmax: Maximum value.
        num_bins: Number of histogram bins (default 65536).

    Returns:
        Histogram-equalized data in [0, 1].
    """
    # Clip and flatten
    clipped = np.clip(data, vmin, vmax)
    flat = clipped.flatten()

    # Compute histogram
    hist, bin_edges = np.histogram(flat[np.isfinite(flat)], bins=num_bins)
    cdf = hist.cumsum()
    if cdf.size == 0 or cdf[-1] == 0:
        return np.zeros_like(clipped, dtype=np.float32)
    cdf_normalized = cdf / cdf[-1]

    # Map values through CDF
    bin_indices = np.searchsorted(bin_edges[:-1], clipped) - 1
    bin_indices = np.clip(bin_indices, 0, num_bins - 1)
    result = cdf_normalized[bin_indices]

    return result.astype(np.float32)


def scale_zscale(
    data: NDArray[np.float32],
    vmin: float,
    vmax: float,
    contrast: float = 0.25,
    num_samples: int = 1000,
    num_iterations: int = 5,
    **kwargs,
) -> NDArray[np.float32]:
    """
    Apply IRAF zscale algorithm.

    The zscale algorithm determines display limits based on the
    distribution of pixel values, optimized for astronomical images.

    Args:
        data: Input data.
        vmin: Minimum value (used as fallback).
        vmax: Maximum value (used as fallback).
        contrast: Contrast parameter (default 0.25).
        num_samples: Number of samples for estimation (default 1000).
        num_iterations: Number of sigma-clipping iterations (default 5).

    Returns:
        Zscale-adjusted data in [0, 1].
    """
    z1, z2 = compute_zscale_limits(data, contrast, num_samples, num_iterations)
    return scale_linear(data, z1, z2)


def compute_zscale_limits(
    data: NDArray[np.float32],
    contrast: float = 0.25,
    num_samples: int = 1000,
    num_iterations: int = 5,
) -> Tuple[float, float]:
    """
    Compute zscale display limits.

    Args:
        data: Input data.
        contrast: Contrast parameter.
        num_samples: Number of samples.
        num_iterations: Sigma-clipping iterations.

    Returns:
        Tuple of (z1, z2) display limits.
    """
    # Get finite values only
    finite_data = data[np.isfinite(data)]
    if len(finite_data) == 0:
        return (0.0, 1.0)

    # Sample data
    if len(finite_data) > num_samples:
        indices = np.linspace(0, len(finite_data) - 1, num_samples, dtype=int)
        samples = np.sort(finite_data.flatten())[indices]
    else:
        samples = np.sort(finite_data.flatten())

    n = len(samples)
    if n < 2:
        return (float(samples[0]), float(samples[0]) + 1.0)

    # Fit line with iterative sigma clipping
    x = np.arange(n)
    for _ in range(num_iterations):
        coeffs = np.polyfit(x, samples, 1)
        fitted = np.polyval(coeffs, x)
        residuals = samples - fitted
        std = np.std(residuals)
        mask = np.abs(residuals) < 2.5 * std
        if np.sum(mask) < 2:
            break
        x = x[mask]
        samples = samples[mask]

    # Compute limits
    median_val = np.median(samples)
    slope = coeffs[0] if len(coeffs) > 0 else 0.0

    z1 = median_val - (n / 2.0) * slope / contrast
    z2 = median_val + (n / 2.0) * slope / contrast

    # Ensure valid range
    data_min = float(np.nanmin(data))
    data_max = float(np.nanmax(data))
    z1 = max(z1, data_min)
    z2 = min(z2, data_max)

    if z1 >= z2:
        z1, z2 = data_min, data_max

    return (float(z1), float(z2))
