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
DS9's Bin: turning a FITS table into an image.

An events table is a list of photons, each with a position and whatever else
the instrument recorded. To display it, DS9 lays a grid over two of its
columns and counts -- or sums a third column's values -- into each cell. Its
Bin menu (`ds9/library/mbin.tcl`) is the parameters of that: the function
(Average or Sum, defaulting to Sum), a bin factor of 1 to 256 saying how many
column units go into one image pixel, a buffer size from 128 to 8192 capping
the image's dimensions, a depth for a third axis, and a row filter.

This is the half of PLAN.md §3.4 that M4 left: it gave events tables the
plain two-dimensional count, which is what makes them displayable at all,
and left the rest here.

**The bin function** is what `ds9/doc/ref/bin.html` says it is: "Average --
all pixel values that fall into one pixel bin are averaged. Sum -- all pixel
values that fall into one pixel bin are summed." With no third column each
row contributes one, so Sum is the row count and Average is one everywhere;
with a third column named -- DS9's `[bin=x,y,pha]` -- it is that column's
values that are summed or averaged.

**Bin centring.** Where the grid sits matters as much as how fine it is. DS9
looks for the axis's extent in four places, in this order, and falls back to
the data's own middle:

1. `TDMINn` / `TDMAXn` -- the actual data range, which some missions write.
2. `TLMINn` / `TLMAXn` -- the column's legal range.
3. `TALENn` -- the axis length, taken as 1..TALEN.
4. `AXLENn` -- the same, under an older name.

**Two things this does not follow DS9 on, both recorded rather than hidden.**

DS9 describes the buffer size as "the overall size of the image generated
... no relation to min and max values of the columns", which read strictly
would make every binned image exactly `buffer_size` square with the data
centred in it and the rest blank -- 1024 by 1024 for a 512-unit detector at
the default. The buffer is treated here as a *cap* instead: the image is as
big as the data needs, up to the buffer. That is the reading under which
"Bin to Fit calculate[s] a bin block factor ... that will allow the entire
data space to be displayed", which is DS9's own wording for Fit, means
anything -- with a fixed size, changing the factor could not make anything
fit.

`BinSettings.depth` is recorded and offered in the Binning Parameters dialog
but only two-dimensional binning is implemented. DS9 can bin a table into a
cube, one plane per slice of a third column; that needs the depth to become a
third histogram axis.

Author: Yogesh Wadadekar
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from enum import Enum
from typing import Any, cast

import numpy as np
from astropy.io import fits
from numpy.typing import NDArray

from .file_spec import BinSpec
from .image_data import ImageData

#: The bin factors DS9's menu offers.
BIN_FACTORS: tuple[float, ...] = (1, 2, 4, 8, 16, 32, 64, 128, 256)

#: The buffer sizes DS9's menu offers, and its default.
BUFFER_SIZES: tuple[int, ...] = (128, 256, 512, 1024, 2048, 4096, 8192)
DEFAULT_BUFFER_SIZE = 1024

#: The card pairs DS9 consults for an axis's extent, in its order of
#: preference. A single-card entry gives a range of 1..value.
EXTENT_CARDS: tuple[tuple[str, str | None], ...] = (
    ("TDMIN", "TDMAX"),
    ("TLMIN", "TLMAX"),
    ("TALEN", None),
    ("AXLEN", None),
)


class BinFunction(Enum):
    """What goes into a bin.

    DS9's default is Sum: a bin holds the count of rows that fall in it, or
    the sum of the depth column's values over them.
    """

    SUM = "sum"
    AVERAGE = "average"


class BinTableError(ValueError):
    """A table that cannot be binned, for the reason given."""


@dataclass(frozen=True)
class BinSettings:
    """DS9's Bin menu and Binning Parameters dialog, as one object."""

    function: BinFunction = BinFunction.SUM
    #: Column units per image pixel. DS9 allows fractions below one, which
    #: oversample; its menu offers only the integers of `BIN_FACTORS`.
    factor: float = 1.0
    #: The largest image either axis may have, DS9's `bin(buffersize)`.
    buffer_size: int = DEFAULT_BUFFER_SIZE
    #: Planes along a third column, DS9's `bin(depth)`.
    depth: int = 1
    #: A row filter, in the syntax `core/file_spec.py` parses out of a
    #: specification's brackets.
    filter: str = ""

    def with_factor(self, factor: float) -> BinSettings:
        """A copy at a different bin factor.

        Raises:
            BinTableError: If the factor is not positive.
        """
        if factor <= 0:
            raise BinTableError(f"bin factor must be positive, got {factor}")
        return replace(self, factor=float(factor))

    def describe(self) -> str:
        """How the settings read in the status bar."""
        return f"{self.function.value}, bin {self.factor:g}, buffer {self.buffer_size}"


