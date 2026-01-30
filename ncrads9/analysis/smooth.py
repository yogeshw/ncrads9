# ncrads9 - NCRA DS9 Analysis Package
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
Image smoothing functions for astronomical images.

Provides Gaussian, boxcar, and tophat smoothing operations.

Author: Yogesh Wadadekar
"""

from typing import Optional, Tuple, Union
import numpy as np
from numpy.typing import NDArray
from scipy import ndimage


def gaussian_smooth(
    data: NDArray[np.floating],
    sigma: Union[float, Tuple[float, float]],
    mode: str = "constant",
    cval: float = 0.0,
    truncate: float = 4.0,
) -> NDArray[np.floating]:
    """
    Apply Gaussian smoothing to an image.

    Parameters
    ----------
    data : NDArray
        Input 2D image data.
    sigma : float or tuple of float
        Standard deviation of Gaussian kernel. If tuple, (sigma_y, sigma_x).
    mode : str, default 'constant'
        Boundary mode: 'constant', 'nearest', 'reflect', 'wrap'.
    cval : float, default 0.0
        Value for constant mode.
    truncate : float, default 4.0
        Truncate filter at this many sigmas.

    Returns
    -------
    NDArray
        Smoothed image.
    """
    return ndimage.gaussian_filter(
        data, sigma=sigma, mode=mode, cval=cval, truncate=truncate
    )


def boxcar_smooth(
    data: NDArray[np.floating],
    size: Union[int, Tuple[int, int]],
    mode: str = "constant",
    cval: float = 0.0,
) -> NDArray[np.floating]:
    """
    Apply boxcar (uniform/mean) smoothing to an image.

    Parameters
    ----------
    data : NDArray
        Input 2D image data.
    size : int or tuple of int
        Size of the boxcar kernel. If int, uses square kernel.
    mode : str, default 'constant'
        Boundary mode: 'constant', 'nearest', 'reflect', 'wrap'.
    cval : float, default 0.0
        Value for constant mode.

    Returns
    -------
    NDArray
        Smoothed image.
    """
    if isinstance(size, int):
        size = (size, size)

    return ndimage.uniform_filter(data, size=size, mode=mode, cval=cval)


def tophat_smooth(
    data: NDArray[np.floating],
    radius: float,
    mode: str = "constant",
    cval: float = 0.0,
) -> NDArray[np.floating]:
    """
    Apply tophat (circular pillbox) smoothing to an image.

    Parameters
    ----------
    data : NDArray
        Input 2D image data.
    radius : float
        Radius of the circular tophat kernel.
    mode : str, default 'constant'
        Boundary mode: 'constant', 'nearest', 'reflect', 'wrap'.
    cval : float, default 0.0
        Value for constant mode.

    Returns
    -------
    NDArray
        Smoothed image.
    """
    kernel = _create_tophat_kernel(radius)
    return ndimage.convolve(data, kernel, mode=mode, cval=cval)


def _create_tophat_kernel(radius: float) -> NDArray[np.floating]:
    """
    Create a normalized circular tophat kernel.

    Parameters
    ----------
    radius : float
        Radius of the tophat in pixels.

    Returns
    -------
    NDArray
        Normalized 2D tophat kernel.
    """
    size = int(np.ceil(radius) * 2 + 1)
    center = size // 2

    y, x = np.ogrid[:size, :size]
    distance = np.sqrt((x - center) ** 2 + (y - center) ** 2)

    kernel = (distance <= radius).astype(float)
    kernel /= np.sum(kernel)

    return kernel


def adaptive_smooth(
    data: NDArray[np.floating],
    sigma_min: float = 1.0,
    sigma_max: float = 5.0,
    threshold: Optional[float] = None,
) -> NDArray[np.floating]:
    """
    Apply adaptive smoothing based on local signal strength.

    Uses less smoothing in high signal regions and more in low signal regions.

    Parameters
    ----------
    data : NDArray
        Input 2D image data.
    sigma_min : float, default 1.0
        Minimum smoothing sigma (used in high signal regions).
    sigma_max : float, default 5.0
        Maximum smoothing sigma (used in low signal regions).
    threshold : float, optional
        Signal threshold. If None, uses median of data.

    Returns
    -------
    NDArray
        Adaptively smoothed image.
    """
    if threshold is None:
        threshold = float(np.nanmedian(data))

    smoothed_min = gaussian_smooth(data, sigma_min)
    smoothed_max = gaussian_smooth(data, sigma_max)

    signal_strength = np.abs(data - threshold)
    signal_max = np.nanmax(signal_strength)
    if signal_max > 0:
        weight = signal_strength / signal_max
    else:
        weight = np.zeros_like(data)

    weight = np.clip(weight, 0, 1)
    result = weight * smoothed_min + (1 - weight) * smoothed_max

    return result


def smooth_with_nan(
    data: NDArray[np.floating],
    sigma: float,
    method: str = "gaussian",
) -> NDArray[np.floating]:
    """
    Apply smoothing while properly handling NaN values.

    Parameters
    ----------
    data : NDArray
        Input 2D image data with possible NaN values.
    sigma : float
        Smoothing parameter (sigma for gaussian, size for boxcar).
    method : str, default 'gaussian'
        Smoothing method: 'gaussian' or 'boxcar'.

    Returns
    -------
    NDArray
        Smoothed image with NaN values preserved.
    """
    nan_mask = np.isnan(data)
    data_filled = np.where(nan_mask, 0, data)
    weights = np.where(nan_mask, 0, 1).astype(float)

    if method == "gaussian":
        smoothed_data = gaussian_smooth(data_filled, sigma)
        smoothed_weights = gaussian_smooth(weights, sigma)
    elif method == "boxcar":
        smoothed_data = boxcar_smooth(data_filled, int(sigma))
        smoothed_weights = boxcar_smooth(weights, int(sigma))
    else:
        raise ValueError(f"Unknown method: {method}")

    with np.errstate(divide="ignore", invalid="ignore"):
        result = smoothed_data / smoothed_weights

    result[nan_mask] = np.nan

    return result
