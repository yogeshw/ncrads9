# This file is part of ncrads9.
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
Data caching module for large file support.

Provides memory-mapped file handling for efficient access to large FITS files.

Author: Yogesh Wadadekar
"""

from typing import Optional, Dict, Any, Union
from pathlib import Path
import weakref
import hashlib

import numpy as np
from astropy.io import fits
from numpy.typing import NDArray


class DataCache:
    """Cache manager for memory-mapped large file support.

    This class manages memory-mapped access to large FITS files,
    providing efficient read access without loading entire files into memory.

    Attributes:
        max_cache_size: Maximum number of files to keep in cache.
        use_memmap: Whether to use memory mapping.
    """

    _instance: Optional["DataCache"] = None

    def __new__(cls, *args, **kwargs) -> "DataCache":
        """Singleton pattern for cache manager."""
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(
        self,
        max_cache_size: int = 10,
        use_memmap: bool = True,
    ) -> None:
        """Initialize DataCache.

        Args:
            max_cache_size: Maximum number of files to cache.
            use_memmap: Whether to use memory-mapped file access.
        """
        if self._initialized:
            return

        self._max_cache_size: int = max_cache_size
        self._use_memmap: bool = use_memmap
        self._cache: Dict[str, weakref.ref] = {}
        self._access_order: list = []
        self._initialized: bool = True

    @property
    def max_cache_size(self) -> int:
        """Get maximum cache size."""
        return self._max_cache_size

    @max_cache_size.setter
    def max_cache_size(self, value: int) -> None:
        """Set maximum cache size."""
        self._max_cache_size = value
        self._cleanup()

    @property
    def use_memmap(self) -> bool:
        """Get memory mapping setting."""
        return self._use_memmap

    @use_memmap.setter
    def use_memmap(self, value: bool) -> None:
        """Set memory mapping setting."""
        self._use_memmap = value

    def _get_cache_key(self, filepath: Union[str, Path], ext: int = 0) -> str:
        """Generate a cache key for a file and extension.

        Args:
            filepath: Path to the file.
            ext: Extension index.

        Returns:
            Cache key string.
        """
        path_str = str(Path(filepath).resolve())
        return hashlib.md5(f"{path_str}:{ext}".encode()).hexdigest()

    def get(
        self,
        filepath: Union[str, Path],
        ext: int = 0,
    ) -> Optional[NDArray[np.floating]]:
        """Get data from cache or load from file.

        Args:
            filepath: Path to the FITS file.
            ext: Extension index.

        Returns:
            The data array, or None if loading fails.
        """
        key = self._get_cache_key(filepath, ext)

        # Check cache
        if key in self._cache:
            ref = self._cache[key]
            data = ref()
            if data is not None:
                self._update_access(key)
                return data
            else:
                del self._cache[key]

        # Load from file
        data = self._load_data(filepath, ext)
        if data is not None:
            self._add_to_cache(key, data)

        return data

    def _load_data(
        self,
        filepath: Union[str, Path],
        ext: int = 0,
    ) -> Optional[NDArray[np.floating]]:
        """Load data from a FITS file.

        Args:
            filepath: Path to the FITS file.
            ext: Extension index.

        Returns:
            The data array, or None if loading fails.
        """
        try:
            with fits.open(filepath, memmap=self._use_memmap) as hdul:
                data = hdul[ext].data
                if data is not None:
                    return np.array(data)
        except Exception:
            pass
        return None

    def _add_to_cache(self, key: str, data: NDArray) -> None:
        """Add data to the cache.

        Args:
            key: Cache key.
            data: Data array to cache.
        """
        self._cache[key] = weakref.ref(data)
        self._access_order.append(key)
        self._cleanup()

    def _update_access(self, key: str) -> None:
        """Update access order for LRU tracking.

        Args:
            key: Cache key that was accessed.
        """
        if key in self._access_order:
            self._access_order.remove(key)
        self._access_order.append(key)

    def _cleanup(self) -> None:
        """Remove stale entries and enforce cache size limit."""
        # Remove dead references
        dead_keys = [k for k, v in self._cache.items() if v() is None]
        for key in dead_keys:
            del self._cache[key]
            if key in self._access_order:
                self._access_order.remove(key)

        # Enforce size limit
        while len(self._cache) > self._max_cache_size and self._access_order:
            oldest_key = self._access_order.pop(0)
            if oldest_key in self._cache:
                del self._cache[oldest_key]

    def clear(self) -> None:
        """Clear the entire cache."""
        self._cache.clear()
        self._access_order.clear()

    def remove(self, filepath: Union[str, Path], ext: int = 0) -> bool:
        """Remove a specific file from cache.

        Args:
            filepath: Path to the file.
            ext: Extension index.

        Returns:
            True if the entry was removed.
        """
        key = self._get_cache_key(filepath, ext)
        if key in self._cache:
            del self._cache[key]
            if key in self._access_order:
                self._access_order.remove(key)
            return True
        return False

    def get_stats(self) -> Dict[str, Any]:
        """Get cache statistics.

        Returns:
            Dictionary of cache statistics.
        """
        return {
            "cached_items": len(self._cache),
            "max_size": self._max_cache_size,
            "use_memmap": self._use_memmap,
        }

    @classmethod
    def reset_instance(cls) -> None:
        """Reset the singleton instance (for testing)."""
        cls._instance = None
