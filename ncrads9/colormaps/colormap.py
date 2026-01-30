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
#
# Author: Yogesh Wadadekar

"""Colormap base class for ncrads9."""

from typing import List, Tuple, Optional, Union
import numpy as np
from numpy.typing import NDArray


class Colormap:
    """Base class for colormaps.

    A colormap maps scalar values to colors for image display.

    Attributes:
        name: The name of the colormap.
        colors: Array of RGB colors with shape (N, 3), values in range [0, 1].
    """

    def __init__(
        self,
        name: str,
        colors: Union[List[Tuple[float, float, float]], NDArray[np.floating]],
    ) -> None:
        """Initialize a Colormap.

        Args:
            name: The name of the colormap.
            colors: List of RGB tuples or numpy array with shape (N, 3).
                    Values should be in range [0, 1].
        """
        self.name: str = name
        self.colors: NDArray[np.floating] = np.asarray(colors, dtype=np.float64)

        if self.colors.ndim != 2 or self.colors.shape[1] != 3:
            raise ValueError("Colors must have shape (N, 3)")

    def __repr__(self) -> str:
        """Return string representation of the colormap."""
        return f"Colormap(name='{self.name}', num_colors={len(self.colors)})"

    def __len__(self) -> int:
        """Return the number of colors in the colormap."""
        return len(self.colors)

    def apply(
        self,
        data: NDArray[np.floating],
        vmin: Optional[float] = None,
        vmax: Optional[float] = None,
    ) -> NDArray[np.uint8]:
        """Apply the colormap to data.

        Args:
            data: Input data array to colorize.
            vmin: Minimum value for scaling. Defaults to data minimum.
            vmax: Maximum value for scaling. Defaults to data maximum.

        Returns:
            RGB image array with shape (*data.shape, 3) and dtype uint8.
        """
        data = np.asarray(data, dtype=np.float64)

        if vmin is None:
            vmin = float(np.nanmin(data))
        if vmax is None:
            vmax = float(np.nanmax(data))

        # Normalize data to [0, 1]
        if vmax > vmin:
            normalized = (data - vmin) / (vmax - vmin)
        else:
            normalized = np.zeros_like(data)

        # Clip to valid range
        normalized = np.clip(normalized, 0.0, 1.0)

        # Map to color indices
        num_colors = len(self.colors)
        indices = (normalized * (num_colors - 1)).astype(np.int64)
        indices = np.clip(indices, 0, num_colors - 1)

        # Apply colormap
        rgb = self.colors[indices]

        # Convert to uint8
        return (rgb * 255).astype(np.uint8)

    def reversed(self) -> "Colormap":
        """Return a reversed version of the colormap.

        Returns:
            New Colormap with reversed color order.
        """
        return Colormap(f"{self.name}_r", self.colors[::-1].copy())

    def to_lut(self) -> NDArray[np.uint8]:
        """Convert colormap to lookup table format.

        Returns:
            Lookup table with shape (256, 3) and dtype uint8.
        """
        indices = np.linspace(0, len(self.colors) - 1, 256).astype(np.int64)
        lut = self.colors[indices]
        return (lut * 255).astype(np.uint8)
