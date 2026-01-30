# NCRADS9 - Texture Manager
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
GPU texture management for astronomical image rendering.

Provides efficient texture allocation, caching, and lifecycle management
for OpenGL textures used in image display.
"""

from dataclasses import dataclass
from typing import Dict, Optional, Tuple

import numpy as np
from numpy.typing import NDArray


@dataclass
class TextureInfo:
    """Information about a GPU texture."""

    texture_id: int
    width: int
    height: int
    format: str
    size_bytes: int
    mipmap: bool


class TextureManager:
    """
    Manager for GPU texture resources.

    Handles texture creation, updating, caching, and cleanup.
    Optimizes memory usage through texture reuse and cache management.

    Attributes:
        max_cache_size: Maximum texture cache size in bytes.
        current_cache_size: Current texture cache usage in bytes.
    """

    def __init__(
        self,
        max_cache_size: int = 512 * 1024 * 1024,  # 512 MB default
    ) -> None:
        """
        Initialize the texture manager.

        Args:
            max_cache_size: Maximum cache size in bytes.
        """
        self._max_cache_size: int = max_cache_size
        self._current_cache_size: int = 0
        self._textures: Dict[str, TextureInfo] = {}
        self._lru_order: list[str] = []
        self._gl_context_valid: bool = False

    @property
    def max_cache_size(self) -> int:
        """Get maximum cache size in bytes."""
        return self._max_cache_size

    @max_cache_size.setter
    def max_cache_size(self, value: int) -> None:
        """Set maximum cache size and evict if necessary."""
        self._max_cache_size = value
        self._evict_to_limit()

    @property
    def current_cache_size(self) -> int:
        """Get current cache usage in bytes."""
        return self._current_cache_size

    def initialize(self) -> None:
        """Initialize the texture manager with a valid OpenGL context."""
        self._gl_context_valid = True

    def shutdown(self) -> None:
        """Release all textures and shutdown the manager."""
        self.clear_cache()
        self._gl_context_valid = False

    def create_texture(
        self,
        key: str,
        data: NDArray[np.float32],
        generate_mipmap: bool = False,
    ) -> int:
        """
        Create a new texture from image data.

        Args:
            key: Unique identifier for the texture.
            data: 2D or 3D image data (HxW or HxWxC).
            generate_mipmap: Whether to generate mipmaps.

        Returns:
            OpenGL texture ID.

        Raises:
            RuntimeError: If OpenGL context is not valid.
        """
        if not self._gl_context_valid:
            raise RuntimeError("OpenGL context not initialized")

        # Delete existing texture with same key
        if key in self._textures:
            self.delete_texture(key)

        # Determine texture format
        if data.ndim == 2:
            height, width = data.shape
            channels = 1
            gl_format = "R32F"
        else:
            height, width, channels = data.shape
            gl_format = {1: "R32F", 3: "RGB32F", 4: "RGBA32F"}.get(channels, "RGBA32F")

        # Calculate size
        size_bytes = width * height * channels * 4  # 4 bytes per float32

        # Ensure cache has room
        self._ensure_cache_space(size_bytes)

        # Create texture (placeholder - actual OpenGL calls go here)
        texture_id = self._allocate_gl_texture(data, generate_mipmap)

        # Store texture info
        info = TextureInfo(
            texture_id=texture_id,
            width=width,
            height=height,
            format=gl_format,
            size_bytes=size_bytes,
            mipmap=generate_mipmap,
        )
        self._textures[key] = info
        self._lru_order.append(key)
        self._current_cache_size += size_bytes

        return texture_id

    def update_texture(
        self,
        key: str,
        data: NDArray[np.float32],
        offset: Tuple[int, int] = (0, 0),
    ) -> None:
        """
        Update an existing texture with new data.

        Args:
            key: Texture identifier.
            data: New image data.
            offset: (x, y) offset for partial update.

        Raises:
            KeyError: If texture does not exist.
        """
        if key not in self._textures:
            raise KeyError(f"Texture '{key}' not found")

        info = self._textures[key]
        self._update_gl_texture(info.texture_id, data, offset)
        self._touch(key)

    def get_texture(self, key: str) -> Optional[int]:
        """
        Get texture ID by key.

        Args:
            key: Texture identifier.

        Returns:
            OpenGL texture ID or None if not found.
        """
        if key in self._textures:
            self._touch(key)
            return self._textures[key].texture_id
        return None

    def get_texture_info(self, key: str) -> Optional[TextureInfo]:
        """
        Get texture information.

        Args:
            key: Texture identifier.

        Returns:
            TextureInfo or None if not found.
        """
        return self._textures.get(key)

    def delete_texture(self, key: str) -> None:
        """
        Delete a texture.

        Args:
            key: Texture identifier.
        """
        if key not in self._textures:
            return

        info = self._textures[key]
        self._delete_gl_texture(info.texture_id)
        self._current_cache_size -= info.size_bytes
        del self._textures[key]
        if key in self._lru_order:
            self._lru_order.remove(key)

    def clear_cache(self) -> None:
        """Delete all cached textures."""
        for key in list(self._textures.keys()):
            self.delete_texture(key)

    def has_texture(self, key: str) -> bool:
        """
        Check if a texture exists.

        Args:
            key: Texture identifier.

        Returns:
            True if texture exists.
        """
        return key in self._textures

    def _touch(self, key: str) -> None:
        """Move texture to end of LRU list (most recently used)."""
        if key in self._lru_order:
            self._lru_order.remove(key)
        self._lru_order.append(key)

    def _ensure_cache_space(self, required_bytes: int) -> None:
        """Evict textures if necessary to make room."""
        while (
            self._current_cache_size + required_bytes > self._max_cache_size
            and self._lru_order
        ):
            oldest_key = self._lru_order[0]
            self.delete_texture(oldest_key)

    def _evict_to_limit(self) -> None:
        """Evict textures until cache is within limit."""
        while self._current_cache_size > self._max_cache_size and self._lru_order:
            oldest_key = self._lru_order[0]
            self.delete_texture(oldest_key)

    def _allocate_gl_texture(
        self,
        data: NDArray[np.float32],
        generate_mipmap: bool,
    ) -> int:
        """
        Allocate OpenGL texture (placeholder for actual implementation).

        Args:
            data: Image data.
            generate_mipmap: Whether to generate mipmaps.

        Returns:
            OpenGL texture ID.
        """
        # Placeholder - actual OpenGL calls would go here
        # glGenTextures, glBindTexture, glTexImage2D, etc.
        return hash(data.tobytes()) % (2**31)

    def _update_gl_texture(
        self,
        texture_id: int,
        data: NDArray[np.float32],
        offset: Tuple[int, int],
    ) -> None:
        """
        Update OpenGL texture (placeholder for actual implementation).

        Args:
            texture_id: OpenGL texture ID.
            data: New image data.
            offset: Update offset.
        """
        # Placeholder - actual OpenGL calls would go here
        # glBindTexture, glTexSubImage2D, etc.
        pass

    def _delete_gl_texture(self, texture_id: int) -> None:
        """
        Delete OpenGL texture (placeholder for actual implementation).

        Args:
            texture_id: OpenGL texture ID.
        """
        # Placeholder - actual OpenGL call would go here
        # glDeleteTextures
        pass
