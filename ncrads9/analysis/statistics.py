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
Image statistics functions.

Provides functions for computing statistical measures on astronomical images
with support for region-based analysis.

Author: Yogesh Wadadekar
"""

from typing import Optional, Tuple, Dict, Any, Union
import numpy as np
from numpy.typing import NDArray


def _apply_region_mask(
    data: NDArray[np.floating],
    region: Optional[Tuple[slice, slice]] = None,
    mask: Optional[NDArray[np.bool_]] = None,
) -> NDArray[np.floating]:
    """
    Apply region selection and mask to data.

    Parameters
    ----------
    data : NDArray
        Input image data.
    region : tuple of slices, optional
        Region to analyze as (y_slice, x_slice).
    mask : NDArray[bool], optional
        Boolean mask where True indicates valid pixels.

    Returns
    -------
    NDArray
        Flattened array of valid pixel values.
    """
    if region is not None:
        data = data[region]

    if mask is not None:
        if region is not None:
            mask = mask[region]
        data = data[mask]

    return data.flatten()


def image_mean(
    data: NDArray[np.floating],
    region: Optional[Tuple[slice, slice]] = None,
    mask: Optional[NDArray[np.bool_]] = None,
    ignore_nan: bool = True,
) -> float:
    """
    Calculate the mean of image pixel values.

    Parameters
    ----------
    data : NDArray
        Input image data.
    region : tuple of slices, optional
        Region to analyze as (y_slice, x_slice).
    mask : NDArray[bool], optional
        Boolean mask where True indicates valid pixels.
    ignore_nan : bool, default True
        If True, ignore NaN values in calculation.

    Returns
    -------
    float
        Mean pixel value.
    """
    pixels = _apply_region_mask(data, region, mask)
    if ignore_nan:
        return float(np.nanmean(pixels))
    return float(np.mean(pixels))


def image_median(
    data: NDArray[np.floating],
    region: Optional[Tuple[slice, slice]] = None,
    mask: Optional[NDArray[np.bool_]] = None,
    ignore_nan: bool = True,
) -> float:
    """
    Calculate the median of image pixel values.

    Parameters
    ----------
    data : NDArray
        Input image data.
    region : tuple of slices, optional
        Region to analyze as (y_slice, x_slice).
    mask : NDArray[bool], optional
        Boolean mask where True indicates valid pixels.
    ignore_nan : bool, default True
        If True, ignore NaN values in calculation.

    Returns
    -------
    float
        Median pixel value.
    """
    pixels = _apply_region_mask(data, region, mask)
    if ignore_nan:
        return float(np.nanmedian(pixels))
    return float(np.median(pixels))


def image_std(
    data: NDArray[np.floating],
    region: Optional[Tuple[slice, slice]] = None,
    mask: Optional[NDArray[np.bool_]] = None,
    ignore_nan: bool = True,
    ddof: int = 0,
) -> float:
    """
    Calculate the standard deviation of image pixel values.

    Parameters
    ----------
    data : NDArray
        Input image data.
    region : tuple of slices, optional
        Region to analyze as (y_slice, x_slice).
    mask : NDArray[bool], optional
        Boolean mask where True indicates valid pixels.
    ignore_nan : bool, default True
        If True, ignore NaN values in calculation.
    ddof : int, default 0
        Delta degrees of freedom for std calculation.

    Returns
    -------
    float
        Standard deviation of pixel values.
    """
    pixels = _apply_region_mask(data, region, mask)
    if ignore_nan:
        return float(np.nanstd(pixels, ddof=ddof))
    return float(np.std(pixels, ddof=ddof))


def image_min(
    data: NDArray[np.floating],
    region: Optional[Tuple[slice, slice]] = None,
    mask: Optional[NDArray[np.bool_]] = None,
    ignore_nan: bool = True,
) -> float:
    """
    Calculate the minimum of image pixel values.

    Parameters
    ----------
    data : NDArray
        Input image data.
    region : tuple of slices, optional
        Region to analyze as (y_slice, x_slice).
    mask : NDArray[bool], optional
        Boolean mask where True indicates valid pixels.
    ignore_nan : bool, default True
        If True, ignore NaN values in calculation.

    Returns
    -------
    float
        Minimum pixel value.
    """
    pixels = _apply_region_mask(data, region, mask)
    if ignore_nan:
        return float(np.nanmin(pixels))
    return float(np.min(pixels))


def image_max(
    data: NDArray[np.floating],
    region: Optional[Tuple[slice, slice]] = None,
    mask: Optional[NDArray[np.bool_]] = None,
    ignore_nan: bool = True,
) -> float:
    """
    Calculate the maximum of image pixel values.

    Parameters
    ----------
    data : NDArray
        Input image data.
    region : tuple of slices, optional
        Region to analyze as (y_slice, x_slice).
    mask : NDArray[bool], optional
        Boolean mask where True indicates valid pixels.
    ignore_nan : bool, default True
        If True, ignore NaN values in calculation.

    Returns
    -------
    float
        Maximum pixel value.
    """
    pixels = _apply_region_mask(data, region, mask)
    if ignore_nan:
        return float(np.nanmax(pixels))
    return float(np.max(pixels))


def image_stats(
    data: NDArray[np.floating],
    region: Optional[Tuple[slice, slice]] = None,
    mask: Optional[NDArray[np.bool_]] = None,
    ignore_nan: bool = True,
) -> Dict[str, float]:
    """
    Calculate comprehensive statistics for image pixel values.

    Parameters
    ----------
    data : NDArray
        Input image data.
    region : tuple of slices, optional
        Region to analyze as (y_slice, x_slice).
    mask : NDArray[bool], optional
        Boolean mask where True indicates valid pixels.
    ignore_nan : bool, default True
        If True, ignore NaN values in calculation.

    Returns
    -------
    dict
        Dictionary containing mean, median, std, min, max, and npixels.
    """
    pixels = _apply_region_mask(data, region, mask)

    if ignore_nan:
        valid_pixels = pixels[~np.isnan(pixels)]
    else:
        valid_pixels = pixels

    return {
        "mean": float(np.mean(valid_pixels)),
        "median": float(np.median(valid_pixels)),
        "std": float(np.std(valid_pixels)),
        "min": float(np.min(valid_pixels)),
        "max": float(np.max(valid_pixels)),
        "npixels": int(len(valid_pixels)),
    }