def column_names(hdu: fits.hdu.base.ExtensionHDU) -> tuple[str, ...]:
    """A table HDU's column names, uppercased."""
    columns = getattr(hdu, "columns", None)
    if columns is None:
        return ()
    try:
        return tuple(str(name).upper() for name in columns.names)
    except Exception:
        return ()


def column_index(hdu: fits.hdu.base.ExtensionHDU, name: str) -> int | None:
    """A column's one-based position, for reading its `T*` cards."""
    names = column_names(hdu)
    wanted = name.strip().upper()
    return names.index(wanted) + 1 if wanted in names else None


def column_extent(
    hdu: fits.hdu.base.ExtensionHDU,
    name: str,
    values: NDArray[np.floating] | None = None,
) -> tuple[float, float]:
    """The range an axis should cover, in column units.

    Follows DS9's order of preference through `EXTENT_CARDS`, falling back to
    the values' own range -- and to 0..1 when there are no values either.

    Args:
        hdu: The table HDU.
        name: The column's name.
        values: The column's data, for the fallback.

    Returns:
        (low, high) inclusive, with `low < high` guaranteed.
    """
    index = column_index(hdu, name)
    header = hdu.header

    if index is not None:
        for low_card, high_card in EXTENT_CARDS:
            low = header.get(f"{low_card}{index}")
            if not isinstance(low, (int, float)):
                continue
            if high_card is None:
                # TALEN and AXLEN give a length, so the axis runs 1..length.
                return 1.0, float(low)
            high = header.get(f"{high_card}{index}")
            if isinstance(high, (int, float)):
                return _ordered(float(low), float(high))

    if values is not None and values.size:
        finite = values[np.isfinite(values)]
        if finite.size:
            return _ordered(float(np.floor(finite.min())), float(np.ceil(finite.max())))
    return 0.0, 1.0


def _ordered(low: float, high: float) -> tuple[float, float]:
    """Put an extent in order, widening a degenerate one."""
    if high < low:
        low, high = high, low
    return low, (high if high > low else low + 1.0)


def bin_edges(
    extent: tuple[float, float],
    settings: BinSettings,
) -> NDArray[np.floating]:
    """The grid over one axis.

    The grid spans exactly `low - 0.5` to `high + 0.5`, the pixel-boundary
    reading of an inclusive integer range, so a column running 1..64 at a
    factor of one gives 64 pixels rather than 63 -- as it does in DS9 -- and
    no value in the extent can fall off an edge whatever the factor. Anchoring
    on the bin *centres* instead loses everything above the last centre plus
    half a bin: at a factor of four, a 1..64 column lost every event above 63.

    The buffer size caps the count, since a wide column at a fine factor
    would otherwise ask for an image of millions of pixels a side.

    Args:
        extent: (low, high) in column units.
        settings: The factor and buffer size to use.

    Returns:
        The bin edges, at least two of them.
    """
    low, high = extent
    span = high - low + 1.0
    factor = max(float(settings.factor), 1e-9)
    count = max(1, int(round(span / factor)))
    count = min(count, max(1, int(settings.buffer_size)))
    step = span / count
    return (low - 0.5) + np.arange(count + 1, dtype=np.float64) * step


def apply_filter(
    hdu: fits.hdu.base.ExtensionHDU,
    expression: str,
) -> NDArray[np.bool_] | None:
    """Which rows a filter expression keeps.

    The expression is funtools' syntax -- `pha>5&&ccd_id==3` -- which is
    close enough to Python's that it can be evaluated over the columns as
    numpy arrays once `&&` and `||` are translated. Each conjunct is
    parenthesised as part of that translation: Python binds `&` tighter than
    `>`, so a bare substitution turns `pha>50&&x<32` into
    `pha > (50 & x) < 32`, which is a different question and usually a type
    error. Column names are the only names in scope, so an expression naming
    anything else fails rather than reaching the interpreter's globals.

    Args:
        hdu: The table HDU.
        expression: The filter, or empty for no filtering.

    Returns:
        A boolean mask, or None when there is nothing to filter on.

    Raises:
        BinTableError: If the expression cannot be evaluated.
    """
    expression = (expression or "").strip()
    if not expression:
        return None

    data = hdu.data
    if data is None:
        return None

    scope: dict[str, Any] = {name: np.asarray(data[name]) for name in column_names(hdu) if name in data.names}
    # Column names are case-insensitive in DS9, so offer both spellings.
    scope.update({name.lower(): array for name, array in dict(scope).items()})

    translated = "(" + expression.replace("&&", ") & (").replace("||", ") | (") + ")"
    try:
        # No builtins: only the columns are in scope, so an expression cannot
        # reach anything else even though it comes from a file name.
        mask = eval(translated, {"__builtins__": {}}, scope)
    except Exception as exc:
        raise BinTableError(f"cannot apply filter {expression!r}: {exc}") from exc

    array = np.asarray(mask)
    if array.dtype != bool or array.shape != (len(data),):
        raise BinTableError(f"filter {expression!r} is not a row-by-row condition")
    return array


