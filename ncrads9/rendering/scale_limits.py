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
Where the clip limits come from: DS9's Limits section of the Scale menu.

DS9 separates *how* data is stretched between two values -- the transfer
function, which lives in `scale_algorithms.py` -- from *which two values*.
The second is a whole menu section of its own (`ds9/library/mscale.tcl`):

* a **mode**: Min Max, one of eight percentile presets, ZScale, ZMax, or User
  limits typed into the Scale Parameters dialog;
* a **min/max method** for the Min Max mode: Scan every pixel, Sample every
  nth, or take the header's `DATAMIN`/`DATAMAX` or `IRAF-MIN`/`IRAF-MAX`;
* a **scope**: Local, meaning the slice on screen, or Global, meaning the
  whole extension including the slices that are not;
* **Use DATASEC**, which restricts everything above to the region the header
  calls real data rather than overscan;
* and the **ZScale parameters** -- contrast, sample count, samples per line.

`ScaleLimits` is that set of choices as one immutable object, and
`compute_limits` is the single function that turns it and an array into a
pair of numbers. Keeping it apart from the controller means every mode can be
tested against known data without a window, and gives M8's XPA `scale` access
point one object to read and write.

Author: Yogesh Wadadekar
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from enum import Enum

import numpy as np
from numpy.typing import NDArray

from .scale_algorithms import compute_zscale_limits

#: DS9's percentile presets, in menu order. The number is the fraction of
#: pixels kept, centred on the median: 99.5% clips 0.25% off each end.
PERCENT_PRESETS: tuple[float, ...] = (99.5, 99.0, 98.0, 97.0, 96.0, 95.0, 92.5, 90.0)

#: DS9's ZScale defaults (`zscale(contrast)`, `zscale(sample)`, `zscale(line)`).
DEFAULT_CONTRAST = 0.25
DEFAULT_SAMPLES = 600
DEFAULT_SAMPLES_PER_LINE = 120

#: DS9's `minmax(sample)` -- take every nth pixel when sampling.
DEFAULT_SAMPLE_INCREMENT = 20

#: Returned when there is nothing finite to measure.
FALLBACK_LIMITS: tuple[float, float] = (0.0, 1.0)


class LimitMode(Enum):
    """Where the clip limits come from."""

    MINMAX = "minmax"
    #: One of `PERCENT_PRESETS`, the exact figure in `ScaleLimits.percent`.
    PERCENT = "percent"
    ZSCALE = "zscale"
    #: ZScale's low limit with the data's own maximum, which DS9 calls ZMax.
    ZMAX = "zmax"
    #: The numbers the user typed.
    USER = "user"


class MinMaxMethod(Enum):
    """How the Min Max mode finds the extremes."""

    #: Every pixel.
    SCAN = "scan"
    #: Every nth pixel, `ScaleLimits.sample_increment` apart.
    SAMPLE = "sample"
    #: The header's `DATAMIN` and `DATAMAX`.
    DATAMIN = "datamin"
    #: The header's `IRAF-MIN` and `IRAF-MAX`.
    IRAF = "irafminmax"


class LimitScope(Enum):
    """Which pixels the limits are measured over."""

    #: The slice on screen.
    LOCAL = "local"
    #: The whole extension, so stepping a cube does not restretch it.
    GLOBAL = "global"


#: The header cards each min/max method reads, low then high.
METHOD_CARDS: dict[MinMaxMethod, tuple[str, str]] = {
    MinMaxMethod.DATAMIN: ("DATAMIN", "DATAMAX"),
    MinMaxMethod.IRAF: ("IRAF-MIN", "IRAF-MAX"),
}


@dataclass(frozen=True)
class ScaleLimits:
    """Everything that decides the clip limits, at DS9's defaults."""

    mode: LimitMode = LimitMode.MINMAX
    #: The preset in force when `mode` is PERCENT.
    percent: float = 99.5
    method: MinMaxMethod = MinMaxMethod.SCAN
    sample_increment: int = DEFAULT_SAMPLE_INCREMENT
    scope: LimitScope = LimitScope.LOCAL
    use_datasec: bool = True

    contrast: float = DEFAULT_CONTRAST
    samples: int = DEFAULT_SAMPLES
    samples_per_line: int = DEFAULT_SAMPLES_PER_LINE

    #: The limits typed in for `LimitMode.USER`.
    user_low: float = 0.0
    user_high: float = 1.0

    #: DS9's Log Exponent, the `a` of its log transfer function. Not a limit,
    #: but the Scale menu's own parameter and stored with its siblings.
    log_exponent: float = 1000.0

    def with_mode(self, mode: LimitMode, percent: float | None = None) -> ScaleLimits:
        """A copy in a different mode.

        Args:
            mode: The mode to switch to.
            percent: The preset, when switching to `LimitMode.PERCENT`.

        Returns:
            The new settings.

        Raises:
            ValueError: If `percent` is not one of `PERCENT_PRESETS`.
        """
        if mode is LimitMode.PERCENT:
            wanted = self.percent if percent is None else float(percent)
            if wanted not in PERCENT_PRESETS:
                raise ValueError(
                    f"{wanted} is not one of DS9's presets: "
                    f"{', '.join(f'{value}%' for value in PERCENT_PRESETS)}"
                )
            return replace(self, mode=mode, percent=wanted)
        return replace(self, mode=mode)

    def describe(self) -> str:
        """How the mode reads in the status bar."""
        if self.mode is LimitMode.PERCENT:
            return f"{self.percent:g}%"
        if self.mode is LimitMode.MINMAX:
            return f"minmax ({self.method.value})"
        if self.mode is LimitMode.USER:
            return f"user {self.user_low:g} .. {self.user_high:g}"
        return self.mode.value


