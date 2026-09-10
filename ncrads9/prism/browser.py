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
What DS9's Prism browses: a file's extensions, headers and table rows.

Prism is a FITS browser, not a spectrum tool -- `prism.tcl` builds an
extension list, a header pane and a table of the selected extension's rows,
and its buttons load an extension into a frame or plot a column. (What this
package held before was a spectral-analysis skeleton nothing called, which
was a guess at the name rather than at DS9.)

The reading is here and the window is in `ui/dialogs/prism_dialog.py`, so
paging, column extraction and the header text can be tested without one.

Author: Yogesh Wadadekar
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
from astropy.io import fits
from numpy.typing import NDArray

from ..core.fits_handler import HDUInfo, HDUKind, classify

#: How many rows Prism shows at once (`iprism(block)`, `prism.tcl:16`).
BLOCK = 1000

#: How many rows and columns the empty table keeps, so the window has a
#: shape before a file is opened (`iprism(minrows)`, `mincols`).
MIN_ROWS = 20
MIN_COLS = 10


class PrismBrowser:
    """One file, opened for browsing.

    Nothing is read until it is asked for, and the file is held open only
    while a read is in progress: a Prism window can sit on a file for as
    long as it likes without keeping a descriptor.
    """

    def __init__(self) -> None:
        #: The file being browsed, or None.
        self.path: Path | None = None
        #: Its extensions, in file order.
        self.extensions: list[HDUInfo] = []
        #: Which extension is being shown.
        self.index = 0
        #: The first row of the block on screen, counting from zero.
        self.start = 0

    # -- opening and closing --------------------------------------------------

    def open(self, path: str | Path) -> list[HDUInfo]:
        """Open a file and describe its extensions.

        Args:
            path: The FITS file.

        Returns:
            One `HDUInfo` per extension.

        Raises:
            OSError: If the file cannot be read.
        """
        target = Path(path)
        with fits.open(target, memmap=False) as hdus:
            extensions = [classify(hdu, index) for index, hdu in enumerate(hdus)]

        self.path = target
        self.extensions = extensions
        self.start = 0
        self.index = self.default_index()
        return extensions

    def clear(self) -> None:
        """Forget the file, as DS9's Clear does."""
        self.path = None
        self.extensions = []
        self.index = 0
        self.start = 0

    @property
    def is_open(self) -> bool:
        """Whether a file is being browsed."""
        return self.path is not None

    def default_index(self) -> int:
        """Which extension to show first.

        DS9 skips leading header-only extensions (`prism.tcl:536`), because
        the primary of a multi-extension file is usually empty and showing
        it would say nothing about the file.
        """
        for info in self.extensions:
            if info.kind is not HDUKind.EMPTY:
                return info.index
        return 0

    # -- the selected extension -------------------------------------------------

    def select(self, index: int) -> HDUInfo | None:
        """Show one extension, from the start of its rows."""
        if not 0 <= index < len(self.extensions):
            return None
        self.index = index
        self.start = 0
        return self.extensions[index]

    @property
    def current(self) -> HDUInfo | None:
        """The extension being shown, or None with no file."""
        if not self.extensions:
            return None
        return self.extensions[min(self.index, len(self.extensions) - 1)]

    @property
    def is_table(self) -> bool:
        """Whether the shown extension has rows to page through."""
        info = self.current
        return bool(info is not None and info.rows)

    @property
    def rows(self) -> int:
        """How many rows the shown extension has, or zero for an image."""
        info = self.current
        return int(info.rows) if info is not None and info.rows else 0

    @property
    def columns(self) -> tuple[str, ...]:
        """The shown extension's column names, or () for an image."""
        info = self.current
        return info.columns if info is not None else ()

    def header_text(self, index: int | None = None) -> str:
        """One extension's header as DS9's Prism shows it: the cards.

        Args:
            index: Which extension, or None for the shown one.

        Returns:
            The header's cards, one per line, or "" with no file.
        """
        if self.path is None:
            return ""
        which = self.index if index is None else index
        with fits.open(self.path, memmap=False) as hdus:
            if not 0 <= which < len(hdus):
                return ""
            header = hdus[which].header
        return "\n".join(str(card).rstrip() for card in header.cards)

    # -- the rows -------------------------------------------------------------------

    def block(self) -> tuple[list[str], list[list[str]]]:
        """The block of rows on screen.

        Returns:
            (column names, rows), each row a list of strings in column
            order. Empty for an image extension, which has no rows.
        """
        if self.path is None or not self.is_table:
            return ([], [])

        with fits.open(self.path, memmap=False) as hdus:
            data = hdus[self.index].data
            if data is None:
                return ([], [])
            names = list(data.columns.names)
            stop = min(self.start + BLOCK, len(data))
            block = data[self.start : stop]
            rows = [[format_value(value) for value in tuple(row)] for row in block]
        return (names, rows)

    def column(self, name: str) -> NDArray[np.floating]:
        """One whole column, for a plot or a histogram.

        The whole column, not the block on screen: a plot of a thousand
        rows out of a million would be a plot of the wrong thing.

        Raises:
            KeyError: If the extension has no such column.
        """
        if self.path is None or not self.is_table:
            raise KeyError(name)
        with fits.open(self.path, memmap=False) as hdus:
            data = hdus[self.index].data
            if data is None or name not in data.columns.names:
                raise KeyError(name)
            values = np.asarray(data[name])
        # A vector column cannot be plotted against a scalar one; its first
        # element is what DS9's plot dialog offers.
        if values.ndim > 1:
            values = values[:, 0]
        return np.asarray(values, dtype=np.float64)

    # -- paging through them ----------------------------------------------------------

    def first_block(self) -> int:
        """Show the first block."""
        self.start = 0
        return self.start

    def next_block(self) -> int:
        """Show the next block, stopping at the last one."""
        if self.start + BLOCK >= self.rows:
            return self.last_block()
        self.start += BLOCK
        return self.start

    def previous_block(self) -> int:
        """Show the previous block, stopping at the first."""
        self.start = max(0, self.start - BLOCK)
        return self.start

    def last_block(self) -> int:
        """Show the block the last row is in."""
        if self.rows <= 0:
            self.start = 0
        else:
            self.start = ((self.rows - 1) // BLOCK) * BLOCK
        return self.start

    def goto_row(self, row: int) -> int:
        """Show the block one row is in, and say where in it that row is.

        Args:
            row: The row, counting from one as DS9's dialog does.

        Returns:
            The row's offset within the block on screen, from zero.
        """
        if self.rows <= 0:
            return 0
        wanted = max(1, min(int(row), self.rows)) - 1
        self.start = (wanted // BLOCK) * BLOCK
        return wanted - self.start


def format_value(value) -> str:
    """One table value as a string, kept short enough for a cell."""
    if isinstance(value, (bytes, np.bytes_)):
        return value.decode("utf-8", "replace").strip()
    if isinstance(value, np.ndarray):
        # A vector cell: its first few elements, so the row stays readable.
        shown = ", ".join(format_value(item) for item in value.ravel()[:4])
        return f"[{shown}{' ...' if value.size > 4 else ''}]"
    if isinstance(value, (float, np.floating)):
        # %g rather than str, so a whole number reads as one: a column of
        # integers read from a text file arrives as floats.
        return f"{float(value):.10g}"
    return str(value)
