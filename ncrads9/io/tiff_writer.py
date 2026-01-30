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
TIFF image writer for NCRADS9.

Author: Yogesh Wadadekar
"""

from pathlib import Path
from typing import Any, Optional, Union

import numpy as np
from numpy.typing import NDArray
from PIL import Image


class TIFFWriter:
    """Writer for TIFF image files."""

    def __init__(self, filepath: Union[str, Path]) -> None:
        """
        Initialize TIFF writer.

        Args:
            filepath: Path for the output TIFF file.
        """
        self.filepath = Path(filepath)

    def write(
        self,
        data: NDArray[Any],
        normalize: bool = False,
        compression: str = "none",
        dpi: Optional[tuple[int, int]] = None,
    ) -> None:
        """
        Write image data to TIFF file.

        Args:
            data: Image data as numpy array.
            normalize: Whether to normalize data to 8-bit.
            compression: Compression type ('none', 'lzw', 'zip').
            dpi: Resolution as (x_dpi, y_dpi).
        """
        if normalize:
            data = self._normalize(data)
            data = data.astype(np.uint8)

        if data.ndim == 2:
            if data.dtype == np.float32:
                mode = "F"
            elif data.dtype == np.int32:
                mode = "I"
            else:
                mode = "L"
        elif data.ndim == 3 and data.shape[2] == 3:
            mode = "RGB"
        elif data.ndim == 3 and data.shape[2] == 4:
            mode = "RGBA"
        else:
            raise ValueError(f"Unsupported array shape: {data.shape}")

        image = Image.fromarray(data, mode=mode)

        save_kwargs: dict[str, Any] = {}
        if compression != "none":
            save_kwargs["compression"] = compression
        if dpi is not None:
            save_kwargs["dpi"] = dpi

        image.save(self.filepath, format="TIFF", **save_kwargs)

    def write_multipage(
        self,
        pages: list[NDArray[Any]],
        normalize: bool = False,
        compression: str = "none",
    ) -> None:
        """
        Write multi-page TIFF file.

        Args:
            pages: List of image arrays.
            normalize: Whether to normalize data.
            compression: Compression type.
        """
        if not pages:
            raise ValueError("No pages to write")

        images = []
        for page_data in pages:
            if normalize:
                page_data = self._normalize(page_data).astype(np.uint8)

            if page_data.ndim == 2:
                mode = "L"
            else:
                mode = "RGB"

            images.append(Image.fromarray(page_data, mode=mode))

        save_kwargs: dict[str, Any] = {"save_all": True, "append_images": images[1:]}
        if compression != "none":
            save_kwargs["compression"] = compression

        images[0].save(self.filepath, format="TIFF", **save_kwargs)

    def _normalize(self, data: NDArray[Any]) -> NDArray[Any]:
        """Normalize data to 0-255 range."""
        data = np.asarray(data, dtype=np.float64)
        data_min = np.nanmin(data)
        data_max = np.nanmax(data)
        if data_max > data_min:
            data = (data - data_min) / (data_max - data_min) * 255
        return data
