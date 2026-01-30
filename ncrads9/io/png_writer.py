# NCRADS9 - NCRA DS9 Visualization Tool
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
PNG image writer for NCRADS9.

Author: Yogesh Wadadekar
"""

from pathlib import Path
from typing import Any, Optional, Union

import numpy as np
from numpy.typing import NDArray
from PIL import Image


class PNGWriter:
    """Writer for PNG image files."""

    def __init__(self, filepath: Union[str, Path]) -> None:
        """
        Initialize PNG writer.

        Args:
            filepath: Path for the output PNG file.
        """
        self.filepath = Path(filepath)

    def write(
        self,
        data: NDArray[Any],
        normalize: bool = True,
        bit_depth: int = 8,
        dpi: Optional[tuple[int, int]] = None,
    ) -> None:
        """
        Write image data to PNG file.

        Args:
            data: Image data as numpy array.
            normalize: Whether to normalize data.
            bit_depth: Bit depth (8 or 16).
            dpi: Resolution as (x_dpi, y_dpi).
        """
        if normalize:
            data = self._normalize(data, bit_depth)

        if bit_depth == 16:
            data = data.astype(np.uint16)
        else:
            data = data.astype(np.uint8)

        if data.ndim == 2:
            mode = "L" if bit_depth == 8 else "I;16"
        elif data.ndim == 3 and data.shape[2] == 3:
            mode = "RGB"
        elif data.ndim == 3 and data.shape[2] == 4:
            mode = "RGBA"
        else:
            raise ValueError(f"Unsupported array shape: {data.shape}")

        image = Image.fromarray(data, mode=mode)

        save_kwargs: dict[str, Any] = {}
        if dpi is not None:
            save_kwargs["dpi"] = dpi

        image.save(self.filepath, format="PNG", **save_kwargs)

    def _normalize(self, data: NDArray[Any], bit_depth: int = 8) -> NDArray[Any]:
        """Normalize data to appropriate range."""
        data = np.asarray(data, dtype=np.float64)
        data_min = np.nanmin(data)
        data_max = np.nanmax(data)
        max_val = 65535 if bit_depth == 16 else 255
        if data_max > data_min:
            data = (data - data_min) / (data_max - data_min) * max_val
        return data
