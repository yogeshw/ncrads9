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
The catalogues loaded on a frame, their symbols, and what is selected.

"DS9 allows you to overlay symbols from multiple catalogs on the current
image" (`ds9/doc/ref/catalog.html`), so this is a list rather than one
catalogue, and each entry carries its own filter, its own symbol rules and
its own selection.

A symbol rule is DS9's: a condition, a shape, a colour, two sizes, an angle
and a text, each of the last four an expression over the row's columns.
"For each row of the catalog, one or more conditional expressions are
evaluated. For the first expression to evaluate true, a given symbol is
displayed" -- first match wins, which is what makes a list of rules a
classification rather than a set of overlapping ones.

`catalog_display.py` used to be the home for this. It rendered DS9 *region
text* and shipped it to an external DS9 over XPA, which is a way of driving
somebody else's viewer rather than drawing in this one.

Author: Yogesh Wadadekar
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field, replace
from pathlib import Path

import numpy as np
from astropy.coordinates import SkyCoord
from astropy.table import Table
from numpy.typing import NDArray

from .catalog_filter import FilterError, evaluate, evaluate_text, evaluate_values
from .catalog_query import positions

#: The symbol shapes DS9's editor offers (`catsym.tcl:155`). The `point`
#: family is its Point cascade.
SHAPES: tuple[str, ...] = (
    "circle",
    "ellipse",
    "box",
    "vector",
    "text",
    "circle point",
    "box point",
    "diamond point",
    "cross point",
    "x point",
    "arrow point",
    "boxcircle point",
)

#: The colours it offers, the same eight as everywhere else in DS9.
COLORS: tuple[str, ...] = (
    "black",
    "white",
    "red",
    "green",
    "blue",
    "cyan",
    "magenta",
    "yellow",
)

#: What a symbol takes when nothing says otherwise -- DS9's `pcat(sym,*)`.
DEFAULT_SHAPE = "circle point"
DEFAULT_COLOR = "green"
DEFAULT_SIZE = 11.0
DEFAULT_WIDTH = 1

#: The version stamped into a saved symbol file.
SYMBOL_FORMAT_VERSION = 1


@dataclass
class Symbol:
    """One rule from DS9's symbol editor.

    Attributes:
        condition: When to use this symbol. Empty or "1" means always.
        shape: One of `SHAPES`.
        color: One of `COLORS`.
        width: The line width.
        size: The symbol's size, as an expression over the columns.
        size2: Its second size, for an ellipse or a box.
        angle: Its rotation, likewise an expression.
        text: The label above it -- text unless it uses `$` or `[expr ...]`.
        font, font_size: How the label is set.
        units: Whether the sizes are in image pixels or on the sky.
    """

    condition: str = ""
    shape: str = DEFAULT_SHAPE
    color: str = DEFAULT_COLOR
    width: int = DEFAULT_WIDTH
    size: str = str(int(DEFAULT_SIZE))
    size2: str = str(int(DEFAULT_SIZE))
    angle: str = "0"
    text: str = ""
    font: str = "helvetica"
    font_size: int = 10
    units: str = "physical"

    def to_dict(self) -> dict:
        """The rule as plain data, for a saved symbol file."""
        return {
            "condition": self.condition,
            "shape": self.shape,
            "color": self.color,
            "width": self.width,
            "size": self.size,
            "size2": self.size2,
            "angle": self.angle,
            "text": self.text,
            "font": self.font,
            "font_size": self.font_size,
            "units": self.units,
        }

    @classmethod
    def from_dict(cls, data: dict) -> Symbol:
        """Read a rule back, keeping defaults for anything absent."""
        blank = cls()
        return cls(
            condition=str(data.get("condition", "")),
            shape=str(data.get("shape", blank.shape)),
            color=str(data.get("color", blank.color)),
            width=int(data.get("width", blank.width)),
            size=str(data.get("size", blank.size)),
            size2=str(data.get("size2", blank.size2)),
            angle=str(data.get("angle", blank.angle)),
            text=str(data.get("text", "")),
            font=str(data.get("font", blank.font)),
            font_size=int(data.get("font_size", blank.font_size)),
            units=str(data.get("units", blank.units)),
        )


