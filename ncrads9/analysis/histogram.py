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
Histogram calculation and display for astronomical images.

Author: Yogesh Wadadekar
"""

from typing import Optional, Tuple, Union
import numpy as np
from numpy.typing import NDArray


class Histogram:
    """
    Class for calculating and displaying image histograms.

    Parameters
    ----------
    data : NDArray
        Input image data.
    bins : int or sequence, default 256
        Number of histogram bins or bin edges.
    range : tuple of float, optional
        Range of values to include (min, max).
    mask : NDArray[bool], optional
        Boolean mask where True indicates valid pixels.
    ignore_nan : bool, default True
        If True, ignore NaN values.

    Attributes
    ----------
    counts : NDArray
        Histogram bin counts.
    bin_edges : NDArray
        Histogram bin edges.
    bin_centers : NDArray
        Histogram bin centers.
    """

    def __init__(
        self,
        data: NDArray[np.floating],
        bins: Union[int, NDArray[np.floating]] = 256,
        range: Optional[Tuple[float, float]] = None,
        mask: Optional[NDArray[np.bool_]] = None,
        ignore_nan: bool = True,
    ) -> None:
        self._data = data
        self._bins = bins
        self._range = range
        self._mask = mask
        self._ignore_nan = ignore_nan

        self.counts: NDArray[np.int_]
        self.bin_edges: NDArray[np.floating]
        self.bin_centers: NDArray[np.floating]

        self._compute()

    def _compute(self) -> None:
        """Compute the histogram."""
        pixels = self._data.flatten()

        if self._mask is not None:
            pixels = pixels[self._mask.flatten()]

        if self._ignore_nan:
            pixels = pixels[~np.isnan(pixels)]

        self.counts, self.bin_edges = np.histogram(
            pixels, bins=self._bins, range=self._range
        )
        self.bin_centers = (self.bin_edges[:-1] + self.bin_edges[1:]) / 2

    def get_percentile(self, percentile: float) -> float:
        """
        Get the value at a given percentile.

        Parameters
        ----------
        percentile : float
            Percentile value (0-100).

        Returns
        -------
        float
            Value at the specified percentile.
        """
        cumsum = np.cumsum(self.counts)
        cumsum_norm = cumsum / cumsum[-1] * 100
        idx = np.searchsorted(cumsum_norm, percentile)
        return float(self.bin_centers[min(idx, len(self.bin_centers) - 1)])

    def get_mode(self) -> float:
        """
        Get the mode (most frequent value).

        Returns
        -------
        float
            Bin center with highest count.
        """
        max_idx = np.argmax(self.counts)
        return float(self.bin_centers[max_idx])

    def rebin(
        self,
        bins: Union[int, NDArray[np.floating]],
        range: Optional[Tuple[float, float]] = None,
    ) -> "Histogram":
        """
        Recompute histogram with new binning.

        Parameters
        ----------
        bins : int or sequence
            New number of bins or bin edges.
        range : tuple of float, optional
            New range of values.

        Returns
        -------
        Histogram
            New Histogram object with updated binning.
        """
        return Histogram(
            self._data,
            bins=bins,
            range=range if range is not None else self._range,
            mask=self._mask,
            ignore_nan=self._ignore_nan,
        )

    def to_log(self) -> Tuple[NDArray[np.floating], NDArray[np.floating]]:
        """
        Get log-scaled histogram counts.

        Returns
        -------
        tuple
            (bin_centers, log_counts) where log_counts is log10(counts + 1).
        """
        log_counts = np.log10(self.counts.astype(float) + 1)
        return self.bin_centers, log_counts

    def cumulative(self) -> Tuple[NDArray[np.floating], NDArray[np.floating]]:
        """
        Get cumulative histogram.

        Returns
        -------
        tuple
            (bin_centers, cumulative_counts).
        """
        cumsum = np.cumsum(self.counts)
        return self.bin_centers, cumsum.astype(float)

    def normalized(self) -> Tuple[NDArray[np.floating], NDArray[np.floating]]:
        """
        Get normalized histogram (probability density).

        Returns
        -------
        tuple
            (bin_centers, normalized_counts) where sum equals 1.
        """
        total = np.sum(self.counts)
        if total > 0:
            norm_counts = self.counts.astype(float) / total
        else:
            norm_counts = self.counts.astype(float)
        return self.bin_centers, norm_counts
