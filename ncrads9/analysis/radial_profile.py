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
Radial profile extraction for astronomical images.

Author: Yogesh Wadadekar
"""

from typing import Optional, Tuple
import numpy as np
from numpy.typing import NDArray


class RadialProfile:
    """
    Class for extracting radial profiles from astronomical images.

    Parameters
    ----------
    data : NDArray
        Input 2D image data.
    center : tuple of float, optional
        Center coordinates (x, y). If None, uses image center.
    mask : NDArray[bool], optional
        Boolean mask where True indicates valid pixels.

    Attributes
    ----------
    radii : NDArray
        Radial distances from center.
    profile : NDArray
        Mean pixel values at each radius.
    profile_std : NDArray
        Standard deviation at each radius.
    npixels : NDArray
        Number of pixels in each radial bin.
    """

    def __init__(
        self,
        data: NDArray[np.floating],
        center: Optional[Tuple[float, float]] = None,
        mask: Optional[NDArray[np.bool_]] = None,
    ) -> None:
        self._data = data
        self._mask = mask

        if center is None:
            self._center = (data.shape[1] / 2, data.shape[0] / 2)
        else:
            self._center = center

        self.radii: NDArray[np.floating]
        self.profile: NDArray[np.floating]
        self.profile_std: NDArray[np.floating]
        self.npixels: NDArray[np.int_]

        self._distance_map: NDArray[np.floating]
        self._compute_distance_map()

    def _compute_distance_map(self) -> None:
        """Compute the distance of each pixel from the center."""
        y, x = np.ogrid[: self._data.shape[0], : self._data.shape[1]]
        self._distance_map = np.sqrt(
            (x - self._center[0]) ** 2 + (y - self._center[1]) ** 2
        )

    def extract(
        self,
        max_radius: Optional[float] = None,
        bin_width: float = 1.0,
        method: str = "mean",
    ) -> Tuple[NDArray[np.floating], NDArray[np.floating]]:
        """
        Extract the radial profile.

        Parameters
        ----------
        max_radius : float, optional
            Maximum radius to extract. If None, uses half the image size.
        bin_width : float, default 1.0
            Width of radial bins in pixels.
        method : str, default 'mean'
            Aggregation method: 'mean', 'median', or 'sum'.

        Returns
        -------
        tuple
            (radii, profile) arrays.
        """
        if max_radius is None:
            max_radius = min(self._data.shape) / 2

        n_bins = int(np.ceil(max_radius / bin_width))
        self.radii = np.arange(n_bins) * bin_width + bin_width / 2
        self.profile = np.zeros(n_bins)
        self.profile_std = np.zeros(n_bins)
        self.npixels = np.zeros(n_bins, dtype=int)

        data_flat = self._data.flatten()
        dist_flat = self._distance_map.flatten()

        if self._mask is not None:
            mask_flat = self._mask.flatten()
            data_flat = data_flat[mask_flat]
            dist_flat = dist_flat[mask_flat]

        valid = ~np.isnan(data_flat)
        data_flat = data_flat[valid]
        dist_flat = dist_flat[valid]

        for i in range(n_bins):
            r_inner = i * bin_width
            r_outer = (i + 1) * bin_width
            in_bin = (dist_flat >= r_inner) & (dist_flat < r_outer)

            if np.any(in_bin):
                bin_data = data_flat[in_bin]
                self.npixels[i] = len(bin_data)

                if method == "mean":
                    self.profile[i] = np.mean(bin_data)
                elif method == "median":
                    self.profile[i] = np.median(bin_data)
                elif method == "sum":
                    self.profile[i] = np.sum(bin_data)
                else:
                    raise ValueError(f"Unknown method: {method}")

                self.profile_std[i] = np.std(bin_data)

        return self.radii, self.profile

    def extract_azimuthal(
        self,
        radius: float,
        width: float = 1.0,
        n_sectors: int = 8,
    ) -> Tuple[NDArray[np.floating], NDArray[np.floating]]:
        """
        Extract azimuthal profile at a given radius.

        Parameters
        ----------
        radius : float
            Radius at which to extract profile.
        width : float, default 1.0
            Width of the annulus.
        n_sectors : int, default 8
            Number of azimuthal sectors.

        Returns
        -------
        tuple
            (angles, profile) arrays where angles are in degrees.
        """
        y, x = np.ogrid[: self._data.shape[0], : self._data.shape[1]]
        angles = np.arctan2(y - self._center[1], x - self._center[0])
        angles = np.degrees(angles)

        in_annulus = (self._distance_map >= radius - width / 2) & (
            self._distance_map < radius + width / 2
        )

        sector_angles = np.linspace(-180, 180, n_sectors + 1)
        sector_centers = (sector_angles[:-1] + sector_angles[1:]) / 2
        profile = np.zeros(n_sectors)

        for i in range(n_sectors):
            in_sector = (angles >= sector_angles[i]) & (angles < sector_angles[i + 1])
            combined_mask = in_annulus & in_sector

            if self._mask is not None:
                combined_mask = combined_mask & self._mask

            if np.any(combined_mask):
                sector_data = self._data[combined_mask]
                valid = ~np.isnan(sector_data)
                if np.any(valid):
                    profile[i] = np.mean(sector_data[valid])

        return sector_centers, profile

    @property
    def center(self) -> Tuple[float, float]:
        """Return the center coordinates."""
        return self._center

    @center.setter
    def center(self, value: Tuple[float, float]) -> None:
        """Set the center and recompute distance map."""
        self._center = value
        self._compute_distance_map()
