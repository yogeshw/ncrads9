# NCRADS9 - Tile Renderer
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

"""
Tile-based renderer for large astronomical images.

Implements efficient rendering of large FITS images by dividing them
into tiles that can be individually loaded, cached, and rendered
based on the current viewport.
"""

from dataclasses import dataclass
from typing import Callable, Iterator, List, Optional, Tuple

import numpy as np
from numpy.typing import NDArray

from .texture_manager import TextureManager


@dataclass
class Tile:
    """Represents a single image tile."""

    x: int  # Tile column index
    y: int  # Tile row index
    x_pixel: int  # Pixel x offset in full image
    y_pixel: int  # Pixel y offset in full image
    width: int  # Tile width in pixels
    height: int  # Tile height in pixels
    texture_key: str  # Key for TextureManager
    loaded: bool = False


@dataclass
class Viewport:
    """Represents the visible region of the image."""

    x: float  # Left edge in image coordinates
    y: float  # Top edge in image coordinates
    width: float  # Width in image coordinates
    height: float  # Height in image coordinates
    zoom: float  # Current zoom level


class TileRenderer:
    """
    Renderer for large images using tile-based approach.

    Divides large images into manageable tiles that can be loaded
    on-demand based on viewport visibility, enabling smooth navigation
    of very large astronomical images.

    Attributes:
        tile_size: Size of each tile in pixels.
        image_width: Total image width in pixels.
        image_height: Total image height in pixels.
    """

    def __init__(
        self,
        texture_manager: TextureManager,
        tile_size: int = 512,
        prefetch_margin: int = 1,
    ) -> None:
        """
        Initialize the tile renderer.

        Args:
            texture_manager: TextureManager for GPU texture handling.
            tile_size: Size of tiles in pixels (default 512).
            prefetch_margin: Number of tiles to prefetch around viewport.
        """
        self._texture_manager: TextureManager = texture_manager
        self._tile_size: int = tile_size
        self._prefetch_margin: int = prefetch_margin

        self._image_width: int = 0
        self._image_height: int = 0
        self._tiles: List[List[Tile]] = []
        self._data_provider: Optional[Callable[[int, int, int, int], NDArray]] = None

    @property
    def tile_size(self) -> int:
        """Get tile size in pixels."""
        return self._tile_size

    @property
    def image_width(self) -> int:
        """Get total image width."""
        return self._image_width

    @property
    def image_height(self) -> int:
        """Get total image height."""
        return self._image_height

    @property
    def num_tiles_x(self) -> int:
        """Get number of tile columns."""
        return len(self._tiles[0]) if self._tiles else 0

    @property
    def num_tiles_y(self) -> int:
        """Get number of tile rows."""
        return len(self._tiles)

    def set_image(
        self,
        width: int,
        height: int,
        data_provider: Callable[[int, int, int, int], NDArray[np.float32]],
    ) -> None:
        """
        Set up tiling for an image.

        Args:
            width: Image width in pixels.
            height: Image height in pixels.
            data_provider: Callable(x, y, w, h) that returns image data
                          for the specified region.
        """
        self._image_width = width
        self._image_height = height
        self._data_provider = data_provider
        self._create_tiles()

    def _create_tiles(self) -> None:
        """Create tile grid for the current image."""
        self._tiles = []

        num_x = (self._image_width + self._tile_size - 1) // self._tile_size
        num_y = (self._image_height + self._tile_size - 1) // self._tile_size

        for ty in range(num_y):
            row = []
            y_pixel = ty * self._tile_size
            tile_height = min(self._tile_size, self._image_height - y_pixel)

            for tx in range(num_x):
                x_pixel = tx * self._tile_size
                tile_width = min(self._tile_size, self._image_width - x_pixel)

                tile = Tile(
                    x=tx,
                    y=ty,
                    x_pixel=x_pixel,
                    y_pixel=y_pixel,
                    width=tile_width,
                    height=tile_height,
                    texture_key=f"tile_{tx}_{ty}",
                )
                row.append(tile)
            self._tiles.append(row)

    def get_visible_tiles(self, viewport: Viewport) -> List[Tile]:
        """
        Get tiles visible in the current viewport.

        Args:
            viewport: Current viewport.

        Returns:
            List of visible tiles.
        """
        if not self._tiles:
            return []

        # Calculate tile range
        x_start = max(0, int(viewport.x // self._tile_size))
        y_start = max(0, int(viewport.y // self._tile_size))
        x_end = min(
            self.num_tiles_x,
            int((viewport.x + viewport.width) // self._tile_size) + 1,
        )
        y_end = min(
            self.num_tiles_y,
            int((viewport.y + viewport.height) // self._tile_size) + 1,
        )

        visible = []
        for ty in range(y_start, y_end):
            for tx in range(x_start, x_end):
                visible.append(self._tiles[ty][tx])

        return visible

    def get_prefetch_tiles(self, viewport: Viewport) -> List[Tile]:
        """
        Get tiles to prefetch around the viewport.

        Args:
            viewport: Current viewport.

        Returns:
            List of tiles to prefetch.
        """
        if not self._tiles:
            return []

        visible = set((t.x, t.y) for t in self.get_visible_tiles(viewport))

        # Calculate expanded range
        x_start = max(0, int(viewport.x // self._tile_size) - self._prefetch_margin)
        y_start = max(0, int(viewport.y // self._tile_size) - self._prefetch_margin)
        x_end = min(
            self.num_tiles_x,
            int((viewport.x + viewport.width) // self._tile_size)
            + 1
            + self._prefetch_margin,
        )
        y_end = min(
            self.num_tiles_y,
            int((viewport.y + viewport.height) // self._tile_size)
            + 1
            + self._prefetch_margin,
        )

        prefetch = []
        for ty in range(y_start, y_end):
            for tx in range(x_start, x_end):
                if (tx, ty) not in visible and not self._tiles[ty][tx].loaded:
                    prefetch.append(self._tiles[ty][tx])

        return prefetch

    def load_tile(self, tile: Tile) -> None:
        """
        Load a tile's data to GPU texture.

        Args:
            tile: Tile to load.
        """
        if tile.loaded or self._data_provider is None:
            return

        data = self._data_provider(
            tile.x_pixel,
            tile.y_pixel,
            tile.width,
            tile.height,
        )

        self._texture_manager.create_texture(
            tile.texture_key,
            data.astype(np.float32),
        )
        tile.loaded = True

    def unload_tile(self, tile: Tile) -> None:
        """
        Unload a tile's texture from GPU.

        Args:
            tile: Tile to unload.
        """
        if not tile.loaded:
            return

        self._texture_manager.delete_texture(tile.texture_key)
        tile.loaded = False

    def render(self, viewport: Viewport) -> None:
        """
        Render visible tiles.

        Args:
            viewport: Current viewport.
        """
        visible_tiles = self.get_visible_tiles(viewport)

        # Ensure visible tiles are loaded
        for tile in visible_tiles:
            if not tile.loaded:
                self.load_tile(tile)

        # Render each tile
        for tile in visible_tiles:
            self._render_tile(tile, viewport)

    def _render_tile(self, tile: Tile, viewport: Viewport) -> None:
        """
        Render a single tile.

        Args:
            tile: Tile to render.
            viewport: Current viewport for transformation.
        """
        if not tile.loaded:
            return

        texture_id = self._texture_manager.get_texture(tile.texture_key)
        if texture_id is None:
            return

        # Calculate screen coordinates for tile
        # Placeholder - actual OpenGL rendering would go here
        # glBindTexture, set uniforms, draw quad, etc.
        pass

    def cleanup_distant_tiles(self, viewport: Viewport, distance: int = 3) -> None:
        """
        Unload tiles far from the current viewport.

        Args:
            viewport: Current viewport.
            distance: Tile distance threshold for cleanup.
        """
        center_tx = int((viewport.x + viewport.width / 2) // self._tile_size)
        center_ty = int((viewport.y + viewport.height / 2) // self._tile_size)

        for row in self._tiles:
            for tile in row:
                if tile.loaded:
                    dx = abs(tile.x - center_tx)
                    dy = abs(tile.y - center_ty)
                    if dx > distance or dy > distance:
                        self.unload_tile(tile)

    def clear(self) -> None:
        """Unload all tiles and reset state."""
        for row in self._tiles:
            for tile in row:
                self.unload_tile(tile)
        self._tiles = []
        self._image_width = 0
        self._image_height = 0
        self._data_provider = None

    def iter_all_tiles(self) -> Iterator[Tile]:
        """
        Iterate over all tiles.

        Yields:
            Each tile in the grid.
        """
        for row in self._tiles:
            yield from row
