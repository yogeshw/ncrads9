# NCRA DS9 - Astronomical Image Viewer
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
#
# Author: Yogesh Wadadekar

"""TileLayout class for arranging frames in NxM grid."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum, auto
from typing import Optional

from .frame import Frame


class TileMode(Enum):
    """Tile layout modes."""

    SINGLE = auto()
    COLUMN = auto()
    ROW = auto()
    GRID = auto()


@dataclass
class TilePosition:
    """Position and size of a tile in the layout."""

    row: int
    col: int
    x: float
    y: float
    width: float
    height: float


class TileLayout:
    """Arranges frames in an NxM grid layout."""

    def __init__(
        self,
        rows: int = 1,
        cols: int = 1,
        gap: float = 2.0,
    ) -> None:
        """Initialize a TileLayout.

        Args:
            rows: Number of rows in the grid.
            cols: Number of columns in the grid.
            gap: Gap between tiles in pixels.
        """
        self._rows = max(1, rows)
        self._cols = max(1, cols)
        self._gap = gap
        self._tiles: dict[tuple[int, int], Optional[Frame]] = {}
        self._canvas_width: float = 800.0
        self._canvas_height: float = 600.0
        self._mode = TileMode.GRID

        # Initialize empty grid
        for r in range(self._rows):
            for c in range(self._cols):
                self._tiles[(r, c)] = None

    @property
    def rows(self) -> int:
        """Return the number of rows."""
        return self._rows

    @rows.setter
    def rows(self, value: int) -> None:
        """Set the number of rows."""
        new_rows = max(1, value)
        if new_rows != self._rows:
            self._resize_grid(new_rows, self._cols)

    @property
    def cols(self) -> int:
        """Return the number of columns."""
        return self._cols

    @cols.setter
    def cols(self, value: int) -> None:
        """Set the number of columns."""
        new_cols = max(1, value)
        if new_cols != self._cols:
            self._resize_grid(self._rows, new_cols)

    @property
    def gap(self) -> float:
        """Return the gap between tiles."""
        return self._gap

    @gap.setter
    def gap(self, value: float) -> None:
        """Set the gap between tiles."""
        self._gap = max(0.0, value)

    @property
    def mode(self) -> TileMode:
        """Return the tile mode."""
        return self._mode

    @mode.setter
    def mode(self, value: TileMode) -> None:
        """Set the tile mode."""
        self._mode = value

    @property
    def tile_count(self) -> int:
        """Return the total number of tiles."""
        return self._rows * self._cols

    @property
    def canvas_size(self) -> tuple[float, float]:
        """Return the canvas size (width, height)."""
        return (self._canvas_width, self._canvas_height)

    def set_canvas_size(self, width: float, height: float) -> None:
        """Set the canvas size.

        Args:
            width: Canvas width in pixels.
            height: Canvas height in pixels.
        """
        self._canvas_width = max(1.0, width)
        self._canvas_height = max(1.0, height)

    def _resize_grid(self, new_rows: int, new_cols: int) -> None:
        """Resize the grid, preserving existing tiles where possible.

        Args:
            new_rows: New number of rows.
            new_cols: New number of columns.
        """
        old_tiles = self._tiles.copy()
        self._tiles = {}

        self._rows = new_rows
        self._cols = new_cols

        for r in range(new_rows):
            for c in range(new_cols):
                if (r, c) in old_tiles:
                    self._tiles[(r, c)] = old_tiles[(r, c)]
                else:
                    self._tiles[(r, c)] = None

    def set_grid(self, rows: int, cols: int) -> None:
        """Set the grid dimensions.

        Args:
            rows: Number of rows.
            cols: Number of columns.
        """
        self._resize_grid(max(1, rows), max(1, cols))

    def get_tile(self, row: int, col: int) -> Optional[Frame]:
        """Get the frame at a tile position.

        Args:
            row: Row index.
            col: Column index.

        Returns:
            The frame at this position, or None.
        """
        return self._tiles.get((row, col))

    def set_tile(self, row: int, col: int, frame: Optional[Frame]) -> bool:
        """Set a frame at a tile position.

        Args:
            row: Row index.
            col: Column index.
            frame: The frame to place, or None to clear.

        Returns:
            True if the tile was set, False if position is invalid.
        """
        if 0 <= row < self._rows and 0 <= col < self._cols:
            self._tiles[(row, col)] = frame
            return True
        return False

    def clear_tile(self, row: int, col: int) -> bool:
        """Clear a tile.

        Args:
            row: Row index.
            col: Column index.

        Returns:
            True if the tile was cleared, False if position is invalid.
        """
        return self.set_tile(row, col, None)

    def clear_all(self) -> None:
        """Clear all tiles."""
        for key in self._tiles:
            self._tiles[key] = None

    def get_tile_position(self, row: int, col: int) -> Optional[TilePosition]:
        """Calculate the position and size of a tile.

        Args:
            row: Row index.
            col: Column index.

        Returns:
            TilePosition with position and size, or None if invalid.
        """
        if not (0 <= row < self._rows and 0 <= col < self._cols):
            return None

        # Calculate tile dimensions
        total_gap_x = self._gap * (self._cols + 1)
        total_gap_y = self._gap * (self._rows + 1)

        tile_width = (self._canvas_width - total_gap_x) / self._cols
        tile_height = (self._canvas_height - total_gap_y) / self._rows

        # Calculate position
        x = self._gap + col * (tile_width + self._gap)
        y = self._gap + row * (tile_height + self._gap)

        return TilePosition(
            row=row,
            col=col,
            x=x,
            y=y,
            width=tile_width,
            height=tile_height,
        )

    def get_all_positions(self) -> list[TilePosition]:
        """Get positions for all tiles.

        Returns:
            List of TilePosition objects.
        """
        positions = []
        for r in range(self._rows):
            for c in range(self._cols):
                pos = self.get_tile_position(r, c)
                if pos is not None:
                    positions.append(pos)
        return positions

    def find_tile_at(self, x: float, y: float) -> Optional[tuple[int, int]]:
        """Find which tile contains a point.

        Args:
            x: X coordinate.
            y: Y coordinate.

        Returns:
            Tuple of (row, col), or None if not in any tile.
        """
        for r in range(self._rows):
            for c in range(self._cols):
                pos = self.get_tile_position(r, c)
                if pos is not None:
                    if (
                        pos.x <= x < pos.x + pos.width
                        and pos.y <= y < pos.y + pos.height
                    ):
                        return (r, c)
        return None

    def arrange_frames(self, frames: list[Frame]) -> None:
        """Arrange a list of frames into the grid.

        Args:
            frames: List of frames to arrange.
        """
        self.clear_all()
        index = 0
        for r in range(self._rows):
            for c in range(self._cols):
                if index < len(frames):
                    self._tiles[(r, c)] = frames[index]
                    index += 1

    def get_frames(self) -> list[Frame]:
        """Get all non-None frames in the layout.

        Returns:
            List of frames in row-major order.
        """
        frames = []
        for r in range(self._rows):
            for c in range(self._cols):
                frame = self._tiles.get((r, c))
                if frame is not None:
                    frames.append(frame)
        return frames

    def auto_layout(self, frame_count: int) -> None:
        """Automatically set grid dimensions based on frame count.

        Args:
            frame_count: Number of frames to layout.
        """
        if frame_count <= 0:
            self.set_grid(1, 1)
            return

        import math

        cols = math.ceil(math.sqrt(frame_count))
        rows = math.ceil(frame_count / cols)
        self.set_grid(rows, cols)
