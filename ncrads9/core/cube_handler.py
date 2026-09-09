# NCRADS9 - NCRA DS9-like FITS Viewer
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
Data cubes: which slice is on screen, and which way round the axes go.

DS9's `Frame -> Cube` dialog (`ds9/library/cube.tcl`) shows one slice of a
cube at a time, with a slider over the slice axis, an Axis Order menu offering
the six permutations `123` .. `321`, and a play/stop pair that walks the slices
at a settable interval. `AxisOrder` below is that menu and `CubeHandler` is
the slicing behind it.

Axis numbering is FITS's throughout the public API -- axis 1 is `NAXIS1`, the
fastest-varying one -- because that is what DS9's dialog and the FITS header
both use. numpy's ordering is the reverse, and `_numpy_axis` is the single
place the two are reconciled.

The moment maps and `collapse` are not DS9 features; they were here before M0
and are kept because M7's analysis work wants them. They read the cube in its
declared order, not the display order.

Author: Yogesh Wadadekar
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

import numpy as np
from astropy.io import fits
from astropy.wcs import WCS
from numpy.typing import NDArray

#: How many axes a cube has, in DS9's dialog and in this module.
CUBE_AXES = 3

#: The collapse methods `collapse` accepts, mapped to their numpy reduction.
COLLAPSE_METHODS: dict[str, Callable[..., NDArray[np.floating]]] = {
    "sum": np.nansum,
    "mean": np.nanmean,
    "max": np.nanmax,
    "min": np.nanmin,
}


@dataclass(frozen=True)
class AxisOrder:
    """Which FITS axis is display x, which is y, and which is sliced.

    DS9 writes an order as three digits: `123` is the default, where axis 1
    runs across the display, axis 2 up it, and axis 3 is stepped through.
    `321` swaps the first and third, so a position-velocity cube can be
    sliced along right ascension instead.
    """

    x: int = 1
    y: int = 2
    z: int = 3

    def __post_init__(self) -> None:
        if sorted((self.x, self.y, self.z)) != [1, 2, 3]:
            raise ValueError(f"axis order must be a permutation of 1,2,3; got {self}")

    @classmethod
    def parse(cls, text: str | AxisOrder) -> AxisOrder:
        """Read DS9's three-digit form.

        Args:
            text: An `AxisOrder`, or a string such as "123" or "321".

        Returns:
            The order.

        Raises:
            ValueError: If the string is not a permutation of 1, 2 and 3.
        """
        if isinstance(text, AxisOrder):
            return text
        digits = str(text).strip()
        if len(digits) != CUBE_AXES or not digits.isdigit():
            raise ValueError(f"axis order must be three digits, got {text!r}")
        return cls(int(digits[0]), int(digits[1]), int(digits[2]))

    def __str__(self) -> str:
        return f"{self.x}{self.y}{self.z}"

    @property
    def is_default(self) -> bool:
        """True for DS9's `123`."""
        return (self.x, self.y, self.z) == (1, 2, 3)


#: The six orders DS9's Axis Order menu offers, in its order.
AXIS_ORDERS: tuple[AxisOrder, ...] = (
    AxisOrder(1, 2, 3),
    AxisOrder(1, 3, 2),
    AxisOrder(2, 1, 3),
    AxisOrder(2, 3, 1),
    AxisOrder(3, 1, 2),
    AxisOrder(3, 2, 1),
)


def is_cube(data: NDArray[np.floating] | None) -> bool:
    """Whether an array has three or more axes worth stepping through.

    A degenerate axis -- `NAXIS3 = 1`, which many instruments write -- does
    not make a cube, and DS9 does not offer its dialog for one either.
    """
    if data is None or data.ndim < CUBE_AXES:
        return False
    return len([length for length in data.shape if length > 1]) >= CUBE_AXES


