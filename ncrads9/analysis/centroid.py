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
Centroid calculation functions for astronomical images.

Author: Yogesh Wadadekar
"""


import numpy as np
from numpy.typing import NDArray
from scipy import ndimage


def calculate_centroid(
    data: NDArray[np.floating],
    region: tuple[slice, slice] | None = None,
    mask: NDArray[np.bool_] | None = None,
    threshold: float | None = None,
) -> tuple[float, float]:
    """
    Calculate the intensity-weighted centroid of an image region.

    Parameters
    ----------
    data : NDArray
        Input 2D image data.
    region : tuple of slices, optional
        Region to analyze as (y_slice, x_slice).
    mask : NDArray[bool], optional
        Boolean mask where True indicates valid pixels.
    threshold : float, optional
        Only include pixels above this threshold.

    Returns
    -------
    tuple
        (x_centroid, y_centroid) in pixel coordinates.
    """
    if region is not None:
        data = data[region]
        if mask is not None:
            mask = mask[region]

    work_data = data.copy()

    if mask is not None:
        work_data = np.where(mask, work_data, np.nan)

    if threshold is not None:
        work_data = np.where(work_data >= threshold, work_data, 0)

    work_data = np.nan_to_num(work_data, nan=0.0)

    total = np.sum(work_data)
    if total == 0:
        return (float(data.shape[1] / 2), float(data.shape[0] / 2))

    y_indices, x_indices = np.indices(work_data.shape)
    x_centroid = np.sum(x_indices * work_data) / total
    y_centroid = np.sum(y_indices * work_data) / total

    if region is not None:
        x_centroid += region[1].start if region[1].start else 0
        y_centroid += region[0].start if region[0].start else 0

    return (float(x_centroid), float(y_centroid))


def calculate_centroid_iterative(
    data: NDArray[np.floating],
    initial_guess: tuple[float, float] | None = None,
    box_size: int = 11,
    max_iterations: int = 10,
    tolerance: float = 0.01,
    threshold_sigma: float = 3.0,
) -> tuple[float, float]:
    """
    Calculate centroid iteratively with a moving box.

    Parameters
    ----------
    data : NDArray
        Input 2D image data.
    initial_guess : tuple of float, optional
        Initial (x, y) guess. If None, uses image center.
    box_size : int, default 11
        Size of the box for centroid calculation.
    max_iterations : int, default 10
        Maximum number of iterations.
    tolerance : float, default 0.01
        Convergence tolerance in pixels.
    threshold_sigma : float, default 3.0
        Sigma threshold for background subtraction.

    Returns
    -------
    tuple
        (x_centroid, y_centroid) in pixel coordinates.
    """
    if initial_guess is None:
        x_cen, y_cen = data.shape[1] / 2, data.shape[0] / 2
    else:
        x_cen, y_cen = initial_guess

    half_box = box_size // 2

    for _ in range(max_iterations):
        x_min = max(0, int(x_cen - half_box))
        x_max = min(data.shape[1], int(x_cen + half_box + 1))
        y_min = max(0, int(y_cen - half_box))
        y_max = min(data.shape[0], int(y_cen + half_box + 1))

        region = (slice(y_min, y_max), slice(x_min, x_max))
        subdata = data[region].copy()

        background = np.nanmedian(subdata)
        rms = np.nanstd(subdata)
        threshold = background + threshold_sigma * rms

        new_x, new_y = calculate_centroid(data, region=region, threshold=threshold)

        if abs(new_x - x_cen) < tolerance and abs(new_y - y_cen) < tolerance:
            return (new_x, new_y)

        x_cen, y_cen = new_x, new_y

    return (x_cen, y_cen)


def calculate_gaussian_centroid(
    data: NDArray[np.floating],
    initial_guess: tuple[float, float] | None = None,
    box_size: int = 11,
) -> tuple[float, float, float, float]:
    """
    Calculate centroid by fitting a 2D Gaussian.

    Parameters
    ----------
    data : NDArray
        Input 2D image data.
    initial_guess : tuple of float, optional
        Initial (x, y) guess. If None, uses intensity centroid.
    box_size : int, default 11
        Size of the box for fitting.

    Returns
    -------
    tuple
        (x_centroid, y_centroid, sigma_x, sigma_y).
    """
    if initial_guess is None:
        x_init, y_init = calculate_centroid(data)
    else:
        x_init, y_init = initial_guess

    half_box = box_size // 2
    x_min = max(0, int(x_init - half_box))
    x_max = min(data.shape[1], int(x_init + half_box + 1))
    y_min = max(0, int(y_init - half_box))
    y_max = min(data.shape[0], int(y_init + half_box + 1))

    subdata = data[y_min:y_max, x_min:x_max]
    subdata = np.nan_to_num(subdata, nan=0.0)

    y_marginal = np.sum(subdata, axis=1)
    x_marginal = np.sum(subdata, axis=0)

    x_local = _gaussian_1d_centroid(x_marginal)
    y_local = _gaussian_1d_centroid(y_marginal)

    x_cen = x_min + x_local
    y_cen = y_min + y_local

    sigma_x = _estimate_sigma(x_marginal)
    sigma_y = _estimate_sigma(y_marginal)

    return (x_cen, y_cen, sigma_x, sigma_y)


def _gaussian_1d_centroid(profile: NDArray[np.floating]) -> float:
    """Estimate centroid of a 1D profile using moments."""
    profile = profile - np.min(profile)
    total = np.sum(profile)
    if total == 0:
        return len(profile) / 2
    indices = np.arange(len(profile))
    return float(np.sum(indices * profile) / total)


def _estimate_sigma(profile: NDArray[np.floating]) -> float:
    """Estimate Gaussian sigma from a 1D profile using second moment."""
    profile = profile - np.min(profile)
    total = np.sum(profile)
    if total == 0:
        return 1.0
    indices = np.arange(len(profile))
    mean = np.sum(indices * profile) / total
    variance = np.sum((indices - mean) ** 2 * profile) / total
    return float(np.sqrt(max(variance, 0)))


def peak_local_max(
    data: NDArray[np.floating],
    threshold: float | None = None,
    min_distance: int = 5,
    num_peaks: int = 10,
) -> NDArray[np.int_]:
    """
    Find local maxima in an image.

    Parameters
    ----------
    data : NDArray
        Input 2D image data.
    threshold : float, optional
        Minimum peak height. If None, uses median + 3*std.
    min_distance : int, default 5
        Minimum distance between peaks.
    num_peaks : int, default 10
        Maximum number of peaks to return.

    Returns
    -------
    NDArray
        Array of peak coordinates with shape (n_peaks, 2) as (y, x).
    """
    work_data = np.nan_to_num(data, nan=np.nanmin(data))

    if threshold is None:
        threshold = float(np.median(work_data) + 3 * np.std(work_data))

    max_filtered = ndimage.maximum_filter(work_data, size=min_distance)
    local_max = (work_data == max_filtered) & (work_data >= threshold)

    y_coords, x_coords = np.where(local_max)
    peak_values = work_data[local_max]

    sorted_indices = np.argsort(peak_values)[::-1]
    y_coords = y_coords[sorted_indices][:num_peaks]
    x_coords = x_coords[sorted_indices][:num_peaks]

    return np.column_stack([y_coords, x_coords])


# -- DS9's own centroid (M6-20) ------------------------------------------------
#
# `Base::centroid` in `tksao/frame/frmarker.C:855`. The functions above are
# general-purpose; this one is DS9's, because Region -> Centroid has to move a
# region where DS9 would move it and not merely somewhere defensible.

#: DS9's defaults, from `ds9/library/marker.tcl:28`.
DEFAULT_ITERATIONS = 30
DEFAULT_RADIUS = 10.0


def centroid_at(
    data: NDArray[np.floating],
    x: float,
    y: float,
    radius: float = DEFAULT_RADIUS,
    iterations: int = DEFAULT_ITERATIONS,
) -> tuple[float, float]:
    """Walk a position onto the nearby flux, as DS9's Centroid does.

    Each pass takes the flux-weighted mean of the pixels within `radius` of
    the current position and moves there; `iterations` passes let the
    position walk to a peak it did not start on. Non-finite pixels are
    skipped, and a pass whose weight is not positive stops the walk -- over
    empty sky there is nothing to be drawn towards, and DS9 returns the
    position unmoved rather than drifting to the corner of the box.

    Args:
        data: The image, indexed [y, x].
        x: Starting x, in image pixels (1-based, as regions are).
        y: Starting y.
        radius: The aperture radius, in pixels.
        iterations: How many passes to make.

    Returns:
        The centroid, in the same 1-based image pixels.
    """
    if data is None or data.ndim != 2 or radius <= 0:
        return (float(x), float(y))

    height, width = data.shape
    reach = int(radius)
    offsets = np.arange(-reach, reach + 1)
    dx, dy = np.meshgrid(offsets, offsets)
    inside = dx * dx + dy * dy <= radius * radius

    # Regions count pixels from one; arrays from zero.
    cx, cy = float(x) - 1.0, float(y) - 1.0
    for _pass in range(max(1, iterations)):
        column = np.rint(cx).astype(int) + dx
        row = np.rint(cy).astype(int) + dy
        usable = inside & (column >= 0) & (column < width) & (row >= 0) & (row < height)
        if not usable.any():
            break

        values = np.where(usable, data[np.clip(row, 0, height - 1), np.clip(column, 0, width - 1)], 0.0)
        values = np.where(np.isfinite(values), values, 0.0)
        values = np.where(usable, values, 0.0)

        weight = float(values.sum())
        if weight <= 0:
            break
        moved_x = float((column * values).sum()) / weight
        moved_y = float((row * values).sum()) / weight
        if abs(moved_x - cx) < 1e-9 and abs(moved_y - cy) < 1e-9:
            cx, cy = moved_x, moved_y
            break
        cx, cy = moved_x, moved_y

    return (cx + 1.0, cy + 1.0)
