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
Contours for astronomical images.

DS9's two contour methods, the levels to draw them at, and the tracing
itself. `trace` is a marching-squares tracer written here so that a
contour does not depend on an optional package being installed; where
scikit-image *is* installed its tracer runs instead, and a test holds the
two to the same answers.

The one thing a contour must get right is which points belong to the same
curve. Getting that wrong does not look like a bug in the mathematics --
it looks like a line drawn from one source to the next, which is how it
was reported.

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


#: The sixteen marching-squares cases, as pairs of cell edges to join.
#:
#: A cell is the square between four neighbouring pixel centres, and its
#: index is which of those four are at or above the level::
#:
#:     bit 0  upper left      bit 2  lower right
#:     bit 1  upper right     bit 3  lower left
#:
#: Each entry is the edges the contour crosses -- "t"op, "r"ight, "b"ottom,
#: "l"eft -- in pairs, and the crossing point on an edge is found by
#: interpolating between the two pixels it joins.
#:
#: Cases 5 and 10 are the saddles, where the two corners above the level are
#: diagonally opposite and the cell alone cannot say whether they are one
#: island or two. Both are resolved *apart*, which is what makes two sources
#: that touch only at a corner stay two contours rather than one -- the same
#: choice `skimage.measure.find_contours` makes with its default
#: `fully_connected="low"`, so the two paths through this module agree.
_CASES: tuple[tuple[tuple[str, str], ...], ...] = (
    (),  # 0000  none above
    (("l", "t"),),  # 0001  upper left
    (("t", "r"),),  # 0010  upper right
    (("l", "r"),),  # 0011  top
    (("r", "b"),),  # 0100  lower right
    (("l", "t"), ("r", "b")),  # 0101  saddle, kept apart
    (("t", "b"),),  # 0110  right
    (("l", "b"),),  # 0111  all but lower left
    (("b", "l"),),  # 1000  lower left
    (("t", "b"),),  # 1001  left
    (("t", "r"), ("b", "l")),  # 1010  saddle, kept apart
    (("r", "b"),),  # 1011  all but lower right
    (("l", "r"),),  # 1100  bottom
    (("t", "r"),),  # 1101  all but upper right
    (("l", "t"),),  # 1110  all but upper left
    (),  # 1111  all above
)


def _crossing(
    edge: str,
    row: int,
    column: int,
    upper_left: float,
    upper_right: float,
    lower_left: float,
    lower_right: float,
    level: float,
) -> tuple[float, float]:
    """Where the level crosses one edge of one cell, in (row, column).

    Linear interpolation between the two pixel centres the edge joins. A
    zero denominator cannot arise: an edge is only crossed when its two
    values are on opposite sides of the level, so they differ.
    """
    if edge == "t":
        return (float(row), column + (level - upper_left) / (upper_right - upper_left))
    if edge == "b":
        return (float(row + 1), column + (level - lower_left) / (lower_right - lower_left))
    if edge == "l":
        return (row + (level - upper_left) / (lower_left - upper_left), float(column))
    return (row + (level - upper_right) / (lower_right - upper_right), float(column + 1))


def _segments(
    data: NDArray[np.floating], level: float
) -> list[tuple[tuple[float, float], tuple[float, float]]]:
    """Every contour segment at `level`, one or two per crossed cell.

    A pixel exactly at the level counts as above it, so that a level equal
    to some of the data still produces a contour rather than nothing.
    """
    above = data >= level
    upper_left = above[:-1, :-1]
    upper_right = above[:-1, 1:]
    lower_left = above[1:, :-1]
    lower_right = above[1:, 1:]
    index = (
        upper_left.astype(np.uint8)
        | (upper_right.astype(np.uint8) << 1)
        | (lower_right.astype(np.uint8) << 2)
        | (lower_left.astype(np.uint8) << 3)
    )

    found: list[tuple[tuple[float, float], tuple[float, float]]] = []
    rows, columns = np.nonzero((index != 0) & (index != 15))
    for row, column in zip(rows.tolist(), columns.tolist(), strict=True):
        values = (
            float(data[row, column]),
            float(data[row, column + 1]),
            float(data[row + 1, column]),
            float(data[row + 1, column + 1]),
        )
        if any(value != value for value in values):
            # A blank pixel says nothing about where the level lies, so the
            # cell is left out rather than contoured through the gap.
            continue
        for first, second in _CASES[int(index[row, column])]:
            found.append(
                (
                    _crossing(first, row, column, *values, level),
                    _crossing(second, row, column, *values, level),
                )
            )
    return found