@dataclass
class DrawnSymbol:
    """One symbol to draw, after the rules have been evaluated.

    Attributes:
        row: Which row of the catalogue it came from, so a click on it can
            select that row.
        longitude, latitude: Where it goes, in degrees.
        shape, color, width, font, font_size: How it looks.
        size, size2, angle: Its dimensions, as numbers.
        text: Its label.
        selected: Whether the row is selected, which is drawn differently.
    """

    row: int
    longitude: float
    latitude: float
    shape: str = DEFAULT_SHAPE
    color: str = DEFAULT_COLOR
    width: int = DEFAULT_WIDTH
    size: float = DEFAULT_SIZE
    size2: float = DEFAULT_SIZE
    angle: float = 0.0
    text: str = ""
    font: str = "helvetica"
    font_size: int = 10
    selected: bool = False


@dataclass
class LoadedCatalog:
    """One catalogue on the frame.

    Attributes:
        name: What to call it -- the server's label, or the file's name.
        table: Every row, as loaded. The filter is applied on the way out
            rather than by deleting rows, so clearing a filter brings them
            back without re-querying.
        symbols: The symbol rules, first match winning.
        filter_expression: DS9's row filter.
        selected: Which rows of the *whole* table are selected.
        visible: Whether its symbols are drawn.
        source: Where it came from, for the header view.
    """

    name: str
    table: Table
    symbols: list[Symbol] = field(default_factory=lambda: [Symbol()])
    filter_expression: str = ""
    selected: set[int] = field(default_factory=set)
    visible: bool = True
    source: str = ""

    def __len__(self) -> int:
        return len(self.table)

    @property
    def columns(self) -> list[str]:
        """The catalogue's column names."""
        return list(self.table.colnames)

    def mask(self) -> NDArray[np.bool_]:
        """Which rows the filter keeps.

        A filter that cannot be evaluated keeps every row: hiding the whole
        catalogue because of a typo, with no way to see the typo, is worse
        than ignoring it. `filter_error` says what went wrong.
        """
        try:
            self.filter_error = ""
            return evaluate(self.table, self.filter_expression)
        except FilterError as exc:
            self.filter_error = str(exc)
            return np.ones(len(self.table), dtype=bool)

    #: What went wrong with the filter, if anything did.
    filter_error: str = ""

    def rows(self) -> list[int]:
        """The indices of the rows the filter keeps, in table order."""
        return [int(index) for index in np.nonzero(self.mask())[0]]

    def filtered(self) -> Table:
        """The rows the filter keeps, as a table."""
        return self.table[self.mask()]

    def select(self, rows) -> None:
        """Replace the selection with these row indices."""
        self.selected = {int(row) for row in rows if 0 <= int(row) < len(self.table)}

    def positions(self) -> SkyCoord | None:
        """The sky positions of every row, or None if there are none."""
        return positions(self.table)

    def draw(self) -> list[DrawnSymbol]:
        """Work out the symbol for each row the filter keeps.

        Every expression is evaluated once over the whole column rather
        than once per row: a catalogue of fifty thousand stars is common
        and a per-row `eval` would take seconds.
        """
        coordinates = self.positions()
        if coordinates is None or not len(self.table):
            return []

        keep = self.mask()
        longitude = coordinates.ra.deg
        latitude = coordinates.dec.deg

        # Which rule applies to each row: the first whose condition holds.
        chosen = np.full(len(self.table), -1, dtype=int)
        for index, symbol in enumerate(self.symbols):
            try:
                matches = evaluate(self.table, symbol.condition)
            except FilterError:
                # A rule with an unusable condition is skipped, not fatal:
                # the other rules still classify the catalogue.
                continue
            chosen = np.where((chosen < 0) & matches, index, chosen)

        drawn: list[DrawnSymbol] = []
        for index, symbol in enumerate(self.symbols):
            rows = np.nonzero(keep & (chosen == index))[0]
            if not rows.size:
                continue
            sizes = evaluate_values(self.table, symbol.size, DEFAULT_SIZE)
            sizes2 = evaluate_values(self.table, symbol.size2, DEFAULT_SIZE)
            angles = evaluate_values(self.table, symbol.angle, 0.0)
            labels = evaluate_text(self.table, symbol.text)

            for row in rows:
                drawn.append(
                    DrawnSymbol(
                        row=int(row),
                        longitude=float(longitude[row]),
                        latitude=float(latitude[row]),
                        shape=symbol.shape,
                        color=symbol.color,
                        width=symbol.width,
                        size=float(sizes[row]),
                        size2=float(sizes2[row]),
                        angle=float(angles[row]),
                        text=labels[row] if row < len(labels) else "",
                        font=symbol.font,
                        font_size=symbol.font_size,
                        selected=int(row) in self.selected,
                    )
                )

        # In row order, so the drawing order does not depend on which rule
        # matched -- which would make the overlay flicker as a rule changed.
        drawn.sort(key=lambda symbol: symbol.row)
        return drawn

    def header(self) -> str:
        """The catalogue's header, as DS9's Header view shows it."""
        lines = [f"Name\t{self.name}"]
        if self.source:
            lines.append(f"Source\t{self.source}")
        lines.append(f"Rows\t{len(self.table)}")
        lines.append(f"Columns\t{len(self.table.colnames)}")
        for key, value in (self.table.meta or {}).items():
            lines.append(f"{key}\t{value}")
        return "\n".join(lines)


