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


import numpy as np
from numpy.typing import NDArray
from scipy import ndimage


def gaussian_smooth(
    data: NDArray[np.floating],
    sigma: float | tuple[float, float],
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
    return ndimage.gaussian_filter(data, sigma=sigma, mode=mode, cval=cval, truncate=truncate)


def elliptical_gaussian_kernel(
    major_radius: int,
    minor_radius: int,
    major_sigma: float,
    minor_sigma: float,
    angle: float = 0.0,
) -> NDArray[np.floating]:
    """
    Build DS9's elliptical Gaussian kernel.

    DS9's Smooth dialog offers four functions -- boxcar, tophat, Gaussian
    and elliptical Gaussian -- and the last takes a major and a minor radius
    and sigma plus a position angle (`ds9/library/smooth.tcl:124`). Its
    diameter is "2*radius+1" in each direction, which is DS9's own note
    beside the sliders: a kernel of even width has no centre pixel, and a
    smoothed image would shift by half a pixel.

    Parameters
    ----------
    major_radius : int
        Half-width along the major axis, in pixels.
    minor_radius : int
        Half-width along the minor axis.
    major_sigma : float
        Gaussian sigma along the major axis.
    minor_sigma : float
        Sigma along the minor axis.
    angle : float
        Position angle of the major axis, in degrees anticlockwise from x.

    Returns
    -------
    NDArray
        The kernel, normalised to sum to one so smoothing preserves flux.
    """
    major_radius = max(1, int(major_radius))
    minor_radius = max(1, int(minor_radius))
    major_sigma = max(1e-6, float(major_sigma))
    minor_sigma = max(1e-6, float(minor_sigma))

    # The kernel is square and large enough for the ellipse at any angle:
    # a kernel sized to the axes and then rotated would clip its own corners.
    reach = max(major_radius, minor_radius)
    offsets = np.arange(-reach, reach + 1, dtype=np.float64)
    dx, dy = np.meshgrid(offsets, offsets)

    radians = np.radians(float(angle))
    cosine, sine = np.cos(radians), np.sin(radians)
    along = dx * cosine + dy * sine
    across = -dx * sine + dy * cosine

    kernel = np.exp(-0.5 * ((along / major_sigma) ** 2 + (across / minor_sigma) ** 2))
    # Outside the ellipse the kernel is cut off, which is what the two radii
    # are for -- without it they would have no effect at all.
    kernel[(along / major_radius) ** 2 + (across / minor_radius) ** 2 > 1.0] = 0.0

    total = kernel.sum()
    return kernel / total if total else kernel


def elliptical_gaussian_smooth(
    data: NDArray[np.floating],
    major_radius: int = 3,
    minor_radius: int = 2,
    major_sigma: float = 1.5,
    minor_sigma: float = 1.0,
    angle: float = 0.0,
    mode: str = "nearest",
) -> NDArray[np.floating]:
    """
    Smooth an image with DS9's elliptical Gaussian.

    Parameters
    ----------
    data : NDArray
        Input 2D image data.
    major_radius, minor_radius : int
        The kernel's two half-widths, in pixels.
    major_sigma, minor_sigma : float
        Its two sigmas.
    angle : float
        The major axis's position angle, in degrees.
    mode : str
        Boundary mode, as `scipy.ndimage` takes it.

    Returns
    -------
    NDArray
        Smoothed image.
    """
    kernel = elliptical_gaussian_kernel(major_radius, minor_radius, major_sigma, minor_sigma, angle)
    return ndimage.convolve(np.asarray(data, dtype=np.float64), kernel, mode=mode)


def boxcar_smooth(
    data: NDArray[np.floating],
    size: int | tuple[int, int],
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
    threshold: float | None = None,
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
