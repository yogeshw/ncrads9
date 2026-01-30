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

"""
Resource loading utilities for icons, colormaps, and other assets.

Author: Yogesh Wadadekar
"""

from __future__ import annotations

import importlib.resources
from functools import lru_cache
from pathlib import Path
from typing import Any


class ResourceLoader:
    """Utility class for loading application resources."""

    def __init__(self, resource_base: Path | str | None = None) -> None:
        """
        Initialize resource loader.

        Args:
            resource_base: Base path for resources directory.
        """
        if resource_base is not None:
            self._base_path = Path(resource_base)
        else:
            self._base_path = self._get_default_resource_path()

    def _get_default_resource_path(self) -> Path:
        """Get the default resource path from package."""
        try:
            with importlib.resources.files("ncrads9") as pkg_path:
                return Path(pkg_path) / "resources"
        except (TypeError, ModuleNotFoundError):
            return Path(__file__).parent.parent / "resources"

    @lru_cache(maxsize=64)
    def get_icon_path(self, name: str) -> Path | None:
        """
        Get path to an icon file.

        Args:
            name: Icon name (without extension).

        Returns:
            Path to icon file or None if not found.
        """
        icons_dir = self._base_path / "icons"
        for ext in (".png", ".svg", ".ico"):
            icon_path = icons_dir / f"{name}{ext}"
            if icon_path.exists():
                return icon_path
        return None

    @lru_cache(maxsize=32)
    def get_colormap_path(self, name: str) -> Path | None:
        """
        Get path to a colormap file.

        Args:
            name: Colormap name.

        Returns:
            Path to colormap file or None if not found.
        """
        cmap_dir = self._base_path / "colormaps"
        for ext in (".cmap", ".lut", ".json"):
            cmap_path = cmap_dir / f"{name}{ext}"
            if cmap_path.exists():
                return cmap_path
        return None

    def list_colormaps(self) -> list[str]:
        """
        List available colormaps.

        Returns:
            List of colormap names.
        """
        cmap_dir = self._base_path / "colormaps"
        if not cmap_dir.exists():
            return []

        colormaps = []
        for path in cmap_dir.iterdir():
            if path.suffix in (".cmap", ".lut", ".json"):
                colormaps.append(path.stem)
        return sorted(colormaps)

    def load_text_resource(self, relative_path: str) -> str | None:
        """
        Load a text resource file.

        Args:
            relative_path: Path relative to resource base.

        Returns:
            File contents or None if not found.
        """
        resource_path = self._base_path / relative_path
        if resource_path.exists():
            return resource_path.read_text(encoding="utf-8")
        return None

    def load_binary_resource(self, relative_path: str) -> bytes | None:
        """
        Load a binary resource file.

        Args:
            relative_path: Path relative to resource base.

        Returns:
            File contents or None if not found.
        """
        resource_path = self._base_path / relative_path
        if resource_path.exists():
            return resource_path.read_bytes()
        return None

    @property
    def base_path(self) -> Path:
        """Return the resource base path."""
        return self._base_path

    def __repr__(self) -> str:
        """Return string representation."""
        return f"ResourceLoader(base={self._base_path})"