class CubeHandler:
    """Slices a data cube, in whichever axis order is asked for.

    Attributes:
        data: The cube array, in its on-disk (numpy) order.
        header: The FITS header, if there is one.
        wcs: The cube's WCS, if the header yielded one.
    """

    def __init__(
        self,
        data: NDArray[np.floating] | None = None,
        header: fits.Header | None = None,
    ) -> None:
        """Initialize CubeHandler.

        Args:
            data: The cube array. Three or more axes; the extra ones are
                taken at index zero, as DS9 does.
            header: The FITS header.

        Raises:
            ValueError: If `data` has fewer than three axes.
        """
        self._data: NDArray[np.floating] | None = data
        self._header: fits.Header | None = header
        self._wcs: WCS | None = None

        if header is not None:
            try:
                self._wcs = WCS(header)
            except Exception:
                self._wcs = None

        if data is not None and data.ndim < CUBE_AXES:
            raise ValueError(f"expected a cube of {CUBE_AXES} or more axes, got {data.ndim}")

    # -- the cube ------------------------------------------------------------

    @property
    def data(self) -> NDArray[np.floating] | None:
        """The cube array."""
        return self._data

    @property
    def header(self) -> fits.Header | None:
        """The FITS header."""
        return self._header

    @property
    def wcs(self) -> WCS | None:
        """The cube's WCS."""
        return self._wcs

    @property
    def shape(self) -> tuple[int, ...] | None:
        """The array shape, in numpy order."""
        return None if self._data is None else tuple(int(n) for n in self._data.shape)

    @property
    def n_channels(self) -> int | None:
        """Slices along the default order's third axis."""
        return None if self._data is None else self.depth()

    def _numpy_axis(self, fits_axis: int) -> int:
        """The numpy axis holding one FITS axis.

        FITS counts axes from the fastest-varying; numpy from the slowest, so
        the two are reverses of each other. An array with more than three
        axes keeps its leading ones, which is why this counts from the end.
        """
        if self._data is None:
            raise ValueError("no cube loaded")
        if not 1 <= fits_axis <= self._data.ndim:
            raise ValueError(f"no FITS axis {fits_axis} in a {self._data.ndim}D array")
        return self._data.ndim - fits_axis

    def depth(self, order: AxisOrder | str = AxisOrder()) -> int:
        """How many slices the given order has to step through.

        Args:
            order: The axis order, as an `AxisOrder` or "123"-style string.

        Returns:
            The length of the sliced axis, or 0 with no cube loaded.
        """
        if self._data is None:
            return 0
        return int(self._data.shape[self._numpy_axis(AxisOrder.parse(order).z)])

    def get_slice(
        self,
        channel: int,
        order: AxisOrder | str = AxisOrder(),
    ) -> NDArray[np.floating] | None:
        """One 2D slice, laid out for display.

        Args:
            channel: The slice index along the order's third axis, from zero.
            order: The axis order.

        Returns:
            The slice with the order's y axis down the rows and its x axis
            across the columns, or None with no cube loaded.

        Raises:
            IndexError: If `channel` is outside the sliced axis.
        """
        if self._data is None:
            return None

        axes = AxisOrder.parse(order)
        depth = self.depth(axes)
        if not 0 <= channel < depth:
            raise IndexError(f"slice {channel} outside 0..{depth - 1}")

        plane = np.take(self._data, channel, axis=self._numpy_axis(axes.z))
        # Any axes beyond the third are taken at their first element, which
        # is what DS9 does with a four-dimensional file.
        while plane.ndim > 2:
            plane = plane[0]

        # After the take, the two remaining axes are the other two FITS axes
        # in descending FITS order. Transpose when the order wants them the
        # other way round.
        remaining = sorted((axes.x, axes.y), reverse=True)
        return plane.T if remaining[0] == axes.x else plane

    def get_spectrum(
        self,
        x: int,
        y: int,
        order: AxisOrder | str = AxisOrder(),
    ) -> NDArray[np.floating] | None:
        """The values down the sliced axis at one display position.

        Args:
            x: Column in the displayed slice.
            y: Row in the displayed slice.
            order: The axis order.

        Returns:
            One value per slice, or None with no cube loaded.
        """
        if self._data is None:
            return None
        planes = [self.get_slice(index, order) for index in range(self.depth(order))]
        return np.array(
            [plane[y, x] for plane in planes if plane is not None],
            dtype=self._data.dtype,
        )

    def slice_coordinate(
        self,
        channel: int,
        order: AxisOrder | str = AxisOrder(),
    ) -> tuple[float, str] | None:
        """The world coordinate of one slice, and its unit.

        DS9's cube dialog shows this beside the slider, so a spectral cube
        reads in frequency or velocity rather than channel number.

        Args:
            channel: The slice index, from zero.
            order: The axis order.

        Returns:
            (value, unit), or None when the header carries no scale for that
            axis.
        """
        if self._header is None:
            return None
        axis = AxisOrder.parse(order).z
        crval = self._header.get(f"CRVAL{axis}")
        cdelt = self._header.get(f"CDELT{axis}", self._header.get(f"CD{axis}_{axis}"))
        crpix = self._header.get(f"CRPIX{axis}", 1.0)
        if crval is None or cdelt is None:
            return None
        unit = str(self._header.get(f"CUNIT{axis}", "")).strip()
        # FITS pixels count from one.
        value = float(crval) + (channel + 1 - float(crpix)) * float(cdelt)
        return value, unit

    def get_channel_wcs(self, channel: int) -> WCS | None:
        """A 2D WCS for one slice of the default order.

        Args:
            channel: The slice index. Unused for a separable WCS, but kept in
                the signature because a cube with a coupled third axis would
                need it.

        Returns:
            The celestial part of the cube's WCS, or None.
        """
        if self._wcs is None:
            return None
        try:
            return self._wcs.celestial
        except Exception:
            return None

    # -- reductions, for M7's analysis --------------------------------------

    def moment0(self) -> NDArray[np.floating] | None:
        """The integrated-intensity map, summing the default slice axis."""
        return self.collapse(method="sum")

    def moment1(self) -> NDArray[np.floating] | None:
        """The intensity-weighted mean channel."""
        if self._data is None:
            return None
        total = np.nansum(self._data, axis=0)
        channels = np.arange(self._data.shape[0], dtype=np.float64)
        weighted = np.nansum(self._data * channels[:, None, None], axis=0)
        with np.errstate(invalid="ignore", divide="ignore"):
            return np.where(total != 0, weighted / total, np.nan)

    def moment2(self) -> NDArray[np.floating] | None:
        """The intensity-weighted channel dispersion."""
        if self._data is None:
            return None
        mean = self.moment1()
        if mean is None:
            return None
        total = np.nansum(self._data, axis=0)
        channels = np.arange(self._data.shape[0], dtype=np.float64)
        spread = (channels[:, None, None] - mean[None, :, :]) ** 2
        weighted = np.nansum(self._data * spread, axis=0)
        with np.errstate(invalid="ignore", divide="ignore"):
            return np.sqrt(np.where(total != 0, weighted / total, np.nan))

    def collapse(
        self,
        start_channel: int | None = None,
        end_channel: int | None = None,
        method: str = "sum",
    ) -> NDArray[np.floating] | None:
        """Reduce a run of slices to one image.

        Args:
            start_channel: First slice, inclusive. None for the first.
            end_channel: Last slice, exclusive. None for the end.
            method: One of `COLLAPSE_METHODS`.

        Returns:
            The reduced image, or None with no cube loaded.

        Raises:
            ValueError: If `method` is not one of `COLLAPSE_METHODS`.
        """
        if self._data is None:
            return None
        reduce = COLLAPSE_METHODS.get(method)
        if reduce is None:
            raise ValueError(
                f"unknown collapse method {method!r}; expected one of "
                f"{', '.join(sorted(COLLAPSE_METHODS))}"
            )
        return reduce(self._data[start_channel:end_channel], axis=0)
