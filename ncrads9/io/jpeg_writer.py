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
JPEG image writer for NCRADS9.

Author: Yogesh Wadadekar
"""

from pathlib import Path
from typing import Any, Optional, Union

import numpy as np
from numpy.typing import NDArray
from PIL import Image


class JPEGWriter:
    """Writer for JPEG image files."""

    def __init__(self, filepath: Union[str, Path]) -> None:
        """
        Initialize JPEG writer.

        Args:
            filepath: Path for the output JPEG file.
        """
        self.filepath = Path(filepath)

    def write(
        self,
        data: NDArray[Any],
        normalize: bool = True,
        quality: int = 85,
        dpi: Optional[tuple[int, int]] = None,
        optimize: bool = True,
    ) -> None:
        """
        Write image data to JPEG file.

        Args:
            data: Image data as numpy array.
            normalize: Whether to normalize data.
            quality: JPEG quality (1-95).
            dpi: Resolution as (x_dpi, y_dpi).
            optimize: Whether to optimize entropy coding.
        """
        if normalize:
            data = self._normalize(data)

        data = data.astype(np.uint8)

        if data.ndim == 2:
            mode = "L"
        elif data.ndim == 3 and data.shape[2] == 3:
            mode = "RGB"
        elif data.ndim == 3 and data.shape[2] == 4:
            data = data[:, :, :3]
            mode = "RGB"
        else:
            raise ValueError(f"Unsupported array shape: {data.shape}")

        image = Image.fromarray(data, mode=mode)

        save_kwargs: dict[str, Any] = {
            "quality": quality,
            "optimize": optimize,
        }
        if dpi is not None:
            save_kwargs["dpi"] = dpi

        image.save(self.filepath, format="JPEG", **save_kwargs)

    def _normalize(self, data: NDArray[Any]) -> NDArray[Any]:
        """Normalize data to 0-255 range."""
        data = np.asarray(data, dtype=np.float64)
        data_min = np.nanmin(data)
        data_max = np.nanmax(data)
        if data_max > data_min:
            data = (data - data_min) / (data_max - data_min) * 255
        return data
