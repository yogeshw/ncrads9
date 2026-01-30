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
PDF writer for NCRADS9.

Author: Yogesh Wadadekar
"""

from pathlib import Path
from typing import Any, Optional, Union

import numpy as np
from numpy.typing import NDArray
from PIL import Image


class PDFWriter:
    """Writer for PDF files."""

    def __init__(self, filepath: Union[str, Path]) -> None:
        """
        Initialize PDF writer.

        Args:
            filepath: Path for the output PDF file.
        """
        self.filepath = Path(filepath)
        self._pages: list[Image.Image] = []

    def add_page(
        self,
        data: NDArray[Any],
        normalize: bool = True,
    ) -> None:
        """
        Add a page from image data.

        Args:
            data: Image data as numpy array.
            normalize: Whether to normalize data.
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
        self._pages.append(image)

    def write(
        self,
        dpi: int = 300,
        title: Optional[str] = None,
        author: Optional[str] = None,
    ) -> None:
        """
        Write the PDF to disk.

        Args:
            dpi: Resolution in dots per inch.
            title: Optional document title.
            author: Optional document author.
        """
        if not self._pages:
            raise ValueError("No pages to write")

        save_kwargs: dict[str, Any] = {
            "resolution": dpi,
            "save_all": True,
            "append_images": self._pages[1:],
        }

        if title is not None:
            save_kwargs["title"] = title
        if author is not None:
            save_kwargs["author"] = author

        self._pages[0].save(self.filepath, format="PDF", **save_kwargs)

    def write_figure(
        self,
        figure: Any,
        dpi: int = 300,
        bbox_inches: str = "tight",
        pad_inches: float = 0.1,
    ) -> None:
        """
        Write a matplotlib figure to PDF.

        Args:
            figure: Matplotlib figure object.
            dpi: Resolution in dots per inch.
            bbox_inches: Bounding box mode.
            pad_inches: Padding around figure.
        """
        figure.savefig(
            self.filepath,
            format="pdf",
            dpi=dpi,
            bbox_inches=bbox_inches,
            pad_inches=pad_inches,
        )

    def clear(self) -> None:
        """Clear all pages."""
        self._pages.clear()

    def _normalize(self, data: NDArray[Any]) -> NDArray[Any]:
        """Normalize data to 0-255 range."""
        data = np.asarray(data, dtype=np.float64)
        data_min = np.nanmin(data)
        data_max = np.nanmax(data)
        if data_max > data_min:
            data = (data - data_min) / (data_max - data_min) * 255
        return data
