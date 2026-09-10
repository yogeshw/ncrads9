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


import numpy as np
from numpy.typing import NDArray
from scipy import ndimage

#: DS9's two contour methods (`ds9/doc/ref/contour.html`, Contour Method).
CONTOUR_METHODS: tuple[str, ...] = ("block", "smooth")

#: What DS9 calls the smoothness when nothing says otherwise: evaluate the
#: contour at every image pixel.
DEFAULT_SMOOTHNESS = 1


def _block_down(data: NDArray[np.floating], factor: int) -> NDArray[np.floating]:
    """Average `data` down by an integer factor, DS9's BLOCK.

    The trailing pixels that do not fill a whole block are dropped rather
    than averaged with fewer: a partial block is brighter or fainter than
    its neighbours for no physical reason, and it shows as a bright edge on
    the last contour.
    """
    step = max(1, int(factor))
    if step == 1:
        return data
    height = (data.shape[0] // step) * step
    width = (data.shape[1] // step) * step
    if height == 0 or width == 0:
        return data
    trimmed = data[:height, :width]
    return trimmed.reshape(height // step, step, width // step, step).mean(axis=(1, 3))


class ContourGenerator:
    """
    Class for generating contours from astronomical images.

    DS9 offers two methods, and they are opposites in cost as well as in
    effect (`ds9/doc/ref/contour.html`): BLOCK "blocks down the image, by
    the smoothness factor, before contours are calculated", so a larger
    smoothness is *faster* and coarser; SMOOTH "smooths the image before
    calculating contours", so a larger smoothness is *slower* and rounder.
    Blocking also means the contours come back in the blocked image's
    coordinates, and have to be scaled back to the original -- which is
    what `_scale` does, and what makes a blocked contour land on the data
    it was computed from.

    Parameters
    ----------
    data : NDArray
        Input 2D image data.
    smooth : float, optional
        Gaussian smoothing sigma to apply before contouring. Kept for the
        callers that predate `method`; `smoothness` is DS9's own control.
    method : str
        "block" or "smooth".
    smoothness : int
        DS9's smoothness factor: the block factor for BLOCK, the boxcar
        width for SMOOTH. One means every pixel, and no change either way.

    Attributes
    ----------
    data : NDArray
        The image data, blocked or smoothed as the method asked.
    levels : list
        List of contour levels.
    contours : list
        List of contour paths for each level.
    """

    def __init__(
        self,
        data: NDArray[np.floating],
        smooth: float | None = None,
        method: str = "block",
        smoothness: int = DEFAULT_SMOOTHNESS,
    ) -> None:
        self.method = method if method in CONTOUR_METHODS else "block"
        self.smoothness = max(1, int(smoothness))
        #: How much the data was blocked down, so the contours can be
        #: scaled back to the original image's coordinates.
        self._block = 1

        working = np.asarray(data, dtype=np.float64)
        if smooth is not None and smooth > 0:
            working = ndimage.gaussian_filter(working, sigma=smooth)

        if self.smoothness > 1:
            if self.method == "block":
                working = _block_down(working, self.smoothness)
                self._block = self.smoothness
            else:
                # A boxcar of the smoothness width, which is what "smooths
                # the image" means here: a mean over that many pixels.
                working = ndimage.uniform_filter(working, size=self.smoothness)

        self.data = working
        self.levels: list[float] = []
        self.contours: list[list[NDArray[np.floating]]] = []

    def _scale(self, path: NDArray[np.floating]) -> NDArray[np.floating]:
        """Put a contour computed on blocked data back on the original grid."""
        if self._block <= 1:
            return path
        # Pixel k of the blocked image covers pixels k*b .. k*b+b-1 of the
        # original, whose centre is at k*b + (b-1)/2.
        return path * float(self._block) + (self._block - 1) / 2.0

    def generate_levels(
        self,
        n_levels: int = 10,
        vmin: float | None = None,
        vmax: float | None = None,
        log_scale: bool = False,
    ) -> list[float]:
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
        sigmas: list[float],
        base_level: float | None = None,
        rms: float | None = None,
    ) -> list[float]:
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
        levels: list[float] | None = None,
    ) -> list[list[NDArray[np.floating]]]:
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
            self.contours.append([self._scale(path) for path in contour_paths])

        return self.contours

    def find_contours_scipy(
        self,
        levels: list[float] | None = None,
    ) -> list[list[tuple[NDArray[np.floating], NDArray[np.floating]]]]:
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
            # `np.where` gives integer indices; the caller is promised
            # floating-point coordinates, since a real contour lies between
            # pixels.
            contours.append([(x_coords.astype(float), y_coords.astype(float))])

        return contours

    def get_contour_at_level(
        self,
        level: float,
    ) -> list[NDArray[np.floating]]:
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