class CatalogSet:
    """Every catalogue loaded on the frame, in the order loaded."""

    def __init__(self) -> None:
        self._catalogs: list[LoadedCatalog] = []

    def __len__(self) -> int:
        return len(self._catalogs)

    def __iter__(self):
        return iter(self._catalogs)

    def __bool__(self) -> bool:
        return bool(self._catalogs)

    @property
    def catalogs(self) -> tuple[LoadedCatalog, ...]:
        """The catalogues, oldest first."""
        return tuple(self._catalogs)

    def add(self, catalog: LoadedCatalog) -> LoadedCatalog:
        """Add a catalogue, giving it a distinct name.

        Two catalogues called "GAIA DR2" cannot be told apart in a menu, so
        the second becomes "GAIA DR2 (2)".
        """
        taken = {existing.name for existing in self._catalogs}
        if catalog.name in taken:
            number = 2
            while f"{catalog.name} ({number})" in taken:
                number += 1
            catalog.name = f"{catalog.name} ({number})"
        self._catalogs.append(catalog)
        return catalog

    def remove(self, name: str) -> bool:
        """Remove one catalogue by name.

        Returns:
            Whether there was one to remove.
        """
        before = len(self._catalogs)
        self._catalogs = [entry for entry in self._catalogs if entry.name != name]
        return len(self._catalogs) != before

    def clear(self) -> int:
        """Remove every catalogue, DS9's Clear All.

        Returns:
            How many went.
        """
        count = len(self._catalogs)
        self._catalogs.clear()
        return count

    def by_name(self, name: str) -> LoadedCatalog | None:
        """One catalogue by name."""
        return next((entry for entry in self._catalogs if entry.name == name), None)

    def draw(self) -> list[DrawnSymbol]:
        """Every visible catalogue's symbols, in the order loaded."""
        drawn: list[DrawnSymbol] = []
        for catalog in self._catalogs:
            if catalog.visible:
                drawn.extend(catalog.draw())
        return drawn


# -- symbol files (M8-3) ----------------------------------------------------------


def save_symbols(path: str | Path, symbols: list[Symbol]) -> None:
    """Write a symbol set, DS9's Save in the symbol editor.

    Raises:
        OSError: If it cannot be written.
    """
    payload = {
        "version": SYMBOL_FORMAT_VERSION,
        "symbols": [symbol.to_dict() for symbol in symbols],
    }
    Path(path).write_text(json.dumps(payload, indent=2))


def load_symbols(path: str | Path) -> list[Symbol]:
    """Read a symbol set back.

    Raises:
        ValueError: If the file is not a saved symbol set.
        OSError: If it cannot be read.
    """
    data = json.loads(Path(path).read_text())
    if not isinstance(data, dict) or "symbols" not in data:
        raise ValueError("not a saved symbol set")
    return [Symbol.from_dict(entry) for entry in data["symbols"]]


def default_symbols() -> list[Symbol]:
    """The one rule a newly loaded catalogue starts with."""
    return [replace(Symbol())]