def datasec_slice(header: object | None) -> tuple[slice, slice] | None:
    """The `DATASEC` region of an image, as numpy slices.

    `DATASEC` is written `[x0:x1,y0:y1]` in one-based inclusive FITS pixels
    and marks the part of the array that is real data rather than overscan or
    bias. DS9's Use DATASEC restricts the limit measurement to it.

    Args:
        header: A FITS header or mapping, or None.

    Returns:
        (rows, columns) slices, or None when there is no usable `DATASEC`.
    """
    if header is None:
        return None
    try:
        value = header.get("DATASEC")
    except AttributeError:
        return None
    if not value:
        return None

    from ..core.mosaic import parse_section

    placement = parse_section(value)
    if placement is None:
        return None
    return slice(placement.y0, placement.y1), slice(placement.x0, placement.x1)


def _measurable(
    data: NDArray[np.floating] | None,
    settings: ScaleLimits,
    header: object | None,
) -> NDArray[np.floating] | None:
    """The pixels a measurement should look at, or None if there are none.

    Applies Use DATASEC and, for the Sample method, the sample increment.
    Returns a flat array of finite values.
    """
    if data is None or data.size == 0:
        return None

    if settings.use_datasec:
        region = datasec_slice(header)
        if region is not None and data.ndim >= 2:
            leading = (slice(None),) * (data.ndim - 2)
            candidate = data[(*leading, *region)]
            if candidate.size:
                data = candidate

    flat = np.ravel(data)
    if settings.mode is LimitMode.MINMAX and settings.method is MinMaxMethod.SAMPLE:
        step = max(1, int(settings.sample_increment))
        flat = flat[::step]

    finite = flat[np.isfinite(flat)]
    return finite if finite.size else None


def _header_limits(
    settings: ScaleLimits,
    header: object | None,
) -> tuple[float, float] | None:
    """The limits a header-based min/max method asks for, if present."""
    cards = METHOD_CARDS.get(settings.method)
    if cards is None or header is None:
        return None
    try:
        low, high = header.get(cards[0]), header.get(cards[1])
    except AttributeError:
        return None
    if not isinstance(low, (int, float)) or not isinstance(high, (int, float)):
        return None
    return float(low), float(high)


def percentile_limits(values: NDArray[np.floating], percent: float) -> tuple[float, float]:
    """The central `percent` of a distribution.

    Args:
        values: Finite pixel values, in any order.
        percent: The fraction to keep, 0 to 100.

    Returns:
        (low, high). A preset of 99.5 clips a quarter of a percent off each
        end, which is how DS9 words it.
    """
    tail = (100.0 - float(percent)) / 2.0
    low = float(np.percentile(values, tail))
    high = float(np.percentile(values, 100.0 - tail))
    return low, high


def compute_limits(
    data: NDArray[np.floating] | None,
    settings: ScaleLimits | None = None,
    header: object | None = None,
    global_data: NDArray[np.floating] | None = None,
) -> tuple[float, float]:
    """The clip limits for one array under one set of settings.

    Args:
        data: The slice on screen.
        settings: The mode and its parameters. Defaults to DS9's defaults.
        header: The extension's header, for `DATASEC` and the header-based
            min/max methods.
        global_data: The whole extension, used instead of `data` when the
            scope is Global. Ignored when absent, so a caller with only one
            array need not pass it twice.

    Returns:
        (low, high), always with `low <= high`. Falls back to (0, 1) when
        there is nothing finite to measure, and widens a degenerate range so
        the caller never divides by zero.
    """
    settings = settings or ScaleLimits()

    if settings.mode is LimitMode.USER:
        return _ordered(settings.user_low, settings.user_high)

    source = data
    if settings.scope is LimitScope.GLOBAL and global_data is not None:
        source = global_data

    if settings.mode is LimitMode.MINMAX:
        from_header = _header_limits(settings, header)
        if from_header is not None:
            return _ordered(*from_header)

    values = _measurable(source, settings, header)
    if values is None:
        return FALLBACK_LIMITS

    if settings.mode is LimitMode.PERCENT:
        return _ordered(*percentile_limits(values, settings.percent))

    if settings.mode in (LimitMode.ZSCALE, LimitMode.ZMAX):
        low, high = compute_zscale_limits(
            values,
            contrast=settings.contrast,
            num_samples=max(1, int(settings.samples)),
        )
        if settings.mode is LimitMode.ZMAX:
            # DS9's ZMax: zscale's low limit against the data's own maximum,
            # so faint structure keeps its stretch and nothing bright clips.
            high = float(np.max(values))
        return _ordered(low, high)

    return _ordered(float(np.min(values)), float(np.max(values)))


def _ordered(low: float, high: float) -> tuple[float, float]:
    """Put two limits in order, widening a degenerate pair.

    A flat image would otherwise give `low == high` and make every consumer
    divide by zero.
    """
    low, high = float(low), float(high)
    if not np.isfinite(low) or not np.isfinite(high):
        return FALLBACK_LIMITS
    if high < low:
        low, high = high, low
    if high == low:
        return low, low + 1.0
    return low, high