def bin_table(
    hdu: fits.hdu.base.ExtensionHDU,
    spec: BinSpec | None = None,
    settings: BinSettings | None = None,
) -> ImageData:
    """Turn a FITS table into an image.

    Args:
        hdu: The table HDU.
        spec: The parsed `bin=` group, naming the two axis columns and
            optionally a third to bin the values of. Defaults to DS9's X and
            Y.
        settings: The function, factor, buffer size, depth and filter.
            Defaults to DS9's defaults.

    Returns:
        The image, with a WCS built from the axis columns' own `TCRVL`,
        `TCRPX`, `TCDLT` and `TCTYP` cards when the table carries them.

    Raises:
        BinTableError: If a named column is not in the table, or a filter
            cannot be applied.
    """
    spec = spec or BinSpec()
    settings = settings or BinSettings()

    data = hdu.data
    available = column_names(hdu)
    axes = spec.columns[:2]
    for name in axes:
        if name.strip().upper() not in available:
            raise BinTableError(f"no column {name!r} to bin on; the table has {', '.join(available)}")

    mask = apply_filter(hdu, settings.filter or spec.filter)
    values = [np.asarray(data[name.strip().upper()], dtype=np.float64) for name in axes]
    weights = _depth_values(hdu, spec, data)
    if mask is not None:
        values = [column[mask] for column in values]
        if weights is not None:
            weights = weights[mask]

    edges = [
        bin_edges(column_extent(hdu, name, column), settings)
        for name, column in zip(axes, values, strict=True)
    ]
    # numpy accepts explicit bin edges, but its stubs type `bins` as only a
    # count or a sequence of counts, so the pair has to be cast.
    bins = cast("Any", (edges[0], edges[1]))

    totals, _x, _y = np.histogram2d(values[0], values[1], bins=bins, weights=weights)
    if settings.function is BinFunction.AVERAGE:
        counts, _x, _y = np.histogram2d(values[0], values[1], bins=bins)
        with np.errstate(invalid="ignore", divide="ignore"):
            totals = np.where(counts > 0, totals / counts, 0.0)

    # histogram2d indexes [x, y]; an image is [row, column] = [y, x].
    image = np.ascontiguousarray(totals.T.astype(np.float32))
    return ImageData(data=image, header=bin_header(hdu, axes, edges))


def _depth_values(
    hdu: fits.hdu.base.ExtensionHDU,
    spec: BinSpec,
    data: Any,
) -> NDArray[np.floating] | None:
    """The third column's values, to bin instead of counting rows.

    Returns None for DS9's default, which is to count.

    Raises:
        BinTableError: If the named column is not in the table.
    """
    if len(spec.columns) < 3:
        return None
    name = spec.columns[2].strip().upper()
    if name not in column_names(hdu):
        raise BinTableError(f"no column {spec.columns[2]!r} to bin the values of")
    return np.asarray(data[name], dtype=np.float64)


def bin_header(
    hdu: fits.hdu.base.ExtensionHDU,
    axes: tuple[str, ...],
    edges: list[NDArray[np.floating]],
) -> fits.Header:
    """Build an image header for a binned table.

    Carries over the axis columns' own world-coordinate cards -- `TCTYPn`,
    `TCRVLn`, `TCRPXn`, `TCDLTn` -- which is how DS9 gives a binned events
    image sky coordinates. A table without them yields a header with no WCS.
    """
    header = fits.Header()
    header["OBJECT"] = hdu.header.get("OBJECT", "")

    for axis, (name, axis_edges) in enumerate(zip(axes, edges, strict=True), start=1):
        index = column_index(hdu, name)
        if index is None:
            continue
        ctype = hdu.header.get(f"TCTYP{index}")
        crval = hdu.header.get(f"TCRVL{index}")
        crpix = hdu.header.get(f"TCRPX{index}")
        cdelt = hdu.header.get(f"TCDLT{index}")
        if ctype is None or crval is None or crpix is None or cdelt is None:
            continue

        step = float(axis_edges[1] - axis_edges[0])
        first_centre = float(axis_edges[0]) + step / 2.0
        header[f"CTYPE{axis}"] = ctype
        header[f"CRVAL{axis}"] = crval
        # Column value v lands on image pixel (v - first_centre) / step + 1.
        header[f"CRPIX{axis}"] = (float(crpix) - first_centre) / step + 1.0
        # A bin wider than one column unit stretches the sky per pixel with it.
        header[f"CDELT{axis}"] = float(cdelt) * step

    return header