def _link(segments: list[tuple[tuple[float, float], tuple[float, float]]]) -> list[NDArray[np.floating]]:
    """Join segments end to end into as many separate paths as there are.

    This is the part that was missing. Without it every crossing in the
    image is one heap of points, and drawing that heap as a polyline runs a
    line from each island to the next -- which is the bug this replaces.

    Endpoints match exactly rather than approximately: the edge shared by
    two neighbouring cells is interpolated from the same two pixel values
    both times, so the two cells produce the same float for it.
    """
    ends: dict[tuple[float, float], list[int]] = {}
    for position, (start, finish) in enumerate(segments):
        ends.setdefault(start, []).append(position)
        ends.setdefault(finish, []).append(position)

    used = [False] * len(segments)
    paths: list[NDArray[np.floating]] = []

    def walk(point: tuple[float, float]) -> list[tuple[float, float]]:
        """Follow the chain from `point` until it ends or closes."""
        chain = [point]
        while True:
            nxt = None
            for position in ends.get(chain[-1], ()):
                if not used[position]:
                    nxt = position
                    break
            if nxt is None:
                return chain
            used[nxt] = True
            start, finish = segments[nxt]
            chain.append(finish if start == chain[-1] else start)

    # Open paths first, from the endpoints only one segment touches: a
    # closed loop has none of those, and starting a loop mid-way would cut
    # it into two.
    for point, positions in ends.items():
        if len(positions) == 1 and not used[positions[0]]:
            chain = walk(point)
            if len(chain) > 1:
                paths.append(np.asarray(chain, dtype=np.float64))

    for position, (start, _finish) in enumerate(segments):
        if used[position]:
            continue
        chain = walk(start)
        if len(chain) > 1:
            paths.append(np.asarray(chain, dtype=np.float64))

    return paths


def trace(data: NDArray[np.floating], level: float) -> list[NDArray[np.floating]]:
    """Contour `data` at `level`, as separate paths in (row, column).

    Marching squares, with the segments linked into paths -- the same
    contract as `skimage.measure.find_contours`, which is what this stands
    in for when scikit-image is not installed.
    """
    array = np.asarray(data, dtype=np.float64)
    if array.ndim != 2 or array.shape[0] < 2 or array.shape[1] < 2:
        return []
    return _link(_segments(array, float(level)))


def _paths(data: NDArray[np.floating], level: float) -> list[NDArray[np.floating]]:
    """Contour one level, as separate paths in (row, column).

    scikit-image's tracer where it is installed, `trace` where it is not.
    They agree -- case for case, including which way the saddles go -- and
    a test holds them to that, so which one runs changes the speed and
    nothing else.

    It used to matter a great deal. scikit-image was never declared as a
    dependency, so on any clean install the import failed, and the caller's
    `except Exception` quietly reached for a "fallback" that was not a
    contour tracer at all: it collected every crossing pixel in the image
    into one array, in raster order, and the overlay drew that as a single
    polyline. Every island was joined to the next by a straight line, worst
    at the lowest level where the islands are largest -- which is how the
    fault was reported. scikit-image is declared now *and* the fallback is
    a real tracer, because a contour that is quietly wrong is worse in a
    measuring tool than one that is missing.
    """
    try:
        from skimage import measure
    except ImportError:
        return trace(data, level)
    return list(measure.find_contours(data, level))


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
        if levels is not None:
            self.levels = levels

        if not self.levels:
            self.generate_levels()

        self.contours = []
        for level in self.levels:
            self.contours.append([self._scale(path) for path in _paths(self.data, level)])

        return self.contours

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
        return [self._scale(path) for path in _paths(self.data, level)]

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
