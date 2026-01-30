# NCRADS9 - Colormap Engine
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
Colormap engine for applying colormaps to scaled astronomical data.

Provides colormap management and application with support for standard
astronomical colormaps and custom colormap definitions.
"""

from typing import Dict, List, Optional, Tuple

import numpy as np
from numpy.typing import NDArray


class ColormapEngine:
    """
    Engine for applying colormaps to scaled image data.

    Manages colormap lookup tables and provides efficient colormap
    application for image rendering.

    Attributes:
        current_colormap: Name of the currently active colormap.
        inverted: Whether the colormap is inverted.
    """

    # Standard astronomical colormaps
    BUILTIN_COLORMAPS: List[str] = [
        "gray",
        "heat",
        "rainbow",
        "viridis",
        "plasma",
        "inferno",
        "magma",
        "cividis",
        "cubehelix",
        "sls",
        "red",
        "green",
        "blue",
    ]

    def __init__(self, colormap: str = "gray", lut_size: int = 256) -> None:
        """
        Initialize the colormap engine.

        Args:
            colormap: Initial colormap name.
            lut_size: Size of the lookup table (default 256).
        """
        self._lut_size: int = lut_size
        self._current_colormap: str = colormap
        self._inverted: bool = False
        self._custom_colormaps: Dict[str, NDArray[np.uint8]] = {}
        self._lut: NDArray[np.uint8] = np.zeros((lut_size, 4), dtype=np.uint8)
        self._build_lut()

    @property
    def current_colormap(self) -> str:
        """Get the current colormap name."""
        return self._current_colormap

    @current_colormap.setter
    def current_colormap(self, name: str) -> None:
        """Set the current colormap by name."""
        self._current_colormap = name
        self._build_lut()

    @property
    def inverted(self) -> bool:
        """Get colormap inversion state."""
        return self._inverted

    @inverted.setter
    def inverted(self, value: bool) -> None:
        """Set colormap inversion state."""
        self._inverted = value
        self._build_lut()

    @property
    def available_colormaps(self) -> List[str]:
        """Get list of available colormap names."""
        return self.BUILTIN_COLORMAPS + list(self._custom_colormaps.keys())

    def apply(self, data: NDArray[np.float32]) -> NDArray[np.uint8]:
        """
        Apply colormap to scaled data.

        Args:
            data: Scaled data in [0, 1] range.

        Returns:
            RGBA image array with shape (H, W, 4).
        """
        # Clip and convert to LUT indices
        indices = np.clip(data * (self._lut_size - 1), 0, self._lut_size - 1)
        indices = indices.astype(np.int32)

        # Apply LUT
        return self._lut[indices]

    def get_lut(self) -> NDArray[np.uint8]:
        """
        Get the current lookup table.

        Returns:
            RGBA lookup table with shape (lut_size, 4).
        """
        return self._lut.copy()

    def register_colormap(
        self,
        name: str,
        colors: NDArray[np.uint8],
    ) -> None:
        """
        Register a custom colormap.

        Args:
            name: Name for the custom colormap.
            colors: RGBA color array with shape (N, 4).
        """
        # Resample to LUT size if needed
        if len(colors) != self._lut_size:
            colors = self._resample_colors(colors)
        self._custom_colormaps[name] = colors

    def _build_lut(self) -> None:
        """Build the lookup table for the current colormap."""
        if self._current_colormap in self._custom_colormaps:
            self._lut = self._custom_colormaps[self._current_colormap].copy()
        else:
            self._lut = self._generate_builtin_lut(self._current_colormap)

        if self._inverted:
            self._lut = self._lut[::-1].copy()

    def _generate_builtin_lut(self, name: str) -> NDArray[np.uint8]:
        """
        Generate a built-in colormap LUT.

        Args:
            name: Colormap name.

        Returns:
            RGBA lookup table.
        """
        lut = np.zeros((self._lut_size, 4), dtype=np.uint8)
        t = np.linspace(0, 1, self._lut_size)

        if name == "gray":
            lut[:, 0] = (t * 255).astype(np.uint8)
            lut[:, 1] = (t * 255).astype(np.uint8)
            lut[:, 2] = (t * 255).astype(np.uint8)
        elif name == "heat":
            lut[:, 0] = np.clip(t * 3 * 255, 0, 255).astype(np.uint8)
            lut[:, 1] = np.clip((t - 0.33) * 3 * 255, 0, 255).astype(np.uint8)
            lut[:, 2] = np.clip((t - 0.67) * 3 * 255, 0, 255).astype(np.uint8)
        elif name == "red":
            lut[:, 0] = (t * 255).astype(np.uint8)
            lut[:, 1] = 0
            lut[:, 2] = 0
        elif name == "green":
            lut[:, 0] = 0
            lut[:, 1] = (t * 255).astype(np.uint8)
            lut[:, 2] = 0
        elif name == "blue":
            lut[:, 0] = 0
            lut[:, 1] = 0
            lut[:, 2] = (t * 255).astype(np.uint8)
        elif name == "rainbow":
            lut = self._generate_rainbow_lut()
        else:
            # Default to gray for unknown colormaps
            lut[:, 0] = (t * 255).astype(np.uint8)
            lut[:, 1] = (t * 255).astype(np.uint8)
            lut[:, 2] = (t * 255).astype(np.uint8)

        lut[:, 3] = 255  # Full alpha
        return lut

    def _generate_rainbow_lut(self) -> NDArray[np.uint8]:
        """Generate rainbow colormap LUT."""
        lut = np.zeros((self._lut_size, 4), dtype=np.uint8)
        for i in range(self._lut_size):
            hue = i / self._lut_size
            r, g, b = self._hsv_to_rgb(hue, 1.0, 1.0)
            lut[i, 0] = int(r * 255)
            lut[i, 1] = int(g * 255)
            lut[i, 2] = int(b * 255)
        lut[:, 3] = 255
        return lut

    @staticmethod
    def _hsv_to_rgb(h: float, s: float, v: float) -> Tuple[float, float, float]:
        """
        Convert HSV to RGB color.

        Args:
            h: Hue [0, 1].
            s: Saturation [0, 1].
            v: Value [0, 1].

        Returns:
            Tuple of (r, g, b) in [0, 1].
        """
        if s == 0.0:
            return (v, v, v)

        i = int(h * 6.0)
        f = (h * 6.0) - i
        p = v * (1.0 - s)
        q = v * (1.0 - s * f)
        t = v * (1.0 - s * (1.0 - f))
        i = i % 6

        if i == 0:
            return (v, t, p)
        elif i == 1:
            return (q, v, p)
        elif i == 2:
            return (p, v, t)
        elif i == 3:
            return (p, q, v)
        elif i == 4:
            return (t, p, v)
        else:
            return (v, p, q)

    def _resample_colors(self, colors: NDArray[np.uint8]) -> NDArray[np.uint8]:
        """
        Resample color array to LUT size.

        Args:
            colors: Input color array.

        Returns:
            Resampled color array with lut_size entries.
        """
        n_in = len(colors)
        indices = np.linspace(0, n_in - 1, self._lut_size)
        resampled = np.zeros((self._lut_size, 4), dtype=np.uint8)
        for c in range(4):
            resampled[:, c] = np.interp(indices, np.arange(n_in), colors[:, c])
        return resampled
