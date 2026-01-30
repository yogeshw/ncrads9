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
Contour generation for astronomical images using scipy.

Author: Yogesh Wadadekar
"""

from typing import List, Optional, Tuple, Union
import numpy as np
from numpy.typing import NDArray
from scipy import ndimage


class ContourGenerator:
    """
    Class for generating contours from astronomical images.

    Parameters
    ----------
    data : NDArray
        Input 2D image data.
    smooth : float, optional
        Gaussian smoothing sigma to apply before contouring.

    Attributes
    ----------
    data : NDArray
        The image data (possibly smoothed).
    levels : list
        List of contour levels.
    contours : list
        List of contour paths for each level.
    """

    def __init__(
        self,
        data: NDArray[np.floating],
        smooth: Optional[float] = None,
    ) -> None:
        if smooth is not None and smooth > 0:
            self.data = ndimage.gaussian_filter(data, sigma=smooth)
        else:
            self.data = data.copy()

        self.levels: List[float] = []
        self.contours: List[List[NDArray[np.floating]]] = []

    def generate_levels(
        self,
        n_levels: int = 10,
        vmin: Optional[float] = None,
        vmax: Optional[float] = None,
        log_scale: bool = False,
    ) -> List[float]:
        """
        Generate contour levels.

        Parameters
        ----------
        n_levels : int, default 10
            Number of contour levels.
        vmin : float, optional
            Minimum level value. If None, uses data minimum.
        vmax : float, optional
            Maximum level value. If None, uses data maximum.
        log_scale : bool, default False
            If True, use logarithmic spacing.

        Returns
        -------
        list
            List of contour level values.
        """
        valid_data = self.data[~np.isnan(self.data)]

        if vmin is None:
            vmin = float(np.min(valid_data))
        if vmax is None:
            vmax = float(np.max(valid_data))

        if log_scale and vmin > 0:
            self.levels = list(np.logspace(np.log10(vmin), np.log10(vmax), n_levels))
        else:
            self.levels = list(np.linspace(vmin, vmax, n_levels))

        return self.levels

    def generate_sigma_levels(
        self,
        sigmas: List[float],
        base_level: Optional[float] = None,
        rms: Optional[float] = None,
    ) -> List[float]:
        """
        Generate contour levels based on sigma values.

        Parameters
        ----------
        sigmas : list of float
            Sigma multipliers for levels (e.g., [3, 5, 10, 20]).
        base_level : float, optional
            Base level (usually noise floor). If None, uses median.
        rms : float, optional
            RMS noise level. If None, estimates from data.

        Returns
        -------
        list
            List of contour level values.
        """
        valid_data = self.data[~np.isnan(self.data)]

        if base_level is None:
            base_level = float(np.median(valid_data))
        if rms is None:
            rms = float(np.std(valid_data))

        self.levels = [base_level + s * rms for s in sigmas]
        return self.levels

    def find_contours(
        self,
        levels: Optional[List[float]] = None,
    ) -> List[List[NDArray[np.floating]]]:
        """
        Find contour paths at specified levels.

        Parameters
        ----------
        levels : list of float, optional
            Contour levels. If None, uses previously generated levels.

        Returns
        -------
        list
            List of contour paths for each level.
        """
        from skimage import measure

        if levels is not None:
            self.levels = levels

        if not self.levels:
            self.generate_levels()

        self.contours = []
        for level in self.levels:
            contour_paths = measure.find_contours(self.data, level)
            self.contours.append(contour_paths)

        return self.contours

    def find_contours_scipy(
        self,
        levels: Optional[List[float]] = None,
    ) -> List[List[Tuple[NDArray[np.floating], NDArray[np.floating]]]]:
        """
        Find contour paths using scipy's binary dilation method.

        This is a simpler fallback when skimage is not available.

        Parameters
        ----------
        levels : list of float, optional
            Contour levels. If None, uses previously generated levels.

        Returns
        -------
        list
            List of (x, y) coordinate arrays for each level.
        """
        if levels is not None:
            self.levels = levels

        if not self.levels:
            self.generate_levels()

        contours = []
        for level in self.levels:
            binary = self.data >= level
            dilated = ndimage.binary_dilation(binary)
            edge = dilated ^ binary
            y_coords, x_coords = np.where(edge)
            contours.append([(x_coords, y_coords)])

        return contours

    def get_contour_at_level(
        self,
        level: float,
    ) -> List[NDArray[np.floating]]:
        """
        Get contour paths at a specific level.

        Parameters
        ----------
        level : float
            Contour level value.

        Returns
        -------
        list
            List of contour paths at this level.
        """
        from skimage import measure

        return measure.find_contours(self.data, level)

    def contour_area(
        self,
        level: float,
    ) -> float:
        """
        Calculate the area enclosed by a contour level.

        Parameters
        ----------
        level : float
            Contour level value.

        Returns
        -------
        float
            Area in square pixels.
        """
        binary = self.data >= level
        return float(np.sum(binary))

    def contour_perimeter(
        self,
        level: float,
    ) -> float:
        """
        Calculate the perimeter of a contour level.

        Parameters
        ----------
        level : float
            Contour level value.

        Returns
        -------
        float
            Perimeter in pixels.
        """
        binary = self.data >= level
        dilated = ndimage.binary_dilation(binary)
        edge = dilated ^ binary
        return float(np.sum(edge))
