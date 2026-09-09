# NCRADS9 - NCRA DS9 Viewer
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
Geometry for DS9's Tile Frames mode.

Pure arithmetic: given a tile count, an arrangement mode and a cell size, this
works out the grid, the size of the composite mosaic, where each tile goes, and
which tile a click landed on. It touches neither Qt nor NumPy, so it is
directly unit-testable.

Before M1 this logic lived as an untyped dict built inline in
`MainWindow._display_tiled_frames` and re-read by index in
`_select_tiled_frame`, while a `TileLayout` class modelling a grid of Frame
objects sat unused. The class was rewritten to do the job the application
actually needs.

Author: Yogesh Wadadekar
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from enum import Enum

#: Pixels between tiles, and around the outside of the mosaic. DS9's default.
DEFAULT_GAP = 8


class TileMode(Enum):
    """How tiles are arranged, matching DS9's Frame Parameters -> Tile menu."""

    GRID = "grid"
    COLUMN = "column"
    ROW = "row"


@dataclass(frozen=True)
class TilePlacement:
    """Where one tile sits in the composite, in bottom-up image coordinates."""

    index: int
    row: int
    col: int
    x: int
    y: int
    width: int
    height: int


@dataclass(frozen=True)
class TileLayout:
    """A computed tile grid.

    Coordinates follow the image convention used by the rest of the renderer:
    the origin is bottom-left, and `y` grows upward.
    """

    count: int
    rows: int
    cols: int
    cell_width: int
    cell_height: int
    gap: int = DEFAULT_GAP

    @classmethod
    def compute(
        cls,
        count: int,
        cell_width: int,
        cell_height: int,
        mode: TileMode | str = TileMode.GRID,
        gap: int = DEFAULT_GAP,
    ) -> TileLayout:
        """Work out the grid for `count` tiles of the given cell size.

        GRID keeps the mosaic as square as possible, which is what DS9's
        automatic grid mode does; COLUMN stacks vertically and ROW horizontally.
        """
        if isinstance(mode, str):
            mode = TileMode(mode)
        count = max(0, int(count))

        if count == 0:
            rows = cols = 0
        elif mode is TileMode.COLUMN:
            cols, rows = 1, count
        elif mode is TileMode.ROW:
            cols, rows = count, 1
        else:
            cols = max(1, math.ceil(math.sqrt(count)))
            rows = math.ceil(count / cols)

        return cls(
            count=count,
            rows=rows,
            cols=cols,
            cell_width=max(0, int(cell_width)),
            cell_height=max(0, int(cell_height)),
            gap=max(0, int(gap)),
        )

    @property
    def width(self) -> int:
        """Total mosaic width, including the gaps around the outside."""
        if self.cols == 0:
            return 0
        return self.cols * self.cell_width + (self.cols + 1) * self.gap

    @property
    def height(self) -> int:
        """Total mosaic height, including the gaps around the outside."""
        if self.rows == 0:
            return 0
        return self.rows * self.cell_height + (self.rows + 1) * self.gap

    def placement(self, index: int) -> TilePlacement | None:
        """Where tile `index` goes, or None if it is out of range.

        Tiles fill left-to-right then top-to-bottom, so tile 0 is the top-left
        of the mosaic. Because `y` grows upward, the top row has the largest y.
        """
        if not 0 <= index < self.count:
            return None
        row, col = divmod(index, self.cols)
        x = self.gap + col * (self.cell_width + self.gap)
        top_y = self.gap + row * (self.cell_height + self.gap)
        y = self.height - top_y - self.cell_height
        return TilePlacement(
            index=index,
            row=row,
            col=col,
            x=x,
            y=y,
            width=self.cell_width,
            height=self.cell_height,
        )

    def placements(self) -> list[TilePlacement]:
        """Placements for every tile, in index order."""
        return [p for p in (self.placement(i) for i in range(self.count)) if p is not None]

    def tile_at(self, x: float, y: float) -> int | None:
        """Return the tile index at image point (x, y), or None.

        None covers both a point outside the mosaic and a point in the gap
        between tiles, so a click in the gutter does not select a frame.
        """
        if self.count == 0 or self.cell_width == 0 or self.cell_height == 0:
            return None

        # Convert to top-down coordinates, where the grid arithmetic is simpler.
        top_y = self.height - 1 - y
        if x < self.gap or top_y < self.gap:
            return None

        col_span = self.cell_width + self.gap
        row_span = self.cell_height + self.gap
        col_offset = x - self.gap
        row_offset = top_y - self.gap

        col = int(col_offset // col_span)
        row = int(row_offset // row_span)
        if col < 0 or row < 0 or col >= self.cols or row >= self.rows:
            return None
        # Landed in a gap rather than on a tile.
        if col_offset % col_span >= self.cell_width:
            return None
        if row_offset % row_span >= self.cell_height:
            return None

        index = row * self.cols + col
        return index if index < self.count else None
